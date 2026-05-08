"""
BOSS 简历筛选器 - 打包脚本
用法: python build.py
默认使用 pack_venv 虚拟环境，如不存在则自动创建
"""
import subprocess
import sys
import shutil
import os
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()
DIST_DIR = BASE_DIR / "dist"
BUILD_DIR = BASE_DIR / "build"
VENV_DIR = BASE_DIR / "pack_venv"
VENV_PYTHON = VENV_DIR / "Scripts" / "python.exe"


def ensure_venv():
    """确保在 pack_venv 中运行，不在则切进去再跑"""
    if Path(sys.executable).resolve() == VENV_PYTHON.resolve():
        return  # 已经在 venv 里

    if not VENV_PYTHON.exists():
        print("[创建虚拟环境] pack_venv")
        subprocess.run([sys.executable, "-m", "venv", str(VENV_DIR)], check=True)
        subprocess.run(
            [str(VENV_PYTHON), "-m", "pip", "install", "-q", "--disable-pip-version-check", "-r", "requirements.txt"],
            check=True,
        )
        subprocess.run(
            [str(VENV_PYTHON), "-m", "pip", "install", "-q", "--disable-pip-version-check", "pyinstaller"],
            check=True,
        )

    # 用 venv python 重新执行本脚本
    print(f"[切换环境] → {VENV_PYTHON}")
    os.execl(str(VENV_PYTHON), str(VENV_PYTHON), __file__)


def ensure_deps():
    """仅检查依赖是否齐全，缺了才装"""
    required = ["DrissionPage", "pandas", "openpyxl", "requests", "python-dotenv", "keyring", "pyinstaller"]
    missing = []
    for pkg in required:
        try:
            __import__(pkg.replace("-", "_"))
        except ImportError:
            missing.append(pkg)

    if missing:
        print(f"[安装缺失依赖] {', '.join(missing)}")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-q", "--disable-pip-version-check", *missing],
            check=True,
        )
    else:
        print("[依赖检查] 全部就绪")


def clean():
    """仅清理 dist，保留 build 缓存加速后续打包"""
    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
        print(f"  清理: {DIST_DIR}")


def build_gui():
    """打包 GUI 版本"""
    print("\n" + "=" * 60)
    print("  打包 GUI 版本")
    print("=" * 60)

    cmd = (
        "pyinstaller "
        "--onefile "
        "--noconsole "
        "--log-level WARN "
        '--name "BOSS_简历筛选器" '
        '--add-data "job_config.json;." '
        '--add-data "api_config.json;." '
"--hidden-import=tkinter "
        "--hidden-import=tkinter.ttk "
        "--hidden-import=tkinter.font "
        "--hidden-import=tkinter.filedialog "
        "--hidden-import=tkinter.messagebox "
        "--exclude-module=PyQt5 "
        "--exclude-module=PySide6 "
        "--exclude-module=torch "
        "--exclude-module=botocore "
        "--exclude-module=boto3 "
        "gui_main.py"
    )
    print(f">>> {cmd}")
    result = subprocess.run(cmd, shell=True)
    if result.returncode != 0:
        print(f"\n[错误] 打包失败")
        sys.exit(1)

    exe_path = DIST_DIR / "BOSS_简历筛选器.exe"
    size_mb = exe_path.stat().st_size / (1024 * 1024)
    print(f"\n[完成] {exe_path}  ({size_mb:.1f} MB)")


def copy_artifacts():
    """复制辅助文件到 dist"""
    print("\n" + "=" * 60)
    print("  复制辅助文件")
    print("=" * 60)

    for file in ["README.md", "requirements.txt", "job_config.json", "gui.bat"]:
        src = BASE_DIR / file
        if src.exists():
            shutil.copy2(src, DIST_DIR / file)
            print(f"  复制: {file}")



def main():
    print("""
╔══════════════════════════════════════════════════════════════╗
║         BOSS 简历筛选器 - 自动打包脚本                        ║
╚══════════════════════════════════════════════════════════════╝
""")

    ensure_venv()
    ensure_deps()
    clean()
    build_gui()
    copy_artifacts()

    print("""
╔══════════════════════════════════════════════════════════════╗
║                     打包完成                                  ║
╠══════════════════════════════════════════════════════════════╣
║  输出目录: dist/                                             ║
║  主程序  : dist/BOSS_简历筛选器.exe                           ║
╚══════════════════════════════════════════════════════════════╝
""")


if __name__ == "__main__":
    main()
