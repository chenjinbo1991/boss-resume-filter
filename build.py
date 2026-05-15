"""
BOSS 简历筛选器 - 打包脚本
用法：
  python build.py                      仅打包 + 版本核对
  python build.py --release            打包 → 提交 → 打 tag → 推送 → GitHub Release
  python build.py --release --version 2.5  自动更新 __version__ + 一键发布
"""
import argparse
import ast
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


# ---------------------------------------------------------------------------
#  Release 子步骤（仅 --release 模式调用）
# ---------------------------------------------------------------------------

def _git_status():
    """返回 (has_changes, status_text)"""
    r = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, cwd=BASE_DIR)
    return bool(r.stdout.strip()), r.stdout.strip()


def _git_commit(version):
    """提交所有未暂存变更（gitignore 已排除 .claude/ dist/ 等）"""
    has_changes, status_text = _git_status()
    if not has_changes:
        print("  [跳过] 没有未提交的变更")
        return

    print(f"\n  待提交的变更：\n")
    for line in status_text.splitlines():
        print(f"    {line}")

    subprocess.run(["git", "add", "-A"], cwd=BASE_DIR, check=True)
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


def _gh_release(version):
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
        from datetime import date
        title = f"v{version} — {date.today().strftime('%Y-%m-%d')}"
        subprocess.run(["gh", "release", "create", tag, "--title", title, "--notes", ""],
                       cwd=BASE_DIR, check=True)
        print(f"  [OK] GitHub Release 已创建: {tag}")
    else:
        print(f"  [OK] GitHub Release 已存在: {tag}")

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
    parser.add_argument("--release", action="store_true",
                        help="打包后自动提交→打tag→推送→GitHub Release上传")
    parser.add_argument("--version", type=str, default=None, metavar="X.Y",
                        help="自动更新 gui_main.py 中的 __version__")
    args = parser.parse_args()

    run_in_venv()

    # ---- 版本号更新（在打包之前） ----
    if args.version:
        old = _read_version()
        if args.version != old:
            _write_version(args.version)
        else:
            print(f"  [跳过] __version__ 已经是 \"{args.version}\"\n")

    print("""
╔══════════════════════════════════════════════════════════════╗
║         BOSS 简历筛选器 - 自动打包脚本 (v2)                   ║
╚══════════════════════════════════════════════════════════════╝
""")

    # ---- 打包前：验证所有依赖可导入 ----
    _check_dependencies()

    clean_dist()

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
    result = subprocess.run(cmd)

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

    # ---- Release 模式：提交 → 打 tag → 推送 → GitHub Release ----
    if args.release:
        print(f"\n{'='*60}")
        print(f"  Release 模式：v{version}")
        print(f"{'='*60}")

        _git_commit(version)
        _git_tag(version)
        _git_push(version)
        _gh_release(version)

        print(f"\n{'='*60}")
        print(f"  v{version} 发布完成！")
        print(f"  {exe_path} ({size_mb:.1f} MB)")
        print(f"{'='*60}\n")
    else:
        print(f"\n  下一步：python build.py --release  一键完成提交/打tag/推送/Release")
        print(f"  或手动：git push origin master && git push origin v{version}\n")


if __name__ == "__main__":
    main()