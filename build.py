"""
BOSS 简历筛选器 - 打包脚本
用法：
  python build.py --check                仅执行发布前检查，不打包、不提交、不推送
  python build.py                      仅打包 + 版本核对
  python build.py --release            打包 → 提交 → 打 tag → 推送 → GitHub Release
  python build.py --release --version 2.5  自动更新 __version__ + 一键发布
  python build.py --ci --release       CI 模式：跳过 venv/git，由 GitHub Actions 调用
  python build.py --gitee-upload X.Y.Z 手动补传产物到 Gitee Release
"""
import argparse
import ast
import json
import os
import re
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

BASE_DIR = Path(__file__).parent.resolve()
DIST_DIR = BASE_DIR / "dist"
BUILD_DIR = BASE_DIR / "build"
VENV_DIR = BASE_DIR / "pack_venv"

# 平台检测
IS_MAC = sys.platform == 'darwin'
IS_WIN = sys.platform == 'win32'
SEP = ':' if IS_MAC else ';'  # PyInstaller --add-data 分隔符

# 虚拟环境 Python 路径（按平台）
if IS_MAC:
    VENV_PYTHON = VENV_DIR / "bin" / "python"
else:
    VENV_PYTHON = VENV_DIR / "Scripts" / "python.exe"
SENSITIVE_TRACKED_PATHS = [
    ".env",
    "candidates_all.json",
    "candidates_all.xlsx",
]
SOURCE_CHECK_FILES = [
    "bossmaster.py",
    "gui_main.py",
    "filtering.py",
    "storage.py",
    "llm_eval.py",
    "doc_parser.py",
    "security.py",
    "build.py",
    "icons.py",
    "migrate_keys.py",
    "tests/run_unit_tests.py",
    "tests/test_import.py",
    "tests/unit/test_core_logic.py",
    "tests/unit/test_llm_eval.py",
    "tests/unit/test_selectors.py",
]


def _find_conda_tcl_tk():
    """Return Anaconda Tcl/Tk paths when the pack venv is based on conda Python."""
    # macOS 上 Homebrew Python 的 Tcl/Tk 由 PyInstaller 自动收集，无需手动指定
    if IS_MAC:
        return None

    base_prefix = Path(sys.base_prefix).resolve()
    tkinter_dir = base_prefix / "Lib" / "tkinter"
    tkinter_pyd = base_prefix / "DLLs" / "_tkinter.pyd"
    lib_dir = base_prefix / "Library" / "lib"
    bin_dir = base_prefix / "Library" / "bin"
    tcl_dir = lib_dir / "tcl8.6"
    tk_dir = lib_dir / "tk8.6"
    tcl_dll = bin_dir / "tcl86t.dll"
    tk_dll = bin_dir / "tk86t.dll"

    paths = {
        "tkinter_dir": tkinter_dir,
        "tkinter_pyd": tkinter_pyd,
        "tcl_dir": tcl_dir,
        "tk_dir": tk_dir,
        "tcl_dll": tcl_dll,
        "tk_dll": tk_dll,
    }
    if all(path.exists() for path in paths.values()):
        return paths
    return None


def _check_tkinter_packaging_support():
    """Fail before PyInstaller if Tcl/Tk cannot be located for a Tkinter GUI build."""
    try:
        import tkinter  # noqa: F401
        import tkinter.ttk  # noqa: F401
        import tkinter.font  # noqa: F401
        import tkinter.filedialog  # noqa: F401
        import tkinter.messagebox  # noqa: F401
    except ImportError as e:
        print(f"[错误] tkinter 导入失败：{e}")
        sys.exit(1)

    tcl_tk = _find_conda_tcl_tk()
    if tcl_tk:
        print("  [OK] Tcl/Tk 运行库已定位")
        return

    # Non-conda Python distributions normally let PyInstaller's tkinter hook
    # find Tcl/Tk automatically. Keep the check permissive outside conda.
    print("  [跳过] 未检测到 Anaconda Tcl/Tk 布局，交给 PyInstaller 自动收集")


def _pyinstaller_tk_args():
    """Return PyInstaller arguments and environment needed for Tkinter bundling."""
    tcl_tk = _find_conda_tcl_tk()
    if not tcl_tk:
        return [], os.environ.copy()

    env = os.environ.copy()
    env["TCL_LIBRARY"] = str(tcl_tk["tcl_dir"])
    env["TK_LIBRARY"] = str(tcl_tk["tk_dir"])

    return [
        "--collect-submodules", "tkinter",
        "--add-data", f'{tcl_tk["tkinter_dir"]}{SEP}tkinter',
        "--add-binary", f'{tcl_tk["tkinter_pyd"]}{SEP}.',
        "--add-data", f'{tcl_tk["tcl_dir"]}{SEP}tcl/tcl8.6' if IS_MAC else f'{tcl_tk["tcl_dir"]}{SEP}tcl\\tcl8.6',
        "--add-data", f'{tcl_tk["tk_dir"]}{SEP}tcl/tk8.6' if IS_MAC else f'{tcl_tk["tk_dir"]}{SEP}tcl\\tk8.6',
        "--add-binary", f'{tcl_tk["tcl_dll"]}{SEP}.',
        "--add-binary", f'{tcl_tk["tk_dll"]}{SEP}.',
    ], env


def run_in_venv():
    """如果在系统 Python 中运行，切换到 pack_venv 执行"""
    if Path(sys.executable).resolve() != VENV_PYTHON.resolve():
        if not VENV_PYTHON.exists():
            print(f"[错误] 虚拟环境不存在：{VENV_DIR}")
            if IS_MAC:
                print("请先创建：python3 -m venv pack_venv && source pack_venv/bin/activate && pip install -r requirements.txt pyinstaller")
            else:
                print("请先创建：python -m venv pack_venv && pack_venv\\Scripts\\activate && pip install -r requirements.txt pyinstaller")
            sys.exit(1)
        print(f"[使用虚拟环境] {VENV_PYTHON}")
        result = subprocess.run([str(VENV_PYTHON), __file__] + sys.argv[1:])
        sys.exit(result.returncode)


def clean_dist():
    """清理旧的打包产物"""
    if IS_MAC:
        # macOS: 清理 .app bundle、PyInstaller 中间目录、.zip、.dmg
        app_path = DIST_DIR / "BOSS_ResumeFilter.app"
        collect_path = DIST_DIR / "BOSS_ResumeFilter"
        zip_path = DIST_DIR / "BOSS_ResumeFilter_mac.zip"
        dmg_path = DIST_DIR / "BOSS_ResumeFilter.dmg"

        for path in [app_path, collect_path]:
            if path.exists():
                shutil.rmtree(path)
                print(f"  删除旧目录: {path}")

        for path in [zip_path, dmg_path]:
            if path.exists():
                path.unlink()
                print(f"  删除旧文件: {path}")
    else:
        # Windows: 清理 .exe
        exe_path = DIST_DIR / "BOSS_ResumeFilter.exe"
        if exe_path.exists():
            for attempt in range(3):
                try:
                    exe_path.unlink()
                    print(f"  删除旧 EXE: {exe_path}")
                    return
                except PermissionError as e:
                    if attempt < 2:
                        print(f"  等待文件释放... ({attempt + 1}/3)")
                        time.sleep(2)
                    else:
                        print(f"[警告] 无法删除旧 EXE (可能被占用): {e}")
                        print("  请手动关闭占用进程后重试")
                        sys.exit(1)


def _create_mac_zip():
    """创建 macOS ZIP 包（用于自动更新）"""
    app_dir = DIST_DIR / "BOSS_ResumeFilter.app"
    zip_path = DIST_DIR / "BOSS_ResumeFilter_mac.zip"

    if not app_dir.exists():
        print(f"[错误] .app 不存在：{app_dir}")
        sys.exit(1)

    print(f"\n>>> 创建 ZIP 包...")

    if zip_path.exists():
        zip_path.unlink()

    # macOS .app bundles contain framework symlinks, executable bits, and
    # extended attributes. Python zipfile loses enough of that metadata to
    # make PyInstaller apps fail after auto-update, so use ditto here.
    subprocess.run(
        [
            "ditto",
            "-c",
            "-k",
            "--sequesterRsrc",
            "--keepParent",
            str(app_dir),
            str(zip_path),
        ],
        cwd=DIST_DIR,
        check=True,
    )

    size_mb = zip_path.stat().st_size / (1024 * 1024)
    print(f"  [OK] ZIP: {zip_path} ({size_mb:.1f} MB)")
    return zip_path


def _create_mac_dmg():
    """创建 macOS DMG 安装包（标准布局：.app 在左，Applications 在右）"""
    app_dir = DIST_DIR / "BOSS_ResumeFilter.app"
    dmg_path = DIST_DIR / "BOSS_ResumeFilter.dmg"

    if not app_dir.exists():
        print(f"[错误] .app 不存在：{app_dir}")
        sys.exit(1)

    print(f"\n>>> 创建 DMG 安装包...")

    try:
        import dmgbuild
    except ImportError:
        print("[错误] 缺少 dmgbuild 依赖，请运行：pip install dmgbuild")
        sys.exit(1)

    # 根据 .app 大小自动计算 DMG 容量（留 50MB 余量）
    app_size_mb = sum(f.stat().st_size for f in app_dir.rglob('*') if f.is_file()) / (1024 * 1024)
    dmg_size_mb = int(app_size_mb) + 50

    settings = {
        'format': 'UDBZ',
        'size': f'{dmg_size_mb}m',
        'files': [str(app_dir)],
        'symlinks': {'Applications': '/Applications'},
        'icon_locations': {
            'BOSS_ResumeFilter.app': (140, 200),
            'Applications': (500, 200),
        },
        'icon_size': 100,
        'window_rect': ((100, 100), (640, 480)),
        'include_iconview_settings': True,
        'default_view': 'icon-view',
        'show_icon_preview': False,
        'text_size': 13,
    }

    dmgbuild.build_dmg(
        filename=str(dmg_path),
        volume_name='BOSS简历筛选器',
        settings=settings,
    )

    size_mb = dmg_path.stat().st_size / (1024 * 1024)
    print(f"  [OK] DMG: {dmg_path} ({size_mb:.1f} MB)")
    return dmg_path


# PyPI 包名 → import 名 映射（部分包名与 import 名不同）
REQUIRED_IMPORTS = {
    "DrissionPage": "DrissionPage",
    "pandas": "pandas",
    "openpyxl": "openpyxl",
    "requests": "requests",
    "dotenv": "python-dotenv",
    "keyring": "keyring",
    "PIL": "Pillow",
}


def _check_dependencies():
    """打包前验证所有关键依赖已安装，缺失时直接中断并给出修复命令"""
    missing = []
    for import_name, pkg_name in REQUIRED_IMPORTS.items():
        try:
            __import__(import_name)
        except ImportError:
            missing.append((import_name, pkg_name))

    if missing:
        print("[依赖缺失] 以下包未安装：\n")
        for import_name, pkg_name in missing:
            print(f"  ✗ {pkg_name}（import '{import_name}' 失败）")
        print(f"\n请在 pack_venv 中安装缺失依赖后重试：")
        print(f"  pack_venv\\Scripts\\pip install -r requirements.txt\n")
        sys.exit(1)

    print("  [OK] 依赖检查通过\n")


def _run_checked(cmd, description):
    """运行检查命令，失败时中断"""
    print(f">>> {description}")
    result = subprocess.run(cmd, cwd=BASE_DIR)
    if result.returncode != 0:
        print(f"[错误] {description} 失败")
        sys.exit(result.returncode)


def _git_output(args):
    """返回 git 命令 stdout"""
    result = subprocess.run(["git", *args], cwd=BASE_DIR, capture_output=True, text=True, check=True)
    return result.stdout.strip()


def _tracked_paths(paths):
    """返回仍被 Git 跟踪的路径"""
    tracked = []
    for path in paths:
        result = subprocess.run(["git", "ls-files", "--", path], cwd=BASE_DIR, capture_output=True, text=True)
        if result.stdout.strip():
            tracked.append(path)
    return tracked


def _check_storage_not_tracked():
    tracked_count = len(_git_output(["ls-files", ".storage"]).splitlines())
    if tracked_count:
        print(f"[错误] .storage 仍有 {tracked_count} 个文件被 Git 跟踪")
        print("请先执行：git rm -r --cached -- .storage")
        sys.exit(1)
    print("  [OK] .storage 未被 Git 跟踪")


def _check_sensitive_files_not_tracked():
    tracked = _tracked_paths(SENSITIVE_TRACKED_PATHS)
    if tracked:
        print("[错误] 以下本地敏感/运行数据仍被 Git 跟踪：")
        for path in tracked:
            print(f"  - {path}")
        sys.exit(1)
    print("  [OK] 敏感/运行数据未被 Git 跟踪")


def _check_api_config_has_no_plaintext_key():
    config_path = BASE_DIR / "api_config.json"
    if not config_path.exists():
        print("  [跳过] api_config.json 不存在")
        return
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"[错误] api_config.json 不是合法 JSON：{e}")
        sys.exit(1)

    offenders = []
    if config.get("api_key"):
        offenders.append("api_key")
    for idx, model in enumerate(config.get("saved_models", [])):
        if isinstance(model, dict) and (model.get("api_key") or model.get("api_key_ref")):
            offenders.append(f"saved_models[{idx}]")

    if offenders:
        print("[错误] api_config.json 含明文或旧版 API Key 引用：")
        for item in offenders:
            print(f"  - {item}")
        sys.exit(1)
    print("  [OK] api_config.json 不含明文 API Key")


def _check_source_compiles():
    files = [str(BASE_DIR / path) for path in SOURCE_CHECK_FILES if (BASE_DIR / path).exists()]
    _run_checked([sys.executable, "-m", "py_compile", *files], "源码编译检查")


def _run_unit_checks():
    _run_checked([sys.executable, "tests/run_unit_tests.py"], "稳定单元回归")
    _run_checked([sys.executable, "tests/test_import.py"], "导入烟测")


def _check_changelog_updated():
    """检测核心代码有变更时 CHANGELOG.md 必须同步更新。"""
    result = subprocess.run(
        ["git", "describe", "--tags", "--abbrev=0"],
        capture_output=True, text=True, cwd=BASE_DIR
    )
    if result.returncode != 0:
        print("  [跳过] CHANGELOG 检查：无法获取上一个 tag")
        return

    last_tag = result.stdout.strip()

    # 检查核心代码是否有变更
    core_files = ["gui_main.py", "bossmaster.py", "filtering.py", "storage.py",
                  "llm_eval.py", "doc_parser.py", "security.py", "updater.py", "icons.py"]
    result = subprocess.run(
        ["git", "diff", "--name-only", last_tag, "HEAD", "--"] + core_files,
        capture_output=True, text=True, cwd=BASE_DIR
    )
    changed_core = [f for f in result.stdout.strip().splitlines() if f]

    if not changed_core:
        print("  [OK] CHANGELOG 检查：核心代码无变更")
        return

    # 检查 CHANGELOG.md 是否更新
    result = subprocess.run(
        ["git", "diff", "--name-only", last_tag, "HEAD", "--", "CHANGELOG.md"],
        capture_output=True, text=True, cwd=BASE_DIR
    )
    changelog_changed = bool(result.stdout.strip())

    if not changelog_changed:
        print("[错误] 核心代码已变更但 CHANGELOG.md 未更新：\n")
        for f in changed_core:
            print(f"  - {f}")
        print("\n请先更新 CHANGELOG.md 再发布")
        sys.exit(1)

    print("  [OK] CHANGELOG 已同步更新")


def _check_todo_not_stale():
    """检测 TODO.md 是否还保留已完成的发布事项。"""
    todo_path = BASE_DIR / "TODO.md"
    if not todo_path.exists():
        return

    content = todo_path.read_text(encoding="utf-8")
    stale_items = [
        ("国内备用更新源", "Gitee/GitHub 双源更新已在 v2.8.8 落地"),
    ]
    found = [
        (keyword, reason)
        for keyword, reason in stale_items
        if re.search(rf"^\s*-\s+\[\s*\]\s+.*{re.escape(keyword)}", content, re.MULTILINE)
    ]
    if found:
        print("[错误] TODO.md 含已完成但仍未勾选的事项：")
        for keyword, reason in found:
            print(f"  - {keyword}：{reason}")
        print("请先删除、勾选或改写为真实未完成事项。")
        sys.exit(1)

    print("  [OK] TODO.md 无已完成待办残留")


def _preflight_checks(require_clean=True):
    """发布/打包前检查"""
    print("\n>>> 发布前检查")
    _check_dependencies()
    _check_tkinter_packaging_support()
    _check_storage_not_tracked()
    _check_sensitive_files_not_tracked()
    _check_api_config_has_no_plaintext_key()
    _check_source_compiles()
    _check_changelog_updated()
    _check_todo_not_stale()
    _run_unit_checks()

    if require_clean:
        has_changes, status_text = _git_status()
        if has_changes:
            print("[错误] 工作区不干净，请先提交或撤销变更：\n")
            for line in status_text.splitlines():
                print(f"  {line}")
            sys.exit(1)
        print("  [OK] 工作区干净")

    print(">>> 发布前检查通过\n")


def _read_version():
    """AST 解析 gui_main.py 提取 __version__"""
    gui_path = BASE_DIR / "gui_main.py"
    with open(gui_path, encoding="utf-8") as f:
        tree = ast.parse(f.read())
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name) and target.id == "__version__":
                if isinstance(node.value, ast.Constant):
                    return node.value.value
    print("[错误] 无法从 gui_main.py 提取 __version__")
    sys.exit(1)


def _write_version(version: str):
    """将 __version__ = "X.Y" 写入 gui_main.py"""
    gui_path = BASE_DIR / "gui_main.py"
    content = gui_path.read_text(encoding="utf-8")
    new_content = re.sub(
        r'^__version__\s*=\s*"[^"]*"',
        f'__version__ = "{version}"',
        content,
        flags=re.MULTILINE
    )
    if new_content == content:
        print(f"[错误] 无法在 gui_main.py 中定位 __version__ 行")
        sys.exit(1)
    gui_path.write_text(new_content, encoding="utf-8")
    print(f"  [OK] __version__ = \"{version}\"\n")


def _check_version_consistency():
    """读取 __version__ 并与打包产物核对，返回 (version, artifact_path, size_mb)"""
    version = _read_version()

    if IS_MAC:
        # macOS: 检查 .app、.zip、.dmg
        app_path = DIST_DIR / "BOSS_ResumeFilter.app"
        zip_path = DIST_DIR / "BOSS_ResumeFilter_mac.zip"
        dmg_path = DIST_DIR / "BOSS_ResumeFilter.dmg"

        for path, label in [(app_path, ".app"), (zip_path, "ZIP"), (dmg_path, "DMG")]:
            if not path.exists():
                print(f"[错误] {label} 不存在：{path}")
                sys.exit(1)

        size_mb = zip_path.stat().st_size / (1024 * 1024)
        dmg_size_mb = dmg_path.stat().st_size / (1024 * 1024)
        print(f"\n{'='*60}")
        print(f"  打包完成: v{version}")
        print(f"  APP:  {app_path}")
        print(f"  ZIP:  {zip_path} ({size_mb:.1f} MB)")
        print(f"  DMG:  {dmg_path} ({dmg_size_mb:.1f} MB)")
        print(f"{'='*60}")
        return version, zip_path, size_mb
    else:
        # Windows: 检查 .exe
        exe_path = DIST_DIR / "BOSS_ResumeFilter.exe"
        if not exe_path.exists():
            print(f"[错误] EXE 不存在：{exe_path}")
            sys.exit(1)

        size_mb = exe_path.stat().st_size / (1024 * 1024)
        print(f"\n{'='*60}")
        print(f"  打包完成: v{version}")
        print(f"  EXE:  {exe_path} ({size_mb:.1f} MB)")
        print(f"{'='*60}")
        return version, exe_path, size_mb


def _extract_changelog_release(version):
    """从 CHANGELOG.md 提取当前版本的 Release 标题和正文。"""
    changelog_path = BASE_DIR / "CHANGELOG.md"
    if not changelog_path.exists():
        print("[错误] CHANGELOG.md 不存在，Release 必须先写本地更新日志")
        sys.exit(1)

    content = changelog_path.read_text(encoding="utf-8")
    pattern = re.compile(
        rf"^##\s+(v{re.escape(version)}[^\n]*)\n(?P<body>.*?)(?=^##\s+v|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(content)
    if not match:
        print(f"[错误] CHANGELOG.md 中未找到 v{version} 段落")
        print("请先在 CHANGELOG.md 顶部补充本版本发布说明，再执行 --release。")
        sys.exit(1)

    title = match.group(1).strip()
    body = match.group("body").strip()
    if not body:
        print(f"[错误] CHANGELOG.md 中 v{version} 段落正文为空")
        sys.exit(1)

    required_sections = ["新增功能", "体验优化", "问题修复"]
    found_sections = re.findall(r"^###\s+(.+?)\s*$", body, re.MULTILINE)

    # 至少有一个分类
    present = [section for section in required_sections if section in found_sections]
    if not present:
        print(f"[错误] CHANGELOG.md 中 v{version} 段落缺少发布分类")
        print(f"至少需要以下分类之一：{', '.join(required_sections)}")
        sys.exit(1)

    # 检查存在的分类是否按规范顺序排列
    present_positions = [(section, found_sections.index(section)) for section in required_sections if section in found_sections]
    positions = [pos for _, pos in present_positions]
    if positions != sorted(positions):
        print(f"[错误] CHANGELOG.md 中 v{version} 段落发布分类顺序不正确")
        print("当前顺序：")
        for section in found_sections:
            print(f"  - {section}")
        print("\n要求顺序：")
        for section in required_sections:
            print(f"  - {section}")
        sys.exit(1)

    print(f"  [OK] Release 标题来自 CHANGELOG.md：{title}")
    print("  [OK] Release 说明来自 CHANGELOG.md 当前版本段落")
    return title, body


def _check_readme_release(version):
    """验证 README.md 已同步当前发布版本。"""
    readme_path = BASE_DIR / "README.md"
    if not readme_path.exists():
        print("[错误] README.md 不存在，Release 必须先更新项目主页说明")
        sys.exit(1)

    content = readme_path.read_text(encoding="utf-8")
    required_version_text = f"当前发布版本：v{version}"
    version_label_pattern = re.compile(
        rf"^>\s*当前发布版本：.*v{re.escape(version)}.*$",
        re.MULTILINE,
    )
    if not version_label_pattern.search(content):
        print(f"[错误] README.md 未同步当前发布版本：v{version}")
        print(f"请在 README.md 顶部加入或更新：> {required_version_text}")
        sys.exit(1)

    release_heading = re.compile(
        rf"^###\s+(?:v{re.escape(version)}(?:\s|$)|v2\.8\s+补丁版本\s*$)",
        re.MULTILINE,
    )
    if not release_heading.search(content):
        print(f"[错误] README.md 未找到 v{version} 功能摘要小节")
        print(f"请在 README.md 功能特性中补充：### v{version} 新增功能")
        sys.exit(1)

    gui_version_text = f"gui_main.py            # 图形界面主程序（v{version}）"
    if gui_version_text not in content:
        print(f"[错误] README.md 项目结构中的 gui_main.py 版本未同步为 v{version}")
        print(f"请将项目结构中的 gui_main.py 标注更新为：# 图形界面主程序（v{version}）")
        sys.exit(1)

    print(f"  [OK] README.md 已同步 v{version} 项目主页说明")


# ---------------------------------------------------------------------------
#  Release 子步骤（仅 --release 模式调用）
# ---------------------------------------------------------------------------

def _git_status():
    """返回 (has_changes, status_text)"""
    r = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, cwd=BASE_DIR)
    status_text = r.stdout.rstrip()
    return bool(status_text), status_text


def _git_commit(version, allowed_paths=None):
    """只提交明确允许的发布相关变更"""
    has_changes, status_text = _git_status()
    if not has_changes:
        print("  [跳过] 没有未提交的变更")
        return

    allowed = set(allowed_paths or [])
    changed = []
    for line in status_text.splitlines():
        # porcelain: XY path 或 XY old -> new
        path = line[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        changed.append(path)

    unexpected = [path for path in changed if path not in allowed]
    if unexpected:
        print("[错误] Release 模式拒绝自动提交非发布文件：\n")
        for line in status_text.splitlines():
            print(f"  {line}")
        print("\n请先手动提交这些变更，或只使用 --version 让发布脚本更新 gui_main.py。")
        sys.exit(1)

    print(f"\n  待提交的变更：\n")
    for line in status_text.splitlines():
        print(f"    {line}")

    subprocess.run(["git", "add", *sorted(allowed)], cwd=BASE_DIR, check=True)
    msg = f"release: v{version}"
    subprocess.run(["git", "commit", "-m", msg], cwd=BASE_DIR, check=True)
    print(f"  [OK] 已提交：{msg}")


def update_latest_json(version, release_notes, downloads_cn=None):
    """更新 latest.json 文件（供 Gitee 镜像使用）

    Args:
        downloads_cn: Gitee 国内下载链接字典 {"windows": url, "macos": url}
    """
    from datetime import date

    latest_data = {
        "version": version,
        "release_date": date.today().isoformat(),
        "downloads": {
            "windows": f"https://github.com/yaoyouzhong/boss-resume-filter/releases/download/v{version}/BOSS_ResumeFilter.exe",
            "macos": f"https://github.com/yaoyouzhong/boss-resume-filter/releases/download/v{version}/BOSS_ResumeFilter_mac.zip",
            "macos_dmg": f"https://github.com/yaoyouzhong/boss-resume-filter/releases/download/v{version}/BOSS_ResumeFilter.dmg",
            "job_config": f"https://github.com/yaoyouzhong/boss-resume-filter/releases/download/v{version}/job_config.json",
            "readme": f"https://github.com/yaoyouzhong/boss-resume-filter/releases/download/v{version}/README.md"
        },
        "release_notes": release_notes
    }

    if downloads_cn:
        latest_data["downloads_cn"] = downloads_cn

    latest_path = BASE_DIR / "latest.json"
    with open(latest_path, 'w', encoding='utf-8') as f:
        json.dump(latest_data, f, ensure_ascii=False, indent=2)

    print(f"  [OK] 已更新 latest.json (v{version})")


def _git_tag(version):
    """创建或更新本地 tag"""
    tag = f"v{version}"
    existing = subprocess.run(["git", "tag", "-l", tag], capture_output=True, text=True, cwd=BASE_DIR)
    if existing.stdout.strip():
        subprocess.run(["git", "tag", "-f", tag], cwd=BASE_DIR, check=True)
        print(f"  [OK] 已更新本地 tag: {tag}")
    else:
        subprocess.run(["git", "tag", tag], cwd=BASE_DIR, check=True)
        print(f"  [OK] 已创建本地 tag: {tag}")


def _git_push(version):
    """推送 master 和 tag 到远程"""
    tag = f"v{version}"

    # 检查远程是否已有 tag（需要 force）
    remote_tags = subprocess.run(["git", "ls-remote", "--tags", "origin", tag],
                                 capture_output=True, text=True, cwd=BASE_DIR)
    tag_exists_remote = bool(remote_tags.stdout.strip())

    print(f"\n{'='*60}")
    print(f"  即将推送到远程：")
    print(f"    1. git push origin master")
    cmd2 = f"    2. git push origin {tag}" + (" --force" if tag_exists_remote else "")
    print(cmd2)
    print(f"{'='*60}")

    resp = input("\n  确认推送？[y/N] ").strip().lower()
    if resp != 'y':
        print("  已取消推送。tag 和提交保留在本地，可稍后手动推送。")
        sys.exit(0)

    subprocess.run(["git", "push", "origin", "master"], cwd=BASE_DIR, check=True)
    print(f"  [OK] master 已推送")

    push_cmd = ["git", "push", "origin", tag]
    if tag_exists_remote:
        push_cmd.append("--force")
    subprocess.run(push_cmd, cwd=BASE_DIR, check=True)
    print(f"  [OK] {tag} 已推送")


def _gh_release(version, release_title, release_notes):
    """创建/更新 GitHub Release 并上传资源文件"""
    tag = f"v{version}"
    cfg = DIST_DIR / "job_config.json"
    readme = DIST_DIR / "README.md"

    # 按平台选择上传的文件
    if IS_MAC:
        dmg = DIST_DIR / "BOSS_ResumeFilter.dmg"
        mac_zip = DIST_DIR / "BOSS_ResumeFilter_mac.zip"
        artifacts = [(dmg, "DMG"), (mac_zip, "Mac-ZIP"), (cfg, "Config"), (readme, "README")]
    else:
        exe = DIST_DIR / "BOSS_ResumeFilter.exe"
        artifacts = [(exe, "EXE"), (cfg, "Config"), (readme, "README")]

    # 检查 gh CLI
    r = subprocess.run(["gh", "--version"], capture_output=True, cwd=BASE_DIR)
    if r.returncode != 0:
        print("[错误] gh CLI 未安装或未登录，请先运行 gh auth login")
        sys.exit(1)

    # 删除 Release 中已有的当前平台资源（保留对端产物，由 _trigger_cross_platform_ci 处理）
    existing = subprocess.run(["gh", "release", "view", tag, "--json", "assets"],
                              capture_output=True, text=True, cwd=BASE_DIR)
    if existing.returncode == 0 and existing.stdout.strip():
        import json
        assets = json.loads(existing.stdout).get("assets", [])
        # 只删当前平台产物，保留对端（Windows 保留 DMG/ZIP，macOS 保留 EXE）
        if IS_MAC:
            skip_names = {"BOSS_ResumeFilter.exe"}
        else:
            skip_names = {"BOSS_ResumeFilter.dmg", "BOSS_ResumeFilter_mac.zip"}
        for a in assets:
            if a['name'] in skip_names:
                continue
            print(f"  删除旧资源: {a['name']}")
            subprocess.run(["gh", "release", "delete-asset", tag, a["name"], "-y"],
                           cwd=BASE_DIR, check=True)

    # 创建 Release（如果已存在则跳过创建步骤）
    r = subprocess.run(["gh", "release", "view", tag], capture_output=True, cwd=BASE_DIR)
    if r.returncode != 0:
        # Release 不存在，创建它
        subprocess.run(["gh", "release", "create", tag, "--title", release_title, "--notes", release_notes],
                       cwd=BASE_DIR, check=True)
        print(f"  [OK] GitHub Release 已创建: {tag}")
    else:
        print(f"  [OK] GitHub Release 已存在: {tag}")
        subprocess.run(["gh", "release", "edit", tag, "--title", release_title, "--notes", release_notes],
                       cwd=BASE_DIR, check=True)
        print("  [OK] GitHub Release 标题和说明已同步")

    # 上传资源
    for f, label in artifacts:
        if f.exists():
            subprocess.run(["gh", "release", "upload", tag, str(f), "--clobber"],
                           cwd=BASE_DIR, check=True)
            print(f"  [OK] 已上传: {f.name}")
        else:
            print(f"  [跳过] 文件不存在: {f.name}")

    # 覆盖发布：删除对端产物 + 触发 CI 重建
    need_ci = _trigger_cross_platform_ci(tag)

    # 上传本地平台产物到 Gitee Release（国内下载源）
    downloads_cn = _gitee_upload_local(version, release_title, release_notes)

    # 等待 CI 完成，从 GitHub 下载对端产物并上传到 Gitee
    gitee_sync = _sync_gitee_from_github(version, release_title, release_notes, need_wait=need_ci)
    if gitee_sync:
        downloads_cn = downloads_cn or {}
        downloads_cn.update(gitee_sync)

    return downloads_cn


def _trigger_cross_platform_ci(tag):
    """覆盖发布后，删除对端旧产物并触发 CI 重建。

    Windows 发布 → 删旧 DMG/ZIP → CI 自动构建 macOS
    macOS 发布 → 删旧 EXE → CI 自动构建 Windows

    返回 True 表示需要等待 CI 构建对端产物。
    """
    if IS_MAC:
        opposite_assets = ["BOSS_ResumeFilter.exe"]
    else:
        opposite_assets = ["BOSS_ResumeFilter.dmg", "BOSS_ResumeFilter_mac.zip"]

    # 删除对端旧产物
    deleted = False
    for asset_name in opposite_assets:
        r = subprocess.run(
            ["gh", "release", "delete-asset", tag, asset_name, "-y"],
            capture_output=True, text=True, cwd=BASE_DIR
        )
        if r.returncode == 0:
            print(f"  [OK] 已删除旧产物: {asset_name}")
            deleted = True

    if not deleted:
        print("  [跳过] 对端产物不存在，无需触发 CI")
        return False

    # 手动触发 CI workflow
    r = subprocess.run(
        ["gh", "workflow", "run", "release.yml", "--ref", tag],
        capture_output=True, text=True, cwd=BASE_DIR
    )
    if r.returncode == 0:
        print(f"  [OK] 已触发 CI 构建对端产物 ({tag})")
    else:
        print(f"  [警告] CI 触发失败: {r.stderr.strip()}")
        print("  可手动执行: gh workflow run release.yml --ref " + tag)

    return True


def _gitee_find_or_create_release(api_base, token, tag, release_title, release_notes):
    """查找或创建 Gitee Release，返回 (release_id, existing_asset_names)。"""
    resp = requests.get(
        f"{api_base}/releases",
        params={"access_token": token},
        timeout=10,
    )
    resp.raise_for_status()
    release = next((r for r in resp.json() if r.get("tag_name") == tag), None)

    if release:
        return release["id"], {a["name"] for a in release.get("assets", [])}

    resp = requests.post(
        f"{api_base}/releases",
        data={
            "access_token": token,
            "tag_name": tag,
            "name": release_title or tag,
            "body": release_notes or "",
            "target_commitish": "master",
        },
        timeout=10,
    )
    resp.raise_for_status()
    print(f"  [OK] Gitee Release 已创建: {tag}")
    return resp.json()["id"], set()


def _gitee_upload_single(filepath, api_base, token, release_id, max_retries=3):
    """上传单个文件到 Gitee Release，带重试。返回 (文件名, 响应JSON)。"""
    for attempt in range(max_retries):
        try:
            with open(filepath, "rb") as fh:
                resp = requests.post(
                    f"{api_base}/releases/{release_id}/attach_files",
                    files={"file": (filepath.name, fh)},
                    params={"access_token": token},
                    timeout=300,
                )
            resp.raise_for_status()
            return filepath.name, resp.json()
        except requests.exceptions.RequestException as e:
            if attempt < max_retries - 1:
                delay = 2 ** (attempt + 1)
                print(f"  [Gitee] {filepath.name} 上传失败 ({e})，{delay}s 后重试 ({attempt+1}/{max_retries})")
                time.sleep(delay)
            else:
                raise


def _gitee_asset_url(owner, repo, tag, filename):
    """构造 Gitee Release 下载链接。"""
    return f"https://gitee.com/{owner}/{repo}/releases/download/{tag}/{filename}"


def _gitee_upload_local(version, release_title, release_notes):
    """上传本地平台的产物到 Gitee Release。

    Windows: EXE + job_config.json + README.md
    macOS:   DMG + ZIP + job_config.json + README.md

    返回 downloads_cn 字典。需要环境变量 GITEE_TOKEN，未设置时返回 None。
    """
    token = os.environ.get("GITEE_TOKEN")
    if not token:
        print("  [跳过] Gitee Release: 未设置 GITEE_TOKEN 环境变量")
        return None

    owner = "yaoyouzhong"
    repo = "boss-resume-filter"
    tag = f"v{version}"
    api_base = f"https://gitee.com/api/v5/repos/{owner}/{repo}"

    if IS_MAC:
        artifacts = [
            DIST_DIR / "BOSS_ResumeFilter.dmg",
            DIST_DIR / "BOSS_ResumeFilter_mac.zip",
            DIST_DIR / "job_config.json",
            DIST_DIR / "README.md",
        ]
    else:
        artifacts = [
            DIST_DIR / "BOSS_ResumeFilter.exe",
            DIST_DIR / "job_config.json",
            DIST_DIR / "README.md",
        ]

    try:
        release_id, _ = _gitee_find_or_create_release(
            api_base, token, tag, release_title, release_notes)

        downloads_cn = {}
        failed = []
        for f in artifacts:
            if not f.exists():
                print(f"  [Gitee 跳过] 文件不存在: {f.name}")
                continue
            try:
                name, asset = _gitee_upload_single(f, api_base, token, release_id)
                url = asset.get("browser_download_url", _gitee_asset_url(owner, repo, tag, name))
                downloads_cn[_downloads_cn_key(name)] = url
                print(f"  [OK] Gitee 已上传: {name}")
            except requests.exceptions.RequestException as e:
                print(f"  [失败] Gitee 上传失败: {f.name} ({e})")
                failed.append(f.name)

        if failed:
            print(f"\n{'!'*60}")
            print(f"  ⚠️  Gitee 上传部分失败: {', '.join(failed)}")
            print(f"  手动补传: python build.py --gitee-upload {version}")
            print(f"{'!'*60}\n")

        return downloads_cn if downloads_cn else None

    except requests.exceptions.RequestException as e:
        print(f"\n{'!'*60}")
        print(f"  ⚠️  Gitee Release 整体失败: {e}")
        print(f"  手动补传: python build.py --gitee-upload {version}")
        print(f"{'!'*60}\n")
        return None


def _downloads_cn_key(filename):
    """文件名 → downloads_cn 字典 key。"""
    if filename.endswith(".exe"):
        return "windows"
    if filename.endswith("_mac.zip"):
        return "macos"
    if filename.endswith(".dmg"):
        return "macos_dmg"
    if filename == "job_config.json":
        return "job_config"
    if filename == "README.md":
        return "readme"
    return filename


def _download_from_github_release(tag, asset_name, dest_dir):
    """从 GitHub Release 下载单个产物。返回下载后的 Path。"""
    owner = "yaoyouzhong"
    repo = "boss-resume-filter"
    url = (
        f"https://api.github.com/repos/{owner}/{repo}/releases/assets/"
    )
    # 使用 gh CLI 下载更可靠（自动认证）
    dest = Path(dest_dir) / asset_name
    r = subprocess.run(
        ["gh", "release", "download", tag, "-p", asset_name, "-D", str(dest_dir)],
        capture_output=True, text=True, cwd=BASE_DIR,
    )
    if r.returncode != 0:
        raise RuntimeError(f"gh download 失败: {r.stderr.strip()}")
    return dest


def _sync_gitee_from_github(version, release_title, release_notes, need_wait=False):
    """从 GitHub Release 下载对端产物，并行上传到 Gitee Release。

    当 need_wait=True 时，先轮询等待 CI 构建完成（对端产物出现在 GitHub Release）。
    返回 downloads_cn 字典，失败返回 None。
    """
    token = os.environ.get("GITEE_TOKEN")
    if not token:
        print("  [跳过] Gitee 同步: 未设置 GITEE_TOKEN")
        return None

    owner = "yaoyouzhong"
    repo = "boss-resume-filter"
    tag = f"v{version}"
    api_base = f"https://gitee.com/api/v5/repos/{owner}/{repo}"

    # 对端产物列表
    if IS_MAC:
        opposite_assets = ["BOSS_ResumeFilter.exe"]
    else:
        opposite_assets = ["BOSS_ResumeFilter.dmg", "BOSS_ResumeFilter_mac.zip"]

    # 所有需要上传到 Gitee 的本地文件（两个平台共用）
    all_local_files = [
        DIST_DIR / "BOSS_ResumeFilter.exe",
        DIST_DIR / "BOSS_ResumeFilter.dmg",
        DIST_DIR / "BOSS_ResumeFilter_mac.zip",
        DIST_DIR / "job_config.json",
        DIST_DIR / "README.md",
    ]

    print(f"\n>>> 同步 Gitee Release（从 GitHub 下载对端产物）")

    if need_wait:
        print(f"  等待 CI 构建对端产物（{', '.join(opposite_assets)}）...")
        poll_interval = 30
        max_wait = 600
        elapsed = 0
        while elapsed < max_wait:
            try:
                r = subprocess.run(
                    ["gh", "release", "view", tag, "--json", "assets"],
                    capture_output=True, text=True, cwd=BASE_DIR,
                )
                if r.returncode == 0:
                    gh_assets = {a["name"] for a in json.loads(r.stdout).get("assets", [])}
                    if all(name in gh_assets for name in opposite_assets):
                        print(f"  [OK] 对端产物已就绪（{elapsed}s）")
                        break
                    missing = [n for n in opposite_assets if n not in gh_assets]
                    print(f"  等待中... {elapsed}s / {max_wait}s，缺少: {', '.join(missing)}")
                else:
                    print(f"  等待中... {elapsed}s / {max_wait}s（GitHub Release 查询失败）")
            except Exception:
                pass
            time.sleep(poll_interval)
            elapsed += poll_interval
        else:
            print(f"\n{'!'*60}")
            print(f"  ⚠️  等待超时 ({max_wait}s)，CI 可能未完成")
            print(f"  手动同步: python build.py --gitee-upload {version}")
            print(f"{'!'*60}\n")
            return None

    # 并行下载对端产物
    download_dir = DIST_DIR / "_gh_download"
    download_dir.mkdir(exist_ok=True)

    print(f"  并行下载对端产物...")
    downloaded = []
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {
            pool.submit(_download_from_github_release, tag, name, download_dir): name
            for name in opposite_assets
        }
        for future in as_completed(futures):
            name = futures[future]
            try:
                path = future.result()
                print(f"  [OK] 已下载: {name}")
                downloaded.append(path)
            except Exception as e:
                print(f"  [失败] 下载失败: {name} ({e})")

    if not downloaded:
        print(f"\n  ⚠️  未成功下载任何对端产物")
        return None

    # 收集所有需要上传的文件（本地已有的 + 刚下载的）
    upload_files = []
    for f in all_local_files:
        if f.exists():
            upload_files.append(f)
    upload_files.extend(downloaded)

    # 并行上传到 Gitee
    print(f"  并行上传 {len(upload_files)} 个文件到 Gitee Release...")
    try:
        release_id, existing = _gitee_find_or_create_release(
            api_base, token, tag, release_title, release_notes)

        downloads_cn = {}
        failed = []

        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = {
                pool.submit(_gitee_upload_single, f, api_base, token, release_id): f
                for f in upload_files
            }
            for future in as_completed(futures):
                f = futures[future]
                try:
                    name, asset = future.result()
                    url = asset.get("browser_download_url",
                                    _gitee_asset_url(owner, repo, tag, name))
                    downloads_cn[_downloads_cn_key(name)] = url
                    print(f"  [OK] Gitee 已上传: {name}")
                except Exception as e:
                    print(f"  [失败] Gitee 上传失败: {f.name} ({e})")
                    failed.append(f.name)

        if failed:
            print(f"\n{'!'*60}")
            print(f"  ⚠️  Gitee 上传部分失败: {', '.join(failed)}")
            print(f"  手动补传: python build.py --gitee-upload {version}")
            print(f"{'!'*60}\n")

        # 清理临时下载目录
        shutil.rmtree(download_dir, ignore_errors=True)

        return downloads_cn if downloads_cn else None

    except requests.exceptions.RequestException as e:
        shutil.rmtree(download_dir, ignore_errors=True)
        print(f"\n{'!'*60}")
        print(f"  ⚠️  Gitee Release 同步失败: {e}")
        print(f"  手动补传: python build.py --gitee-upload {version}")
        print(f"{'!'*60}\n")
        return None


# ---------------------------------------------------------------------------
#  主流程
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="BOSS 简历筛选器 - 打包及发布脚本")
    parser.add_argument("--check", action="store_true",
                        help="仅执行发布前检查，不打包、不提交、不推送")
    parser.add_argument("--release", action="store_true",
                        help="打包后自动提交→打tag→推送→GitHub Release上传")
    parser.add_argument("--version", type=str, default=None, metavar="X.Y",
                        help="自动更新 gui_main.py 中的 __version__")
    parser.add_argument("--ci", action="store_true",
                        help="CI 模式：跳过虚拟环境切换和 git 操作，用于 GitHub Actions")
    parser.add_argument("--gitee-upload", type=str, default=None, metavar="X.Y.Z",
                        help="手动补传产物到 Gitee Release（需要 GITEE_TOKEN）")
    args = parser.parse_args()

    version_changed = False

    # ---- 版本号更新（在打包之前） ----
    if args.version:
        old = _read_version()
        if args.version != old:
            _write_version(args.version)
            version_changed = True
        else:
            print(f"  [跳过] __version__ 已经是 \"{args.version}\"\n")

    if not args.ci:
        run_in_venv()

    if args.check:
        _preflight_checks(require_clean=True)
        return

    if args.gitee_upload:
        version = args.gitee_upload
        tag = f"v{version}"
        print(f"\n>>> 手动上传产物到 Gitee Release {tag}")

        # 从 GitHub Release 读取 release notes
        release_title = tag
        release_notes = ""
        try:
            r = subprocess.run(
                ["gh", "release", "view", tag, "--json", "name,body"],
                capture_output=True, text=True, cwd=BASE_DIR,
            )
            if r.returncode == 0:
                data = json.loads(r.stdout)
                release_title = data.get("name", tag)
                release_notes = data.get("body", "")
        except Exception:
            pass

        # 上传本地已有的产物
        downloads_cn = _gitee_upload_local(version, release_title, release_notes)

        # 从 GitHub 下载对端产物并上传到 Gitee（不等待，CI 应已完成）
        gitee_sync = _sync_gitee_from_github(version, release_title, release_notes, need_wait=False)
        if gitee_sync:
            downloads_cn = downloads_cn or {}
            downloads_cn.update(gitee_sync)

        if downloads_cn:
            update_latest_json(version, release_notes, downloads_cn)
            print(f"\n  [OK] downloads_cn 已更新，请手动提交推送：")
            print(f"  git add latest.json && git commit -m \"chore: 更新 Gitee 下载链接\" && git push")
        else:
            print(f"\n  [失败] Gitee 上传未成功")
        return

    print("""
╔══════════════════════════════════════════════════════════════╗
║         BOSS 简历筛选器 - 自动打包脚本 (v2)                   ║
╚══════════════════════════════════════════════════════════════╝
""")

    # ---- 打包前：验证依赖、敏感路径、源码和测试 ----
    _preflight_checks(require_clean=not version_changed)

    clean_dist()

    tk_args, pyinstaller_env = _pyinstaller_tk_args()
    if tk_args:
        print("  [OK] 将 Anaconda Tcl/Tk 运行库加入 PyInstaller")

    # CI 模式使用当前 Python，否则使用虚拟环境
    python_exe = sys.executable if args.ci else str(VENV_PYTHON)

    cmd = [
        python_exe, "-m", "PyInstaller",
    ]

    # macOS: --onedir --windowed (生成 .app bundle)
    # Windows: --onefile --noconsole (生成单文件 .exe)
    if IS_MAC:
        cmd += ["--onedir", "--windowed", "--osx-bundle-identifier", "com.boss.resume-filter"]
    else:
        cmd += ["--onefile", "--noconsole"]

    cmd += [
        '--name', 'BOSS_ResumeFilter',
        '--add-data', f'{BASE_DIR / "job_config.json"}{SEP}.',
        '--add-data', f'{BASE_DIR / "api_config.json"}{SEP}.',
        '--add-data', f'{BASE_DIR / "selectors.json"}{SEP}.',
        '--add-data', f'{BASE_DIR / "CHANGELOG.md"}{SEP}.',
        '--hidden-import=tkinter',
        '--hidden-import=tkinter.ttk',
        '--hidden-import=tkinter.font',
        '--hidden-import=tkinter.filedialog',
        '--hidden-import=tkinter.messagebox',
        *tk_args,
        '--collect-all', 'PIL',
        '--exclude-module=PyQt5',
        '--exclude-module=PySide6',
        '--exclude-module=torch',
        '--exclude-module=botocore',
        '--exclude-module=boto3',
        str(BASE_DIR / "gui_main.py")
    ]

    print(">>> PyInstaller 打包中...")
    os.chdir(BASE_DIR)
    result = subprocess.run(cmd, env=pyinstaller_env)

    if result.returncode != 0:
        print("\n[错误] 打包失败")
        sys.exit(1)

    print("\n  更新辅助文件...")
    for file in ["README.md", "job_config.json", "selectors.json"]:
        src = BASE_DIR / file
        dst = DIST_DIR / file
        if src.exists():
            shutil.copy2(src, dst)
            print(f"    + {file}")
        else:
            print(f"    ! {file} (源文件缺失)")

    # macOS: 创建 ZIP 和 DMG 分发包
    if IS_MAC:
        _create_mac_zip()
        _create_mac_dmg()

    version, artifact_path, size_mb = _check_version_consistency()
    release_title = release_notes = None
    if args.release:
        release_title, release_notes = _extract_changelog_release(version)
        _check_readme_release(version)

    # ---- Release 模式：提交 → 打 tag → 推送 → GitHub Release ----
    if args.release and not args.ci:
        print(f"\n{'='*60}")
        print(f"  Release 模式：v{version}")
        print(f"{'='*60}")

        # 更新 latest.json（供 Gitee 镜像使用）
        update_latest_json(version, release_notes)

        # 提交变更（允许 gui_main.py 和 latest.json）
        allowed = ["gui_main.py"] if args.version else []
        allowed.append("latest.json")
        _git_commit(version, allowed_paths=allowed)
        _git_tag(version)
        _git_push(version)
        downloads_cn = _gh_release(version, release_title, release_notes)

        # Gitee 上传成功后，更新 latest.json 加入国内下载链接
        if downloads_cn:
            update_latest_json(version, release_notes, downloads_cn)
            subprocess.run(["git", "add", "latest.json"], cwd=BASE_DIR, check=True)
            subprocess.run(["git", "commit", "-m", "chore: 更新 Gitee 下载链接"],
                           cwd=BASE_DIR, check=True)
            subprocess.run(["git", "push", "origin", "master"], cwd=BASE_DIR, check=True)
            print("  [OK] latest.json 已自动提交并推送（含 Gitee 下载链接）")

        print(f"\n{'='*60}")
        print(f"  v{version} 发布完成！")
        print(f"  {artifact_path} ({size_mb:.1f} MB)")
        print(f"{'='*60}\n")
    elif args.release and args.ci:
        print(f"\n{'='*60}")
        print(f"  CI 打包完成：v{version}")
        print(f"  {artifact_path} ({size_mb:.1f} MB)")
        print(f"  GitHub Actions 将自动上传到 Release")
        print(f"{'='*60}\n")
    else:
        print(f"\n  下一步：python build.py --release  一键完成提交/打tag/推送/Release")
        print(f"  或手动：git push origin master && git push origin v{version}\n")


if __name__ == "__main__":
    main()
