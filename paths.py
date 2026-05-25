"""Path utilities for BOSS resume filter - handles PyInstaller packaging."""
import sys
import shutil
from pathlib import Path


def get_base_dir() -> Path:
    """
    获取程序基础目录（处理 PyInstaller 打包后的路径）。

    - 源码运行：返回脚本所在目录
    - Windows EXE：返回 EXE 所在目录
    - macOS .app：返回 .app 的父目录（因为 sys.executable 指向 .app/Contents/MacOS/）
    """
    if getattr(sys, 'frozen', False):
        exe_dir = Path(sys.executable).parent.resolve()
        if sys.platform == 'darwin' and exe_dir.name == 'MacOS':
            return exe_dir.parent.parent.parent
        return exe_dir
    return Path(__file__).parent.resolve()


def ensure_config_files(base_dir: Path) -> None:
    """
    确保配置文件存在。首次运行时（如 macOS DMG 安装后），
    从 PyInstaller 嵌入的 _MEIPASS 复制默认配置到可写位置。

    Args:
        base_dir: 程序基础目录
    """
    if not getattr(sys, 'frozen', False):
        return

    if not hasattr(sys, '_MEIPASS'):
        return

    meipass = Path(sys._MEIPASS)
    config_files = ["job_config.json", "selectors.json", "api_config.json"]

    for fname in config_files:
        target = base_dir / fname
        if not target.exists():
            src = meipass / fname
            if src.exists():
                shutil.copy2(str(src), str(target))


# 便捷常量
BASE_DIR = get_base_dir()
SELECTORS_PATH = BASE_DIR / "selectors.json"
CONFIG_PATH = BASE_DIR / "job_config.json"
CANDIDATES_PATH = BASE_DIR / "candidates_all.json"
CANDIDATES_XLSX_PATH = BASE_DIR / "candidates_all.xlsx"
