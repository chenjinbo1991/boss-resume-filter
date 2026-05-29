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
import time
import requests
import shlex
import tempfile
import plistlib
import hashlib
from pathlib import Path
from tkinter import messagebox
import tkinter as tk
from paths import get_base_dir


def _get_font_family():
    """获取字体 - 与 gui_main.py 保持一致"""
    if sys.platform == 'win32':
        return 'Microsoft YaHei UI'
    elif sys.platform == 'darwin':
        return 'PingFang SC'
    return 'Helvetica'


_FONT_FAMILY = _get_font_family()


def _place_dialog_centered(dialog, parent, width, height):
    """将更新弹窗相对父窗口居中，并限制在屏幕可见范围内。"""
    parent.update_idletasks()
    dialog.update_idletasks()

    screen_width = dialog.winfo_screenwidth()
    screen_height = dialog.winfo_screenheight()
    if width > screen_width:
        width = max(1, int(screen_width * 0.9))
    if height > screen_height:
        height = max(1, int(screen_height * 0.85))

    parent_x = parent.winfo_rootx()
    parent_y = parent.winfo_rooty()
    parent_width = parent.winfo_width()
    parent_height = parent.winfo_height()

    x = parent_x + (parent_width - width) // 2
    y = parent_y + (parent_height - height) // 2
    y -= _get_parent_titlebar_center_offset(parent)
    x = min(max(0, x), max(0, screen_width - width))
    y = min(max(0, y), max(0, screen_height - height))
    dialog.geometry(f"{width}x{height}+{x}+{y}")
    _bind_parent_center_correction(dialog, parent, width, height, 0, 0, screen_width, screen_height)


def _bind_parent_center_correction(dialog, parent, width, height, screen_left, screen_top, screen_width, screen_height):
    """更新弹窗显示后用 Tk 实际坐标再校正一次父子中心。"""
    try:
        if getattr(dialog, "_parent_center_correction_bound", False):
            return
        dialog._parent_center_correction_bound = True

        def correct_once(event=None):
            try:
                dialog.unbind("<Map>", getattr(dialog, "_parent_center_correction_bind_id", ""))
            except tk.TclError:
                pass
            try:
                parent.update_idletasks()
                dialog.update_idletasks()
                parent_center_x = parent.winfo_rootx() + parent.winfo_width() // 2
                parent_center_y = parent.winfo_rooty() + parent.winfo_height() // 2
                dialog_center_x = dialog.winfo_rootx() + dialog.winfo_width() // 2
                dialog_center_y = dialog.winfo_rooty() + dialog.winfo_height() // 2
                dx = parent_center_x - dialog_center_x
                dy = parent_center_y - dialog_center_y
                if abs(dx) < 1 and abs(dy) < 1:
                    return
                new_x = dialog.winfo_rootx() + dx
                new_y = dialog.winfo_rooty() + dy
                max_x = screen_left + max(0, screen_width - width)
                max_y = screen_top + max(0, screen_height - height)
                new_x = min(max(screen_left, new_x), max_x)
                new_y = min(max(screen_top, new_y), max_y)
                dialog.geometry(f"{width}x{height}+{int(new_x)}+{int(new_y)}")
            except (tk.TclError, AttributeError):
                return

        bind_id = dialog.bind("<Map>", correct_once, add="+")
        dialog._parent_center_correction_bind_id = bind_id
        dialog.after(50, correct_once)
    except (tk.TclError, AttributeError):
        return


def _get_parent_titlebar_center_offset(parent):
    """估算父窗口标题栏导致的视觉中心下偏，只修正纵向中心。"""
    try:
        titlebar_height = int(parent.winfo_rooty()) - int(parent.winfo_y())
    except (tk.TclError, AttributeError, TypeError, ValueError):
        return 0
    if titlebar_height <= 0 or titlebar_height > 120:
        return 0
    return titlebar_height // 2


def get_current_version():
    """获取当前版本号"""
    try:
        # gui_main 是程序入口，updater 被调用时已在 sys.modules 中
        # 直接读取模块属性，无需解析源文件，兼容所有打包模式
        import gui_main
        return gui_main.__version__
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
        'download_url_fallback': None,
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
            except Exception:
                return (0, 0, 0)

        current_tuple = parse_version(result['current'])
        latest_tuple = parse_version(latest_version)

        result['has_update'] = latest_tuple > current_tuple

        # 查找下载链接
        if sys.platform == 'win32':
            # Windows: 查找 .exe
            for asset in release.get('assets', []):
                if asset.get('name', '').endswith('.exe'):
                    result['download_url'] = asset.get('browser_download_url')
                    result['asset_info'] = {'size': asset.get('size')}
                    break
        elif sys.platform == 'darwin':
            # macOS: 查找 _mac.zip
            for asset in release.get('assets', []):
                if asset.get('name', '').endswith('_mac.zip'):
                    result['download_url'] = asset.get('browser_download_url')
                    result['asset_info'] = {'size': asset.get('size')}
                    break

    except requests.exceptions.Timeout:
        result['error'] = "网络连接超时"
    except requests.exceptions.RequestException as e:
        result['error'] = f"网络请求失败: {e}"
    except Exception as e:
        result['error'] = f"检查更新失败: {e}"

    return result


def check_gitee_latest(latest_json_url="https://gitee.com/yaoyouzhong/boss-resume-filter/raw/master/latest.json"):
    """
    从 Gitee 检查最新版本（国内备用源）

    Args:
        latest_json_url: Gitee 上 latest.json 的 URL

    Returns:
        dict: 与 check_github_release() 返回结构相同
    """
    result = {
        'latest': None,
        'current': get_current_version(),
        'has_update': False,
        'release_info': None,
        'download_url': None,
        'download_url_fallback': None,
        'error': None
    }

    try:
        response = requests.get(latest_json_url, timeout=8)  # 8秒超时，国内一般够用
        response.raise_for_status()

        data = response.json()
        latest_version = data.get('version', '').lstrip('v')
        result['latest'] = latest_version

        # 比较版本号
        def parse_version(v):
            try:
                parts = [int(x) for x in v.split('.')]
                return tuple(parts)
            except Exception:
                return (0, 0, 0)

        current_tuple = parse_version(result['current'])
        latest_tuple = parse_version(latest_version)
        result['has_update'] = latest_tuple > current_tuple

        # 构造 release_info（兼容 GitHub 格式）
        result['release_info'] = {
            'tag_name': f"v{latest_version}",
            'body': data.get('release_notes', '无更新说明')
        }

        # 获取下载链接：优先使用 Gitee 国内下载链接，回退到 GitHub 链接
        downloads = data.get('downloads', {})
        downloads_cn = data.get('downloads_cn', {})
        assets = data.get('assets', {})
        if sys.platform == 'win32':
            result['download_url'] = downloads_cn.get('windows') or downloads.get('windows')
            result['download_url_fallback'] = downloads.get('windows')
            result['asset_info'] = assets.get('windows', {})
        elif sys.platform == 'darwin':
            result['download_url'] = downloads_cn.get('macos') or downloads.get('macos')
            result['download_url_fallback'] = downloads.get('macos')
            result['asset_info'] = assets.get('macos', {})

    except requests.exceptions.Timeout:
        result['error'] = "Gitee 连接超时"
    except requests.exceptions.RequestException as e:
        result['error'] = f"Gitee 请求失败: {e}"
    except Exception as e:
        result['error'] = f"检查更新失败: {e}"

    return result


def _file_sha256(path):
    """计算文件 SHA256，用于更新包完整性校验。"""
    digest = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def verify_downloaded_file(path, asset_info=None):
    """校验下载文件的大小和 SHA256。自动更新核心资产必须同时提供两项元数据。"""
    asset_info = asset_info or {}
    expected_size = asset_info.get('size')
    expected_sha256 = asset_info.get('sha256')

    if expected_size is None or not expected_sha256:
        return False, "更新源缺少文件大小或 SHA256 校验信息，已拒绝安装"

    if expected_size is not None:
        try:
            expected_size = int(expected_size)
        except (TypeError, ValueError):
            return False, f"更新源文件大小元数据无效: {expected_size}"
        actual_size = Path(path).stat().st_size
        if actual_size != expected_size:
            return False, f"文件大小不匹配: 期望 {expected_size} bytes，实际 {actual_size} bytes"

    magic_error = _validate_file_magic(path)
    if magic_error:
        return False, magic_error

    if expected_sha256:
        actual_sha256 = _file_sha256(path)
        if actual_sha256.lower() != str(expected_sha256).lower():
            return False, (
                "SHA256 不匹配: "
                f"期望 {expected_sha256}，实际 {actual_sha256}"
            )

    return True, None


def _validate_file_magic(path):
    """检查常见更新包文件头，防止 HTML 错误页等非目标文件进入安装流程。"""
    path = Path(path)
    suffix = path.suffix.lower()
    expected = None
    label = None
    if suffix == ".exe":
        expected = b"MZ"
        label = "EXE"
    elif suffix == ".zip":
        expected = b"PK"
        label = "ZIP"

    if not expected:
        return None

    try:
        with open(path, "rb") as f:
            actual = f.read(len(expected))
    except OSError as e:
        return f"无法读取更新包文件头: {e}"

    if actual != expected:
        return f"{label} 文件头无效，下载内容可能不是正确的更新包"
    return None


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


def download_and_verify_file(url, dest_path, asset_info=None, progress_callback=None):
    """下载文件，并在有元数据时校验大小和 SHA256。"""
    success, error = download_file(url, dest_path, progress_callback)
    if not success:
        return False, error

    verified, verify_error = verify_downloaded_file(dest_path, asset_info)
    if not verified:
        try:
            Path(dest_path).unlink(missing_ok=True)
        except OSError:
            pass
        return False, verify_error

    return True, None


def mark_update_success_and_cleanup():
    """新版本成功进入 GUI 后写入启动标记，并清理平台相关旧版本备份。"""
    if not getattr(sys, 'frozen', False):
        return

    try:
        marker = os.environ.get("BOSS_UPDATE_MARKER")
        if marker:
            Path(marker).write_text(str(time.time()), encoding="utf-8")
            print(f"[更新] 已写入启动成功标记: {marker}")

        if sys.platform == 'win32':
            for suffix in (".old", ".old.previous"):
                old_exe = Path(sys.executable + suffix)
                if old_exe.exists():
                    old_exe.unlink()
                    print(f"[更新] 已清理旧版本备份: {old_exe}")
    except OSError as e:
        print(f"[更新] 清理旧版本备份失败: {e}")


def update_windows(new_exe_path, current_exe_path):
    """
    Windows EXE 更新逻辑

    生成 update.bat 脚本，然后启动脚本并退出当前程序

    流程：
    1. 等待当前进程退出
    2. 重命名当前 EXE 为 .old
    3. 复制新 EXE 到原位置
    4. 启动新 EXE
    5. 清理临时下载文件和脚本自身，旧 EXE 留到新版本成功启动后清理
    """
    try:
        # 生成 update.bat
        bat_path = Path(current_exe_path).parent / "update.bat"
        temp_dir = Path(new_exe_path).parent
        marker_path = Path(current_exe_path).with_suffix(Path(current_exe_path).suffix + ".update_ok")
        current_pid = os.getpid()

        bat_content = f"""@echo off
setlocal
set "OLD_EXE={current_exe_path}"
set "NEW_EXE={new_exe_path}"
set "TEMP_DIR={temp_dir}"
set "MARKER_FILE={marker_path}"
set "OLD_PID={current_pid}"
set "LOG_FILE=%TEMP%\\boss_resume_filter_update.log"
set "FAILED_FILE=%OLD_EXE%.update_failed.txt"

echo [%date% %time%] Starting update > "%LOG_FILE%"
echo 正在更新 BOSS 简历筛选器...

echo 等待旧程序退出...
echo [%date% %time%] Waiting for old process %OLD_PID% >> "%LOG_FILE%"
for /l %%i in (1,1,60) do (
    tasklist /FI "PID eq %OLD_PID%" 2>NUL | find "%OLD_PID%" >NUL
    if errorlevel 1 goto process_exited
    timeout /t 1 /nobreak >nul
)

echo [%date% %time%] Old process did not exit in time >> "%LOG_FILE%"
exit /b 1

:process_exited
echo [%date% %time%] Old process exited >> "%LOG_FILE%"

echo 备份旧版本...
if exist "%OLD_EXE%.old" move /y "%OLD_EXE%.old" "%OLD_EXE%.old.previous" >> "%LOG_FILE%" 2>&1
move /y "%OLD_EXE%" "%OLD_EXE%.old" >> "%LOG_FILE%" 2>&1
if errorlevel 1 (
    echo [%date% %time%] Failed to backup old executable >> "%LOG_FILE%"
    exit /b 1
)

echo 安装新版本...
copy /y "%NEW_EXE%" "%OLD_EXE%" >> "%LOG_FILE%" 2>&1
if errorlevel 1 (
    echo [%date% %time%] Failed to copy new executable, rolling back >> "%LOG_FILE%"
    if exist "%OLD_EXE%.old" move /y "%OLD_EXE%.old" "%OLD_EXE%" >> "%LOG_FILE%" 2>&1
    exit /b 1
)

echo 验证新版本...
for %%A in ("%NEW_EXE%") do set "NEW_SIZE=%%~zA"
for %%A in ("%OLD_EXE%") do set "OLD_SIZE=%%~zA"
if not "%NEW_SIZE%"=="%OLD_SIZE%" (
    echo [%date% %time%] File size mismatch: new=%NEW_SIZE%, old=%OLD_SIZE% >> "%LOG_FILE%"
    if exist "%OLD_EXE%.old" move /y "%OLD_EXE%.old" "%OLD_EXE%" >> "%LOG_FILE%" 2>&1
    exit /b 1
)

echo 等待文件系统刷盘...
timeout /t 8 /nobreak >nul

echo 准备干净的 PyInstaller 重启环境...
echo [%date% %time%] Resetting PyInstaller runtime environment >> "%LOG_FILE%"
set "PYINSTALLER_RESET_ENVIRONMENT=1"
for /f "tokens=1 delims==" %%V in ('set _PYI_ 2^>nul') do set "%%V="

echo 启动新版本...
if exist "%MARKER_FILE%" del /f /q "%MARKER_FILE%" >> "%LOG_FILE%" 2>&1
set "BOSS_UPDATE_MARKER=%MARKER_FILE%"
set "NEW_PID="
for /f %%P in ('powershell -NoProfile -Command "$p = Start-Process -FilePath $env:OLD_EXE -WorkingDirectory (Split-Path $env:OLD_EXE) -PassThru; $p.Id"') do set "NEW_PID=%%P"
echo [%date% %time%] Started new process PID=%NEW_PID% >> "%LOG_FILE%"

echo 等待新版本启动确认...
echo [%date% %time%] Waiting for startup marker %MARKER_FILE% >> "%LOG_FILE%"
for /l %%i in (1,1,45) do (
    if exist "%MARKER_FILE%" goto update_confirmed
    timeout /t 1 /nobreak >nul
)

echo [%date% %time%] First startup marker not found, retrying once >> "%LOG_FILE%"
if defined NEW_PID taskkill /f /pid %NEW_PID% >> "%LOG_FILE%" 2>&1
timeout /t 5 /nobreak >nul
set "NEW_PID="
for /f %%P in ('powershell -NoProfile -Command "$p = Start-Process -FilePath $env:OLD_EXE -WorkingDirectory (Split-Path $env:OLD_EXE) -PassThru; $p.Id"') do set "NEW_PID=%%P"
echo [%date% %time%] Retried new process PID=%NEW_PID% >> "%LOG_FILE%"
for /l %%i in (1,1,90) do (
    if exist "%MARKER_FILE%" goto update_confirmed
    timeout /t 1 /nobreak >nul
)

echo [%date% %time%] Startup marker not found after retry, rolling back >> "%LOG_FILE%"
echo 自动更新失败，已回滚到旧版本。> "%FAILED_FILE%"
echo 失败时间: %date% %time%>> "%FAILED_FILE%"
echo 详细日志: %LOG_FILE%>> "%FAILED_FILE%"
if defined NEW_PID taskkill /f /pid %NEW_PID% >> "%LOG_FILE%" 2>&1
timeout /t 2 /nobreak >nul
if exist "%OLD_EXE%" del /f /q "%OLD_EXE%" >> "%LOG_FILE%" 2>&1
if exist "%OLD_EXE%.old" move /y "%OLD_EXE%.old" "%OLD_EXE%" >> "%LOG_FILE%" 2>&1
if exist "%TEMP_DIR%" rmdir /s /q "%TEMP_DIR%" >> "%LOG_FILE%" 2>&1
echo [%date% %time%] Rolled back to old executable >> "%LOG_FILE%"
exit /b 1

:update_confirmed
echo [%date% %time%] Startup marker found, update confirmed >> "%LOG_FILE%"
if exist "%MARKER_FILE%" del /f /q "%MARKER_FILE%" >> "%LOG_FILE%" 2>&1
if exist "%OLD_EXE%.old" del /f /q "%OLD_EXE%.old" >> "%LOG_FILE%" 2>&1
if exist "%OLD_EXE%.old.previous" del /f /q "%OLD_EXE%.old.previous" >> "%LOG_FILE%" 2>&1
if exist "%TEMP_DIR%" rmdir /s /q "%TEMP_DIR%" >> "%LOG_FILE%" 2>&1

echo 更新完成！
echo [%date% %time%] Update completed >> "%LOG_FILE%"
del "%~f0"
"""

        with open(bat_path, 'w', encoding='utf-8') as f:
            f.write(bat_content)

        # 启动 update.bat（最小化窗口）
        subprocess.Popen(
            ["cmd", "/c", str(bat_path)],
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
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


def update_macos_app(zip_path, current_app_path):
    """
    macOS .app 更新逻辑

    解压 ZIP 包，替换旧的 .app bundle，然后重启应用

    Args:
        zip_path: 下载的 ZIP 文件路径
        current_app_path: 当前 .app bundle 路径
    """
    try:
        # 用 ditto 解压，保留 .app bundle 内的 symlink、权限和扩展属性。
        # zipfile.extractall() 会破坏 Python.framework，导致更新后的 app 无法打开。
        temp_dir = Path(tempfile.mkdtemp())
        subprocess.run(
            ["ditto", "-x", "-k", str(zip_path), str(temp_dir)],
            check=True,
            capture_output=True,
            text=True,
        )

        # 找到解压后的 .app
        app_candidates = list(temp_dir.glob("*.app")) + list(temp_dir.glob("*/*.app"))
        new_app_path = app_candidates[0] if app_candidates else None

        if not new_app_path:
            return False, "ZIP 包中未找到 .app"

        info_plist = new_app_path / "Contents" / "Info.plist"
        if not info_plist.exists():
            return False, "ZIP 包中的 .app 缺少 Info.plist"

        with open(info_plist, "rb") as f:
            bundle_info = plistlib.load(f)
        executable_name = bundle_info.get("CFBundleExecutable")
        if not executable_name:
            return False, "ZIP 包中的 .app 缺少 CFBundleExecutable"

        executable_path = new_app_path / "Contents" / "MacOS" / executable_name
        if not executable_path.exists():
            return False, f"ZIP 包中的主程序不存在: {executable_name}"
        executable_path.chmod(executable_path.stat().st_mode | 0o755)

        # 生成替换脚本
        # 脚本写入 /tmp/（稳定位置），不放在 temp_dir 内，
        # 避免 sys.exit(0) 退出时 temp_dir 被 OS 清理导致脚本丢失
        # ditto 保留所有资源分支和扩展属性（cp -R 可能丢失）
        # xattr -cr 清除隔离属性，防止 Gatekeeper 拦截
        # 日志写入 /tmp/boss_update.log 便于诊断
        current_pid = os.getpid()
        quoted_current_app = shlex.quote(str(current_app_path))
        quoted_new_app = shlex.quote(str(new_app_path))
        quoted_temp_dir = shlex.quote(str(temp_dir))
        marker_path = Path(tempfile.gettempdir()) / "boss_update_ok"
        quoted_marker = shlex.quote(str(marker_path))

        script = f'''#!/bin/bash
set -e
exec > /tmp/boss_update.log 2>&1
OLD_APP={quoted_current_app}
NEW_APP={quoted_new_app}
TEMP_DIR={quoted_temp_dir}
MARKER_FILE={quoted_marker}
BACKUP_APP="${{OLD_APP}}.backup"
FAILED_FILE="${{OLD_APP}}.update_failed.txt"
OLD_PID={current_pid}

rollback() {{
    echo "[$(date)] Rolling back app update"
    rm -rf "$OLD_APP"
    if [ -d "$BACKUP_APP" ]; then
        mv "$BACKUP_APP" "$OLD_APP"
    fi
}}

echo "[$(date)] Starting update"
echo "[$(date)] Waiting for old process $OLD_PID to exit"
for i in {{1..60}}; do
    if ! kill -0 "$OLD_PID" 2>/dev/null; then
        break
    fi
    sleep 0.5
done

if kill -0 "$OLD_PID" 2>/dev/null; then
    echo "[$(date)] Old process did not exit in time"
    exit 1
fi

if [ ! -d "$NEW_APP" ]; then
    echo "[$(date)] New app not found: $NEW_APP"
    exit 1
fi

echo "[$(date)] Removing old app"
rm -rf "$BACKUP_APP"
if [ -d "$OLD_APP" ]; then
    mv "$OLD_APP" "$BACKUP_APP"
fi
echo "[$(date)] Copying new app with ditto"
if ! ditto "$NEW_APP" "$OLD_APP"; then
    rollback
    exit 1
fi
echo "[$(date)] Restoring executable permission"
EXECUTABLE=$(/usr/libexec/PlistBuddy -c 'Print :CFBundleExecutable' "$OLD_APP/Contents/Info.plist")
if [ -z "$EXECUTABLE" ] || [ ! -f "$OLD_APP/Contents/MacOS/$EXECUTABLE" ]; then
    echo "[$(date)] New app executable missing"
    rollback
    exit 1
fi
chmod +x "$OLD_APP/Contents/MacOS/$EXECUTABLE" || {{
    rollback
    exit 1
}}
echo "[$(date)] Clearing quarantine attributes"
xattr -cr "$OLD_APP" 2>/dev/null || true
echo "[$(date)] Opening app"
rm -f "$MARKER_FILE"
BOSS_UPDATE_MARKER="$MARKER_FILE" "$OLD_APP/Contents/MacOS/$EXECUTABLE" &
NEW_PID=$!
echo "[$(date)] Started new process PID=$NEW_PID"
echo "[$(date)] Waiting for startup marker $MARKER_FILE"
for i in {{1..90}}; do
    if [ -f "$MARKER_FILE" ]; then
        break
    fi
    sleep 1
done

if [ ! -f "$MARKER_FILE" ]; then
    echo "[$(date)] Startup marker not found"
    cat > "$FAILED_FILE" <<EOF
自动更新失败，已回滚到旧版本。
失败时间: $(date)
详细日志: /tmp/boss_update.log
EOF
    kill "$NEW_PID" 2>/dev/null || true
    rollback
    exit 1
fi

echo "[$(date)] Cleanup"
rm -f "$MARKER_FILE"
rm -rf "$BACKUP_APP"
rm -rf "$TEMP_DIR"
rm -f "$0"
'''

        # 写入 /tmp/（不在 temp_dir 内，不会随进程退出被清理）
        script_path = Path(tempfile.gettempdir()) / "boss_update.sh"
        with open(script_path, 'w') as f:
            f.write(script)
        script_path.chmod(0o755)

        # 启动脚本：start_new_session=True 脱离父进程组，
        # 确保 sys.exit(0) 退出时脚本不会被 macOS 连带杀掉
        subprocess.Popen(
            ['bash', str(script_path)],
            close_fds=True,
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        return True, "更新成功，程序即将重启"

    except Exception as e:
        return False, str(e)


def exit_for_update(root):
    """退出当前 GUI 进程，让外部更新脚本替换并重启应用。"""
    try:
        root.destroy()
    except tk.TclError:
        pass
    os._exit(0)


def check_and_update_gui(root, silent=False, on_complete=None):
    """
    GUI 版本的更新检查和执行

    Args:
        root: tkinter 根窗口
        silent: 是否静默检查（不显示"已是最新版本"提示）
    """
    def do_check():
        # 优先尝试 Gitee（国内快）
        result = check_gitee_latest()

        if result['error']:
            # Gitee 请求失败，回退到 GitHub
            print(f"[更新] Gitee 检查失败: {result['error']}，尝试 GitHub...")
            result = check_github_release()
        elif not result['has_update']:
            # Gitee 返回成功但无更新，用 GitHub 复核（防止 Gitee 镜像同步延迟）
            gh = check_github_release()
            if not gh['error'] and gh['has_update']:
                print(f"[更新] GitHub 发现新版本 v{gh['latest']}，使用 GitHub 结果")
                result = gh

        # 回到主线程处理结果
        root.after(0, lambda: handle_result(result))

    def handle_result(result):
        if result['error']:
            if not silent:
                messagebox.showerror("检查更新失败", result['error'], parent=root)
            if on_complete:
                on_complete(result)
            return

        if not result['has_update']:
            if not silent:
                messagebox.showinfo(
                    "检查更新",
                    f"当前已是最新版本 v{result['current']}",
                    parent=root
                )
            if on_complete:
                on_complete(result)
            return

        # 有新版本，显示更新对话框
        show_update_dialog(root, result)
        if on_complete:
            on_complete(result)

    # 启动后台检查
    threading.Thread(target=do_check, daemon=True).start()


def show_update_dialog(root, result):
    """显示更新对话框"""
    dialog = tk.Toplevel(root)
    dialog.title("发现新版本")
    dialog.transient(root)
    dialog.grab_set()

    # 居中显示
    _place_dialog_centered(dialog, root, 600, 500)

    # 标题行：v2.7 → v2.8
    title_label = tk.Label(
        dialog,
        text=f"v{result['current']} → v{result['latest']}",
        font=(_FONT_FAMILY, 16, "bold")
    )
    title_label.pack(pady=(15, 5))

    # 更新内容（从 release body 读取）
    release_info = result['release_info']
    body = release_info.get('body', '无更新说明')

    content_frame = tk.LabelFrame(dialog, text="更新内容", padx=10, pady=10,
                                  font=(_FONT_FAMILY, 13))
    content_frame.pack(fill="both", expand=True, padx=20, pady=10)

    content_text = tk.Text(content_frame, wrap="word", height=15,
                           font=(_FONT_FAMILY, 12))
    content_text.insert("1.0", body)
    content_text.config(state="disabled")
    content_text.pack(fill="both", expand=True)

    # 进度条（初始隐藏）
    progress_frame = tk.Frame(dialog)
    progress_label = tk.Label(progress_frame, text="下载中...",
                              font=(_FONT_FAMILY, 13))
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
                temp_dir = Path(tempfile.mkdtemp(prefix="boss_update_download_"))
                temp_exe = temp_dir / "BOSS_ResumeFilter_new.exe"

                def progress_callback(downloaded, total):
                    if total > 0:
                        percent = int(downloaded / total * 100)
                        root.after(0, lambda: progress_bar.config(value=percent))
                        root.after(0, lambda: progress_label.config(
                            text=f"下载中... {percent}%"
                        ))

                asset_info = result.get('asset_info', {})
                success, error = download_and_verify_file(
                    str(download_url), temp_exe, asset_info, progress_callback)

                if not success:
                    # Gitee 下载失败，尝试 GitHub fallback
                    fallback_url = result.get('download_url_fallback')
                    if fallback_url and str(fallback_url) != str(download_url):
                        root.after(0, lambda: progress_label.config(text="Gitee 下载失败，尝试 GitHub..."))
                        success, error = download_and_verify_file(
                            str(fallback_url), temp_exe, asset_info, progress_callback)
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
                        progress_label.config(text="更新成功，程序即将重启"),
                        dialog.destroy(),
                        exit_for_update(root)
                    ))
                else:
                    root.after(0, lambda: messagebox.showerror(
                        "更新失败",
                        f"安装失败: {error}",
                        parent=dialog
                    ))

            else:
                # macOS: 判断是否从 .app bundle 运行
                if getattr(sys, 'frozen', False):
                    # 从 .app 运行：下载 ZIP 并替换
                    download_url = result['download_url']
                    if not download_url:
                        root.after(0, lambda: messagebox.showerror(
                            "更新失败",
                            "未找到 macOS ZIP 下载链接",
                            parent=dialog
                        ))
                        return

                    # 下载 ZIP
                    temp_dir = Path(tempfile.mkdtemp(prefix="boss_update_download_"))
                    temp_zip = temp_dir / "BOSS_ResumeFilter_mac.zip"

                    def progress_callback(downloaded, total):
                        if total > 0:
                            percent = int(downloaded / total * 100)
                            root.after(0, lambda: progress_bar.config(value=percent))
                            root.after(0, lambda: progress_label.config(
                                text=f"下载中... {percent}%"
                            ))

                    asset_info = result.get('asset_info', {})
                    success, error = download_and_verify_file(
                        str(download_url), temp_zip, asset_info, progress_callback)

                    if not success:
                        # Gitee 下载失败，尝试 GitHub fallback
                        fallback_url = result.get('download_url_fallback')
                        if fallback_url and str(fallback_url) != str(download_url):
                            root.after(0, lambda: progress_label.config(text="Gitee 下载失败，尝试 GitHub..."))
                            success, error = download_and_verify_file(
                                str(fallback_url), temp_zip, asset_info, progress_callback)
                        if not success:
                            root.after(0, lambda: messagebox.showerror(
                                "下载失败",
                                f"下载新版本失败: {error}",
                                parent=dialog
                            ))
                            return

                    # 执行更新
                    root.after(0, lambda: progress_label.config(text="正在安装..."))

                    # 获取当前 .app 路径
                    # sys.executable 在 .app 中指向 Python 二进制，需要向上找到 .app 目录
                    exe_path = Path(sys.executable).resolve()
                    # 向上查找直到找到 .app 目录
                    current_app = exe_path
                    while current_app.suffix != '.app' and current_app != current_app.parent:
                        current_app = current_app.parent

                    if current_app.suffix != '.app':
                        root.after(0, lambda: messagebox.showerror(
                            "更新失败",
                            "无法定位当前 .app 路径",
                            parent=dialog
                        ))
                        return

                    success, message = update_macos_app(str(temp_zip), str(current_app))

                    if success:
                        root.after(0, lambda: (
                            progress_label.config(text=message),
                            dialog.destroy(),
                            exit_for_update(root)
                        ))
                    else:
                        root.after(0, lambda: messagebox.showerror(
                            "更新失败",
                            f"安装失败: {message}",
                            parent=dialog
                        ))
                else:
                    # 从源码运行：git pull（降级方案）
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
        width=15,
        font=(_FONT_FAMILY, 13)
    )
    cancel_btn.pack(side="left", padx=10)

    update_btn = tk.Button(
        button_frame,
        text="立即更新",
        command=on_update,
        width=15,
        font=(_FONT_FAMILY, 13)
    )
    update_btn.pack(side="left", padx=10)

    # ESC 关闭
    dialog.bind('<Escape>', lambda e: on_cancel())


def auto_check_on_startup(root, delay_ms=3000):
    """
    启动时自动检查更新（延迟执行），带 24 小时冷却机制

    Args:
        root: tkinter 根窗口
        delay_ms: 延迟毫秒数（默认 3 秒，避免启动时卡顿）
    """
    # 检查冷却时间（24 小时内不重复检查）
    base_dir = get_base_dir()
    cooldown_file = base_dir / ".last_update_check"
    failed_cooldown_file = base_dir / ".last_update_check_failed"
    cooldown_hours = 4
    failed_cooldown_hours = 0.25

    try:
        if cooldown_file.exists():
            last_check = float(cooldown_file.read_text().strip())
            hours_since = (time.time() - last_check) / 3600
            if hours_since < cooldown_hours:
                print(f"[更新] 距离上次检查仅 {hours_since:.1f} 小时，跳过自动检查")
                return
    except (ValueError, OSError):
        pass  # 文件损坏或读取失败，继续检查

    try:
        if failed_cooldown_file.exists():
            last_failed = float(failed_cooldown_file.read_text().strip())
            hours_since_failed = (time.time() - last_failed) / 3600
            if hours_since_failed < failed_cooldown_hours:
                print(f"[更新] 距离上次失败仅 {hours_since_failed:.1f} 小时，暂缓自动检查")
                return
    except (ValueError, OSError):
        pass

    def _do_check_and_record():
        """执行检查并记录时间戳"""
        def record_result(result):
            try:
                if result.get('error'):
                    failed_cooldown_file.write_text(str(time.time()))
                else:
                    cooldown_file.write_text(str(time.time()))
                    failed_cooldown_file.unlink(missing_ok=True)
            except OSError:
                pass

        check_and_update_gui(root, silent=True, on_complete=record_result)

    root.after(delay_ms, _do_check_and_record)


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
