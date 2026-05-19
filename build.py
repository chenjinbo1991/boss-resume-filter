"""
BOSS 简历筛选器 - 打包脚本
用法：
  python build.py --check                仅执行发布前检查，不打包、不提交、不推送
  python build.py                      仅打包 + 版本核对
  python build.py --release            打包 → 提交 → 打 tag → 推送 → GitHub Release
  python build.py --release --version 2.5  自动更新 __version__ + 一键发布
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
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()
DIST_DIR = BASE_DIR / "dist"
BUILD_DIR = BASE_DIR / "build"
VENV_DIR = BASE_DIR / "pack_venv"
VENV_PYTHON = VENV_DIR / "Scripts" / "python.exe"
SENSITIVE_TRACKED_PATHS = [
    ".env",
    "candidates_all.json",
    "candidates_all.xlsx",
]
SOURCE_CHECK_FILES = [
    "bossmaster.py",
    "gui_main.py",
    "doc_parser.py",
    "security.py",
    "build.py",
    "icons.py",
    "migrate_keys.py",
    "tests/run_unit_tests.py",
    "tests/test_import.py",
    "tests/unit/test_core_logic.py",
]


def _find_conda_tcl_tk():
    """Return Anaconda Tcl/Tk paths when the pack venv is based on conda Python."""
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
        "--add-data", f'{tcl_tk["tkinter_dir"]};tkinter',
        "--add-binary", f'{tcl_tk["tkinter_pyd"]};.',
        "--add-data", f'{tcl_tk["tcl_dir"]};tcl\\tcl8.6',
        "--add-data", f'{tcl_tk["tk_dir"]};tcl\\tk8.6',
        "--add-binary", f'{tcl_tk["tcl_dll"]};.',
        "--add-binary", f'{tcl_tk["tk_dll"]};.',
    ], env


def run_in_venv():
    """如果在系统 Python 中运行，切换到 pack_venv 执行"""
    if Path(sys.executable).resolve() != VENV_PYTHON.resolve():
        if not VENV_PYTHON.exists():
            print(f"[错误] 虚拟环境不存在：{VENV_DIR}")
            print("请先创建：python -m venv pack_venv && pack_venv\\Scripts\\activate && pip install -r requirements.txt pyinstaller")
            sys.exit(1)
        print(f"[使用虚拟环境] {VENV_PYTHON}")
        result = subprocess.run([str(VENV_PYTHON), __file__] + sys.argv[1:])
        sys.exit(result.returncode)


def clean_dist():
    """只删除旧的 EXE 文件，保留用户数据和配置文件"""
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


def _preflight_checks(require_clean=True):
    """发布/打包前检查"""
    print("\n>>> 发布前检查")
    _check_dependencies()
    _check_tkinter_packaging_support()
    _check_storage_not_tracked()
    _check_sensitive_files_not_tracked()
    _check_api_config_has_no_plaintext_key()
    _check_source_compiles()
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
    """读取 __version__ 并与 dist/EXE 核对，返回 (version, exe_path, size_mb)"""
    version = _read_version()

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

    required_sections = ["新增功能", "行为优化", "UI 改进", "Bug 修复", "构建改进"]
    found_sections = re.findall(r"^###\s+(.+?)\s*$", body, re.MULTILINE)
    missing = [section for section in required_sections if section not in found_sections]

    if missing:
        print(f"[错误] CHANGELOG.md 中 v{version} 段落缺少发布分类：")
        for section in missing:
            print(f"  - {section}")
        print("\n请按：新增功能 / 行为优化 / UI 改进 / Bug 修复 / 构建改进 分类整理后再发布。")
        sys.exit(1)

    required_positions = [found_sections.index(section) for section in required_sections]
    if required_positions != sorted(required_positions):
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


# ---------------------------------------------------------------------------
#  Release 子步骤（仅 --release 模式调用）
# ---------------------------------------------------------------------------

def _git_status():
    """返回 (has_changes, status_text)"""
    r = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, cwd=BASE_DIR)
    return bool(r.stdout.strip()), r.stdout.strip()


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
    exe = DIST_DIR / "BOSS_ResumeFilter.exe"
    cfg = DIST_DIR / "job_config.json"
    readme = DIST_DIR / "README.md"

    # 检查 gh CLI
    r = subprocess.run(["gh", "--version"], capture_output=True, cwd=BASE_DIR)
    if r.returncode != 0:
        print("[错误] gh CLI 未安装或未登录，请先运行 gh auth login")
        sys.exit(1)

    # 删除 Release 中已有的同名资源（如果存在）
    existing = subprocess.run(["gh", "release", "view", tag, "--json", "assets"],
                              capture_output=True, text=True, cwd=BASE_DIR)
    if existing.returncode == 0 and existing.stdout.strip():
        import json
        assets = json.loads(existing.stdout).get("assets", [])
        for a in assets:
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
    for f, label in [(exe, "EXE"), (cfg, "Config"), (readme, "README")]:
        if f.exists():
            subprocess.run(["gh", "release", "upload", tag, str(f), "--clobber"],
                           cwd=BASE_DIR, check=True)
            print(f"  [OK] 已上传: {f.name}")
        else:
            print(f"  [跳过] 文件不存在: {f.name}")


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
    args = parser.parse_args()

    run_in_venv()

    if args.check:
        _preflight_checks(require_clean=True)
        return

    version_changed = False

    # ---- 版本号更新（在打包之前） ----
    if args.version:
        old = _read_version()
        if args.version != old:
            _write_version(args.version)
            version_changed = True
        else:
            print(f"  [跳过] __version__ 已经是 \"{args.version}\"\n")

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

    cmd = [
        str(VENV_PYTHON), "-m", "PyInstaller",
        "--onefile",
        "--noconsole",
        '--name', 'BOSS_ResumeFilter',
        '--add-data', f'{BASE_DIR / "job_config.json"};.',
        '--add-data', f'{BASE_DIR / "api_config.json"};.',
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
    for file in ["README.md", "job_config.json"]:
        src = BASE_DIR / file
        dst = DIST_DIR / file
        if src.exists():
            shutil.copy2(src, dst)
            print(f"    + {file}")
        else:
            print(f"    ! {file} (源文件缺失)")

    version, exe_path, size_mb = _check_version_consistency()
    release_title = release_notes = None
    if args.release:
        release_title, release_notes = _extract_changelog_release(version)

    # ---- Release 模式：提交 → 打 tag → 推送 → GitHub Release ----
    if args.release:
        print(f"\n{'='*60}")
        print(f"  Release 模式：v{version}")
        print(f"{'='*60}")

        _git_commit(version, allowed_paths=["gui_main.py"] if version_changed else [])
        _git_tag(version)
        _git_push(version)
        _gh_release(version, release_title, release_notes)

        print(f"\n{'='*60}")
        print(f"  v{version} 发布完成！")
        print(f"  {exe_path} ({size_mb:.1f} MB)")
        print(f"{'='*60}\n")
    else:
        print(f"\n  下一步：python build.py --release  一键完成提交/打tag/推送/Release")
        print(f"  或手动：git push origin master && git push origin v{version}\n")


if __name__ == "__main__":
    main()
