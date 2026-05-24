"""
自动更新模块
支持 Windows EXE 和 macOS 的自动更新
"""

import os
import sys
import json
import shutil
import subprocess
import threading
import requests
from pathlib import Path
from tkinter import messagebox
import tkinter as tk


def get_base_dir():
    """获取程序基础目录（处理 PyInstaller 打包后的路径）"""
    if getattr(sys, 'frozen', False):
        # PyInstaller 打包后
        return Path(sys.executable).parent.resolve()
    else:
        # 开发环境
        return Path(__file__).parent.resolve()


def get_current_version():
    """获取当前版本号"""
    try:
        # 从 gui_main.py 读取 __version__
        if getattr(sys, 'frozen', False):
            # 打包后从 sys._MEIPASS 读取
            base = Path(sys._MEIPASS)
        else:
            base = Path(__file__).parent

        gui_main_path = base / "gui_main.py"
        with open(gui_main_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.startswith('__version__'):
                    # 提取版本号，如 __version__ = "2.7"
                    return line.split('=')[1].strip().strip('"\'')
    except Exception as e:
        print(f"[更新] 获取当前版本失败: {e}")
    return "0.0.0"


def check_github_release(repo="yaoyouzhong/boss-resume-filter"):
    """
    检查 GitHub Release 最新版本

    Returns:
        dict: {
            'latest': str,  # 最新版本号
            'current': str,  # 当前版本号
            'has_update': bool,  # 是否有更新
            'release_info': dict,  # GitHub Release 信息
            'download_url': str,  # EXE 下载链接（Windows）
            'error': str  # 错误信息
        }
    """
    result = {
        'latest': None,
        'current': get_current_version(),
        'has_update': False,
        'release_info': None,
        'download_url': None,
        'error': None
    }

    try:
        # 调用 GitHub API
        api_url = f"https://api.github.com/repos/{repo}/releases/latest"
        headers = {'Accept': 'application/vnd.github.v3+json'}

        response = requests.get(api_url, headers=headers, timeout=10)
        response.raise_for_status()

        release = response.json()
        result['release_info'] = release

        # 提取版本号（tag_name 可能是 "v2.7" 或 "2.7"）
        tag = release.get('tag_name', '')
        latest_version = tag.lstrip('v')
        result['latest'] = latest_version

        # 比较版本号
        def parse_version(v):
            """将版本号字符串转换为可比较的元组"""
            try:
                parts = [int(x) for x in v.split('.')]
                return tuple(parts)
            except:
                return (0, 0, 0)

        current_tuple = parse_version(result['current'])
        latest_tuple = parse_version(latest_version)

        result['has_update'] = latest_tuple > current_tuple

        # 查找 Windows EXE 下载链接
        if sys.platform == 'win32':
            for asset in release.get('assets', []):
                if asset.get('name', '').endswith('.exe'):
                    result['download_url'] = asset.get('browser_download_url')
                    break

    except requests.exceptions.Timeout:
        result['error'] = "网络连接超时"
    except requests.exceptions.RequestException as e:
        result['error'] = f"网络请求失败: {e}"
    except Exception as e:
        result['error'] = f"检查更新失败: {e}"

    return result


def download_file(url, dest_path, progress_callback=None):
    """
    下载文件，支持进度回调

    Args:
        url: 下载链接
        dest_path: 保存路径
        progress_callback: 进度回调函数 callback(downloaded, total)
    """
    try:
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()

        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0

        with open(dest_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback:
                        progress_callback(downloaded, total_size)

        return True, None
    except Exception as e:
        return False, str(e)


def update_windows(new_exe_path, current_exe_path):
    """
    Windows EXE 更新逻辑

    生成 update.bat 脚本，然后启动脚本并退出当前程序

    流程：
    1. 等待当前进程退出（2秒）
    2. 重命名当前 EXE 为 .old
    3. 复制新 EXE 到原位置
    4. 删除临时文件
    5. 启动新 EXE
    6. 删除 .old 文件和脚本自身
    """
    try:
        # 生成 update.bat
        bat_path = Path(current_exe_path).parent / "update.bat"

        bat_content = f"""@echo off
echo 正在更新 BOSS 简历筛选器...
timeout /t 2 /nobreak >nul

echo 备份旧版本...
if exist "{current_exe_path}.old" del "{current_exe_path}.old"
rename "{current_exe_path}" "{Path(current_exe_path).name}.old"

echo 安装新版本...
copy /y "{new_exe_path}" "{current_exe_path}"

echo 清理临时文件...
del "{new_exe_path}"

echo 启动新版本...
start "" "{current_exe_path}"

echo 删除旧版本...
del "{current_exe_path}.old"

echo 更新完成！
del "%~f0"
"""

        with open(bat_path, 'w', encoding='utf-8') as f:
            f.write(bat_content)

        # 启动 update.bat（最小化窗口）
        subprocess.Popen(
            [bat_path],
            creationflags=subprocess.CREATE_NO_WINDOW,
            close_fds=True
        )

        return True, None
    except Exception as e:
        return False, str(e)


def update_macos():
    """
    macOS 更新逻辑

    执行 git pull，然后提示用户重启应用
    """
    try:
        base_dir = get_base_dir()

        # 检查是否在 git 仓库中
        git_dir = base_dir / ".git"
        if not git_dir.exists():
            return False, "当前不是 git 仓库，无法自动更新"

        # 执行 git pull
        result = subprocess.run(
            ['git', 'pull', 'origin', 'master'],
            cwd=base_dir,
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode != 0:
            return False, f"git pull 失败: {result.stderr}"

        # 检查是否有更新
        if "Already up to date" in result.stdout:
            return True, "已经是最新版本"

        return True, "更新成功，请重启应用"

    except subprocess.TimeoutExpired:
        return False, "git pull 超时"
    except Exception as e:
        return False, str(e)


def check_and_update_gui(root, silent=False):
    """
    GUI 版本的更新检查和执行

    Args:
        root: tkinter 根窗口
        silent: 是否静默检查（不显示"已是最新版本"提示）
    """
    def do_check():
        # 在后台线程中检查
        result = check_github_release()

        # 回到主线程处理结果
        root.after(0, lambda: handle_result(result))

    def handle_result(result):
        if result['error']:
            if not silent:
                messagebox.showerror("检查更新失败", result['error'], parent=root)
            return

        if not result['has_update']:
            if not silent:
                messagebox.showinfo(
                    "检查更新",
                    f"当前已是最新版本 v{result['current']}",
                    parent=root
                )
            return

        # 有新版本，显示更新对话框
        show_update_dialog(root, result)

    # 启动后台检查
    threading.Thread(target=do_check, daemon=True).start()


def show_update_dialog(root, result):
    """显示更新对话框"""
    dialog = tk.Toplevel(root)
    dialog.title("发现新版本")
    dialog.transient(root)
    dialog.grab_set()

    # 居中显示
    dialog.geometry("600x500")
    dialog.update_idletasks()  # 确保几何信息已计算
    x = root.winfo_x() + (root.winfo_width() - 600) // 2
    y = root.winfo_y() + (root.winfo_height() - 500) // 2
    dialog.geometry(f"+{x}+{y}")

    # 标题
    title_label = tk.Label(
        dialog,
        text=f"发现新版本 v{result['latest']}",
        font=("Arial", 16, "bold")
    )
    title_label.pack(pady=20)

    # 当前版本
    current_label = tk.Label(
        dialog,
        text=f"当前版本: v{result['current']}",
        font=("Arial", 10)
    )
    current_label.pack(pady=5)

    # 更新内容（从 release body 读取）
    release_info = result['release_info']
    body = release_info.get('body', '无更新说明')

    content_frame = tk.LabelFrame(dialog, text="更新内容", padx=10, pady=10)
    content_frame.pack(fill="both", expand=True, padx=20, pady=10)

    content_text = tk.Text(content_frame, wrap="word", height=15)
    content_text.insert("1.0", body)
    content_text.config(state="disabled")
    content_text.pack(fill="both", expand=True)

    # 进度条（初始隐藏）
    progress_frame = tk.Frame(dialog)
    progress_label = tk.Label(progress_frame, text="下载中...")
    progress_label.pack(side="left", padx=5)

    from tkinter import ttk
    progress_bar = ttk.Progressbar(progress_frame, length=200, mode='determinate')
    progress_bar.pack(side="left", padx=5)

    # 按钮
    button_frame = tk.Frame(dialog)
    button_frame.pack(pady=20)

    def on_cancel():
        dialog.destroy()

    def on_update():
        """执行更新"""
        # 隐藏按钮，显示进度
        button_frame.pack_forget()
        progress_frame.pack(pady=20)

        def do_update():
            if sys.platform == 'win32':
                # Windows: 下载并替换 EXE
                download_url = result['download_url']
                if not download_url:
                    root.after(0, lambda: messagebox.showerror(
                        "更新失败",
                        "未找到 Windows EXE 下载链接",
                        parent=dialog
                    ))
                    return

                # 下载 EXE
                temp_dir = Path(get_base_dir()) / "temp_update"
                temp_dir.mkdir(exist_ok=True)
                temp_exe = temp_dir / "BOSS_ResumeFilter_new.exe"

                def progress_callback(downloaded, total):
                    if total > 0:
                        percent = int(downloaded / total * 100)
                        root.after(0, lambda: progress_bar.config(value=percent))
                        root.after(0, lambda: progress_label.config(
                            text=f"下载中... {percent}%"
                        ))

                success, error = download_file(str(download_url), temp_exe, progress_callback)

                if not success:
                    root.after(0, lambda: messagebox.showerror(
                        "下载失败",
                        f"下载新版本失败: {error}",
                        parent=dialog
                    ))
                    return

                # 执行更新
                root.after(0, lambda: progress_label.config(text="正在安装..."))

                current_exe = sys.executable
                success, error = update_windows(str(temp_exe), current_exe)

                if success:
                    root.after(0, lambda: (
                        messagebox.showinfo(
                            "更新成功",
                            "新版本已下载，程序即将重启",
                            parent=dialog
                        ),
                        sys.exit(0)
                    ))
                else:
                    root.after(0, lambda: messagebox.showerror(
                        "更新失败",
                        f"安装失败: {error}",
                        parent=dialog
                    ))

            else:
                # macOS: git pull
                success, message = update_macos()

                if success:
                    root.after(0, lambda: (
                        messagebox.showinfo(
                            "更新成功",
                            message + "\n\n请手动重启应用以使用新版本",
                            parent=dialog
                        ),
                        dialog.destroy()
                    ))
                else:
                    root.after(0, lambda: messagebox.showerror(
                        "更新失败",
                        message,
                        parent=dialog
                    ))

        # 在后台线程执行更新
        threading.Thread(target=do_update, daemon=True).start()

    cancel_btn = tk.Button(
        button_frame,
        text="稍后更新",
        command=on_cancel,
        width=15
    )
    cancel_btn.pack(side="left", padx=10)

    update_btn = tk.Button(
        button_frame,
        text="立即更新",
        command=on_update,
        width=15,
        bg="#4CAF50",
        fg="white"
    )
    update_btn.pack(side="left", padx=10)

    # ESC 关闭
    dialog.bind('<Escape>', lambda e: on_cancel())


def auto_check_on_startup(root, delay_ms=3000):
    """
    启动时自动检查更新（延迟执行）

    Args:
        root: tkinter 根窗口
        delay_ms: 延迟毫秒数（默认 3 秒，避免启动时卡顿）
    """
    root.after(delay_ms, lambda: check_and_update_gui(root, silent=True))


if __name__ == "__main__":
    # 测试
    print("测试更新检查...")
    result = check_github_release()
    print(f"当前版本: {result['current']}")
    print(f"最新版本: {result['latest']}")
    print(f"有更新: {result['has_update']}")
    if result['error']:
        print(f"错误: {result['error']}")
    if result['download_url']:
        print(f"下载链接: {result['download_url']}")
