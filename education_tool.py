"""学历证书核验助手独立入口。"""
from __future__ import annotations

import tkinter as tk

from education_tool_config import EDUCATION_TOOL_API_CONFIG
from education_tool_security import get_embedded_api_key
from gui_main import (
    BossFilterGUI,
    _enable_high_dpi_awareness,
    _get_windows_monitor_area,
    _show_main_window_centered,
)


def main() -> None:
    _enable_high_dpi_awareness()
    startup_monitor_area = _get_windows_monitor_area()
    root = tk.Tk()
    root.withdraw()
    BossFilterGUI(
        root,
        standalone_education=True,
        education_api_config=EDUCATION_TOOL_API_CONFIG,
        education_api_key_provider=get_embedded_api_key,
    )
    _show_main_window_centered(root, startup_monitor_area)
    root.mainloop()


if __name__ == "__main__":
    main()
