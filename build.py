"""
BOSS 简历筛选器 - 打包脚本
用法: python build.py
"""
import subprocess
import sys
import shutil
import os
from pathlib import Path

# 项目根目录
BASE_DIR = Path(__file__).parent.resolve()
DIST_DIR = BASE_DIR / "dist"
BUILD_DIR = BASE_DIR / "build"
SPEC_DIR = BASE_DIR / "spec"


def run(cmd, description=""):
    """执行命令并打印输出"""
    if description:
        print(f"\n{'='*60}")
        print(f"  {description}")
        print(f"{'='*60}")
    print(f">>> {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=False, text=True)
    if result.returncode != 0:
        print(f"\n[错误] 命令失败: {cmd}")
        sys.exit(1)
    return result


def clean():
    """清理旧的打包文件"""
    print("\n" + "="*60)
    print("  清理旧文件")
    print("="*60)

    for d in [DIST_DIR, BUILD_DIR, SPEC_DIR]:
        if d.exists():
            shutil.rmtree(d)
            print(f"  删除: {d}")

    for f in BASE_DIR.glob("*.spec"):
        f.unlink()
        print(f"  删除: {f}")


def install_deps():
    """安装打包依赖"""
    print("\n" + "="*60)
    print("  检查环境")
    print("="*60)

    # 检查是否有 pathlib 冲突
    try:
        import pathlib
        if pathlib.__file__ and 'site-packages' in pathlib.__file__:
            print("[警告] 检测到 pathlib 包与 PyInstaller 冲突")
            print("请执行以下命令移除：")
            print("  conda remove pathlib -y")
            print("  # 或")
            print("  pip uninstall pathlib -y")
            print("\n移除后重新运行本脚本。")
            sys.exit(1)
    except ImportError:
        pass

    run("pip install pyinstaller", "安装 PyInstaller")
    run("pip install -r requirements.txt", "安装项目依赖")


def build_gui():
    """打包 GUI 版本（推荐）"""
    print("\n" + "="*60)
    print("  打包 GUI 版本")
    print("="*60)

    run(
        'pyinstaller '
        '--onefile '           # 打包成单个 EXE
        '--noconsole '         # 不显示控制台窗口
        '--name "BOSS_简历筛选器" '  # EXE 名称
        '--add-data "job_config.json;." '  # 包含配置文件
        '--add-data "api_config.json;." '  # 包含 API 配置
        '--add-data "templates;templates" '  # 包含模板目录
        '--hidden-import=tkinter '
        '--hidden-import=tkinter.ttk '
        '--hidden-import=tkinter.font '
        '--hidden-import=tkinter.filedialog '
        '--hidden-import=tkinter.messagebox '
        '--exclude-module=PyQt5 '
        '--exclude-module=PySide6 '
        '--exclude-module=torch '
        '--exclude-module=botocore '
        '--exclude-module=boto3 '
        'gui_main.py',
        "正在打包 GUI 版本..."
    )

    print(f"\n[成功] GUI 版本已打包到: {DIST_DIR}/BOSS_简历筛选器.exe")


def build_cli():
    """打包命令行版本"""
    print("\n" + "="*60)
    print("  打包命令行版本")
    print("="*60)

    run(
        'pyinstaller '
        '--onefile '
        '--name "BOSS_简历筛选器_CLI" '
        '--add-data "job_config.json;." '
        '--add-data "templates;templates" '
        'bossmaster.py',
        "正在打包 CLI 版本..."
    )

    print(f"\n[成功] CLI 版本已打包到: {DIST_DIR}/BOSS_简历筛选器_CLI.exe")


def copy_artifacts():
    """复制必要的辅助文件到 dist 目录"""
    print("\n" + "="*60)
    print("  复制辅助文件")
    print("="*60)

    # 复制 README
    for file in ["README.md", "requirements.txt", "job_config.json", "gui.bat"]:
        src = BASE_DIR / file
        if src.exists():
            shutil.copy2(src, DIST_DIR / file)
            print(f"  复制: {file}")

    # 复制模板目录
    if (BASE_DIR / "templates").exists():
        shutil.copytree(BASE_DIR / "templates", DIST_DIR / "templates", dirs_exist_ok=True)
        print("  复制: templates/")


def main():
    """主入口"""
    print("""
╔══════════════════════════════════════════════════════════════╗
║         BOSS 简历筛选器 - 自动打包脚本                        ║
╚══════════════════════════════════════════════════════════════╝
""")

    # 清理旧文件
    clean()

    # 安装依赖
    install_deps()

    # 打包 GUI 版本（主程序）
    build_gui()

    # 复制辅助文件
    copy_artifacts()

    # 打印完成信息
    print("""
╔══════════════════════════════════════════════════════════════╗
║                     打包完成                                  ║
╠══════════════════════════════════════════════════════════════╣
║  输出目录: dist/                                             ║
║  主程序  : dist/BOSS_简历筛选器.exe                           ║
║  配置文件: dist/job_config.json                              ║
║  模板目录: dist/templates/                                   ║
╚══════════════════════════════════════════════════════════════╝

[注意] 首次运行前，请确保目标电脑已安装 Chrome 浏览器
""")


if __name__ == "__main__":
    main()
