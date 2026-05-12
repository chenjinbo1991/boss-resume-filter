"""
BOSS 简历筛选器 - 打包脚本
用法：python build.py (会自动使用 pack_venv 虚拟环境)
"""
import os
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


def main():
    run_in_venv()

    print("""
╔══════════════════════════════════════════════════════════════╗
║         BOSS 简历筛选器 - 自动打包脚本 (v2)                   ║
╚══════════════════════════════════════════════════════════════╝
""")

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
        '--hidden-import=PIL.Image',
        '--hidden-import=PIL.ImageDraw',
        '--hidden-import=PIL.ImageTk',
        '--exclude-module=PyQt5',
        '--exclude-module=PySide6',
        '--exclude-module=torch',
        '--exclude-module=botocore',
        '--exclude-module=boto3',
        str(BASE_DIR / "gui_main.py")
    ]

    print(">>> PyInstaller 打包中...")
    os.chdir(BASE_DIR)  # PyInstaller 使用 CWD 作为输出根目录
    result = subprocess.run(cmd)

    if result.returncode != 0:
        print("\n[错误] 打包失败")
        sys.exit(1)

    exe_path = DIST_DIR / "BOSS_ResumeFilter.exe"
    size_mb = exe_path.stat().st_size / (1024 * 1024)
    print(f"\n[成功] {exe_path} ({size_mb:.1f} MB)")

    print("\n  更新辅助文件...")
    for file in ["README.md", "job_config.json"]:
        src = BASE_DIR / file
        dst = DIST_DIR / file
        if src.exists():
            shutil.copy2(src, dst)
            print(f"    + {file}")
        else:
            print(f"    ! {file} (源文件缺失)")

    print("""
╔══════════════════════════════════════════════════════════════╗
║                     打包完成                                  ║
╚══════════════════════════════════════════════════════════════╝
""")


if __name__ == "__main__":
    main()
