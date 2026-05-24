"""
BOSS 简历筛选器 - 图形界面版本
优化：浏览器状态检测 + 进度条 + 数据安全性 + UI 细节增强
"""

__version__ = "2.8.4"

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, font
import json
import sys
import os
import re
import shutil
import icons
import time
import threading
import queue
import socket
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse
from security import save_api_key, get_api_key, delete_api_key
import updater

# ========== 路径常量 - 解决相对路径问题 ==========
# PyInstaller --onefile 模式下 __file__ 指向临时解压目录，需特殊处理
def _get_base_dir():
    import sys
    if getattr(sys, 'frozen', False):
        exe_dir = Path(sys.executable).parent.resolve()
        # macOS .app: sys.executable 在 .app/Contents/MacOS/ 内，
        # 用户配置文件（job_config.json 等）在 .app 旁边
        if sys.platform == 'darwin' and exe_dir.name == 'MacOS':
            base = exe_dir.parent.parent.parent
        else:
            base = exe_dir

        # 首次运行时配置文件可能不存在（如 macOS DMG 安装后），
        # 从嵌入的 _MEIPASS 复制默认配置到可写位置
        meipass = Path(sys._MEIPASS)
        for fname in ["job_config.json", "selectors.json", "api_config.json"]:
            target = base / fname
            if not target.exists():
                src = meipass / fname
                if src.exists():
                    import shutil
                    shutil.copy2(str(src), str(target))

        return base
    return Path(__file__).parent.resolve()

BASE_DIR = _get_base_dir()
CONFIG_PATH = BASE_DIR / "job_config.json"
CANDIDATES_PATH = BASE_DIR / "candidates_all.json"
CANDIDATES_XLSX_PATH = BASE_DIR / "candidates_all.xlsx"
CONFIG_BACKUP_PATH = BASE_DIR / "job_config.json.bak"
API_CONFIG_PATH = BASE_DIR / "api_config.json"
CHROME_DEBUG_PORT_FILE = BASE_DIR / ".chrome_debug_port"


def get_font_family():
    """获取字体 - 支持跨平台降级"""
    # 优先使用微软雅黑，macOS/Linux 降级到系统字体
    import sys
    if sys.platform == 'win32':
        return 'Microsoft YaHei UI'
    elif sys.platform == 'darwin':
        return 'PingFang SC'
    else:
        return 'Helvetica'


FONT_FAMILY = get_font_family()


# UI 配置常量（续）
UI_CONFIG = {
    'zoom_factor': 1.3,              # 额外放大系数
    'window_base_width': 1500,       # 窗口基础宽度
    'window_base_height': 950,       # 窗口基础高度
    'window_min_width': 1300,        # 最小窗口宽度
    'window_min_height': 750,        # 最小窗口高度
    'sidebar_width': 230,            # 侧边栏宽度
    'page_padding_x': 50,            # 页面左右边距
    'page_padding_y': 40,            # 页面上下边距
    'card_padding': 30,              # 卡片内边距
    'stat_icon_size': 56,            # 统计图标大小
    'font_scale_base': 20,           # 字体缩放基准
    'logo_padding_x': 25,            # Logo 区域左右边距
    'logo_padding_y': 35,            # Logo 区域上下边距
    'nav_padding': 15,               # 导航项内边距
    'label_frame_padding': 15,       # LabelFrame 默认内边距
    'font_size_title': 32,           # 标题字体大小
    'font_size_logo': 28,            # Logo 字体大小
    'treeview_rowheight': 28,        # Treeview 行高
    'text_height_large': 8,          # 大文本框高度（行）
    'text_height_small': 4,          # 小文本框高度（行）
    'listbox_height': 4,             # 列表框高度
    'treeview_height': 8,            # 树形控件高度
    'spinbox_exp_min': 0,            # 经验 Spinbox 最小值
    'spinbox_exp_max': 30,           # 经验 Spinbox 最大值
    'spinbox_rounds_min': 0,         # 轮次 Spinbox 最小值
    'spinbox_rounds_max': 9999,      # 轮次 Spinbox 最大值（虚拟上限）
    'icon_margin': 4,                # 图标圆形边距
    'combobox_width_job': 40,        # 岗位 Combobox 宽度
    'combobox_width_provider': 15,   # 服务商 Combobox 宽度
    'combobox_width_edu': 15,        # 学历 Combobox 宽度
    'entry_width_label': 10,         # 标签 Entry 宽度
    'entry_width_job': 12,           # 岗位名称 Entry 宽度
    'entry_width_model': 30,         # 模型名称 Entry 宽度
    'entry_width_api_key': 55,       # API Key Entry 宽度
    'entry_width_url': 55,           # Base URL Entry 宽度
    'entry_width_required': 40,      # 必要条件 Entry 宽度
    'treeview_column_width_base_url': 400,  # Treeview 列宽
    'label_width_provider': 10,      # 服务商标签宽度
    'label_width_model': 10,         # 模型名称标签宽度
    'label_width_api_key': 10,       # API Key 标签宽度
    'label_width_url': 10,           # Base URL 标签宽度
    'font_size_status': 11,          # 状态提示字体大小
    'font_size_model_label': 14,     # 模型标签字体大小
}

# macOS Tk 9.0+ 触控板滚动修复标记：
# Tk 9.0 的 Cocoa 后端不向 Canvas 派发触控板滚动事件（scrollWheel: 在 NSView 层被消费），
# 需要通过 ObjC Runtime swizzle 拦截并转发。Windows (Tk 8.6) 不受影响。
_NEED_COCOA_SCROLL_HOOK = sys.platform == 'darwin' and tk.TkVersion >= 9.0

def _draw_search_icon(S, fill, sw_ratio=0.10):
    """在 S×S 画布上绘制放大镜图标（🔍 风格），返回 RGBA Image"""
    from PIL import Image, ImageDraw
    import math
    img = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # 镜片
    rim_color = '#4B5563'      # 金属边框
    glass_fill = (147, 197, 253, 80)  # 淡蓝玻璃
    rim_w = max(3, int(S * 0.07))
    r = int(S * 0.24)
    cx, cy = int(S * 0.33), int(S * 0.33)
    # 镜片玻璃底色
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=glass_fill)
    # 金属边框
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=rim_color, width=rim_w)
    # 反光斜线（白色）
    shine_color = (255, 255, 255, 140)
    shine_w = max(2, int(S * 0.025))
    shine_y = int(cy - r * 0.4)
    shine_len = int(r * 1.1)
    angle = math.radians(-30)
    sx1 = int(cx - shine_len * math.cos(angle))
    sy1 = int(shine_y - shine_len * math.sin(angle))
    sx2 = int(cx + shine_len * math.cos(angle))
    sy2 = int(shine_y + shine_len * math.sin(angle))
    d.line([(sx1, sy1), (sx2, sy2)], fill=shine_color, width=shine_w)
    # 手柄
    handle_color = '#374151'
    handle_w = max(3, int(S * 0.07))
    angle45 = math.radians(45)
    hx0 = int(cx + (r + rim_w // 2) * math.cos(angle45))
    hy0 = int(cy + (r + rim_w // 2) * math.sin(angle45))
    handle_len = int(S * 0.42)
    hx1 = int(hx0 + handle_len * math.cos(angle45))
    hy1 = int(hy0 + handle_len * math.sin(angle45))
    d.line([(hx0, hy0), (hx1, hy1)], fill=handle_color, width=handle_w)
    # 手柄圆头
    cap_r = handle_w // 2
    d.ellipse([hx1 - cap_r, hy1 - cap_r, hx1 + cap_r, hy1 + cap_r], fill=handle_color)
    return img


class BossFilterGUI:
    """BOSS 简历筛选器图形界面 - 优化版"""

    def __init__(self, root):
        self.root = root
        self.root.title(f"BOSS 简历筛选器 v{__version__} - 智能候选人筛选工具")

        # 在 DPI 感知生效前捕获屏幕尺寸（此时与 tkinter geometry 同一虚拟坐标系）
        self.root.update_idletasks()
        _screen_width = self.root.winfo_screenwidth()
        _screen_height = self.root.winfo_screenheight()

        # 高 DPI 支持 - Per Monitor DPI Aware V2
        try:
            from ctypes import windll
            windll.shcore.SetProcessDpiAwareness(2)  # 2 = Per Monitor DPI Aware V2
        except (ImportError, OSError, AttributeError):
            pass

        # 使用 tkinter 内置方法获取 DPI 缩放比例（兼容 PyInstaller 打包）
        try:
            self.dpi_scale = self.root.winfo_fpixels('1i') / 96.0
        except Exception:
            self.dpi_scale = 1.0

        # 额外放大系数 - 让界面更大
        self.zoom_factor = UI_CONFIG['zoom_factor']
        effective_scale = self.dpi_scale * self.zoom_factor

        # 初始化图标缓存（DPI 感知的高清图标）
        self.icons = icons.init(effective_scale)

        # 设置窗口图标（替换 tkinter 默认羽毛图标）
        self._set_window_icon()

        # 设置 Combobox 下拉列表字体
        from tkinter import font as tkfont
        listbox_font = tkfont.Font(family=FONT_FAMILY, size=int(20 * self.dpi_scale * self.zoom_factor))
        self.root.option_add('*TCombobox*Listbox.font', listbox_font)

        # 窗口初始化完成后居中显示（使用 DPI 感知前捕获的屏幕尺寸）
        self.root.update_idletasks()
        window_width = int(UI_CONFIG['window_base_width'] * effective_scale)
        window_height = int(UI_CONFIG['window_base_height'] * effective_scale)

        screen_width = _screen_width
        screen_height = _screen_height
        if window_width > screen_width:
            window_width = int(screen_width * 0.9)
        if window_height > screen_height:
            window_height = int(screen_height * 0.85)
        x = max(0, (screen_width - window_width) // 2)
        y = max(0, (screen_height - window_height) // 2)

        self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")
        self.root.minsize(int(UI_CONFIG['window_min_width'] * effective_scale), int(UI_CONFIG['window_min_height'] * effective_scale))

        # 运行状态
        self.is_running = False
        self.log_queue = queue.Queue()
        self.progress_queue = queue.Queue()  # 进度条队列
        self.confirm_queue = queue.Queue()  # 岗位切换确认队列
        self.ui_queue = queue.Queue()  # UI 更新队列（线程安全）
        self.stop_event = threading.Event()  # 停止信号

        # 浏览器状态
        self.browser_connected = False
        self.browser_page = None
        self._browser_auto_check_id = None  # after() 回调 ID
        self._browser_status_text = ""
        self._browser_status_help_text = ""
        self._selectors_auto_checked = False  # 连接后选择器是否已自动检查
        self._pending_manual_check = False  # 待处理的手动检测请求
        self._pending_chrome_restart = False  # 待处理的 Chrome 重启请求

        # 右键菜单引用列表（统一销毁）
        self._context_menus = []

        # 加载配置
        self.job_rules = {}
        self.load_config()
        self.api_config = {}
        self.load_api_config()

        # 设置样式
        self.setup_styles()

        # 创建界面
        self.create_sidebar()
        self.create_main_content()

        # 启动日志更新
        self.update_log()

        # 启动 UI 更新队列处理（线程安全）
        self._process_ui_queue()

        # 初始加载结果
        self.refresh_results()

        # 注册窗口关闭处理
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # 统一绑定滚轮事件 - 根据当前页面分发到对应的 Canvas
        self.root.bind_all("<MouseWheel>", self._on_mousewheel)
        # macOS/Linux 触控板可能生成 Button-4/5 事件
        if sys.platform != 'win32':
            self.root.bind_all("<Button-4>", self._on_mousewheel)
            self.root.bind_all("<Button-5>", self._on_mousewheel)

        # macOS Tk 9.0+: Cocoa 层拦截触控板滚动事件并转发给 Tk
        if _NEED_COCOA_SCROLL_HOOK:
            self.root.after(500, self._setup_cocoa_scroll_hook)

        # 启动时自动检查更新（延迟 3 秒，避免启动卡顿）
        updater.auto_check_on_startup(self.root, delay_ms=3000)

    def setup_styles(self):
        """设置自定义样式"""
        style = ttk.Style()

        # 尝试使用现代主题
        try:
            style.theme_use('vista')
        except tk.TclError:
            try:
                style.theme_use('clam')
            except tk.TclError:
                pass  # 使用默认主题

        # 配色方案 - 现代化渐变色
        self.colors = {
            'primary': '#1E88E5',      # 主蓝色
            'primary_dark': '#1565C0',
            'primary_light': '#64B5F6',
            'success': '#43A047',       # 成功绿
            'success_light': '#81C784',
            'warning': '#FB8C00',       # 警告橙
            'danger': '#E53935',        # 危险红
            'purple': '#8E24AA',        # 紫色
            'bg_main': '#F8F9FA',       # 主背景
            'bg_card': '#FFFFFF',       # 卡片背景
            'bg_input': '#FAFAFA',      # 输入框背景
            'bg_sidebar': '#2D3748',    # 侧边栏背景
            'bg_tree_tag_high': '#E8F5E9',   # 表格高权重行
            'bg_tree_tag_mid': '#FFF3E0',    # 表格中权重行
            'bg_tree_tag_low': '#F5F5F5',    # 表格低权重行
            'text_primary': '#1A202C',  # 主文字
            'text_secondary': '#718096',# 次要文字
            'text_muted': '#999999',    # 弱化文字
            'text_sidebar': '#A0AEC0',  # 侧边栏文字
            'text_sidebar_active': '#FFFFFF',      # 侧边栏激活文字
            'text_sidebar_subtitle': '#94A3B8',    # 侧边栏副标题
            'text_sidebar_version': '#64748B',     # 侧边栏版本号
            'border': '#E2E8F0',        # 边框
        }

        # 设置字体 - 使用更清晰的大字体（根据 DPI 缩放）
        fs = self.dpi_scale * self.zoom_factor  # 字体缩放系数
        self.font_title = (FONT_FAMILY, int(UI_CONFIG['font_size_title'] * fs))
        self.font_subtitle = (FONT_FAMILY, int(16 * fs))
        self.font_section = (FONT_FAMILY, int(18 * fs))
        self.font_label = (FONT_FAMILY, int(15 * fs))
        self.font_button = (FONT_FAMILY, int(14 * fs))  # 按钮字体
        self.font_stat = (FONT_FAMILY, int(36 * fs))
        self.font_stat_label = (FONT_FAMILY, int(14 * fs))
        self.font_log = ('Consolas', int(12 * fs))
        self.font_table = (FONT_FAMILY, int(13 * fs))  # 表格字体
        self.font_combo = (FONT_FAMILY, int(15 * fs))  # 下拉菜单显示字体（与标签一致）
        self.font_combo_list = (FONT_FAMILY, int(15 * fs))  # 下拉菜单列表字体

        # 配置样式
        style.configure('TFrame', background=self.colors['bg_main'])
        style.configure('TLabel', font=self.font_label, foreground=self.colors['text_primary'])
        style.configure('TButton', font=self.font_button, padding=(15, 8))
        style.configure('Accent.TButton', font=('Microsoft YaHei UI Semibold', int(14 * fs)), padding=(25, 10))
        style.configure('Card.TFrame', background=self.colors['bg_card'], relief='solid', borderwidth=1)
        style.configure('Sidebar.TFrame', background=self.colors['bg_sidebar'])
        sidebar_font_size = int(13 * self.dpi_scale * self.zoom_factor)
        style.configure('Sidebar.TLabel', font=('Microsoft YaHei UI', sidebar_font_size),
                       foreground=self.colors['text_sidebar'], background=self.colors['bg_sidebar'])
        style.configure('SidebarSelected.TLabel', font=('Microsoft YaHei UI', sidebar_font_size, 'bold'),
                       foreground=self.colors['text_sidebar_active'], background=self.colors['bg_sidebar'])
        style.configure('Header.TLabel', font=self.font_title, foreground=self.colors['text_primary'])
        style.configure('Section.TLabel', font=self.font_section, foreground=self.colors['text_primary'])
        style.configure('Stat.TLabel', font=self.font_stat, foreground=self.colors['primary'])
        style.configure('StatLabel.TLabel', font=self.font_stat_label, foreground=self.colors['text_secondary'])
        style.configure('Primary.TLabel', font=self.font_label, foreground=self.colors['primary'])
        style.configure('Success.TLabel', font=self.font_label, foreground=self.colors['success'])
        style.configure('Warning.TLabel', font=self.font_label, foreground=self.colors['warning'])
        # 下拉菜单样式 - 设置行高确保文字垂直居中
        combo_font_size = int(15 * self.dpi_scale * self.zoom_factor)
        style.configure('TCombobox', font=self.font_combo)
        style.configure('TCombobox', rowheight=int(combo_font_size * 1.8))
        style.configure('Custom.TLabelframe', font=self.font_label, background=self.colors['bg_card'])
        style.configure('Custom.TLabelframe.Label', font=self.font_label, background=self.colors['bg_card'])

    def create_sidebar(self):
        """创建左侧边栏"""
        sidebar = ttk.Frame(self.root, style='Sidebar.TFrame', width=int(UI_CONFIG['sidebar_width'] * self.dpi_scale * self.zoom_factor))
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        # Logo 区域 - 上下布局，增加间距
        logo_frame = ttk.Frame(sidebar, style='Sidebar.TFrame')
        logo_frame.pack(fill="x", padx=int(20 * self.dpi_scale * self.zoom_factor), pady=(int(30 * self.dpi_scale * self.zoom_factor), int(20 * self.dpi_scale * self.zoom_factor)))

        # 主标题 "BOSS" - 带 clipboard 图标，大字体
        logo_icon = self.icons.logo('document', self.colors['text_sidebar_active'], self.colors['bg_sidebar'])
        logo_label = ttk.Label(logo_frame, image=logo_icon, text=" BOSS", compound=tk.LEFT,
                               font=('Microsoft YaHei UI Semibold', int(32 * self.dpi_scale * self.zoom_factor)),
                               foreground=self.colors['text_sidebar_active'], background=self.colors['bg_sidebar'])
        logo_label._icon_ref = logo_icon
        logo_label.pack(anchor="w")

        # 副标题 "简历筛选器" - 调大字体
        subtitle_label = ttk.Label(logo_frame, text="简历筛选器",
                                   font=('Microsoft YaHei UI', int(16 * self.dpi_scale * self.zoom_factor)),
                                   foreground=self.colors['text_sidebar_subtitle'], background=self.colors['bg_sidebar'])
        subtitle_label.pack(anchor="w", pady=(int(6 * self.dpi_scale * self.zoom_factor), 0))

        # 分隔线
        sep = ttk.Separator(sidebar, orient='horizontal')
        sep.pack(fill="x", padx=0, pady=int(10 * self.dpi_scale * self.zoom_factor))

        # 导航项 - 使用 Frame 容器确保文字对齐（图标固定宽度）
        nav_items = [
            ("home", "首页", self.show_page_home),
            ("gear", "岗位配置", self.show_page_config),
            ("play", "运行控制", self.show_page_run),
            ("chart", "筛选结果", self.show_page_result),
            ("star", "数据统计", self.show_page_stats),
        ]

        self.nav_labels = []
        self.nav_components = []  # 保存所有导航组件引用，用于 hover 效果
        sidebar_nav_font_size = int(16 * self.dpi_scale * self.zoom_factor)

        # 设置导航项样式
        style = ttk.Style()
        style.configure('SidebarNav.TLabel',
                       font=('Microsoft YaHei UI', sidebar_nav_font_size),
                       foreground=self.colors['text_sidebar'],
                       background=self.colors['bg_sidebar'])
        style.configure('SidebarNavSelected.TLabel',
                       font=('Microsoft YaHei UI Semibold', sidebar_nav_font_size),
                       foreground=self.colors['text_sidebar_active'],
                       background=self.colors['bg_sidebar'])

        # emoji 容器内边距（固定宽度，确保文字对齐）
        emoji_padx = int(20 * self.dpi_scale * self.zoom_factor)
        text_padx = int(10 * self.dpi_scale * self.zoom_factor)

        for idx, (icon_name, text, command) in enumerate(nav_items):
            # 生成两个颜色版本的图标
            icon_default = self.icons.nav(icon_name, self.colors['text_sidebar'], self.colors['bg_sidebar'])
            icon_active = self.icons.nav(icon_name, self.colors['text_sidebar_active'], self.colors['bg_sidebar'])

            # 使用 Frame 容器
            nav_frame = ttk.Frame(sidebar, style='Sidebar.TFrame')
            nav_frame.pack(fill="x", padx=0, pady=1)

            # 图标标签
            icon_label = ttk.Label(nav_frame, image=icon_default,
                                   style='SidebarNav.TLabel', cursor="hand2")
            icon_label._icon_default = icon_default
            icon_label._icon_active = icon_active
            icon_label.pack(side="left", padx=(emoji_padx, 0))

            # 文字标签
            text_label = ttk.Label(nav_frame, text=text,
                                  style='SidebarNav.TLabel', cursor="hand2",
                                  padding=(text_padx, int(14 * self.dpi_scale * self.zoom_factor)))
            text_label.pack(side="left", fill="x", expand=True)

            # 绑定点击和 hover 事件 - 所有子组件绑定到同一个 command
            for widget in [nav_frame, icon_label, text_label]:
                widget.bind("<Button-1>", lambda e, c=command: c())
                widget.bind("<Enter>", lambda e, i=idx: self.on_nav_enter(i))
                widget.bind("<Leave>", lambda e, i=idx: self.on_nav_leave(i))

            # 保存所有组件引用，用于 hover 效果
            self.nav_components.append({
                'frame': nav_frame,
                'icon': icon_label,
                'icon_default': icon_default,
                'icon_active': icon_active,
                'text': text_label,
                'command': command,
                'index': idx
            })

            self.nav_labels.append(text_label)

        # 分隔线 - 导航与设置之间
        sep2 = ttk.Separator(sidebar, orient='horizontal')
        sep2.pack(fill="x", padx=0, pady=int(10 * self.dpi_scale * self.zoom_factor))

        # 系统设置（独立导航项）- 使用 Frame 容器保持一致对齐
        settings_idx = len(nav_items)
        settings_frame = ttk.Frame(sidebar, style='Sidebar.TFrame')
        settings_frame.pack(fill="x", padx=0, pady=1)

        settings_icon_default = self.icons.nav('gear', self.colors['text_sidebar'], self.colors['bg_sidebar'])
        settings_icon_active = self.icons.nav('gear', self.colors['text_sidebar_active'], self.colors['bg_sidebar'])
        settings_icon_label = ttk.Label(settings_frame, image=settings_icon_default,
                                  style='SidebarNav.TLabel', cursor="hand2")
        settings_icon_label._icon_default = settings_icon_default
        settings_icon_label._icon_active = settings_icon_active
        settings_icon_label.pack(side="left", padx=(emoji_padx, 0))

        settings_text = ttk.Label(settings_frame, text="系统设置",
                                 style='SidebarNav.TLabel', cursor="hand2",
                                 padding=(text_padx, int(14 * self.dpi_scale * self.zoom_factor)))
        settings_text.pack(side="left", fill="x", expand=True)

        for widget in [settings_frame, settings_icon_label, settings_text]:
            widget.bind("<Button-1>", lambda e: self.show_page_api())
            widget.bind("<Enter>", lambda e, i=settings_idx: self.on_nav_enter(i))
            widget.bind("<Leave>", lambda e, i=settings_idx: self.on_nav_leave(i))

        self.nav_components.append({
            'frame': settings_frame,
            'icon': settings_icon_label,
            'icon_default': settings_icon_default,
            'icon_active': settings_icon_active,
            'text': settings_text,
            'command': self.show_page_api,
            'index': settings_idx
        })
        self.nav_labels.append(settings_text)

        # 底部信息 - 仅版本号 - 调大字体
        bottom_frame = ttk.Frame(sidebar, style='Sidebar.TFrame')
        bottom_frame.pack(side="bottom", fill="x", padx=int(20 * self.dpi_scale * self.zoom_factor), pady=int(20 * self.dpi_scale * self.zoom_factor))

        version_label = ttk.Label(bottom_frame, text=f"v{__version__}",
                                  font=('Microsoft YaHei UI', int(12 * self.dpi_scale * self.zoom_factor)),
                                  foreground=self.colors['text_sidebar_version'], background=self.colors['bg_sidebar'],
                                  cursor="hand2")
        version_label.pack(anchor="w")
        version_label.bind("<Button-1>", lambda e: self.show_changelog())

    def create_main_content(self):
        """创建主内容区域"""
        # 主容器
        main_frame = ttk.Frame(self.root, style='TFrame')
        main_frame.pack(side="left", fill="both", expand=True)

        # 创建页面容器
        self.pages_frame = ttk.Frame(main_frame, style='TFrame')
        self.pages_frame.pack(fill="both", expand=True, padx=int(UI_CONFIG['page_padding_x'] * self.dpi_scale * self.zoom_factor), pady=int(UI_CONFIG['page_padding_y'] * self.dpi_scale * self.zoom_factor))

        # 创建各个页面
        self.create_home_page()
        self.create_config_page()
        self.create_api_config_page()
        self.create_run_page()
        self.create_result_page()
        self.create_stats_page()

        # 默认显示首页（current_page_index 在 show_page_home 中已设置为 0）
        self.show_page_home()

    def create_home_page(self):
        """创建首页"""
        self.home_page = ttk.Frame(self.pages_frame, style='TFrame')

        # 页面标题
        header_frame = ttk.Frame(self.home_page, style='TFrame')
        header_frame.pack(fill="x", pady=(0, int(25 * self.dpi_scale * self.zoom_factor)))

        title_label = ttk.Label(header_frame, text="欢迎使用 BOSS 简历筛选器",
                               font=self.font_title, foreground=self.colors['text_primary'])
        title_label.pack(anchor="w")

        subtitle_label = ttk.Label(header_frame, text="基于 DrissionPage 的智能候选人筛选工具，智能解析、智能匹配、自动滚动、自动打招呼",
                                   font=self.font_subtitle, foreground=self.colors['text_secondary'])
        subtitle_label.pack(anchor="w", pady=(int(15 * self.dpi_scale * self.zoom_factor), 0))

        # 岗位过滤
        home_filter_frame = ttk.Frame(self.home_page, style='TFrame')
        home_filter_frame.pack(fill="x", pady=(int(15 * self.dpi_scale * self.zoom_factor), 0))
        ttk.Label(home_filter_frame, text="岗位过滤:", font=self.font_label,
                 background=self.colors['bg_main']).pack(side="left")
        self.home_job_var = tk.StringVar(value="全部岗位")
        self.home_job_combo = ttk.Combobox(home_filter_frame, textvariable=self.home_job_var,
                                            values=["全部岗位"], width=28, state="readonly",
                                            font=self.font_combo)
        self.home_job_combo.pack(side="left", padx=int(15 * self.dpi_scale * self.zoom_factor))
        self.home_job_combo.bind("<<ComboboxSelected>>", lambda e: self.refresh_home_stats())

        # 统计卡片区
        stats_container = ttk.Frame(self.home_page, style='TFrame')
        stats_container.pack(fill="x", pady=int(30 * self.dpi_scale * self.zoom_factor))

        # 卡片数据
        cards_data = [
            ("people", "累计候选人", "total_home", self.colors['primary']),
            ("star", "强烈推荐", "strong_home", self.colors['purple']),
            ("thumbs_up", "推荐", "recommended_home", self.colors['success']),
            ("chat", "已打招呼", "greeted_home", self.colors['warning']),
        ]

        self.home_stats_vars = {}
        self.home_stats_labels = {}  # 保存标签引用用于绑定事件
        for icon_name, label_text, var_name, color in cards_data:
            card_frame = ttk.Frame(stats_container, style='Card.TFrame')
            card_frame.pack(side="left", fill="x", expand=True, padx=int(15 * self.dpi_scale * self.zoom_factor), pady=int(12 * self.dpi_scale * self.zoom_factor))

            # 图标容器 - 彩色圆形背景
            icon_size = int(UI_CONFIG['stat_icon_size'] * self.dpi_scale * self.zoom_factor)
            icon_canvas = tk.Canvas(card_frame, width=icon_size, height=icon_size,
                                    bg=self.colors['bg_card'], highlightthickness=0)
            icon_canvas.pack(anchor="center",
                            pady=(int(20 * self.dpi_scale * self.zoom_factor), int(8 * self.dpi_scale * self.zoom_factor)))

            # 绘制彩色圆形背景
            margin = int(UI_CONFIG['icon_margin'] * self.dpi_scale * self.zoom_factor)
            icon_canvas.create_oval(margin, margin, icon_size - margin, icon_size - margin,
                                    fill=color, outline='')

            # 在圆形上绘制白色图标（使用 PhotoImage）
            stat_icon = self.icons.stat(icon_name, 'white')
            icon_canvas.create_image(icon_size // 2, icon_size // 2, image=stat_icon)
            icon_canvas._icon_ref = stat_icon

            # 数值
            var = tk.StringVar(value="0")
            self.home_stats_vars[var_name] = var
            value_label = ttk.Label(card_frame, textvariable=var,
                                   font=self.font_stat, foreground=color,
                                   background=self.colors['bg_card'],
                                   cursor="hand2")
            value_label.pack(anchor="center", pady=(0, int(8 * self.dpi_scale * self.zoom_factor)))

            # 绑定点击事件
            self.home_stats_labels[var_name] = (value_label, label_text)
            value_label.bind("<Button-1>", lambda e, vt=var_name: self.show_stat_detail(vt))

            # 标签
            text_label = ttk.Label(card_frame, text=label_text,
                                  font=self.font_stat_label, foreground=self.colors['text_secondary'],
                                  background=self.colors['bg_card'])
            text_label.pack(anchor="center", pady=(0, int(20 * self.dpi_scale * self.zoom_factor)))

        # 快速操作区
        quick_frame = ttk.LabelFrame(self.home_page, text="  快速操作  ", padding=int(UI_CONFIG['card_padding'] * self.dpi_scale * self.zoom_factor), style='Custom.TLabelframe')
        quick_frame.pack(fill="x", pady=int(30 * self.dpi_scale * self.zoom_factor))

        quick_buttons = ttk.Frame(quick_frame, style='TFrame')
        quick_buttons.pack(fill="x")

        icon_play = self.icons.button('play', self.colors['text_primary'])
        btn1 = ttk.Button(quick_buttons, image=icon_play, text=" 开始筛选", compound=tk.LEFT, command=self.show_page_run, style='TButton')
        btn1._icon_ref = icon_play
        btn1.pack(side="left", padx=int(15 * self.dpi_scale * self.zoom_factor))
        icon_chart = self.icons.button('chart', self.colors['text_primary'])
        btn2 = ttk.Button(quick_buttons, image=icon_chart, text=" 查看结果", compound=tk.LEFT, command=self.show_page_result, style='TButton')
        btn2._icon_ref = icon_chart
        btn2.pack(side="left", padx=int(15 * self.dpi_scale * self.zoom_factor))
        icon_gear = self.icons.button('gear', self.colors['text_primary'])
        btn3 = ttk.Button(quick_buttons, image=icon_gear, text=" 配置岗位", compound=tk.LEFT, command=self.show_page_config, style='TButton')
        btn3._icon_ref = icon_gear
        btn3.pack(side="left", padx=int(15 * self.dpi_scale * self.zoom_factor))

    def create_config_page(self):
        """创建岗位配置页面"""
        self.config_page = ttk.Frame(self.pages_frame, style='TFrame')

        # 页面标题
        header_frame = ttk.Frame(self.config_page, style='TFrame')
        header_frame.pack(fill="x", pady=(0, int(25 * self.dpi_scale * self.zoom_factor)))

        title_label = ttk.Label(header_frame, text="岗位配置",
                               font=self.font_section, foreground=self.colors['text_primary'])
        title_label.pack(anchor="w")

        # 配置容器 - 支持垂直滚动（macOS Tk 9.0+ 用 Text，其他用 Canvas）
        scroll_frame = ttk.Frame(self.config_page, style='Card.TFrame')
        scroll_frame.pack(fill="both", expand=True)

        self.config_canvas, self.config_scrollable_frame = self._create_scroll_container(
            scroll_frame, self.colors['bg_main'])

        # 使用 scrollable_frame 作为实际容器
        config_container = self.config_scrollable_frame

        # 岗位选择区域
        select_frame = ttk.Frame(config_container, style='TFrame')
        select_frame.pack(fill="x", padx=int(25 * self.dpi_scale * self.zoom_factor), pady=(int(25 * self.dpi_scale * self.zoom_factor), int(10 * self.dpi_scale * self.zoom_factor)))

        ttk.Label(select_frame, text="选择岗位:", font=self.font_label,
                 background=self.colors['bg_card']).pack(side="left")
        # 按钮靠右
        icon_trash_small = self.icons.button('trash', self.colors['text_primary'])
        btn_del = ttk.Button(select_frame, image=icon_trash_small, text="删除", compound=tk.LEFT, command=self.delete_job)
        btn_del._icon_ref = icon_trash_small
        btn_del.pack(side="right", padx=(int(8 * self.dpi_scale * self.zoom_factor), 0))
        icon_plus_small = self.icons.button('plus', self.colors['text_primary'])
        btn_add = ttk.Button(select_frame, image=icon_plus_small, text="新建", compound=tk.LEFT, command=self.add_job)
        btn_add._icon_ref = icon_plus_small
        btn_add.pack(side="right", padx=int(8 * self.dpi_scale * self.zoom_factor))
        # 下拉框填充剩余空间
        self.config_job_combo = ttk.Combobox(select_frame, values=list(self.job_rules.keys()), width=UI_CONFIG['combobox_width_job'], font=self.font_combo)
        self.config_job_combo.pack(side="left", padx=int(15 * self.dpi_scale * self.zoom_factor))
        self.config_job_combo.bind("<<ComboboxSelected>>", self.on_job_selected)

        # ===== 需求文档解析区域 =====
        parse_frame = ttk.LabelFrame(config_container, text="  需求文档解析（可选）  ", padding=int(UI_CONFIG['label_frame_padding'] * self.dpi_scale * self.zoom_factor), style='Custom.TLabelframe')
        parse_frame.pack(fill="x", padx=int(25 * self.dpi_scale * self.zoom_factor), pady=int(20 * self.dpi_scale * self.zoom_factor))

        # 需求输入框
        req_header = ttk.Frame(parse_frame, style='TFrame')
        req_header.pack(fill="x", pady=(0, int(10 * self.dpi_scale * self.zoom_factor)))
        ttk.Label(req_header, text="粘贴招聘需求文档:", font=self.font_label,
                 background=self.colors['bg_card']).pack(side="left")
        icon_clipboard = self.icons.button('clipboard', self.colors['text_primary'])
        self.requirement_template_btn = ttk.Button(req_header, image=icon_clipboard, text=" 招聘需求示例", compound=tk.LEFT, command=self._insert_requirement_template)
        self.requirement_template_btn._icon_ref = icon_clipboard
        self.requirement_template_btn.pack(side="right")
        self.requirement_template_btn.state(['disabled'])

        # 需求输入框 - 带滚动条（嵌套在容器内避免布局冲突）
        text_container = ttk.Frame(parse_frame, style='TFrame')
        text_container.pack(fill="x", pady=int(10 * self.dpi_scale * self.zoom_factor))

        self.requirement_text = tk.Text(text_container, height=UI_CONFIG['text_height_large'], font=('Microsoft YaHei UI', int(12 * self.dpi_scale * self.zoom_factor)),
                                        bg=self.colors['bg_input'], borderwidth=1, highlightthickness=0)
        self.requirement_text.pack(side="left", fill="both", expand=True)

        req_scroll = ttk.Scrollbar(text_container, orient="vertical", command=self.requirement_text.yview)
        req_scroll.pack(side="right", fill="y")
        self.requirement_text.config(yscrollcommand=req_scroll.set)

        self.bind_text_context_menu(self.requirement_text)

        # 解析按钮
        parse_btn_frame = ttk.Frame(parse_frame, style='TFrame')
        parse_btn_frame.pack(fill="x", pady=int(10 * self.dpi_scale * self.zoom_factor))
        icon_search_parse = self.icons.button('search', self.colors['text_primary'])
        btn_parse = ttk.Button(parse_btn_frame, image=icon_search_parse, text=" 解析需求文档", compound=tk.LEFT, command=self.parse_requirement)
        btn_parse._icon_ref = icon_search_parse
        btn_parse.pack(side="left")

        # 解析结果展示
        self.parse_result_label = ttk.Label(parse_frame, text="", font=('Microsoft YaHei UI', int(11 * self.dpi_scale * self.zoom_factor)),
                                           foreground=self.colors['success'], background=self.colors['bg_card'])
        self.parse_result_label.pack(anchor="w", pady=int(10 * self.dpi_scale * self.zoom_factor))

        # ===== 解析结果详细展示区域 =====
        self.result_detail_frame = ttk.Frame(config_container, style='Card.TFrame')
        # 先隐藏，等 show_page_config 或 on_job_selected 时再显示

        # 基本信息区
        basic_frame = ttk.LabelFrame(self.result_detail_frame, text="  基本信息  ", padding=int(UI_CONFIG['label_frame_padding'] * self.dpi_scale * self.zoom_factor), style='Custom.TLabelframe')
        basic_frame.pack(fill="x", padx=int(25 * self.dpi_scale * self.zoom_factor), pady=int(15 * self.dpi_scale * self.zoom_factor))

        # 岗位名称
        row1 = ttk.Frame(basic_frame, style='TFrame')
        row1.pack(fill="x", pady=int(10 * self.dpi_scale * self.zoom_factor))
        ttk.Label(row1, text="岗位名称:", font=self.font_label, width=UI_CONFIG['entry_width_job'],
                 background=self.colors['bg_card']).pack(side="left")
        self.job_name_var = tk.StringVar()
        self.job_name_entry = ttk.Entry(row1, textvariable=self.job_name_var, width=50, font=self.font_button)
        self.job_name_entry.pack(side="left", padx=int(15 * self.dpi_scale * self.zoom_factor))
        self.bind_entry_context_menu(self.job_name_entry)

        # 学历和经验
        row2 = ttk.Frame(basic_frame, style='TFrame')
        row2.pack(fill="x", pady=int(10 * self.dpi_scale * self.zoom_factor))
        ttk.Label(row2, text="最低学历:", font=self.font_label, width=UI_CONFIG['entry_width_job'],
                 background=self.colors['bg_card']).pack(side="left")
        self.edu_var = tk.StringVar(value="本科")
        edu_combo = ttk.Combobox(row2, textvariable=self.edu_var,
                                 values=["不限", "高中", "中专", "大专", "本科", "硕士", "博士"],
                                 width=UI_CONFIG['combobox_width_edu'], font=self.font_combo)
        edu_combo.pack(side="left", padx=int(15 * self.dpi_scale * self.zoom_factor))
        # 禁用滚轮切换，防止误操作
        edu_combo.bind('<Enter>', lambda e: edu_combo.bind('<MouseWheel>', lambda ev: 'break'))
        edu_combo.bind('<Leave>', lambda e: edu_combo.unbind('<MouseWheel>'))

        ttk.Label(row2, text="最低经验:", font=self.font_label, width=UI_CONFIG['entry_width_label'],
                 background=self.colors['bg_card']).pack(side="left", padx=(int(30 * self.dpi_scale * self.zoom_factor), 0))
        self.min_exp_var = tk.StringVar(value="3")
        min_exp_spin = ttk.Spinbox(row2, from_=UI_CONFIG['spinbox_exp_min'], to=UI_CONFIG['spinbox_exp_max'], textvariable=self.min_exp_var, width=15, font=self.font_button)
        min_exp_spin.pack(side="left", padx=int(15 * self.dpi_scale * self.zoom_factor))
        # 禁用滚轮切换，防止误操作
        min_exp_spin.bind('<Enter>', lambda e: min_exp_spin.bind('<MouseWheel>', lambda ev: 'break'))
        min_exp_spin.bind('<Leave>', lambda e: min_exp_spin.unbind('<MouseWheel>'))
        ttk.Label(row2, text="年", font=self.font_label, background=self.colors['bg_card']).pack(side="left")

        # 最大年龄
        self.max_age_var = tk.StringVar(value="35")
        row_age = ttk.Frame(basic_frame, style='TFrame')
        row_age.pack(fill="x", pady=int(10 * self.dpi_scale * self.zoom_factor))
        ttk.Label(row_age, text="最大年龄:", font=self.font_label, width=UI_CONFIG['entry_width_job'],
                 background=self.colors['bg_card']).pack(side="left")
        max_age_spin = ttk.Spinbox(row_age, from_=0, to=99, textvariable=self.max_age_var, width=15, font=self.font_button)
        max_age_spin.pack(side="left", padx=int(15 * self.dpi_scale * self.zoom_factor))
        max_age_spin.bind('<Enter>', lambda e: max_age_spin.bind('<MouseWheel>', lambda ev: 'break'))
        max_age_spin.bind('<Leave>', lambda e: max_age_spin.unbind('<MouseWheel>'))
        ttk.Label(row_age, text="岁", font=self.font_label, background=self.colors['bg_card']).pack(side="left")
        ttk.Label(row_age, text="  留空表示不限制",
                 font=(FONT_FAMILY, int(10 * self.dpi_scale * self.zoom_factor)),
                 foreground=self.colors['text_secondary'],
                 background=self.colors['bg_card']).pack(side="left", padx=(int(10 * self.dpi_scale * self.zoom_factor), 0))

        # 薪资范围
        self.salary_min_var = tk.StringVar()
        self.salary_max_var = tk.StringVar()
        self.salary_min_var.trace_add('write', self._validate_salary_input)
        self.salary_max_var.trace_add('write', self._validate_salary_input)
        row_salary = ttk.Frame(basic_frame, style='TFrame')
        row_salary.pack(fill="x", pady=int(10 * self.dpi_scale * self.zoom_factor))
        ttk.Label(row_salary, text="薪资范围:", font=self.font_label, width=UI_CONFIG['entry_width_job'],
                 background=self.colors['bg_card']).pack(side="left")
        salary_min_entry = ttk.Entry(row_salary, textvariable=self.salary_min_var, width=8, font=self.font_button)
        salary_min_entry.pack(side="left", padx=int(5 * self.dpi_scale * self.zoom_factor))
        self.bind_entry_context_menu(salary_min_entry)
        self.salary_min_entry = salary_min_entry
        ttk.Label(row_salary, text="K  ~", font=self.font_label,
                 background=self.colors['bg_card']).pack(side="left")
        salary_max_entry = ttk.Entry(row_salary, textvariable=self.salary_max_var, width=8, font=self.font_button)
        salary_max_entry.pack(side="left", padx=int(5 * self.dpi_scale * self.zoom_factor))
        self.bind_entry_context_menu(salary_max_entry)
        self.salary_max_entry = salary_max_entry
        ttk.Label(row_salary, text="K", font=self.font_label,
                 background=self.colors['bg_card']).pack(side="left")
        ttk.Label(row_salary, text="  留空表示不限制薪资",
                 font=(FONT_FAMILY, int(10 * self.dpi_scale * self.zoom_factor)),
                 foreground=self.colors['text_secondary'],
                 background=self.colors['bg_card']).pack(side="left", padx=(int(10 * self.dpi_scale * self.zoom_factor), 0))

        # 工作地点
        row3 = ttk.Frame(basic_frame, style='TFrame')
        row3.pack(fill="x", pady=int(10 * self.dpi_scale * self.zoom_factor))
        ttk.Label(row3, text="工作地点:", font=self.font_label, width=UI_CONFIG['entry_width_job'],
                 background=self.colors['bg_card']).pack(side="left")
        self.work_location_var = tk.StringVar()
        work_location_entry = ttk.Entry(row3, textvariable=self.work_location_var, width=25, font=self.font_button)
        work_location_entry.pack(side="left", padx=int(15 * self.dpi_scale * self.zoom_factor))
        self.bind_entry_context_menu(work_location_entry)
        ttk.Label(row3, text="留空表示不限   多地点用 / 分隔，如：南京/上海",
                 font=(FONT_FAMILY, int(10 * self.dpi_scale * self.zoom_factor)),
                 foreground=self.colors['text_secondary'], background=self.colors['bg_card']).pack(side="left", padx=(int(10 * self.dpi_scale * self.zoom_factor), 0))

        # 技能关键词区域（带权重显示）- 左右分栏布局
        skills_frame = ttk.LabelFrame(self.result_detail_frame, text="  技能关键词（可编辑权重）  ", padding=int(UI_CONFIG['label_frame_padding'] * self.dpi_scale * self.zoom_factor), style='Custom.TLabelframe')
        skills_frame.pack(fill="both", side="top", padx=int(25 * self.dpi_scale * self.zoom_factor), pady=int(15 * self.dpi_scale * self.zoom_factor))

        # 左右分栏容器
        skills_container = ttk.Frame(skills_frame, style='TFrame')
        skills_container.pack(fill="both", expand=True)

        # 左侧：技能列表（可伸缩）
        skills_left = ttk.Frame(skills_container, style='TFrame')
        skills_left.pack(side="left", fill="both", expand=True)

        # 右侧：操作面板（固定宽度，上下布局）
        skills_right = ttk.Frame(skills_container, style='Card.TFrame', width=int(280 * self.dpi_scale * self.zoom_factor))
        skills_right.pack(side="right", fill="y")
        # 不固定高度，让内容自动撑开

        # === 左侧：技能列表 ===
        list_container = ttk.Frame(skills_left, style='Card.TFrame')
        list_container.pack(fill="both", expand=True)

        # 使用 Treeview 显示技能列表
        columns = ("name", "weight", "source")
        tree_font = (FONT_FAMILY, int(13 * self.dpi_scale * self.zoom_factor))

        self.skills_tree = ttk.Treeview(list_container, columns=columns, show="headings", height=UI_CONFIG['treeview_height'])
        self.skills_tree.heading("name", text="技能名称")
        self.skills_tree.heading("weight", text="权重")
        self.skills_tree.heading("source", text="来源")
        # 设置列 - 全部居中
        self.skills_tree.column("name", width=250, anchor='center')
        self.skills_tree.column("weight", width=70, anchor='center')
        self.skills_tree.column("source", width=80, anchor='center')
        # 设置颜色标记（带字体）- 覆盖所有情况
        self.skills_tree.tag_configure('high_weight', font=tree_font, background=self.colors['bg_tree_tag_high'])
        self.skills_tree.tag_configure('mid_weight', font=tree_font, background=self.colors['bg_tree_tag_mid'])
        self.skills_tree.tag_configure('low_weight', font=tree_font, background=self.colors['bg_tree_tag_low'])

        # 设置 Treeview 默认字体和行高
        _style = ttk.Style()
        _style.configure('Treeview', font=tree_font, rowheight=int(30 * self.dpi_scale * self.zoom_factor))
        _style.configure('Treeview.Heading', font=(FONT_FAMILY, int(14 * self.dpi_scale * self.zoom_factor), 'bold'))

        skills_scroll = ttk.Scrollbar(list_container, orient="vertical", command=self.skills_tree.yview)
        self.skills_tree.configure(yscrollcommand=skills_scroll.set)
        self.skills_tree.pack(side="left", fill="both", expand=True)
        skills_scroll.pack(side="right", fill="y")

        # 选中技能编辑区
        edit_card = ttk.LabelFrame(skills_right, text="  编辑选中技能  ", padding=int(12 * self.dpi_scale * self.zoom_factor), style='Custom.TLabelframe')
        edit_card.pack(fill="x", padx=int(10 * self.dpi_scale * self.zoom_factor), pady=(int(10 * self.dpi_scale * self.zoom_factor), int(15 * self.dpi_scale * self.zoom_factor)))

        # 选中技能名称
        ttk.Label(edit_card, text="当前选中:", font=self.font_label,
                 background=self.colors['bg_card']).pack(anchor="w", pady=(0, int(5 * self.dpi_scale * self.zoom_factor)))
        self.selected_skill_var = tk.StringVar(value="未选择")
        self.selected_skill_label = ttk.Label(edit_card, textvariable=self.selected_skill_var,
                                              font=('Microsoft YaHei UI Semibold', int(15 * self.dpi_scale * self.zoom_factor)),
                                              foreground=self.colors['primary'], background=self.colors['bg_card'],
                                              wraplength=int(240 * self.dpi_scale * self.zoom_factor), justify='left')
        self.selected_skill_label.pack(fill="x", pady=(0, int(10 * self.dpi_scale * self.zoom_factor)))

        # 权重输入框（标签和输入框同一行）
        weight_row = ttk.Frame(edit_card, style='TFrame')
        weight_row.pack(fill="x", pady=(0, int(10 * self.dpi_scale * self.zoom_factor)))
        ttk.Label(weight_row, text="权重 (1-3):", font=self.font_label,
                 background=self.colors['bg_card'], width=UI_CONFIG['entry_width_label']).pack(side="left")
        self.new_skill_weight_var = tk.StringVar(value="2")
        weight_entry = ttk.Entry(weight_row, textvariable=self.new_skill_weight_var,
                                font=self.font_button, width=5, justify='center')
        weight_entry.pack(side="left")
        self.bind_entry_context_menu(weight_entry)

        # 操作按钮
        icon_pencil_skill = self.icons.button('pencil', self.colors['text_primary'])
        btn_update = ttk.Button(edit_card, image=icon_pencil_skill, text=" 更新权重", compound=tk.LEFT, command=self.update_skill_weight)
        btn_update._icon_ref = icon_pencil_skill
        btn_update.pack(fill="x", pady=(0, int(5 * self.dpi_scale * self.zoom_factor)))
        icon_trash_skill = self.icons.button('trash', self.colors['text_primary'])
        btn_del_skill = ttk.Button(edit_card, image=icon_trash_skill, text=" 删除技能", compound=tk.LEFT, command=self.delete_skill)
        btn_del_skill._icon_ref = icon_trash_skill
        btn_del_skill.pack(fill="x")

        # 添加新技能区
        add_card = ttk.LabelFrame(skills_right, text="  添加新技能  ", padding=int(12 * self.dpi_scale * self.zoom_factor), style='Custom.TLabelframe')
        add_card.pack(fill="x", padx=int(10 * self.dpi_scale * self.zoom_factor), pady=int(10 * self.dpi_scale * self.zoom_factor))

        ttk.Label(add_card, text="技能名称:", font=self.font_label,
                 background=self.colors['bg_card']).pack(anchor="w", pady=(0, int(5 * self.dpi_scale * self.zoom_factor)))
        self.new_skill_var = tk.StringVar()
        skill_entry = ttk.Entry(add_card, textvariable=self.new_skill_var, font=self.font_button)
        skill_entry.pack(fill="x", pady=(0, int(8 * self.dpi_scale * self.zoom_factor)))
        self.bind_entry_context_menu(skill_entry)

        # 权重输入框（标签和输入框同一行）
        weight_row = ttk.Frame(add_card, style='TFrame')
        weight_row.pack(fill="x", pady=(0, int(8 * self.dpi_scale * self.zoom_factor)))
        ttk.Label(weight_row, text="权重 (1-3):", font=self.font_label,
                 background=self.colors['bg_card'], width=UI_CONFIG['entry_width_label']).pack(side="left")
        self.new_skill_add_weight_var = tk.StringVar(value="2")
        add_weight_entry = ttk.Entry(weight_row, textvariable=self.new_skill_add_weight_var,
                                    font=self.font_button, width=5, justify='center')
        add_weight_entry.pack(side="left")
        self.bind_entry_context_menu(add_weight_entry)

        icon_plus_add = self.icons.button('plus', self.colors['text_primary'])
        btn_add_skill = ttk.Button(add_card, image=icon_plus_add, text=" 添加技能", compound=tk.LEFT, command=self.add_skill)
        btn_add_skill._icon_ref = icon_plus_add
        btn_add_skill.pack(fill="x", pady=(int(8 * self.dpi_scale * self.zoom_factor), 0))

        # 绑定选中事件
        self.skills_tree.bind("<<TreeviewSelect>>", self.on_skill_selected)

        # 必要条件区域
        required_frame = ttk.LabelFrame(self.result_detail_frame, text="  必要条件（硬性约束）  ", padding=int(UI_CONFIG['label_frame_padding'] * self.dpi_scale * self.zoom_factor), style='Custom.TLabelframe')
        required_frame.pack(fill="x", padx=int(25 * self.dpi_scale * self.zoom_factor), pady=int(15 * self.dpi_scale * self.zoom_factor))

        # 必要条件列表显示
        self.required_listbox = tk.Listbox(required_frame, height=UI_CONFIG['listbox_height'],
                                          font=self.font_button,
                                          borderwidth=1, highlightthickness=0)
        self.required_listbox.pack(fill="x", pady=int(10 * self.dpi_scale * self.zoom_factor))

        # 必要条件编辑 - 条件类型选择 + 关键词（逗号分隔）
        required_edit_frame = ttk.Frame(required_frame, style='TFrame')
        required_edit_frame.pack(fill="x")
        ttk.Label(required_edit_frame, text="类型:", font=self.font_label,
                 background=self.colors['bg_card']).pack(side="left")
        self.required_cond_type_var = tk.StringVar(value="简单匹配")
        cond_type_combo = ttk.Combobox(required_edit_frame, textvariable=self.required_cond_type_var,
                                        values=["简单匹配", "OR（满足任一）", "AND（全部满足）"],
                                        width=12, state="readonly", font=self.font_combo)
        cond_type_combo.pack(side="left", padx=int(3 * self.dpi_scale * self.zoom_factor))
        ttk.Label(required_edit_frame, text="关键词:", font=self.font_label,
                 background=self.colors['bg_card']).pack(side="left", padx=(int(5 * self.dpi_scale * self.zoom_factor), 0))
        self.new_required_var = tk.StringVar()
        required_edit = ttk.Entry(required_edit_frame, textvariable=self.new_required_var, font=self.font_button)
        required_edit.pack(side="left", padx=int(5 * self.dpi_scale * self.zoom_factor), fill="x", expand=True)
        self.bind_entry_context_menu(required_edit)
        ttk.Button(required_edit_frame, text="添加", command=self.add_required_condition).pack(side="left", padx=(int(8 * self.dpi_scale * self.zoom_factor), int(3 * self.dpi_scale * self.zoom_factor)))
        ttk.Button(required_edit_frame, text="删除选中", command=self.delete_required_condition).pack(side="left", padx=(int(3 * self.dpi_scale * self.zoom_factor), 0))

        # ===== 打招呼话术模板 =====
        greet_template_frame = ttk.LabelFrame(self.result_detail_frame, text="  打招呼话术模板（可选）  ", padding=int(UI_CONFIG['label_frame_padding'] * self.dpi_scale * self.zoom_factor), style='Custom.TLabelframe')
        greet_template_frame.pack(fill="x", padx=int(25 * self.dpi_scale * self.zoom_factor), pady=int(15 * self.dpi_scale * self.zoom_factor))

        ttk.Label(greet_template_frame, text="为当前岗位设置打招呼话术（支持变量：{name} 姓名）:",
                 font=self.font_label, background=self.colors['bg_card']).pack(anchor="w", pady=(0, int(10 * self.dpi_scale * self.zoom_factor)))

        # 话术输入框 - 带滚动条（嵌套在容器内避免布局冲突）
        greet_text_container = ttk.Frame(greet_template_frame, style='TFrame')
        greet_text_container.pack(fill="x", pady=int(10 * self.dpi_scale * self.zoom_factor))

        self.greet_template_text = tk.Text(greet_text_container, height=UI_CONFIG['text_height_small'], font=(FONT_FAMILY, int(12 * self.dpi_scale * self.zoom_factor)),
                                          bg=self.colors['bg_input'], borderwidth=1, highlightthickness=0)
        self.greet_template_text.pack(side="left", fill="both", expand=True)

        greet_scroll = ttk.Scrollbar(greet_text_container, orient="vertical", command=self.greet_template_text.yview)
        greet_scroll.pack(side="right", fill="y")
        self.greet_template_text.config(yscrollcommand=greet_scroll.set)

        self.bind_text_context_menu(self.greet_template_text)

        # 话术提示
        ttk.Label(greet_template_frame, text="提示：{name} = 候选人姓名，{job} = 岗位名称",
                 font=(FONT_FAMILY, int(10 * self.dpi_scale * self.zoom_factor)),
                 foreground=self.colors['text_secondary'], background=self.colors['bg_card']).pack(anchor="w")

        # 按钮行（居中布局，固定在页面底部，不随 Canvas 滚动）
        self.btn_frame = ttk.Frame(self.config_page, style='TFrame')
        btn_inner = ttk.Frame(self.btn_frame, style='TFrame')
        btn_inner.pack(anchor="center")

        icon_save_cfg = self.icons.button('save', self.colors['text_primary'])
        btn_save = ttk.Button(btn_inner, image=icon_save_cfg, text=" 保存配置", compound=tk.LEFT, command=self.save_current_job)
        btn_save._icon_ref = icon_save_cfg
        btn_save.pack(side="left", padx=int(5 * self.dpi_scale * self.zoom_factor))
        icon_refresh_cfg = self.icons.button('refresh', self.colors['text_primary'])
        btn_reset = ttk.Button(btn_inner, image=icon_refresh_cfg, text=" 重置", compound=tk.LEFT, command=self.reset_job_form)
        btn_reset._icon_ref = icon_refresh_cfg
        btn_reset.pack(side="left", padx=int(5 * self.dpi_scale * self.zoom_factor))
        icon_import_cfg = self.icons.button('import', self.colors['text_primary'])
        btn_import = ttk.Button(btn_inner, image=icon_import_cfg, text=" 导入配置", compound=tk.LEFT, command=self.import_config)
        btn_import._icon_ref = icon_import_cfg
        btn_import.pack(side="left", padx=int(5 * self.dpi_scale * self.zoom_factor))
        icon_export_cfg = self.icons.button('export', self.colors['text_primary'])
        btn_export = ttk.Button(btn_inner, image=icon_export_cfg, text=" 导出配置", compound=tk.LEFT, command=self.export_config)
        btn_export._icon_ref = icon_export_cfg
        btn_export.pack(side="left", padx=int(5 * self.dpi_scale * self.zoom_factor))

        # 存储技能数据的列表（带权重）
        self.skills_data = []  # [{"name": "Java", "weight": 2, "source": "解析"}, ...]
        self.required_conditions_data = []  # ["统招本科", ...]
        self.greet_template = ""  # 打招呼话术模板

        # 设置下拉框的值
        self.config_job_combo['values'] = list(self.job_rules.keys())

        # 如果有已存在的岗位，自动加载第一个并显示详细结果区域
        if self.job_rules:
            first_job = list(self.job_rules.keys())[0]
            self.config_job_combo.set(first_job)
            rule = self.job_rules[first_job]
            self.load_job_to_form(rule)
            # 注意：这里不 pack result_detail_frame，因为 config_page 还没有被显示
            # 将在 show_page_config 中 pack

        # 底部按钮固定在页面底部，不随 Canvas 滚动
        self.btn_frame.pack(fill="x", side="bottom", pady=(int(10 * self.dpi_scale * self.zoom_factor), int(10 * self.dpi_scale * self.zoom_factor)))

        # 在所有控件创建完毕后绑定滚轮事件
        self._bind_mousewheel(self.config_canvas, self.config_scrollable_frame)

    def create_api_config_page(self):
        """创建 API 配置页面"""
        # 创建带滚动条的页面
        self.api_config_page = ttk.Frame(self.pages_frame, style='TFrame')

        # 创建可滚动容器（macOS Tk 9.0+ 用 Text，其他用 Canvas）
        self.api_canvas, self.api_scrollable_frame = self._create_scroll_container(
            self.api_config_page, self.colors['bg_main'])

        # 在可滚动框架中创建内容
        self._create_api_config_content()

    def _on_api_canvas_configure(self, event):
        """调整可滚动框架宽度以匹配 Canvas"""
        self.api_canvas.itemconfig(self.api_canvas_frame, width=event.width)

    @staticmethod
    def _delta_to_units(delta):
        """将鼠标滚轮 delta 转换为滚动单位数。

        Windows 鼠标滚轮每格 delta=±120；macOS 触控板 delta 通常为 ±1。
        直接除以 120 取整在 macOS 上恒为 0，故按平台分别处理。
        """
        if sys.platform == 'darwin':
            return -1 if delta > 0 else 1
        return int(-1 * (delta / 120))

    @staticmethod
    def _create_scroll_container(parent, bg_color):
        """创建可滚动容器，返回 (canvas, container_frame)。

        所有平台统一使用 Canvas + create_window。
        macOS Tk 9.0+ 触控板滚动通过 _setup_cocoa_scroll_hook() 在 ObjC 层拦截。
        """
        canvas = tk.Canvas(parent, bg=bg_color, highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        container = ttk.Frame(canvas)

        container.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas_window = canvas.create_window((0, 0), window=container, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Canvas 宽度变化 → 同步嵌入 Frame 宽度
        def _on_canvas_configure(event):
            canvas.itemconfig(canvas_window, width=event.width)
        canvas.bind("<Configure>", _on_canvas_configure)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        return canvas, container

    @staticmethod
    def _bind_mousewheel(canvas, parent_frame):
        """在 Canvas 及其所有子控件上绑定滚轮事件（instance binding 优先级最高）。

        macOS 上 ttk 控件的 class binding 会先消费 <MouseWheel> 事件，
        bind_all 优先级最低无法拦截。必须在每个控件上用 bind() 绑定 instance handler，
        返回 'break' 阻止后续 class binding。

        macOS 触控板可能生成 <MouseWheel>（delta=±1）或 <Button-4>/<Button-5> 事件，
        需要同时绑定三种事件类型。
        """
        def _on_wheel(event):
            """处理滚轮/触控板滚动事件"""
            # 优先使用 delta（MouseWheel 事件）
            if hasattr(event, 'delta') and event.delta != 0:
                units = BossFilterGUI._delta_to_units(event.delta)
            # 回退到 num（Button-4/5 事件，macOS X11 兼容模式）
            elif hasattr(event, 'num'):
                if event.num == 4:
                    units = -1
                elif event.num == 5:
                    units = 1
                else:
                    return
            else:
                return
            if units != 0:
                canvas.yview_scroll(units, "units")
            return 'break'

        # 跳过自带滚轮的控件类型
        _skip_types = (ttk.Spinbox, ttk.Combobox, ttk.Scrollbar, tk.Text, tk.Entry, tk.Listbox)

        def _bind_recursive(widget):
            if isinstance(widget, _skip_types):
                return
            # Treeview 也跳过
            if hasattr(widget, 'identify_region'):
                return
            widget.bind("<MouseWheel>", _on_wheel)
            # macOS/Linux 触控板可能生成 Button-4/5 事件
            if sys.platform != 'win32':
                widget.bind("<Button-4>", _on_wheel)
                widget.bind("<Button-5>", _on_wheel)
            for child in widget.winfo_children():
                _bind_recursive(child)

        # Canvas 自身
        canvas.bind("<MouseWheel>", _on_wheel)
        if sys.platform != 'win32':
            canvas.bind("<Button-4>", _on_wheel)
            canvas.bind("<Button-5>", _on_wheel)
        # 递归绑定所有子控件
        _bind_recursive(parent_frame)

    # ── macOS Tk 9.0+ Cocoa 触控板滚动 hook ──────────────────────────────
    # Tk 9.0 的 Cocoa 后端在 NSView.scrollWheel: 中消费触控板事件，
    # 不向 Canvas 等非原生滚动控件生成 Tk MouseWheel 事件。
    # 通过 ObjC Runtime swizzle 拦截 scrollWheel:，直接滚动当前页面的 Canvas。

    _cocoa_hook_installed = False
    _cocoa_refs = {}            # 防止 ObjC 对象/回调被 GC

    def _setup_cocoa_scroll_hook(self):
        """设置 Cocoa scrollWheel: 拦截（仅 macOS Tk 9.0+）。

        通过 ObjC Runtime swizzle NSView.scrollWheel:，
        对非 NSScrollView 子视图直接调用当前页面 Canvas 的 yview_scroll。
        如果设置失败（ctypes/libobjc 不可用），静默降级（触控板不可滚动）。
        """
        if BossFilterGUI._cocoa_hook_installed:
            return
        try:
            import ctypes
            import ctypes.util

            objc_path = ctypes.util.find_library('objc')
            if not objc_path:
                return
            objc = ctypes.cdll.LoadLibrary(objc_path)

            # ── ObjC Runtime 函数签名 ──
            objc.sel_registerName.restype = ctypes.c_void_p
            objc.sel_registerName.argtypes = [ctypes.c_char_p]
            objc.objc_getClass.restype = ctypes.c_void_p
            objc.objc_getClass.argtypes = [ctypes.c_char_p]
            objc.class_getInstanceMethod.restype = ctypes.c_void_p
            objc.class_getInstanceMethod.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
            objc.method_getImplementation.restype = ctypes.c_void_p
            objc.method_getImplementation.argtypes = [ctypes.c_void_p]
            objc.method_setImplementation.restype = ctypes.c_void_p
            objc.method_setImplementation.argtypes = [ctypes.c_void_p, ctypes.c_void_p]

            # objc_msgSend 用于方法调用
            objc.objc_msgSend.restype = ctypes.c_void_p
            objc.objc_msgSend.argtypes = [
                ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]

            sel_scroll = objc.sel_registerName(b'scrollWheel:')
            sel_shared = objc.sel_registerName(b'sharedApplication')
            sel_keywin = objc.sel_registerName(b'keyWindow')
            sel_cv = objc.sel_registerName(b'contentView')
            sel_super = objc.sel_registerName(b'superview')
            sel_is_kind = objc.sel_registerName(b'isKindOfClass:')
            sel_delta_y = objc.sel_registerName(b'scrollingDeltaY')

            cls_nsapp = objc.objc_getClass(b'NSApplication')
            cls_nsview = objc.objc_getClass(b'NSView')
            cls_nssv = objc.objc_getClass(b'NSScrollView')

            if not all([cls_nsapp, cls_nsview, cls_nssv]):
                return

            # ── 获取 NSApplication.sharedApplication.keyWindow.contentView ──
            app = objc.objc_msgSend(cls_nsapp, sel_shared, None)
            if not app:
                self.root.after(1000, self._setup_cocoa_scroll_hook)
                return
            kw = objc.objc_msgSend(app, sel_keywin, None)
            if not kw:
                self.root.after(1000, self._setup_cocoa_scroll_hook)
                return
            content_view = objc.objc_msgSend(kw, sel_cv, None)
            if not content_view:
                self.root.after(1000, self._setup_cocoa_scroll_hook)
                return

            # ── scrollingDeltaY 调用函数（处理 x86_64 fpret vs ARM64） ──
            try:
                objc.objc_msgSend_fpret.restype = ctypes.c_double
                objc.objc_msgSend_fpret.argtypes = [
                    ctypes.c_void_p, ctypes.c_void_p]
                _msg_send_double = objc.objc_msgSend_fpret
            except AttributeError:
                # ARM64 没有 fpret，创建独立的 CFUNCTYPE 避免修改 objc_msgSend 签名
                _msg_send_double = ctypes.CFUNCTYPE(
                    ctypes.c_double, ctypes.c_void_p, ctypes.c_void_p
                )(objc.objc_msgSend)

            # ── isKindOfClass: 调用函数（3 个 c_void_p 参数） ──
            _msg_send_is_kind = ctypes.CFUNCTYPE(
                ctypes.c_bool,
                ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p
            )(objc.objc_msgSend)

            # ── 保存引用，防止被 GC ──
            BossFilterGUI._cocoa_refs['app'] = app
            BossFilterGUI._cocoa_refs['content_view'] = content_view

            # ── scrollWheel: 替代实现 ──
            # C 签名: void scrollWheel:(id self, SEL _cmd, id event)
            SCROLL_CB = ctypes.CFUNCTYPE(
                None, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)

            def _cocoa_scroll_impl(view, _cmd, event):
                """swizzle 后的 scrollWheel: 实现。

                对 NSScrollView 内部视图（Text/Treeview/Listbox）跳过，
                让 Cocoa 原生滚动处理。对其他视图直接滚动当前页面的 Canvas。
                """
                try:
                    # 检查 view 是否在 NSScrollView 内部
                    # （Text/Treeview/Listbox 的 Cocoa 实现是 NSScrollView）
                    v = view
                    for _ in range(10):  # 最多向上 10 层
                        sv = objc.objc_msgSend(v, sel_super, None)
                        if not sv:
                            break
                        if _msg_send_is_kind(sv, sel_is_kind, cls_nssv):
                            return  # 在 NSScrollView 内部 → 让原生滚动处理
                        v = sv

                    # 获取 deltaY（浮点数）
                    delta_y = _msg_send_double(event, sel_delta_y)
                    if delta_y == 0:
                        return

                    # Cocoa deltaY > 0 = 向上 → units = -1（内容上移）
                    # Cocoa deltaY < 0 = 向下 → units = 1（内容下移）
                    units = -1 if delta_y > 0 else 1

                    # 直接滚动当前页面的 Canvas
                    page_canvas = {
                        1: getattr(self, 'config_canvas', None),
                        2: getattr(self, 'run_canvas', None),
                        5: getattr(self, 'api_canvas', None),
                    }.get(getattr(self, 'current_page_index', -1))

                    if page_canvas:
                        page_canvas.yview_scroll(units, "units")

                except Exception:
                    pass

            # ── Swizzle NSView.scrollWheel: ──
            scroll_callback = SCROLL_CB(_cocoa_scroll_impl)
            cb_ptr = ctypes.cast(scroll_callback, ctypes.c_void_p).value

            method = objc.class_getInstanceMethod(cls_nsview, sel_scroll)
            if not method:
                return

            # 保存原始实现（用于 fallback）并替换
            orig_impl = objc.method_getImplementation(method)
            objc.method_setImplementation(method, cb_ptr)

            # 防止回调和 ObjC 引用被 GC
            BossFilterGUI._cocoa_refs['callback'] = scroll_callback
            BossFilterGUI._cocoa_refs['orig_impl'] = orig_impl

            BossFilterGUI._cocoa_hook_installed = True
            print("[Cocoa] scrollWheel: hook installed (Tk 9.0 touchpad fix)")

        except Exception as e:
            print(f"[Cocoa] scrollWheel: hook failed: {e}")

    def _on_mousewheel(self, event):
        """统一处理滚轮事件 - 根据当前页面分发到对应的 Canvas

        使用 bind_all（最高优先级），从事件源控件向上遍历找到所属 Canvas，
        避免 macOS 上 ttk class binding 消费事件的问题。
        """
        widget = event.widget

        # 让自带滚轮处理的控件自行处理
        if isinstance(widget, (tk.Text, tk.Entry, tk.Listbox, ttk.Scrollbar, ttk.Combobox, ttk.Spinbox)):
            return
        # Treeview 也需要跳过（自带垂直滚动）
        if hasattr(widget, 'identify_region'):
            return

        # 计算滚动量
        if hasattr(event, 'delta') and event.delta != 0:
            units = self._delta_to_units(event.delta)
        elif hasattr(event, 'num'):
            if event.num == 4:
                units = -1
            elif event.num == 5:
                units = 1
            else:
                return
        else:
            return

        if units == 0:
            return

        # 检查事件源是否直接就是目标 Canvas
        target_canvas = None
        if hasattr(self, 'config_canvas') and widget is self.config_canvas:
            target_canvas = self.config_canvas
        elif hasattr(self, 'api_canvas') and widget is self.api_canvas:
            target_canvas = self.api_canvas
        elif hasattr(self, 'run_canvas') and widget is self.run_canvas:
            target_canvas = self.run_canvas
        else:
            # 从事件源控件向上遍历，找到所属的可滚动 Canvas
            try:
                w = widget
                while w is not None:
                    parent = w.master
                    if parent is self.config_canvas:
                        target_canvas = self.config_canvas
                        break
                    elif parent is self.api_canvas:
                        target_canvas = self.api_canvas
                        break
                    elif parent is self.run_canvas:
                        target_canvas = self.run_canvas
                        break
                    w = parent
            except Exception:
                return

        if target_canvas is None:
            return

        target_canvas.yview_scroll(units, "units")
        return 'break'

    def _on_rounds_mousewheel(self, event):
        """滚动轮次 Spinbox 的鼠标滚轮处理"""
        step = 10 if event.delta > 0 else -10
        try:
            current = int(self.rounds_var.get())
        except ValueError:
            current = 100
        new_val = current + step
        new_val = max(UI_CONFIG['spinbox_rounds_min'],
                      min(UI_CONFIG['spinbox_rounds_max'], new_val))
        self.rounds_var.set(str(new_val))

    def _create_api_config_content(self):
        """创建 API 配置页面内容（在可滚动框架中）"""
        api_container = self.api_scrollable_frame

        # API 配置页面标题
        api_header_frame = ttk.Frame(api_container, style='TFrame')
        api_header_frame.pack(fill="x", pady=(0, int(25 * self.dpi_scale * self.zoom_factor)))

        api_title_label = ttk.Label(api_header_frame, text="AI 模型 API 配置",
                                   font=self.font_section, foreground=self.colors['text_primary'])
        api_title_label.pack(anchor="w")

        api_subtitle_label = ttk.Label(api_header_frame, text="配置大模型 API 用于智能解析招聘需求文档",
                                      font=self.font_subtitle, foreground=self.colors['text_secondary'])
        api_subtitle_label.pack(anchor="w", pady=(int(10 * self.dpi_scale * self.zoom_factor), 0))

        # 新电脑提示：检测到已保存配置但 API Key 丢失
        self.reconfig_card = None
        if hasattr(self, 'api_config') and self.api_config.get("needs_reconfigure"):
            self.reconfig_card = ttk.LabelFrame(api_container, text="  ⚠️  提示  ", padding=int(UI_CONFIG['label_frame_padding'] * self.dpi_scale * self.zoom_factor), style='Custom.TLabelframe')
            self.reconfig_card.pack(fill="x", padx=int(25 * self.dpi_scale * self.zoom_factor), pady=int(15 * self.dpi_scale * self.zoom_factor))
            ttk.Label(self.reconfig_card, text="检测到已保存的模型配置，但 API Key 未配置（可能是新电脑）",
                     font=self.font_label, foreground=self.colors['warning'],
                     background=self.colors['bg_card']).pack(anchor="w")
            ttk.Label(self.reconfig_card, text="请在下方重新输入 API Key 并点击「保存并添加到列表」",
                     font=self.font_label, foreground=self.colors['text_secondary'],
                     background=self.colors['bg_card']).pack(anchor="w", pady=(5, 0))

        # API 配置卡片
        config_card = ttk.LabelFrame(api_container, text="  API 配置  ", padding=int(UI_CONFIG['label_frame_padding'] * self.dpi_scale * self.zoom_factor), style='Custom.TLabelframe')
        config_card.pack(fill="both", expand=True, padx=int(25 * self.dpi_scale * self.zoom_factor), pady=int(20 * self.dpi_scale * self.zoom_factor))

        # 1. 当前使用模型显示
        current_model_frame = ttk.Frame(config_card, style='TFrame')
        current_model_frame.pack(fill="x", padx=int(25 * self.dpi_scale * self.zoom_factor), pady=int(15 * self.dpi_scale * self.zoom_factor))

        ttk.Label(current_model_frame, text="当前使用模型:", font=self.font_label,
                 background=self.colors['bg_card']).pack(side="left")

        self.current_model_label = ttk.Label(current_model_frame, text="未配置",
                                             font=(FONT_FAMILY, int(14 * self.dpi_scale * self.zoom_factor), 'bold'),
                                             foreground=self.colors['primary'],
                                             background=self.colors['bg_card'])
        self.current_model_label.pack(side="left", padx=(int(10 * self.dpi_scale * self.zoom_factor), 0))

        # 2. API 配置输入区（服务商、Key、URL、模型名称）
        input_frame = ttk.Frame(config_card, style='TFrame')
        input_frame.pack(fill="x", padx=int(25 * self.dpi_scale * self.zoom_factor), pady=int(15 * self.dpi_scale * self.zoom_factor))

        # 第一行：服务商
        row1 = ttk.Frame(input_frame, style='TFrame')
        row1.pack(fill="x")

        ttk.Label(row1, text="服务商:", font=self.font_label, width=UI_CONFIG['label_width_provider']).pack(side="left")
        self.api_provider_var = tk.StringVar(value="qwen")
        self.api_provider_combo = ttk.Combobox(row1, textvariable=self.api_provider_var,
                                               values=["qwen", "deepseek", "kimi", "zhipu", "minimax", "xiaomi", "stepfun", "openai", "anthropic", "custom"],
                                               width=15, font=self.font_combo)
        self.api_provider_combo.pack(side="left", padx=(int(5 * self.dpi_scale * self.zoom_factor), int(20 * self.dpi_scale * self.zoom_factor)))
        self.api_provider_combo.bind("<<ComboboxSelected>>", self.on_api_provider_changed)

        # 第二行：模型名称
        row2 = ttk.Frame(input_frame, style='TFrame')
        row2.pack(fill="x", pady=(int(10 * self.dpi_scale * self.zoom_factor), 0))

        ttk.Label(row2, text="模型名称:", font=self.font_label, width=UI_CONFIG['label_width_model']).pack(side="left")
        self.api_model_var = tk.StringVar()
        model_entry = ttk.Entry(row2, textvariable=self.api_model_var, width=30, font=self.font_combo)
        model_entry.pack(side="left", padx=(int(5 * self.dpi_scale * self.zoom_factor), int(10 * self.dpi_scale * self.zoom_factor)))
        self.bind_entry_context_menu(model_entry)

        # 获取模型列表按钮
        icon_download_models = self.icons.button('download', self.colors['text_primary'])
        btn_fetch = ttk.Button(row2, image=icon_download_models, text=" 获取模型列表", compound=tk.LEFT, command=self.fetch_model_list)
        btn_fetch._icon_ref = icon_download_models
        btn_fetch.pack(side="left")

        # 第三行：API Key
        row3 = ttk.Frame(input_frame, style='TFrame')
        row3.pack(fill="x", pady=(int(10 * self.dpi_scale * self.zoom_factor), 0))

        ttk.Label(row3, text="API Key:", font=self.font_label, width=UI_CONFIG['label_width_api_key']).pack(side="left")
        self.api_key_var = tk.StringVar()
        self.api_key_entry = ttk.Entry(row3, textvariable=self.api_key_var, width=55, font=self.font_button, show="*")
        self.api_key_entry.pack(side="left", padx=(int(5 * self.dpi_scale * self.zoom_factor), 0))
        self.bind_entry_context_menu(self.api_key_entry)

        # 明文/密文切换按钮（无边框 Button 实现，使用图标）
        self.api_key_show_var = tk.BooleanVar(value=False)
        eye_icon = self.icons.button('eye', self.colors['text_primary'])
        eye_off_icon = self.icons.button('eye_off', self.colors['text_primary'])
        self.api_key_toggle_btn = tk.Button(row3, image=eye_icon,
            relief="flat", bd=0, highlightthickness=0, cursor="hand2",
            command=self.toggle_api_key_visibility)
        self.api_key_toggle_btn._icon_eye = eye_icon
        self.api_key_toggle_btn._icon_eye_off = eye_off_icon
        self.api_key_toggle_btn.pack(side="left", padx=(int(5 * self.dpi_scale * self.zoom_factor), 0))

        # 第四行：Base URL
        row4 = ttk.Frame(input_frame, style='TFrame')
        row4.pack(fill="x", pady=(int(10 * self.dpi_scale * self.zoom_factor), 0))

        ttk.Label(row4, text="Base URL:", font=self.font_label, width=UI_CONFIG['label_width_url']).pack(side="left")
        self.api_base_url_var = tk.StringVar()
        url_entry = ttk.Entry(row4, textvariable=self.api_base_url_var, width=55, font=self.font_button)
        url_entry.pack(side="left", padx=(int(5 * self.dpi_scale * self.zoom_factor), 0))
        self.bind_entry_context_menu(url_entry)

        # 操作按钮行
        button_row = ttk.Frame(config_card, style='TFrame')
        button_row.pack(fill="x", padx=int(25 * self.dpi_scale * self.zoom_factor), pady=int(15 * self.dpi_scale * self.zoom_factor))

        icon_save_api = self.icons.button('save', self.colors['text_primary'])
        btn_save_api = ttk.Button(button_row, image=icon_save_api, text=" 保存并添加到列表", compound=tk.LEFT, command=self.save_api_config)
        btn_save_api._icon_ref = icon_save_api
        btn_save_api.pack(side="left", padx=(int(10 * self.dpi_scale * self.zoom_factor), int(5 * self.dpi_scale * self.zoom_factor)))
        icon_search_test = self.icons.button('search', self.colors['text_primary'])
        btn_test = ttk.Button(button_row, image=icon_search_test, text=" 测试连接", compound=tk.LEFT, command=self.test_api_connection)
        btn_test._icon_ref = icon_search_test
        btn_test.pack(side="left", padx=int(5 * self.dpi_scale * self.zoom_factor))

        # API 配置状态提示
        self.api_status_label = ttk.Label(config_card, text="",
                                         font=(FONT_FAMILY, int(11 * self.dpi_scale * self.zoom_factor)),
                                         foreground=self.colors['success'])
        self.api_status_label.pack(anchor="w", padx=int(25 * self.dpi_scale * self.zoom_factor), pady=(0, int(10 * self.dpi_scale * self.zoom_factor)))

        # 3. 已保存模型列表
        model_list_card = ttk.LabelFrame(api_container, text="  已保存模型（双击切换）  ", padding=int(UI_CONFIG['label_frame_padding'] * self.dpi_scale * self.zoom_factor), style='Custom.TLabelframe')
        model_list_card.pack(fill="both", expand=True, padx=int(25 * self.dpi_scale * self.zoom_factor), pady=int(15 * self.dpi_scale * self.zoom_factor))

        # 模型列表 Treeview
        model_columns = ("name", "provider", "base_url")
        self.model_list_tree = ttk.Treeview(model_list_card, columns=model_columns, show="headings")
        self.model_list_tree.heading("name", text="模型名称")
        self.model_list_tree.heading("provider", text="服务商")
        self.model_list_tree.heading("base_url", text="Base URL")
        self.model_list_tree.column("name", width=65, minwidth=65, anchor='center')
        self.model_list_tree.column("provider", width=20, minwidth=20, anchor='center')
        self.model_list_tree.column("base_url", width=400, minwidth=100, anchor='center')

        # 滚动条
        model_scrollbar = ttk.Scrollbar(model_list_card, orient="vertical", command=self.model_list_tree.yview)
        self.model_list_tree.configure(yscrollcommand=model_scrollbar.set)

        self.model_list_tree.pack(side="left", fill="both", expand=True)
        model_scrollbar.pack(side="right", fill="y")

        # 右键菜单 - 模型列表
        model_menu_font = (FONT_FAMILY, int(12 * self.dpi_scale * self.zoom_factor))
        self.model_context_menu = tk.Menu(self.model_list_tree, tearoff=0, font=model_menu_font)
        self.model_context_menu.add_command(label="切换", command=self.use_selected_model)
        self.model_context_menu.add_command(label="删除", command=self.delete_selected_model)

        def show_model_context_menu(event):
            item = self.model_list_tree.identify_row(event.y)
            if item:
                self.model_list_tree.selection_set(item)
                self.model_context_menu.tk_popup(event.x_root, event.y_root)

        self.model_list_tree.bind("<Button-3>", show_model_context_menu)

        # 初始化模型列表
        self.saved_models = []

    def load_api_config_to_ui(self):
        """加载 API 配置到 UI 控件"""
        if not hasattr(self, 'api_config') or not self.api_config:
            return

        # 确保变量已初始化
        if not hasattr(self, 'api_provider_var'):
            return

        self.api_provider_var.set(self.api_config.get("api_provider", "qwen"))
        self.api_key_var.set(self.api_config.get("api_key", ""))
        self.api_base_url_var.set(self.api_config.get("base_url", ""))
        self.api_model_var.set(self.api_config.get("model", ""))

        # 更新当前使用模型显示
        self.update_current_model_display()

        # 加载已保存的模型列表
        self.load_saved_models_to_tree()

    def update_current_model_display(self):
        """更新当前使用模型显示"""
        if not hasattr(self, 'current_model_label'):
            return

        current_model = self.api_config.get("model", "")
        current_provider = self.api_config.get("api_provider", "")

        if current_model:
            display_text = f"{current_provider.upper()} / {current_model}"
            self.current_model_label.config(text=display_text, foreground=self.colors['primary'])
        else:
            self.current_model_label.config(text="未配置", foreground=self.colors['text_secondary'])

    def load_saved_models_to_tree(self):
        """加载已保存的模型列表到 Treeview"""
        if not hasattr(self, 'model_list_tree'):
            return

        # 清空现有列表
        for item in self.model_list_tree.get_children():
            self.model_list_tree.delete(item)

        # 确保 api_config 已加载
        if not hasattr(self, 'api_config') or not self.api_config:
            return

        # 加载已保存的模型
        saved_models = self.api_config.get("saved_models", [])
        current_model = self.api_config.get("model", "")

        # 同步到 self.saved_models（关键修复！）
        self.saved_models = saved_models

        for model_config in saved_models:
            name = model_config.get("model", "")
            provider = model_config.get("api_provider", "")
            base_url = model_config.get("base_url", "")
            is_current = "✓ 使用中" if name == current_model else ""
            self.model_list_tree.insert("", "end", values=(name, provider, base_url), tags=('current' if is_current else ''))

        # 设置使用中标记的样式
        self.model_list_tree.tag_configure('current', foreground=self.colors['success'])

        # 动态调整高度：根据行数自适应，最少1行，最多6行
        row_count = len(saved_models)
        self.model_list_tree['height'] = max(1, min(row_count, 6))

        # 绑定双击事件 - 双击切换模型
        self.model_list_tree.bind("<Double-1>", lambda e: self.use_selected_model())

        # 在所有控件创建完毕后绑定滚轮事件
        self._bind_mousewheel(self.api_canvas, self.api_scrollable_frame)

    def create_run_page(self):
        """创建运行控制页面 - 增强版：浏览器状态检测 + 进度条 + 滚动支持"""
        self.run_page = ttk.Frame(self.pages_frame, style='TFrame')

        # 可滚动容器（macOS Tk 9.0+ 用 Text，其他用 Canvas）
        scroll_frame = ttk.Frame(self.run_page, style='TFrame')
        scroll_frame.pack(fill="both", expand=True)

        self.run_canvas, scrollable_frame = self._create_scroll_container(
            scroll_frame, self.colors['bg_main'])

        self.run_scrollable_frame = scrollable_frame  # 保存引用，供 mousewheel 绑定使用

        # 所有内容放入 scrollable_frame
        content = scrollable_frame

        # 页面标题
        header_frame = ttk.Frame(content, style='TFrame')
        header_frame.pack(fill="x", pady=(0, int(25 * self.dpi_scale * self.zoom_factor)))

        title_label = ttk.Label(header_frame, text="运行控制",
                               font=self.font_section, foreground=self.colors['text_primary'])
        title_label.pack(anchor="w")

        # 控制卡片
        control_container = ttk.Frame(content, style='Card.TFrame')
        control_container.pack(fill="x", pady=int(15 * self.dpi_scale * self.zoom_factor))

        # === 浏览器连接状态检测 ===
        browser_frame = ttk.LabelFrame(control_container, text="  浏览器状态  ", padding=int(UI_CONFIG['label_frame_padding'] * self.dpi_scale * self.zoom_factor), style='Custom.TLabelframe')
        browser_frame.pack(fill="x", padx=int(25 * self.dpi_scale * self.zoom_factor), pady=int(20 * self.dpi_scale * self.zoom_factor))

        browser_status_row = ttk.Frame(browser_frame, style='TFrame')
        browser_status_row.pack(fill="x")

        # 状态指示灯
        self.browser_status_indicator = ttk.Label(browser_status_row, text="🔴 未连接",
                                                  font=(FONT_FAMILY, int(14 * self.dpi_scale * self.zoom_factor)),
                                                  foreground=self.colors['danger'])
        self.browser_status_indicator.pack(side="left")

        # 检测按钮
        icon_browser = self.icons.button('search', self.colors['text_primary'])
        btn_browser = ttk.Button(browser_status_row, image=icon_browser, text=" 检测/连接浏览器", compound=tk.LEFT, command=self.check_browser_connection)
        btn_browser._icon_ref = icon_browser
        btn_browser.pack(side="left", padx=int(20 * self.dpi_scale * self.zoom_factor))

        # 状态说明
        self.browser_status_help = ttk.Label(browser_status_row, text="请点击按钮连接 BOSS 直聘页面",
                                             font=(FONT_FAMILY, int(11 * self.dpi_scale * self.zoom_factor)),
                                             foreground=self.colors['text_secondary'])
        self.browser_status_help.pack(side="left", padx=int(20 * self.dpi_scale * self.zoom_factor))

        # 运行参数
        param_frame = ttk.Frame(control_container, style='TFrame')
        param_frame.pack(fill="x", padx=int(25 * self.dpi_scale * self.zoom_factor), pady=int(20 * self.dpi_scale * self.zoom_factor))

        # 滚动轮次
        row1 = ttk.Frame(param_frame, style='TFrame')
        row1.pack(fill="x", pady=int(15 * self.dpi_scale * self.zoom_factor))
        ttk.Label(row1, text="滚动轮次:", font=self.font_label, width=12,
                 background=self.colors['bg_card']).pack(side="left")
        self.rounds_var = tk.StringVar(value="100")
        self.rounds_spin = ttk.Spinbox(row1, from_=UI_CONFIG['spinbox_rounds_min'],
                                       to=UI_CONFIG['spinbox_rounds_max'],
                                       increment=10, textvariable=self.rounds_var,
                                       width=15, font=self.font_button)
        self.rounds_spin.pack(side="left", padx=int(15 * self.dpi_scale * self.zoom_factor))
        # 鼠标滚轮绑定
        self.rounds_spin.bind('<Enter>',
            lambda e: self.rounds_spin.bind('<MouseWheel>', self._on_rounds_mousewheel))
        self.rounds_spin.bind('<Leave>',
            lambda e: self.rounds_spin.unbind('<MouseWheel>'))
        ttk.Label(row1, text="(推荐 50-200 轮次)", font=(FONT_FAMILY, int(11 * self.dpi_scale * self.zoom_factor)),
                 foreground=self.colors['text_muted'], background=self.colors['bg_card']).pack(side="left", padx=int(10 * self.dpi_scale * self.zoom_factor))

        # 选择岗位（多岗位运行时指定处理哪个岗位）
        row_job = ttk.Frame(param_frame, style='TFrame')
        row_job.pack(fill="x", pady=int(15 * self.dpi_scale * self.zoom_factor))
        ttk.Label(row_job, text="选择岗位:", font=self.font_label, width=12,
                 background=self.colors['bg_card']).pack(side="left")
        self.job_select_var = tk.StringVar(value="全部岗位")
        self.job_combo = ttk.Combobox(row_job, textvariable=self.job_select_var,
                                       values=["全部岗位"], width=28, state="readonly",
                                       font=self.font_combo)
        self.job_combo.pack(side="left", padx=int(15 * self.dpi_scale * self.zoom_factor))
        self.job_combo.bind("<<ComboboxSelected>>", self.on_run_job_selected)
        ttk.Label(row_job, text="(选择要处理的岗位，\"全部岗位\"依次处理)",
                 font=(FONT_FAMILY, int(11 * self.dpi_scale * self.zoom_factor)),
                 foreground=self.colors['text_muted'],
                 background=self.colors['bg_card']).pack(side="left", padx=int(10 * self.dpi_scale * self.zoom_factor))

        # 打招呼等级
        row2 = ttk.Frame(param_frame, style='TFrame')
        row2.pack(fill="x", pady=int(15 * self.dpi_scale * self.zoom_factor))
        ttk.Label(row2, text="自动打招呼:", font=self.font_label, width=12,
                 background=self.colors['bg_card']).pack(side="left")
        self.greet_level_var = tk.StringVar(value="仅强烈推荐")
        greet_combo = ttk.Combobox(row2, textvariable=self.greet_level_var,
                                    values=["不打招呼（仅筛选）", "仅强烈推荐", "强烈推荐 + 推荐"],
                                    width=20, state="readonly", font=self.font_combo)
        greet_combo.pack(side="left", padx=int(15 * self.dpi_scale * self.zoom_factor))
        ttk.Label(row2, text="(自动打招呼的推荐等级)", font=(FONT_FAMILY, int(11 * self.dpi_scale * self.zoom_factor)),
                 foreground=self.colors['text_muted'], background=self.colors['bg_card']).pack(side="left", padx=int(10 * self.dpi_scale * self.zoom_factor))

        # AI 辅助评估开关
        row_ai = ttk.Frame(param_frame, style='TFrame')
        row_ai.pack(fill="x", pady=int(15 * self.dpi_scale * self.zoom_factor))
        ttk.Label(row_ai, text="AI 评估:", font=self.font_label, width=12,
                 background=self.colors['bg_card']).pack(side="left")
        self.ai_eval_var = tk.BooleanVar(value=False)
        # 自定义 ttk 样式：显式设置 indicator 大小，不依赖字体缩放
        _cb_style = ttk.Style()
        _indicator_size = int(20 * self.dpi_scale * self.zoom_factor)
        _cb_style.configure('AIEval.TCheckbutton',
                            font=self.font_combo,
                            background=self.colors['bg_card'],
                            indicatordiameter=_indicator_size)
        _cb_style.map('AIEval.TCheckbutton',
                      background=[('active', self.colors['bg_card'])])
        ai_check = ttk.Checkbutton(row_ai, text="启用 AI 辅助评估",
                                   variable=self.ai_eval_var,
                                   style='AIEval.TCheckbutton')
        ai_check.pack(side="left", padx=int(15 * self.dpi_scale * self.zoom_factor))
        ttk.Label(row_ai, text="(对通过筛选的候选人进行 LLM 二次评分，+-10分调整)",
                 font=(FONT_FAMILY, int(11 * self.dpi_scale * self.zoom_factor)),
                 foreground=self.colors['text_muted'],
                 background=self.colors['bg_card']).pack(side="left", padx=int(10 * self.dpi_scale * self.zoom_factor))

        # === 进度条 ===
        progress_frame = ttk.Frame(param_frame, style='TFrame')
        progress_frame.pack(fill="x", pady=int(15 * self.dpi_scale * self.zoom_factor))

        ttk.Label(progress_frame, text="筛选进度:", font=self.font_label,
                 background=self.colors['bg_card']).pack(side="left")

        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var,
                                            maximum=100, mode='determinate', length=400)
        self.progress_bar.pack(side="left", padx=int(15 * self.dpi_scale * self.zoom_factor), fill="x", expand=True)

        self.progress_label = ttk.Label(progress_frame, text="0%",
                                       font=(FONT_FAMILY, int(11 * self.dpi_scale * self.zoom_factor)),
                                       foreground=self.colors['primary'], width=45)
        self.progress_label.pack(side="left")

        # 控制按钮区
        btn_container = ttk.Frame(control_container, style='TFrame')
        btn_container.pack(fill="x", padx=int(25 * self.dpi_scale * self.zoom_factor), pady=int(20 * self.dpi_scale * self.zoom_factor))

        # 开始/停止按钮
        icon_play_run = self.icons.button('play', self.colors['text_primary'])
        self.start_btn = ttk.Button(btn_container, image=icon_play_run, text=" 开始运行", compound=tk.LEFT, command=self.start_run, style='Accent.TButton', state="disabled")
        self.start_btn._icon_ref = icon_play_run
        self.start_btn.pack(side="left", padx=int(15 * self.dpi_scale * self.zoom_factor))

        icon_stop = self.icons.button('stop', self.colors['text_primary'])
        self.stop_btn = ttk.Button(btn_container, image=icon_stop, text=" 停止", compound=tk.LEFT, command=self.stop_run, state="disabled")
        self.stop_btn._icon_ref = icon_stop
        self.stop_btn.pack(side="left", padx=int(15 * self.dpi_scale * self.zoom_factor))

        # 状态指示器
        self.status_label = ttk.Label(btn_container, text="🟢 就绪",
                                      font=(FONT_FAMILY, int(13 * self.dpi_scale * self.zoom_factor)), foreground=self.colors['success'])
        self.status_label.pack(side="left", padx=int(50 * self.dpi_scale * self.zoom_factor))

        # 日志区域 — 独立于控制卡片，撑满剩余高度
        log_label = ttk.Label(content, text="运行日志",
                             font=self.font_section, foreground=self.colors['text_primary'])
        log_label.pack(anchor="w", padx=int(25 * self.dpi_scale * self.zoom_factor), pady=(int(15 * self.dpi_scale * self.zoom_factor), int(10 * self.dpi_scale * self.zoom_factor)))

        log_wrapper = ttk.Frame(content, style='TFrame')
        log_wrapper.pack(fill="x", padx=int(25 * self.dpi_scale * self.zoom_factor), pady=(0, int(15 * self.dpi_scale * self.zoom_factor)))

        log_container = ttk.Frame(log_wrapper, style='Card.TFrame')
        log_container.pack(fill="x")

        # 日志文本框 - 等宽字体
        log_font = font.Font(family='Consolas', size=int(12 * self.dpi_scale * self.zoom_factor))
        self.log_text = tk.Text(log_container, wrap="word", state="disabled",
                               font=log_font, bg=self.colors['bg_input'], borderwidth=0,
                               highlightthickness=0, height=20)
        self.log_text.pack(side="left", fill="both", expand=True)
        self.bind_text_context_menu(self.log_text, editable=False)

        log_scroll = ttk.Scrollbar(log_container, orient="vertical", command=self.log_text.yview)
        log_scroll.pack(side="right", fill="y")
        self.log_text.config(yscrollcommand=log_scroll.set)

        # 日志工具栏 — 独立于 log_container，避免撑出空白
        log_toolbar = ttk.Frame(log_wrapper, style='TFrame')
        log_toolbar.pack(fill="x", pady=(int(8 * self.dpi_scale * self.zoom_factor), 0))

        icon_trash_log = self.icons.button('trash', self.colors['text_primary'])
        btn_clear_log = ttk.Button(log_toolbar, image=icon_trash_log, text=" 清空日志", compound=tk.LEFT, command=self.clear_log)
        btn_clear_log._icon_ref = icon_trash_log
        btn_clear_log.pack()

        # 启动进度条更新循环
        self.update_progress()

        # 在所有控件创建完毕后绑定滚轮事件
        self._bind_mousewheel(self.run_canvas, self.run_scrollable_frame)

    def create_result_page(self):
        """创建筛选结果页面"""
        self.result_page = ttk.Frame(self.pages_frame, style='TFrame')

        # 页面标题
        header_frame = ttk.Frame(self.result_page, style='TFrame')
        header_frame.pack(fill="x", pady=(0, int(25 * self.dpi_scale * self.zoom_factor)))

        title_label = ttk.Label(header_frame, text="筛选结果",
                               font=self.font_section, foreground=self.colors['text_primary'])
        title_label.pack(anchor="w")

        # 岗位过滤
        filter_frame = ttk.Frame(self.result_page, style='TFrame')
        filter_frame.pack(fill="x", pady=(0, int(10 * self.dpi_scale * self.zoom_factor)))
        ttk.Label(filter_frame, text="岗位过滤:", font=self.font_label,
                 background=self.colors['bg_main']).pack(side="left")
        self.result_job_var = tk.StringVar(value="全部岗位")
        self.result_job_combo = ttk.Combobox(filter_frame, textvariable=self.result_job_var,
                                              values=["全部岗位"], width=28, state="readonly",
                                              font=self.font_combo)
        self.result_job_combo.pack(side="left", padx=int(15 * self.dpi_scale * self.zoom_factor))
        self.result_job_combo.bind("<<ComboboxSelected>>", lambda e: self.refresh_results())

        # 统计卡片区（纵向卡片布局）
        stats_container = ttk.Frame(self.result_page, style='TFrame')
        stats_container.pack(fill="x", pady=int(15 * self.dpi_scale * self.zoom_factor))

        self.result_stats_vars = {}
        self.result_stats_greeted = {}
        self.result_stats_click = {}
        stats_data = [
            ("people", "通过筛选", "passed", self.colors['primary']),
            ("star", "强烈推荐", "strong", self.colors['purple']),
            ("thumbs_up", "推荐", "recommended", self.colors['success']),
        ]

        for icon_name, label_text, var_name, color in stats_data:
            card_frame = ttk.Frame(stats_container, style='Card.TFrame')
            card_frame.pack(side="left", fill="x", expand=True, padx=int(12 * self.dpi_scale * self.zoom_factor))

            # 彩色圆形图标（大号）
            icon_size = int(UI_CONFIG['stat_icon_size'] * self.dpi_scale * self.zoom_factor)
            icon_canvas = tk.Canvas(card_frame, width=icon_size, height=icon_size,
                                    bg=self.colors['bg_card'], highlightthickness=0)
            icon_canvas.pack(anchor="center",
                            pady=(int(12 * self.dpi_scale * self.zoom_factor), int(4 * self.dpi_scale * self.zoom_factor)))
            margin = int(UI_CONFIG['icon_margin'] * self.dpi_scale * self.zoom_factor)
            icon_canvas.create_oval(margin, margin, icon_size - margin, icon_size - margin,
                                    fill=color, outline='')
            stat_icon = self.icons.stat(icon_name, 'white')
            icon_canvas.create_image(icon_size // 2, icon_size // 2, image=stat_icon)
            icon_canvas._icon_ref = stat_icon

            # 数值
            var = tk.StringVar(value="0")
            self.result_stats_vars[var_name] = var
            value_label = ttk.Label(card_frame, textvariable=var, font=self.font_stat,
                                   foreground=color, background=self.colors['bg_card'],
                                   cursor="hand2")
            value_label.pack(anchor="center", pady=(0, int(2 * self.dpi_scale * self.zoom_factor)))

            # 已打招呼
            greeted_var = tk.StringVar(value="0 已打招呼")
            self.result_stats_greeted[var_name] = greeted_var
            greeted_label = ttk.Label(card_frame, textvariable=greeted_var,
                                     font=(FONT_FAMILY, int(10 * self.dpi_scale * self.zoom_factor)),
                                     foreground=self.colors['text_muted'], background=self.colors['bg_card'])
            greeted_label.pack(anchor="center", pady=(0, int(2 * self.dpi_scale * self.zoom_factor)))

            # 标签
            label = ttk.Label(card_frame, text=label_text, font=self.font_stat_label,
                             foreground=self.colors['text_secondary'], background=self.colors['bg_card'])
            label.pack(anchor="center", pady=(0, int(10 * self.dpi_scale * self.zoom_factor)))

            # 绑定点击事件
            self.result_stats_click[var_name] = label_text
            value_label.bind("<Button-1>", lambda e, vt=var_name: self.show_result_stat_detail(vt))
            label.bind("<Button-1>", lambda e, vt=var_name: self.show_result_stat_detail(vt))

        # 结果表格
        table_container = ttk.Frame(self.result_page, style='Card.TFrame')
        table_container.pack(fill="both", expand=True, pady=int(8 * self.dpi_scale * self.zoom_factor))

        # 表格
        columns = ("name", "exp", "salary", "skills", "score", "ai_eval", "level", "status")
        self.result_tree = ttk.Treeview(table_container, columns=columns, show="headings", height=4)

        self.result_tree.heading("name", text="姓名")
        self.result_tree.heading("exp", text="工作年限")
        self.result_tree.heading("salary", text="薪资")
        self.result_tree.heading("skills", text="技能匹配")
        self.result_tree.heading("score", text="匹配分")
        self.result_tree.heading("ai_eval", text="AI评估")
        self.result_tree.heading("level", text="推荐指数")
        self.result_tree.heading("status", text="状态")

        # 设置列宽
        self.result_tree.column("name", width=80, minwidth=60, anchor='center')
        self.result_tree.column("exp", width=100, minwidth=80, anchor='center')
        self.result_tree.column("salary", width=100, minwidth=80, anchor='center')
        self.result_tree.column("skills", width=180, minwidth=120, anchor='center')
        self.result_tree.column("score", width=70, minwidth=60, anchor='center')
        self.result_tree.column("ai_eval", width=70, minwidth=60, anchor='center')
        self.result_tree.column("level", width=110, minwidth=90, anchor='center')
        self.result_tree.column("status", width=70, minwidth=60, anchor='center')

        # 设置表格字体和样式
        style = ttk.Style()
        style.configure("Result.Treeview", font=self.font_table, rowheight=int(UI_CONFIG['treeview_rowheight'] * self.dpi_scale * self.zoom_factor))
        style.configure("Result.Treeview.Heading", font=self.font_button)
        self.result_tree.configure(style="Result.Treeview")

        tree_scroll = ttk.Scrollbar(table_container, orient="vertical", command=self.result_tree.yview)
        self.result_tree.configure(yscrollcommand=tree_scroll.set)

        self.result_tree.pack(side="left", fill="both", expand=True, padx=int(20 * self.dpi_scale * self.zoom_factor), pady=int(12 * self.dpi_scale * self.zoom_factor))
        tree_scroll.pack(side="right", fill="y", pady=int(10 * self.dpi_scale * self.zoom_factor))

        # 操作按钮 - 放在表格下方
        btn_frame = ttk.Frame(self.result_page, style='TFrame')
        btn_frame.pack(fill="x", padx=int(20 * self.dpi_scale * self.zoom_factor), pady=(int(8 * self.dpi_scale * self.zoom_factor), int(12 * self.dpi_scale * self.zoom_factor)))

        icon_refresh_result = self.icons.button('refresh', self.colors['text_primary'])
        btn_refresh = ttk.Button(btn_frame, image=icon_refresh_result, text=" 刷新结果", compound=tk.LEFT, command=self.refresh_results)
        btn_refresh._icon_ref = icon_refresh_result
        btn_refresh.pack(side="left", padx=int(8 * self.dpi_scale * self.zoom_factor))
        icon_chart_excel = self.icons.button('chart', self.colors['text_primary'])
        btn_excel = ttk.Button(btn_frame, image=icon_chart_excel, text=" 导出 Excel", compound=tk.LEFT, command=self.export_excel)
        btn_excel._icon_ref = icon_chart_excel
        btn_excel.pack(side="left", padx=int(8 * self.dpi_scale * self.zoom_factor))
        icon_folder_json = self.icons.button('folder', self.colors['text_primary'])
        btn_json = ttk.Button(btn_frame, image=icon_folder_json, text=" 打开 JSON", compound=tk.LEFT, command=self.open_json)
        btn_json._icon_ref = icon_folder_json
        btn_json.pack(side="left", padx=int(8 * self.dpi_scale * self.zoom_factor))

        icon_clear = self.icons.button('trash', self.colors['danger'])
        btn_clear = ttk.Button(btn_frame, image=icon_clear, text=" 清空候选人", compound=tk.LEFT, command=self.clear_candidates)
        btn_clear._icon_ref = icon_clear
        btn_clear.pack(side="left", padx=int(8 * self.dpi_scale * self.zoom_factor))

    def create_stats_page(self):
        """创建数据统计页面 - 按岗位维度展示筛选和打招呼统计"""
        self.stats_page = ttk.Frame(self.pages_frame, style='TFrame')

        # 页面标题
        header_frame = ttk.Frame(self.stats_page, style='TFrame')
        header_frame.pack(fill="x", pady=(0, int(25 * self.dpi_scale * self.zoom_factor)))

        title_label = ttk.Label(header_frame, text="数据统计",
                               font=self.font_section, foreground=self.colors['text_primary'])
        title_label.pack(anchor="w")

        # 过滤条件行
        filter_frame = ttk.Frame(self.stats_page, style='TFrame')
        filter_frame.pack(fill="x", pady=(0, int(15 * self.dpi_scale * self.zoom_factor)))

        ttk.Label(filter_frame, text="岗位过滤:", font=self.font_label,
                 background=self.colors['bg_main']).pack(side="left")
        self.stats_job_var = tk.StringVar(value="全部岗位")
        self.stats_job_combo = ttk.Combobox(filter_frame, textvariable=self.stats_job_var,
                                             values=["全部岗位"], width=28, state="readonly",
                                             font=self.font_combo)
        self.stats_job_combo.pack(side="left", padx=int(15 * self.dpi_scale * self.zoom_factor))
        self.stats_job_combo.bind("<<ComboboxSelected>>", lambda e: self.refresh_stats())

        # 时间维度过滤
        ttk.Label(filter_frame, text="时间范围:", font=self.font_label,
                 background=self.colors['bg_main']).pack(side="left", padx=int(30 * self.dpi_scale * self.zoom_factor))
        self.stats_time_var = tk.StringVar(value="全部")
        time_combo = ttk.Combobox(filter_frame, textvariable=self.stats_time_var,
                                   values=["今天", "本周", "全部"], width=12, state="readonly",
                                   font=self.font_combo)
        time_combo.pack(side="left", padx=int(15 * self.dpi_scale * self.zoom_factor))
        time_combo.bind("<<ComboboxSelected>>", lambda e: self.refresh_stats())

        # 刷新按钮
        icon_refresh_stats = self.icons.button('refresh', self.colors['text_primary'])
        btn_refresh = ttk.Button(filter_frame, image=icon_refresh_stats, text=" 刷新",
                                compound=tk.LEFT, command=self.refresh_stats)
        btn_refresh._icon_ref = icon_refresh_stats
        btn_refresh.pack(side="left", padx=int(20 * self.dpi_scale * self.zoom_factor))

        # 汇总统计卡片
        summary_container = ttk.Frame(self.stats_page, style='TFrame')
        summary_container.pack(fill="x", pady=int(10 * self.dpi_scale * self.zoom_factor))

        self.stats_summary_vars = {}
        summary_items = [
            ("people", "总候选人", "total", self.colors['primary']),
            ("star", "强烈推荐", "strong", self.colors['purple']),
            ("thumbs_up", "推荐", "recommended", self.colors['success']),
            ("mail", "已打招呼", "greeted", self.colors['warning']),
        ]

        for icon_name, label_text, var_name, color in summary_items:
            card = ttk.Frame(summary_container, style='Card.TFrame')
            card.pack(side="left", fill="x", expand=True, padx=int(10 * self.dpi_scale * self.zoom_factor),
                     pady=int(10 * self.dpi_scale * self.zoom_factor))

            # 图标容器
            icon_size = int(UI_CONFIG['stat_icon_size'] * self.dpi_scale * self.zoom_factor)
            icon_canvas = tk.Canvas(card, width=icon_size, height=icon_size,
                                   bg=self.colors['bg_card'], highlightthickness=0)
            icon_canvas.pack(pady=(int(12 * self.dpi_scale * self.zoom_factor), int(5 * self.dpi_scale * self.zoom_factor)))

            margin = int(UI_CONFIG['icon_margin'] * self.dpi_scale * self.zoom_factor)
            icon_canvas.create_oval(margin, margin, icon_size - margin, icon_size - margin,
                                   fill=color, outline='')

            stat_icon = self.icons.stat(icon_name, 'white')
            icon_canvas.create_image(icon_size // 2, icon_size // 2, image=stat_icon)
            icon_canvas._icon_ref = stat_icon

            # 数值
            var = tk.StringVar(value="0")
            self.stats_summary_vars[var_name] = var
            value_label = ttk.Label(card, textvariable=var, font=self.font_stat,
                                   foreground=color, background=self.colors['bg_card'])
            value_label.pack(pady=(0, int(4 * self.dpi_scale * self.zoom_factor)))

            # 标签
            text_label = ttk.Label(card, text=label_text, font=self.font_stat_label,
                                  foreground=self.colors['text_secondary'],
                                  background=self.colors['bg_card'])
            text_label.pack(pady=(0, int(12 * self.dpi_scale * self.zoom_factor)))

        # 岗位明细表格
        table_label = ttk.Label(self.stats_page, text="岗位明细",
                               font=self.font_section, foreground=self.colors['text_primary'])
        table_label.pack(anchor="w", padx=int(5 * self.dpi_scale * self.zoom_factor),
                        pady=(int(20 * self.dpi_scale * self.zoom_factor), int(10 * self.dpi_scale * self.zoom_factor)))

        table_container = ttk.Frame(self.stats_page, style='Card.TFrame')
        table_container.pack(fill="both", expand=True, pady=int(10 * self.dpi_scale * self.zoom_factor))

        columns = ("job", "total", "strong", "recommended", "pending", "greeted", "pass_rate", "greet_rate", "avg_score")
        self.stats_tree = ttk.Treeview(table_container, columns=columns, show="headings", height=8)

        self.stats_tree.heading("job", text="岗位名称")
        self.stats_tree.heading("total", text="总人数")
        self.stats_tree.heading("strong", text="强烈推荐")
        self.stats_tree.heading("recommended", text="推荐")
        self.stats_tree.heading("pending", text="待定")
        self.stats_tree.heading("greeted", text="已打招呼")
        self.stats_tree.heading("pass_rate", text="优质率")
        self.stats_tree.heading("greet_rate", text="打招呼率")
        self.stats_tree.heading("avg_score", text="平均分")

        self.stats_tree.column("job", width=200, minwidth=150, anchor='w')
        self.stats_tree.column("total", width=90, minwidth=70, anchor='center')
        self.stats_tree.column("strong", width=100, minwidth=80, anchor='center')
        self.stats_tree.column("recommended", width=90, minwidth=70, anchor='center')
        self.stats_tree.column("pending", width=90, minwidth=70, anchor='center')
        self.stats_tree.column("greeted", width=110, minwidth=90, anchor='center')
        self.stats_tree.column("pass_rate", width=90, minwidth=70, anchor='center')
        self.stats_tree.column("greet_rate", width=100, minwidth=80, anchor='center')
        self.stats_tree.column("avg_score", width=90, minwidth=70, anchor='center')

        style = ttk.Style()
        style.configure("Stats.Treeview", font=self.font_table,
                       rowheight=int(UI_CONFIG['treeview_rowheight'] * self.dpi_scale * self.zoom_factor))
        style.configure("Stats.Treeview.Heading", font=self.font_button)
        self.stats_tree.configure(style="Stats.Treeview")

        tree_scroll = ttk.Scrollbar(table_container, orient="vertical", command=self.stats_tree.yview)
        self.stats_tree.configure(yscrollcommand=tree_scroll.set)

        self.stats_tree.pack(side="left", fill="both", expand=True,
                            padx=int(15 * self.dpi_scale * self.zoom_factor),
                            pady=int(15 * self.dpi_scale * self.zoom_factor))
        tree_scroll.pack(side="right", fill="y", pady=int(10 * self.dpi_scale * self.zoom_factor))

    def refresh_stats(self):
        """刷新数据统计页面 - 按岗位维度聚合"""
        try:
            if not CANDIDATES_PATH.exists():
                return

            with open(CANDIDATES_PATH, 'r', encoding='utf-8') as f:
                candidates = json.load(f)

            # 岗位过滤
            selected_job = self.stats_job_var.get()
            if selected_job != "全部岗位":
                candidates = [c for c in candidates if c.get('job_name', '') == selected_job.replace(" ", "")]

            # 时间范围过滤
            time_range = self.stats_time_var.get()
            if time_range != "全部":
                now = datetime.now()
                if time_range == "今天":
                    cutoff = now.replace(hour=0, minute=0, second=0, microsecond=0)
                elif time_range == "本周":
                    days_since_monday = now.weekday()
                    cutoff = (now - timedelta(days=days_since_monday)).replace(hour=0, minute=0, second=0, microsecond=0)
                else:
                    cutoff = None

                if cutoff:
                    cutoff_str = cutoff.strftime("%Y%m%d_%H%M%S")
                    candidates = [c for c in candidates if c.get('batch_timestamp', '') >= cutoff_str]

            # 汇总统计（只计 ≥55 分的候选人）
            qualified = [c for c in candidates if c.get('match_score', 0) >= 55]
            total = len(qualified)
            strong = sum(1 for c in qualified if c.get('match_score', 0) >= 75)
            recommended = sum(1 for c in qualified if 65 <= c.get('match_score', 0) < 75)
            greeted = sum(1 for c in qualified if c.get('greet_sent', False))

            self.stats_summary_vars['total'].set(str(total))
            self.stats_summary_vars['strong'].set(str(strong))
            self.stats_summary_vars['recommended'].set(str(recommended))
            self.stats_summary_vars['greeted'].set(str(greeted))

            # 清空表格
            for item in self.stats_tree.get_children():
                self.stats_tree.delete(item)

            # 按岗位聚合
            from collections import defaultdict
            job_stats = defaultdict(lambda: {
                'total': 0, 'strong': 0, 'recommended': 0, 'pending': 0,
                'greeted': 0, 'scores': []
            })

            for c in candidates:
                job = c.get('job_name', '未知')
                score = c.get('match_score', 0)
                if score < 55:
                    continue  # 低于 55 分不计入统计

                job_stats[job]['total'] += 1
                if score >= 75:
                    job_stats[job]['strong'] += 1
                elif score >= 65:
                    job_stats[job]['recommended'] += 1
                else:
                    job_stats[job]['pending'] += 1

                if c.get('greet_sent', False):
                    job_stats[job]['greeted'] += 1

                job_stats[job]['scores'].append(score)

            # 插入表格行
            for job, stats in sorted(job_stats.items(), key=lambda x: x[1]['total'], reverse=True):
                t = stats['total']
                s = stats['strong']
                r = stats['recommended']
                p = stats['pending']
                g = stats['greeted']
                quality = s + r
                pass_rate = f"{quality*100//t}%" if t > 0 else "—"
                greet_rate = f"{g*100//t}%" if t > 0 else "—"
                avg_score = f"{sum(stats['scores'])/len(stats['scores']):.1f}" if stats['scores'] else "—"

                self.stats_tree.insert("", "end", values=(
                    job, t, s, r, p, g, pass_rate, greet_rate, avg_score
                ))

        except Exception as e:
            self.append_log(f"刷新统计失败：{e}")

    def show_page_home(self):
        """显示首页"""
        self.hide_all_pages()
        self.home_page.pack(fill="both", expand=True)
        self.current_page_index = 0
        self.update_nav_highlight()
        # 刷新岗位过滤列表
        try:
            from bossmaster import load_job_config
            job_rules, _ = load_job_config()
            jobs = ["全部岗位"] + list(job_rules.keys())
            self.home_job_combo['values'] = jobs
        except Exception:
            pass
        self.refresh_home_stats()

    def show_page_config(self):
        """显示配置页面"""
        self.hide_all_pages()
        self.config_page.pack(fill="both", expand=True)
        # 刷新技能树和必要条件列表
        if self.job_rules:
            self.refresh_skills_tree()
            self.refresh_required_listbox()
        # 始终显示详细结果区域（基本信息、技能关键词、必要条件、话术模板）
        self.result_detail_frame.pack(fill="both", expand=True, padx=int(25 * self.dpi_scale * self.zoom_factor), pady=int(15 * self.dpi_scale * self.zoom_factor))
        self.current_page_index = 1
        self.update_nav_highlight()
        # 重新绑定滚轮事件（覆盖动态创建的控件）
        self._bind_mousewheel(self.config_canvas, self.config_scrollable_frame)

    def show_page_run(self):
        """显示运行页面"""
        self.hide_all_pages()
        self.run_page.pack(fill="both", expand=True)
        self.current_page_index = 2
        self.update_nav_highlight()
        # 恢复浏览器自动检测（仅检测连接，不启动浏览器）
        self._start_browser_auto_check()
        # 刷新岗位选择列表
        try:
            from bossmaster import load_job_config
            job_rules, _ = load_job_config()
            jobs = ["全部岗位"] + list(job_rules.keys())
            self.job_combo['values'] = jobs
        except Exception:
            pass
        # 重新绑定滚轮事件（覆盖动态创建的控件）
        self._bind_mousewheel(self.run_canvas, self.run_scrollable_frame)

    def show_page_result(self):
        """显示结果页面"""
        self.hide_all_pages()
        self.result_page.pack(fill="both", expand=True)
        self.current_page_index = 3
        self.update_nav_highlight()
        # 刷新岗位过滤列表
        try:
            from bossmaster import load_job_config
            job_rules, _ = load_job_config()
            jobs = ["全部岗位"] + list(job_rules.keys())
            self.result_job_combo['values'] = jobs
        except Exception:
            pass
        self.refresh_results()

    def show_page_stats(self):
        """显示数据统计页面"""
        self.hide_all_pages()
        self.stats_page.pack(fill="both", expand=True)
        self.current_page_index = 4
        self.update_nav_highlight()
        # 刷新岗位过滤列表
        try:
            from bossmaster import load_job_config
            job_rules, _ = load_job_config()
            jobs = ["全部岗位"] + list(job_rules.keys())
            self.stats_job_combo['values'] = jobs
        except Exception:
            pass
        self.refresh_stats()

    def show_page_api(self):
        """显示 API 配置页面（系统设置）"""
        self.hide_all_pages()
        self.api_config_page.pack(fill="both", expand=True)
        self.current_page_index = 5
        self.update_nav_highlight()
        # 重置滚动条位置到顶部
        if hasattr(self, 'api_canvas'):
            self.api_canvas.yview_moveto(0.0)
        # 显示时加载配置到 UI
        self.load_api_config_to_ui()
        # 重新绑定滚轮事件（覆盖动态创建的控件）
        self._bind_mousewheel(self.api_canvas, self.api_scrollable_frame)

    def hide_all_pages(self):
        """隐藏所有页面"""
        self._stop_browser_auto_check()
        for page in [self.home_page, self.config_page, self.api_config_page, self.run_page, self.result_page, self.stats_page]:
            page.pack_forget()

    def update_nav_highlight(self):
        """更新导航高亮 - 当前页面使用选中颜色，其他使用默认颜色"""
        for i, comp in enumerate(self.nav_components):
            if i == self.current_page_index:
                comp['icon'].configure(image=comp['icon_active'])
                comp['text'].configure(foreground=self.colors['text_sidebar_active'])
            else:
                comp['icon'].configure(image=comp['icon_default'])
                comp['text'].configure(foreground=self.colors['text_sidebar'])

    def on_nav_enter(self, index):
        """鼠标移入导航项时高亮（交换图标和前景色）"""
        comp = self.nav_components[index]
        comp['icon'].configure(image=comp['icon_active'])
        comp['text'].configure(foreground=self.colors['text_sidebar_active'])

    def on_nav_leave(self, index):
        """鼠标移出导航项时恢复样式（当前页面除外）"""
        if index != self.current_page_index:
            comp = self.nav_components[index]
            comp['icon'].configure(image=comp['icon_default'])
            comp['text'].configure(foreground=self.colors['text_sidebar'])

    # ===== 右键菜单功能 =====
    def bind_entry_context_menu(self, entry_widget):
        """为 Entry/Combobox 控件绑定右键复制/粘贴/全选菜单"""
        menu_font = (FONT_FAMILY, int(14 * self.dpi_scale * self.zoom_factor))
        menu = tk.Menu(entry_widget, tearoff=0, font=menu_font)
        self._context_menus.append(menu)

        def do_cut():
            try:
                entry_widget.event_generate('<<Cut>>')
            except tk.TclError:
                pass

        def do_copy():
            try:
                entry_widget.event_generate('<<Copy>>')
            except tk.TclError:
                pass

        def do_paste():
            try:
                entry_widget.event_generate('<<Paste>>')
            except tk.TclError:
                pass

        def do_select_all():
            try:
                entry_widget.select_range(0, 'end')
                entry_widget.icursor('end')
            except tk.TclError:
                pass

        menu.add_command(label="剪切(T)", command=do_cut)
        menu.add_command(label="复制(C)", command=do_copy)
        menu.add_command(label="粘贴(P)", command=do_paste)
        menu.add_separator()
        menu.add_command(label="全选(A)", command=do_select_all)

        def show_menu(event):
            menu.tk_popup(event.x_root, event.y_root)

        entry_widget.bind("<Button-3>", show_menu)

    def bind_text_context_menu(self, text_widget, editable=True):
        """为 Text 控件绑定右键复制/粘贴/全选菜单"""
        menu_font = (FONT_FAMILY, int(14 * self.dpi_scale * self.zoom_factor))
        menu = tk.Menu(text_widget, tearoff=0, font=menu_font)
        self._context_menus.append(menu)

        def do_cut():
            try:
                text_widget.event_generate('<<Cut>>')
            except tk.TclError:
                pass

        def do_copy():
            try:
                text_widget.event_generate('<<Copy>>')
            except tk.TclError:
                pass

        def do_paste():
            try:
                text_widget.event_generate('<<Paste>>')
            except tk.TclError:
                pass

        def do_select_all():
            try:
                text_widget.tag_add('sel', '1.0', 'end')
            except tk.TclError:
                pass

        if editable:
            menu.add_command(label="剪切(T)", command=do_cut)
        menu.add_command(label="复制(C)", command=do_copy)
        if editable:
            menu.add_command(label="粘贴(P)", command=do_paste)
        menu.add_separator()
        menu.add_command(label="全选(A)", command=do_select_all)

        def show_menu(event):
            menu.tk_popup(event.x_root, event.y_root)

        text_widget.bind("<Button-3>", show_menu)

    def refresh_home_stats(self):
        """刷新首页统计"""
        try:
            if CANDIDATES_PATH.exists():
                with open(CANDIDATES_PATH, 'r', encoding='utf-8') as f:
                    candidates = json.load(f)

                # 岗位过滤
                selected_job = self.home_job_var.get()
                if selected_job != "全部岗位":
                    candidates = [c for c in candidates if c.get('job_name', '') == selected_job.replace(" ", "")]

                # 只统计 ≥55 分的候选人
                candidates = [c for c in candidates if c.get('match_score', 0) >= 55]

                total = len(candidates)
                greeted = sum(1 for c in candidates if c.get('greet_sent', False))
                # 强烈推荐：匹配分>=75
                strong = sum(1 for c in candidates if c.get('match_score', 0) >= 75)
                # 推荐：匹配分>=65 且<75
                recommended = sum(1 for c in candidates if 65 <= c.get('match_score', 0) < 75)

                self.home_stats_vars['total_home'].set(str(total))
                self.home_stats_vars['recommended_home'].set(str(recommended))
                self.home_stats_vars['greeted_home'].set(str(greeted))
                self.home_stats_vars['strong_home'].set(str(strong))
        except Exception as e:
            print(f"刷新首页统计失败：{e}")

    def _center_window(self, window, width, height):
        """将子窗口相对于主窗口居中"""
        self.root.update_idletasks()
        x = self.root.winfo_rootx() + (self.root.winfo_width() - width) // 2
        y = self.root.winfo_rooty() + (self.root.winfo_height() - height) // 2
        window.geometry(f"+{x}+{y}")

    def _set_window_icon(self):
        """设置窗口图标，替换 tkinter 默认羽毛图标"""
        try:
            from PIL import Image, ImageTk
            icon_img = _draw_search_icon(256, '#2563EB', sw_ratio=0.10)
            # 用 iconphoto 设置高分图标，Windows 10/11 原生缩放比 ICO 清晰
            self._icon_photo = ImageTk.PhotoImage(icon_img)
            self.root.iconphoto(True, self._icon_photo)
        except Exception:
            pass  # 图标设置失败不影响程序运行

    def show_stat_detail(self, stat_type):
        """显示统计详情"""
        try:
            if not CANDIDATES_PATH.exists():
                messagebox.showinfo("提示", "暂无候选人数据")
                return

            with open(CANDIDATES_PATH, 'r', encoding='utf-8') as f:
                candidates = json.load(f)

            # 岗位过滤
            if hasattr(self, 'home_job_var'):
                selected_job = self.home_job_var.get()
                if selected_job != "全部岗位":
                    candidates = [c for c in candidates if c.get('job_name', '') == selected_job.replace(" ", "")]

            # 根据类型筛选候选人（只统计 ≥55 分）
            if stat_type == 'total_home':
                title = "累计候选人"
                filtered = [c for c in candidates if c.get('match_score', 0) >= 55]
            elif stat_type == 'strong_home':
                title = "强烈推荐"
                filtered = [c for c in candidates if c.get('match_score', 0) >= 75]
            elif stat_type == 'recommended_home':
                title = "推荐"
                filtered = [c for c in candidates if 65 <= c.get('match_score', 0) < 75]
            elif stat_type == 'greeted_home':
                title = "已打招呼"
                filtered = [c for c in candidates if c.get('match_score', 0) >= 55 and c.get('greet_sent', False)]
            else:
                return

            if not filtered:
                messagebox.showinfo("提示", f"{title}：暂无数据")
                return

            # 创建详情窗口
            detail_window = tk.Toplevel(self.root)
            detail_window.transient(self.root)
            detail_window.grab_set()
            detail_window.title(title)

            # 设置固定大小并相对主窗口居中
            window_width = 1000
            window_height = 650
            detail_window.geometry(f"{window_width}x{window_height}")
            self._center_window(detail_window, window_width, window_height)

            # 标题 - 加大加粗
            title_label = ttk.Label(detail_window, text=title,
                                   font=(FONT_FAMILY, int(18 * self.dpi_scale * self.zoom_factor)),
                                   foreground=self.colors['primary'])
            title_label.pack(fill="x", padx=int(20 * self.dpi_scale * self.zoom_factor), pady=(int(15 * self.dpi_scale * self.zoom_factor), 0))

            # 统计信息 - 显示总数和已打招呼数
            greeted_count = len([c for c in filtered if c.get('greet_sent', False)])
            count_label = ttk.Label(detail_window, text=f"共 {len(filtered)} 人，已打招呼 {greeted_count} 人",
                                   font=(FONT_FAMILY, int(12 * self.dpi_scale * self.zoom_factor)),
                                   foreground=self.colors['text_secondary'])
            count_label.pack(anchor="w", padx=int(20 * self.dpi_scale * self.zoom_factor), pady=(int(5 * self.dpi_scale * self.zoom_factor), 0))
            count_label_ref = [count_label]

            # 表格容器
            table_frame = ttk.Frame(detail_window, style='Card.TFrame')
            table_frame.pack(fill="both", expand=True, padx=int(20 * self.dpi_scale * self.zoom_factor), pady=int(15 * self.dpi_scale * self.zoom_factor))

            # 创建表格 - 与筛选结果页主Treeview列完全一致（含推荐指数）
            columns = ("name", "exp", "salary", "skills", "score", "ai_eval", "level", "status")
            tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=18)

            tree.heading("name", text="姓名")
            tree.heading("exp", text="工作年限")
            tree.heading("salary", text="薪资")
            tree.heading("skills", text="技能匹配")
            tree.heading("score", text="匹配分")
            tree.heading("ai_eval", text="AI评估")
            tree.heading("level", text="推荐指数")
            tree.heading("status", text="状态")

            # 设置列宽 - 与筛选结果页Treeview一致
            tree.column("name", width=80, minwidth=60, anchor='center')
            tree.column("exp", width=100, minwidth=80, anchor='center')
            tree.column("salary", width=100, minwidth=80, anchor='center')
            tree.column("skills", width=140, minwidth=100, anchor='center')
            tree.column("score", width=70, minwidth=60, anchor='center')
            tree.column("ai_eval", width=70, minwidth=60, anchor='center')
            tree.column("level", width=120, minwidth=100, anchor='center')
            tree.column("status", width=70, minwidth=60, anchor='center')

            # 设置表格字体和样式 - 与筛选结果页Treeview一致
            tree_style = ttk.Style()
            tree_style.configure("Detail.Treeview",
                                font=self.font_table,
                                rowheight=int(UI_CONFIG['treeview_rowheight'] * self.dpi_scale * self.zoom_factor))
            tree_style.configure("Detail.Treeview.Heading", font=self.font_button)
            tree.configure(style="Detail.Treeview")

            # 添加滚动条
            scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
            tree.configure(yscrollcommand=scrollbar.set)

            tree.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")

            # 绑定右键菜单 - 与筛选结果页一致
            filtered_ref = [filtered]  # 用列表包装以支持闭包内修改

            def on_detail_right_click(event):
                clicked_item = tree.identify_row(event.y)
                if not clicked_item:
                    return
                tree.selection_set(clicked_item)

                context_menu_font = (FONT_FAMILY, int(16 * self.dpi_scale * self.zoom_factor))
                menu = tk.Menu(detail_window, tearoff=0, font=context_menu_font)
                icon_detail = self.icons.button('clipboard', self.colors['text_primary'])
                icon_trash_menu = self.icons.button('trash', self.colors['text_primary'])
                icon_export_menu = self.icons.button('export', self.colors['text_primary'])

                def show_detail():
                    vals = tree.item(clicked_item, 'values')
                    if vals:
                        for c in filtered_ref[0]:
                            if c.get('name') == vals[0]:
                                d_win = tk.Toplevel(detail_window)
                                d_win.title("候选人详情")
                                d_win.transient(detail_window)
                                d_win.withdraw()
                                d_title = f"姓名：{vals[0]} | 匹配分：{vals[4]} | {vals[6]}"
                                ttk.Label(d_win, text=d_title, font=(FONT_FAMILY, 16),
                                         foreground=self.colors['primary']).pack(pady=15)
                                tw = tk.Text(d_win, wrap='word', font=(FONT_FAMILY, 14))
                                tw.pack(fill='both', expand=True, padx=20, pady=10)
                                tw.insert('1.0', self._format_candidate_detail(c))
                                self.bind_text_context_menu(tw, editable=False)
                                d_win.update_idletasks()
                                px = self.root.winfo_x()
                                py = self.root.winfo_y()
                                pw = self.root.winfo_width()
                                ph = self.root.winfo_height()
                                dw, dh = 700, 580
                                dx = px + (pw - dw) // 2
                                dy = py + (ph - dh) // 2
                                d_win.geometry(f"{dw}x{dh}+{max(0, dx)}+{max(0, dy)}")
                                d_win.deiconify()
                                break

                def remove_candidate():
                    if not messagebox.askyesno("确认删除", "确定要移除该候选人吗？"):
                        return
                    vals = tree.item(clicked_item, 'values')
                    name = vals[0]
                    score = vals[4]
                    # 通过 name+score 精确定位候选人，获取 geek_id
                    target_geek_id = None
                    for c in filtered_ref[0]:
                        if c.get('name') == name and str(c.get('match_score', '')) == str(score):
                            target_geek_id = c.get('geek_id')
                            break
                    if not target_geek_id:
                        return
                    # 从当前过滤列表中移除（用 geek_id 精确匹配，避免同名误删）
                    filtered_ref[0] = [c for c in filtered_ref[0] if c.get('geek_id') != target_geek_id]
                    # 从 JSON 中移除
                    if CANDIDATES_PATH.exists():
                        with open(CANDIDATES_PATH, 'r', encoding='utf-8') as f:
                            candidates = json.load(f)
                        candidates = [c for c in candidates if c.get('geek_id') != target_geek_id]
                        with open(CANDIDATES_PATH, 'w', encoding='utf-8') as f:
                            json.dump(candidates, f, ensure_ascii=False, indent=2)
                    # 从表格中移除行
                    tree.delete(clicked_item)
                    # 更新弹窗内统计标签
                    new_total = len(filtered_ref[0])
                    new_greeted = len([c for c in filtered_ref[0] if c.get('greet_sent', False)])
                    count_label_ref[0].config(text=f"共 {new_total} 人，已打招呼 {new_greeted} 人")
                    # 刷新主界面统计
                    self.refresh_home_stats()
                    self.refresh_results()
                    # 保持弹窗焦点
                    detail_window.lift()

                def export_selected():
                    selection = tree.selection()
                    if not selection:
                        messagebox.showwarning("警告", "请先选择要导出的候选人")
                        return
                    selected_data = []
                    for sel_item in selection:
                        sv = tree.item(sel_item, 'values')
                        for c in filtered_ref[0]:
                            if c.get('name') == sv[0]:
                                selected_data.append(c)
                                break
                    file_path = filedialog.asksaveasfilename(
                        title="保存选中的候选人",
                        defaultextension=".json",
                        filetypes=[("JSON 文件", "*.json"), ("所有文件", "*.*")],
                        initialfile=f"selected_candidates_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                    )
                    if file_path:
                        with open(file_path, 'w', encoding='utf-8') as f:
                            json.dump(selected_data, f, ensure_ascii=False, indent=2)
                        messagebox.showinfo("成功", f"已导出 {len(selected_data)} 名候选人到：\n{file_path}")

                menu.add_command(label=" 查看详情", image=icon_detail, compound=tk.LEFT, command=show_detail)
                menu.add_command(label=" 移除此人", image=icon_trash_menu, compound=tk.LEFT, command=remove_candidate)
                menu.add_separator()
                menu.add_command(label=" 导出选中", image=icon_export_menu, compound=tk.LEFT, command=export_selected)
                menu._icon_refs = [icon_detail, icon_trash_menu, icon_export_menu]
                menu.tk_popup(event.x_root, event.y_root)

            tree.bind('<Button-3>', on_detail_right_click)

            # 填充数据
            for c in sorted(filtered, key=lambda x: x.get('match_score', 0), reverse=True):
                score = c.get('match_score', 0)
                level = "强烈推荐" if score >= 75 else ("推荐" if score >= 65 else "待定")
                status = "已招呼" if c.get('greet_sent', False) else "未招呼"
                salary, exp = self._parse_salary_exp(c.get('summary', ''))
                ai_adj = c.get('llm_adjustment')
                if ai_adj is not None and c.get('llm_evaluated'):
                    ai_text = f"+{ai_adj}" if ai_adj > 0 else str(ai_adj)
                else:
                    ai_text = "—"

                tree.insert("", "end", values=(
                    c.get('name', ''),
                    exp,
                    salary,
                    c.get('skill_match_ratio', ''),
                    score,
                    ai_text,
                    level,
                    status
                ))

            # 窗口居中
            self._center_window(detail_window, window_width, window_height)

        except Exception as e:
            messagebox.showerror("错误", f"显示详情失败：{e}")

    def show_result_stat_detail(self, stat_type):
        """显示筛选结果统计详情（新指标）"""
        try:
            if not CANDIDATES_PATH.exists():
                messagebox.showinfo("提示", "暂无候选人数据")
                return

            with open(CANDIDATES_PATH, 'r', encoding='utf-8') as f:
                candidates = json.load(f)

            # 岗位过滤
            if hasattr(self, 'result_job_var'):
                selected_job = self.result_job_var.get()
                if selected_job != "全部岗位":
                    candidates = [c for c in candidates if c.get('job_name', '') == selected_job.replace(" ", "")]

            # 根据类型筛选候选人
            if stat_type == 'passed':
                # 通过筛选：强烈推荐 + 推荐
                title = "通过筛选"
                filtered = [c for c in candidates if c.get('match_score', 0) >= 65]
                # 只显示已打招呼的
                detail_type = 'greeted'
            elif stat_type == 'strong':
                # 强烈推荐
                title = "强烈推荐"
                filtered = [c for c in candidates if c.get('match_score', 0) >= 75]
                detail_type = 'all'
            elif stat_type == 'recommended':
                # 推荐
                title = "推荐"
                filtered = [c for c in candidates if 65 <= c.get('match_score', 0) < 75]
                detail_type = 'all'
            else:
                return

            # 计算总数和已打招呼数
            total = len(filtered)
            greeted = [c for c in filtered if c.get('greet_sent', False)]
            greeted_count = len(greeted)

            if total == 0:
                messagebox.showinfo("提示", f"{title}：暂无数据")
                return

            # 创建详情窗口
            detail_window = tk.Toplevel(self.root)
            detail_window.transient(self.root)
            detail_window.grab_set()
            detail_window.title(title)

            # 设置固定大小并相对主窗口居中
            window_width = 1000
            window_height = 650
            detail_window.geometry(f"{window_width}x{window_height}")
            self._center_window(detail_window, window_width, window_height)

            # 标题
            title_label = ttk.Label(detail_window, text=title,
                                   font=(FONT_FAMILY, int(18 * self.dpi_scale * self.zoom_factor)),
                                   foreground=self.colors['primary'])
            title_label.pack(fill="x", padx=int(20 * self.dpi_scale * self.zoom_factor), pady=(int(15 * self.dpi_scale * self.zoom_factor), 0))

            # 统计信息
            count_label = ttk.Label(detail_window, text=f"共 {total} 人，已打招呼 {greeted_count} 人",
                                   font=(FONT_FAMILY, int(12 * self.dpi_scale * self.zoom_factor)),
                                   foreground=self.colors['text_secondary'])
            count_label.pack(anchor="w", padx=int(20 * self.dpi_scale * self.zoom_factor), pady=(int(5 * self.dpi_scale * self.zoom_factor), 0))
            count_label_ref = [count_label]

            # 表格容器
            table_frame = ttk.Frame(detail_window, style='Card.TFrame')
            table_frame.pack(fill="both", expand=True, padx=int(20 * self.dpi_scale * self.zoom_factor), pady=int(15 * self.dpi_scale * self.zoom_factor))

            # 创建表格
            columns = ("name", "exp", "salary", "skills", "score", "ai_eval", "level", "status")
            tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=18)

            tree.heading("name", text="姓名")
            tree.heading("exp", text="工作年限")
            tree.heading("salary", text="薪资")
            tree.heading("skills", text="技能匹配")
            tree.heading("score", text="匹配分")
            tree.heading("ai_eval", text="AI评估")
            tree.heading("level", text="推荐指数")
            tree.heading("status", text="状态")

            # 设置列宽
            tree.column("name", width=80, anchor='center')
            tree.column("exp", width=100, anchor='center')
            tree.column("salary", width=100, anchor='center')
            tree.column("skills", width=140, anchor='center')
            tree.column("score", width=70, anchor='center')
            tree.column("ai_eval", width=70, anchor='center')
            tree.column("level", width=120, anchor='center')
            tree.column("status", width=70, anchor='center')

            # 设置表格字体和样式（与主界面一致）
            tree_style = ttk.Style()
            tree_style.configure("Detail.Treeview",
                                font=self.font_table,
                                rowheight=int(UI_CONFIG['treeview_rowheight'] * self.dpi_scale * self.zoom_factor))
            tree_style.configure("Detail.Treeview.Heading",
                                font=self.font_button)
            tree.configure(style="Detail.Treeview")

            # 添加滚动条
            scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
            tree.configure(yscrollcommand=scrollbar.set)

            tree.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")

            # 填充数据
            for c in sorted(filtered, key=lambda x: x.get('match_score', 0), reverse=True):
                score = c.get('match_score', 0)
                level = "强烈推荐" if score >= 75 else ("推荐" if score >= 65 else "待定")
                status = "已招呼" if c.get('greet_sent', False) else "未招呼"
                salary, exp = self._parse_salary_exp(c.get('summary', ''))
                ai_adj = c.get('llm_adjustment')
                if ai_adj is not None and c.get('llm_evaluated'):
                    ai_text = f"+{ai_adj}" if ai_adj > 0 else str(ai_adj)
                else:
                    ai_text = "—"

                tree.insert("", "end", values=(
                    c.get('name', ''),
                    exp,
                    salary,
                    c.get('skill_match_ratio', ''),
                    score,
                    ai_text,
                    level,
                    status
                ))

            # 绑定右键菜单 - 与筛选结果页一致
            filtered_ref = [filtered]

            def on_result_detail_right_click(event):
                clicked_item = tree.identify_row(event.y)
                if not clicked_item:
                    return
                tree.selection_set(clicked_item)

                context_menu_font = (FONT_FAMILY, int(16 * self.dpi_scale * self.zoom_factor))
                menu = tk.Menu(detail_window, tearoff=0, font=context_menu_font)
                icon_detail = self.icons.button('clipboard', self.colors['text_primary'])
                icon_trash_menu = self.icons.button('trash', self.colors['text_primary'])
                icon_export_menu = self.icons.button('export', self.colors['text_primary'])

                def show_detail():
                    vals = tree.item(clicked_item, 'values')
                    if vals:
                        for c in filtered_ref[0]:
                            if c.get('name') == vals[0]:
                                d_win = tk.Toplevel(detail_window)
                                d_win.title("候选人详情")
                                d_win.transient(detail_window)
                                d_win.withdraw()
                                d_title = f"姓名：{vals[0]} | 匹配分：{vals[4]} | {vals[6]}"
                                ttk.Label(d_win, text=d_title, font=(FONT_FAMILY, 16),
                                         foreground=self.colors['primary']).pack(pady=15)
                                tw = tk.Text(d_win, wrap='word', font=(FONT_FAMILY, 14))
                                tw.pack(fill='both', expand=True, padx=20, pady=10)
                                tw.insert('1.0', self._format_candidate_detail(c))
                                self.bind_text_context_menu(tw, editable=False)
                                d_win.update_idletasks()
                                px = self.root.winfo_x()
                                py = self.root.winfo_y()
                                pw = self.root.winfo_width()
                                ph = self.root.winfo_height()
                                dw, dh = 700, 580
                                dx = px + (pw - dw) // 2
                                dy = py + (ph - dh) // 2
                                d_win.geometry(f"{dw}x{dh}+{max(0, dx)}+{max(0, dy)}")
                                d_win.deiconify()
                                break

                def remove_candidate():
                    if not messagebox.askyesno("确认删除", "确定要移除该候选人吗？"):
                        return
                    vals = tree.item(clicked_item, 'values')
                    name = vals[0]
                    score = vals[4]
                    target_geek_id = None
                    for c in filtered_ref[0]:
                        if c.get('name') == name and str(c.get('match_score', '')) == str(score):
                            target_geek_id = c.get('geek_id')
                            break
                    if not target_geek_id:
                        return
                    filtered_ref[0] = [c for c in filtered_ref[0] if c.get('geek_id') != target_geek_id]
                    if CANDIDATES_PATH.exists():
                        with open(CANDIDATES_PATH, 'r', encoding='utf-8') as f:
                            candidates_all = json.load(f)
                        candidates_all = [c for c in candidates_all if c.get('geek_id') != target_geek_id]
                        with open(CANDIDATES_PATH, 'w', encoding='utf-8') as f:
                            json.dump(candidates_all, f, ensure_ascii=False, indent=2)
                    tree.delete(clicked_item)
                    # 更新弹窗内统计标签
                    new_total = len(filtered_ref[0])
                    new_greeted = len([c for c in filtered_ref[0] if c.get('greet_sent', False)])
                    count_label_ref[0].config(text=f"共 {new_total} 人，已打招呼 {new_greeted} 人")
                    # 刷新主界面
                    self.refresh_results()
                    # 保持弹窗焦点
                    detail_window.lift()

                def export_selected():
                    selection = tree.selection()
                    if not selection:
                        messagebox.showwarning("警告", "请先选择要导出的候选人")
                        return
                    selected_data = []
                    for sel_item in selection:
                        sv = tree.item(sel_item, 'values')
                        for c in filtered_ref[0]:
                            if c.get('name') == sv[0]:
                                selected_data.append(c)
                                break
                    file_path = filedialog.asksaveasfilename(
                        title="保存选中的候选人",
                        defaultextension=".json",
                        filetypes=[("JSON 文件", "*.json"), ("所有文件", "*.*")],
                        initialfile=f"selected_candidates_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                    )
                    if file_path:
                        with open(file_path, 'w', encoding='utf-8') as f:
                            json.dump(selected_data, f, ensure_ascii=False, indent=2)
                        messagebox.showinfo("成功", f"已导出 {len(selected_data)} 名候选人到：\n{file_path}")

                menu.add_command(label=" 查看详情", image=icon_detail, compound=tk.LEFT, command=show_detail)
                menu.add_command(label=" 移除此人", image=icon_trash_menu, compound=tk.LEFT, command=remove_candidate)
                menu.add_separator()
                menu.add_command(label=" 导出选中", image=icon_export_menu, compound=tk.LEFT, command=export_selected)
                menu._icon_refs = [icon_detail, icon_trash_menu, icon_export_menu]
                menu.tk_popup(event.x_root, event.y_root)

            tree.bind('<Button-3>', on_result_detail_right_click)

        except Exception as e:
            messagebox.showerror("错误", f"显示详情失败：{e}")

    def load_config(self):
        """加载岗位配置"""
        if CONFIG_PATH.exists():
            try:
                with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    # 支持新旧两种格式
                    if "job_requirements" in config:
                        self.job_rules = config["job_requirements"]
                    elif "jobs" in config:
                        self.job_rules = config["jobs"]
                    else:
                        self.job_rules = {}
            except Exception as e:
                # 配置文件损坏时尝试从备份恢复
                if CONFIG_BACKUP_PATH.exists():
                    try:
                        shutil.copy(CONFIG_BACKUP_PATH, CONFIG_PATH)
                        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                            config = json.load(f)
                            if "job_requirements" in config:
                                self.job_rules = config["job_requirements"]
                            elif "jobs" in config:
                                self.job_rules = config["jobs"]
                    except (json.JSONDecodeError, IOError) as e:
                        print(f"从备份恢复配置失败：{e}")
                        self.job_rules = {}
                else:
                    self.job_rules = {}

    def load_api_config(self):
        """加载 API 配置 - 从系统钥匙串读取加密的 API Key（按服务商管理）"""
        if API_CONFIG_PATH.exists():
            try:
                with open(API_CONFIG_PATH, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    # 确保所有必要字段都存在（兼容旧版本配置文件）
                    self.api_config = {
                        "api_provider": config.get("api_provider", "deepseek"),
                        "api_key": "",  # API Key 从 keyring 读取
                        "base_url": config.get("base_url", "https://api.deepseek.com"),
                        "model": config.get("model", "deepseek-chat"),
                        "saved_models": config.get("saved_models", []),
                        "providers": config.get("providers", {})
                    }

                    # 从 keyring 读取当前服务商的 API Key
                    current_provider = self.api_config.get("api_provider", "")
                    if current_provider:
                        encrypted_key = get_api_key(current_provider)
                        if encrypted_key:
                            self.api_config["api_key"] = encrypted_key

                    # 从 keyring 读取所有 saved_models 的 API Key（按服务商）
                    # 同时清理文件中可能已泄露的明文 Key（防御性清理）
                    for model_config in self.api_config["saved_models"]:
                        model_config.pop("api_key", None)
                        model_config.pop("api_key_ref", None)

                    # 检测是否有 saved_models 但 keyring 中无对应 API Key（新电脑场景）
                    if self.api_config["saved_models"]:
                        has_missing_key = False
                        for m in self.api_config["saved_models"]:
                            provider = m.get("api_provider", "")
                            if provider and not get_api_key(provider):
                                has_missing_key = True
                                break
                        if has_missing_key:
                            self.api_config["needs_reconfigure"] = True
                            print("[提示] 检测到已保存的模型配置，但 API Key 未配置（可能是新电脑）")
                            print("[提示] 请在「岗位配置」->「API 配置」中重新输入 API Key 并保存")
            except Exception as e:
                print(f"加载 API 配置失败：{e}")
                self.api_config = self._default_api_config()
        else:
            self.api_config = self._default_api_config()

    def _default_api_config(self):
        """返回默认 API 配置"""
        return {
            "api_provider": "deepseek",
            "api_key": "",
            "base_url": "https://api.deepseek.com",
            "model": "deepseek-chat",
            "saved_models": [],
            "providers": {}
        }

    def _sanitize_config_for_save(self, config):
        """移除所有 api_key 字段（顶层 + saved_models 内嵌），返回可安全写入磁盘的副本"""
        clean = {k: v for k, v in config.items() if k != "api_key"}
        if "saved_models" in clean:
            clean["saved_models"] = [
                {k: v for k, v in m.items() if k not in ("api_key", "api_key_ref")}
                for m in clean["saved_models"]
            ]
        return clean

    def delete_selected_model(self):
        """删除选中的模型"""
        selection = self.model_list_tree.selection()
        if not selection:
            messagebox.showwarning("警告", "请先选择要删除的模型")
            return

        if not messagebox.askyesno("确认", "确定要删除选中的模型吗？"):
            return

        # 获取选中的模型信息
        item = self.model_list_tree.item(selection[0])
        model_name = item['values'][0]
        provider = item['values'][1]

        # 从列表移除
        if hasattr(self, 'saved_models'):
            self.saved_models = [m for m in self.saved_models if m.get("model") != model_name]

        # 同步更新 api_config 并持久化到文件
        if hasattr(self, 'api_config') and self.api_config:
            # 检查是否删除了当前正在使用的模型
            current_model = self.api_config.get("model", "")
            if current_model == model_name:
                # 清空当前模型配置
                self.api_config["model"] = ""
                self.api_config["api_provider"] = ""
                self.api_config["api_key"] = ""
                self.api_config["base_url"] = ""
                # 清空 UI 输入
                self.api_provider_var.set("qwen")
                self.api_key_var.set("")
                self.api_base_url_var.set("")
                self.api_model_var.set("")
                self.update_current_model_display()
            self.api_config["saved_models"] = self.saved_models
            try:
                save_config = self._sanitize_config_for_save(self.api_config)
                with open(API_CONFIG_PATH, 'w', encoding='utf-8') as f:
                    json.dump(save_config, f, ensure_ascii=False, indent=4)
            except Exception as e:
                print(f"保存配置失败：{e}")

        # 刷新显示
        self.load_saved_models_to_tree()
        self.api_status_label.config(text=f"✓ 已删除模型 {model_name}", foreground=self.colors['success'])

    def use_selected_model(self):
        """使用选中的模型 - 从系统钥匙串读取加密的 API Key（按服务商管理）"""
        selection = self.model_list_tree.selection()
        if not selection:
            messagebox.showwarning("警告", "请先选择要使用的模型")
            return

        # 获取选中的模型信息
        item = self.model_list_tree.item(selection[0])
        model_name = item['values'][0]
        provider = item['values'][1]

        # 查找对应的配置
        model_config = None
        for saved in self.saved_models:
            if saved.get("model") == model_name:
                model_config = saved
                break

        if model_config:
            # 从系统钥匙串读取该服务商的 API Key
            saved_api_key = get_api_key(provider)

            if not saved_api_key:
                messagebox.showwarning("警告",
                    f"模型 '{model_name}' 的 API Key 未在系统钥匙串中找到\n\n"
                    f"可能原因：\n"
                    f"1. 系统钥匙串被清理\n"
                    f"2. 配置文件来自其他电脑\n\n"
                    f"请重新输入 API Key 并保存该模型")
                return

            # 更新当前使用的模型配置（包括 API Key）
            self.api_provider_var.set(provider)
            self.api_key_var.set(saved_api_key)
            self.api_base_url_var.set(model_config.get("base_url", ""))
            self.api_model_var.set(model_name)

            # 更新 api_config 中的所有字段
            if hasattr(self, 'api_config') and self.api_config:
                self.api_config["model"] = model_name
                self.api_config["api_provider"] = provider
                self.api_config["api_key"] = saved_api_key
                self.api_config["base_url"] = model_config.get("base_url", "")

            # 更新显示
            self.update_current_model_display()
            self.load_saved_models_to_tree()

            # 保存到文件（排除 api_key，Key 仅存 keyring）
            try:
                save_config = self._sanitize_config_for_save(self.api_config)
                with open(API_CONFIG_PATH, 'w', encoding='utf-8') as f:
                    json.dump(save_config, f, ensure_ascii=False, indent=4)
            except Exception as e:
                print(f"保存配置失败：{e}")

            self.api_status_label.config(text=f"✓ 已切换到 {provider}/{model_name}", foreground=self.colors['success'])
            messagebox.showinfo("切换成功", f"已切换到模型：\n\n{provider} / {model_name}")
        else:
            messagebox.showerror("错误", f"未找到模型 '{model_name}' 的配置信息")

    def save_api_config(self):
        """保存 API 配置 - API Key 按服务商加密存储到系统钥匙串"""
        try:
            provider = self.api_provider_var.get().strip()
            model_name = self.api_model_var.get().strip()
            api_key = self.api_key_var.get().strip()
            base_url = self.api_base_url_var.get().strip()

            if not model_name:
                messagebox.showwarning("警告", "请输入模型名称")
                return
            if not api_key:
                messagebox.showwarning("警告", "请输入 API Key")
                return
            if not base_url:
                messagebox.showwarning("警告", "请输入 Base URL")
                return

            # 按服务商统一存储 API Key（同一服务商的所有模型共享一个 Key）
            save_api_key(provider, api_key)

            # 构建当前配置
            self.api_config = {
                "api_provider": provider,
                "base_url": base_url,
                "model": model_name,
                "saved_models": getattr(self, 'saved_models', []),
                "providers": self.api_config.get("providers", {})
            }

            # 检查当前模型是否已存在于列表
            model_exists = False
            for m in self.api_config["saved_models"]:
                if m.get("model") == model_name and m.get("api_provider") == provider:
                    # 更新已存在模型的配置
                    m["api_provider"] = provider
                    m["base_url"] = base_url
                    model_exists = True
                    break

            if not model_exists:
                # 添加新模型
                self.api_config["saved_models"].append({
                    "api_provider": provider,
                    "base_url": base_url,
                    "model": model_name
                })

            with open(API_CONFIG_PATH, 'w', encoding='utf-8') as f:
                json.dump(self._sanitize_config_for_save(self.api_config), f, ensure_ascii=False, indent=4)

            # 更新内存中的模型列表
            self.saved_models = self.api_config["saved_models"]

            # 刷新列表显示
            self.load_saved_models_to_tree()

            # 更新当前模型显示
            self.update_current_model_display()

            self.api_status_label.config(text="✓ 配置已保存并添加到列表", foreground=self.colors['success'])

            # 保存成功后清除"API Key 未配置"警示卡片
            if getattr(self, 'reconfig_card', None) and self.reconfig_card.winfo_exists():
                self.reconfig_card.destroy()
                self.reconfig_card = None

            messagebox.showinfo("成功", f"API 配置已保存\n模型 {provider}/{model_name} 已添加到已保存模型列表\n\nAPI Key 已按服务商加密存储（同一服务商的模型共享）")
        except Exception as e:
            self.api_status_label.config(text=f"✗ 保存失败：{e}", foreground=self.colors['danger'])
            messagebox.showerror("错误", f"保存 API 配置失败：{e}")

    def on_api_provider_changed(self, event):
        """API 服务商改变时更新默认配置"""
        provider = self.api_provider_var.get()

        # 主流服务商默认配置
        provider_defaults = {
            "qwen": {
                "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                "model": "qwen-plus"
            },
            "deepseek": {
                "base_url": "https://api.deepseek.com",
                "model": "deepseek-chat"
            },
            "kimi": {
                "base_url": "https://api.moonshot.cn/v1",
                "model": "moonshot-v1-8k"
            },
            "zhipu": {
                "base_url": "https://open.bigmodel.cn/api/paas/v4",
                "model": "glm-4"
            },
            "minimax": {
                "base_url": "https://api.minimax.chat/v1",
                "model": "abab6.5s-chat"
            },
            "xiaomi": {
                "base_url": "https://api.ai.xiaomi.com/v1",
                "model": "mi-deep-thinking"
            },
            "stepfun": {
                "base_url": "https://api.stepfun.com/v1",
                "model": "step-1-8k"
            },
            "openai": {
                "base_url": "https://api.openai.com/v1",
                "model": "gpt-4o-mini"
            },
            "anthropic": {
                "base_url": "https://api.anthropic.com/v1",
                "model": "claude-sonnet-4-20250514"
            },
            "custom": {
                "base_url": "",
                "model": ""
            }
        }

        if provider in provider_defaults:
            config = provider_defaults[provider]
            self.api_base_url_var.set(config["base_url"])
            self.api_model_var.set(config["model"])

    def fetch_model_list(self):
        """获取服务商的模型列表 - 使用当前输入的 API Key 和 Base URL"""
        import requests
        import certifi
        import json

        api_key = self.api_key_var.get().strip()
        base_url = self.api_base_url_var.get().strip()
        provider = self.api_provider_var.get()

        if not api_key:
            messagebox.showwarning("警告", "请先输入 API Key")
            return

        if not base_url:
            messagebox.showwarning("警告", "请先输入 Base URL")
            return

        # 显示加载中状态
        self.api_status_label.config(text="⏳ 正在获取模型列表...", foreground=self.colors['warning'])
        self.root.update()

        def fetch_thread():
            try:
                # 构建模型列表 API 端点
                # 大部分服务商兼容 OpenAI 格式：GET /v1/models
                models_url = f"{base_url.rstrip('/')}/models"

                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "User-Agent": "BossResumeFilter/1.0"
                }

                # 发送请求，超时 15 秒
                response = requests.get(
                    models_url,
                    headers=headers,
                    timeout=15,
                    verify=certifi.where()
                )

                if response.status_code == 200:
                    data = response.json()

                    # 解析模型列表（兼容 OpenAI 格式）
                    raw_models = []
                    if "data" in data:
                        # OpenAI / DeepSeek / Kimi / 智谱等格式
                        for item in data["data"]:
                            if isinstance(item, dict):
                                model_id = item.get("id", "")
                                if model_id:
                                    raw_models.append(model_id)
                            elif isinstance(item, str):
                                raw_models.append(item)
                    elif "models" in data:
                        # 部分服务商格式
                        raw_models = data["models"]

                    if raw_models:
                        # 过滤非聊天模型
                        # 排除 embedding、rerank、tts、whisper 等非对话模型
                        exclude_keywords = ['embedding', 'embed-', 'rerank', 'tts-', 'whisper',
                                           'similarity', 'moderation', 'dap', 'tokenizer']
                        chat_models = []
                        for model_id in raw_models:
                            model_lower = model_id.lower()
                            # 检查是否包含排除关键词
                            is_excluded = any(kw in model_lower for kw in exclude_keywords)
                            if not is_excluded:
                                chat_models.append(model_id)

                        # 去重并排序
                        models = sorted(list(set(chat_models)))
                        filtered_count = len(raw_models) - len(models)

                        # 创建选择对话框
                        def show_model_dialog():
                            dialog = tk.Toplevel(self.root)
                            dialog.title("选择模型")
                            dialog.transient(self.root)
                            dialog.withdraw()  # 先隐藏，布局完成后再定位显示

                            # 对话框大小
                            dialog_width = 750
                            dialog_height = 680
                            dialog.resizable(True, True)
                            dialog.minsize(500, 400)

                            # 标题
                            title_text = f"{provider} - 可用模型 ({len(models)} 个)"
                            info_label = ttk.Label(dialog, text=title_text,
                                                   font=self.font_section)
                            info_label.pack(pady=(15, 0))

                            # 过滤说明
                            filter_note = "已自动过滤 embedding、rerank、tts 等非聊天模型" if filtered_count > 0 else ""
                            if filter_note:
                                note_label = ttk.Label(dialog, text=filter_note,
                                                       font=(FONT_FAMILY, int(11 * self.dpi_scale * self.zoom_factor)),
                                                       foreground=self.colors['warning'])
                                note_label.pack(pady=(4, 12))

                            # 模型列表框
                            listbox_frame = ttk.Frame(dialog)
                            listbox_frame.pack(fill="both", expand=True, padx=20, pady=10)

                            listbox = tk.Listbox(listbox_frame, font=self.font_button, height=10)
                            scrollbar = ttk.Scrollbar(listbox_frame, orient="vertical", command=listbox.yview)
                            listbox.configure(yscrollcommand=scrollbar.set)

                            scrollbar.pack(side="right", fill="y")
                            listbox.pack(side="left", fill="both", expand=True)

                            # 填充模型列表
                            for model in models:
                                listbox.insert("end", model)

                            # 按钮行
                            btn_frame = ttk.Frame(dialog)
                            btn_frame.pack(fill="x", padx=25, pady=(10, 15))

                            # 阻止鼠标滚轮事件传播到父窗口
                            def _on_dialog_mousewheel(event):
                                if event.delta > 0:
                                    listbox.yview_scroll(-1, "units")
                                else:
                                    listbox.yview_scroll(1, "units")
                                return "break"

                            dialog.bind("<MouseWheel>", _on_dialog_mousewheel)
                            listbox.bind("<MouseWheel>", _on_dialog_mousewheel)

                            def on_select(event=None):
                                selection = listbox.curselection()
                                if selection:
                                    selected_model = listbox.get(selection[0])
                                    self.api_model_var.set(selected_model)
                                    self.api_status_label.config(
                                        text=f"✓ 已选择 {selected_model}",
                                        foreground=self.colors['success']
                                    )
                                    dialog.destroy()

                            def on_double_click(event):
                                selection = listbox.curselection()
                                if selection:
                                    selected_model = listbox.get(selection[0])
                                    self.api_model_var.set(selected_model)
                                    dialog.destroy()
                                    self.api_status_label.config(text="⏳ 正在测试连接...", foreground=self.colors['warning'])
                                    self.root.after(300, self.test_api_connection)

                            # 按钮布局（居中）
                            btn_inner = ttk.Frame(btn_frame)
                            btn_inner.pack()
                            ttk.Button(btn_inner, text="确定", command=on_select, width=12).pack(side="left", padx=8)
                            ttk.Button(btn_inner, text="取消", command=dialog.destroy, width=12).pack(side="left", padx=8)

                            # 绑定回车键和双击
                            dialog.bind("<Return>", lambda e: on_select())
                            listbox.bind("<Double-Button-1>", on_double_click)

                            # 默认选中第一个
                            if models:
                                listbox.selection_set(0)
                                listbox.see(0)

                            # 相对父窗口居中（不受多显示器DPI差异影响）
                            dialog.update_idletasks()
                            px = self.root.winfo_x()
                            py = self.root.winfo_y()
                            pw = self.root.winfo_width()
                            ph = self.root.winfo_height()
                            x = px + (pw - dialog_width) // 2
                            y = py + (ph - dialog_height) // 2
                            dialog.geometry(f"{dialog_width}x{dialog_height}+{max(0, x)}+{max(0, y)}")
                            dialog.deiconify()
                            dialog.grab_set()
                            dialog.wait_window()

                        self.root.after(0, lambda: self.api_status_label.config(
                            text=f"✓ 找到 {len(models)} 个模型",
                            foreground=self.colors['success']
                        ))
                        self.root.after(100, show_model_dialog)
                    else:
                        self.root.after(0, lambda: self.api_status_label.config(
                            text="⚠️ 未找到模型列表",
                            foreground=self.colors['warning']
                        ))
                        self.root.after(0, lambda: messagebox.showwarning(
                            "未找到模型",
                            f"API 返回的数据中没有模型列表\n\n响应内容：{json.dumps(data, ensure_ascii=False)[:500]}"
                        ))
                elif response.status_code == 401:
                    self.root.after(0, lambda: self.api_status_label.config(
                        text="✗ 认证失败",
                        foreground=self.colors['danger']
                    ))
                    self.root.after(0, lambda: messagebox.showerror(
                        "认证失败",
                        "API Key 无效或已过期\n\n请检查 API Key 是否正确"
                    ))
                elif response.status_code == 404:
                    self.root.after(0, lambda: self.api_status_label.config(
                        text="✗ 接口不存在",
                        foreground=self.colors['danger']
                    ))
                    self.root.after(0, lambda: messagebox.showwarning(
                        "接口不支持",
                        f"该服务商不支持 /models 接口获取模型列表\n\n"
                        f"HTTP 状态码：404\n\n"
                        f"建议：\n"
                        f"• 手动输入模型名称\n"
                        f"• 参考服务商文档获取可用模型"
                    ))
                else:
                    self.root.after(0, lambda: self.api_status_label.config(
                        text=f"✗ 请求失败 ({response.status_code})",
                        foreground=self.colors['danger']
                    ))
                    self.root.after(0, lambda: messagebox.showerror(
                        "请求失败",
                        f"HTTP 状态码：{response.status_code}\n\n"
                        f"响应：{response.text[:300]}"
                    ))

            except requests.exceptions.Timeout:
                self.root.after(0, lambda: self.api_status_label.config(
                    text="⏱️ 请求超时",
                    foreground=self.colors['warning']
                ))
                self.root.after(0, lambda: messagebox.showwarning(
                    "请求超时",
                    "获取模型列表超时\n\n"
                    "可能原因：\n"
                    "• 网络连接不稳定\n"
                    "• 服务商不支持模型列表接口\n"
                    "• 需要配置代理"
                ))
            except requests.exceptions.ConnectionError as e:
                self.root.after(0, lambda: self.api_status_label.config(
                    text="✗ 连接失败",
                    foreground=self.colors['danger']
                ))
                self.root.after(0, lambda m=str(e)[:200]: messagebox.showerror(
                    "连接失败",
                    f"无法连接到 API 服务器\n\n"
                    f"错误详情：{m}"
                ))
            except Exception as e:
                self.root.after(0, lambda: self.api_status_label.config(
                    text="✗ 请求失败",
                    foreground=self.colors['danger']
                ))
                self.root.after(0, lambda m=str(e)[:200]: messagebox.showerror(
                    "请求失败",
                    f"获取模型列表时发生错误\n\n"
                    f"错误详情：{m}"
                ))

        threading.Thread(target=fetch_thread, daemon=True).start()

    def toggle_api_key_visibility(self):
        """切换 API Key 明文/密文显示"""
        if self.api_key_show_var.get():
            # 当前是明文，切换为密文
            self.api_key_entry.configure(show="*")
            self.api_key_toggle_btn.configure(image=self.api_key_toggle_btn._icon_eye)
            self.api_key_show_var.set(False)
        else:
            # 当前是密文，切换为明文
            self.api_key_entry.configure(show="")
            self.api_key_toggle_btn.configure(image=self.api_key_toggle_btn._icon_eye_off)
            self.api_key_show_var.set(True)

    def test_api_connection(self):
        """测试 API 连接 - 高可用版本：每次全新连接 + 并行双策略 + 宽松超时"""
        api_key = self.api_key_var.get().strip()
        base_url = self.api_base_url_var.get().strip()
        model = self.api_model_var.get().strip()

        if not api_key:
            messagebox.showwarning("警告", "请先输入 API Key")
            return

        if not base_url:
            messagebox.showwarning("警告", "请先输入 Base URL")
            return

        if not model:
            messagebox.showwarning("警告", "请先输入模型名称")
            return

        # 显示测试中状态
        self.api_status_label.config(text="⏳ 正在验证...", foreground=self.colors['warning'])
        self.root.update()

        def test_thread():
            import socket
            start_time = time.time()

            # 关键优化：每次测试使用全新 Session，避免 stale connection
            # 这是 50% 失败率的根本原因
            import requests
            import certifi

            # 解析 URL 获取主机，用于 DNS 预检查
            parsed = urlparse(base_url)
            hostname = parsed.hostname
            port = parsed.port or (443 if parsed.scheme == 'https' else 80)

            # === 阶段 1: DNS 解析检查（快速失败）===
            try:
                ip_addr = socket.gethostbyname(hostname)
                # DNS 解析成功，继续
            except socket.gaierror:
                elapsed = time.time() - start_time
                self.root.after(0, lambda: self.api_status_label.config(text="✗ DNS 解析失败", foreground=self.colors['danger']))
                self.root.after(0, lambda: messagebox.showerror(
                    "DNS 解析失败",
                    f"无法解析域名：{hostname}\n\n"
                    f"请检查：\n"
                    f"• Base URL 中的域名是否正确\n"
                    f"• DNS 服务器是否可用\n"
                    f"• 是否需要配置 hosts 文件"
                ))
                return

            # === 阶段 2: TCP 连接检查（可选，快速判断网络可达性）===
            # 国内 API 跳过此步（减少一次握手），海外 API 执行
            is_domestic = any(dom in base_url.lower() for dom in ['aliyun', 'tencent', 'baidu', 'volcengine', 'deepseek', 'zhipu', 'stepfun', 'moonshot', 'minimax', 'xiaomi'])

            # === 阶段 3: HTTPS 请求（宽松超时）===
            # 关键：每次使用全新 Session + 禁用 keep-alive，确保连接新鲜
            session = requests.Session()

            # 不配置 HTTPAdapter，让 requests 使用默认行为（每次新建连接）
            # 这样可以避免连接池中的 stale connection 问题

            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
                "User-Agent": "BossResumeFilter/1.0",
                "Connection": "close"  # 强制关闭连接，不复用
            }

            data = {
                "model": model,
                "messages": [{"role": "user", "content": "1"}],  # 最小请求
                "max_tokens": 1,
                "stream": False
            }

            url = f"{base_url.rstrip('/')}/chat/completions"

            # 宽松超时：连接 5 秒 + 读取 25 秒 = 总 30 秒
            # 宁可慢，也要成功，避免假阳性失败
            timeout = (8, 30)

            max_retries = 3  # 增加重试次数
            last_error = None
            last_status = None

            for attempt in range(max_retries):
                try:
                    # 每次重试都使用全新 Session（关键！）
                    if attempt > 0:
                        session.close()
                        session = requests.Session()

                    response = session.post(
                        url,
                        json=data,
                        headers=headers,
                        timeout=timeout,
                        verify=certifi.where()
                    )
                    elapsed = time.time() - start_time
                    last_status = response.status_code

                    if response.status_code == 200:
                        session.close()
                        self.root.after(0, lambda: self.api_status_label.config(
                            text=f"✓ 验证成功 ({elapsed:.1f}s)",
                            foreground=self.colors['success']
                        ))
                        self.root.after(0, lambda: messagebox.showinfo(
                            "连接测试成功",
                            f"API 连接正常\n\n"
                            f"响应时间：{elapsed:.1f}秒\n"
                            f"服务商：{self.api_provider_var.get().upper()}\n"
                            f"模型：{model}"
                        ))
                        return
                    elif response.status_code == 401:
                        session.close()
                        self.root.after(0, lambda: self.api_status_label.config(text="✗ 认证失败", foreground=self.colors['danger']))
                        self.root.after(0, lambda: messagebox.showerror(
                            "认证失败",
                            f"API Key 无效或已过期\n\n"
                            f"状态码：401\n"
                            f"请检查 API Key 是否正确"
                        ))
                        return
                    elif response.status_code == 429:
                        session.close()
                        self.root.after(0, lambda: self.api_status_label.config(text="⚠️ 请求受限", foreground=self.colors['warning']))
                        self.root.after(0, lambda: messagebox.showwarning(
                            "请求限额",
                            f"API 请求超限额\n\n"
                            f"状态码：429\n"
                            f"请稍后重试"
                        ))
                        return
                    else:
                        # 其他状态码，重试
                        session.close()
                        last_status = response.status_code
                        if attempt < max_retries - 1:
                            time.sleep(0.5)
                            self.root.after(0, lambda a=attempt+2: self.api_status_label.config(
                                text=f"⏳ 重试中 ({a}/{max_retries})... 状态码:{response.status_code}",
                                foreground=self.colors['warning']
                            ))
                            continue
                        # 重试耗尽
                        self.root.after(0, lambda: self.api_status_label.config(text="✗ 验证失败", foreground=self.colors['danger']))
                        self.root.after(0, lambda s=response.status_code, m=response.text[:200]: messagebox.showerror(
                            "连接测试失败",
                            f"HTTP 状态码：{s}\n\n"
                            f"响应：{m}"
                        ))
                        return

                except requests.exceptions.Timeout as e:
                    last_error = f"Timeout: {str(e)[:100]}"
                    if attempt < max_retries - 1:
                        # 超时后重试，指数退避
                        wait_time = 1.0 * (attempt + 1)
                        time.sleep(wait_time)
                        self.root.after(0, lambda a=attempt+2, w=wait_time: self.api_status_label.config(
                            text=f"⏳ 重试中 ({a}/{max_retries})... 等待{w:.0f}s",
                            foreground=self.colors['warning']
                        ))
                        continue
                except requests.exceptions.ConnectionError as e:
                    last_error = f"ConnectionError: {str(e)[:100]}"
                    if attempt < max_retries - 1:
                        wait_time = 0.5 * (attempt + 1)
                        time.sleep(wait_time)
                        self.root.after(0, lambda a=attempt+2: self.api_status_label.config(
                            text=f"⏳ 重试中 ({a}/{max_retries})...",
                            foreground=self.colors['warning']
                        ))
                        continue
                except requests.exceptions.SSLError as e:
                    # SSL 错误不重试，直接提示警告
                    last_error = f"SSLError: {str(e)[:100]}"
                    self.root.after(0, lambda: self.api_status_label.config(text="⚠️ SSL 错误", foreground=self.colors['warning']))
                    self.root.after(0, lambda m=str(e)[:200]: messagebox.showwarning(
                        "SSL 证书错误",
                        f"SSL 证书验证失败\n\n"
                        f"错误：{m}\n\n"
                        f"可忽略此错误，保存配置后尝试实际使用"
                    ))
                    return
                except Exception as e:
                    last_error = f"{type(e).__name__}: {str(e)[:100]}"
                    if attempt < max_retries - 1:
                        time.sleep(0.5)
                        continue

            # 所有重试失败
            session.close()
            elapsed = time.time() - start_time
            self.root.after(0, lambda: self.api_status_label.config(text="✗ 验证失败", foreground=self.colors['danger']))

            # 根据最后错误类型给出针对性建议
            if last_status == 401:
                msg = "API Key 无效或已过期"
            elif "Timeout" in str(last_error):
                msg = f"请求超时 ({elapsed:.1f}秒)\n\n可能原因：\n• 网络延迟高\n• API 服务器响应慢\n• 需要配置代理"
            elif "Connection" in str(last_error):
                msg = f"无法连接 API 服务器\n\n详情：{last_error}\n\n请检查：\n• Base URL 是否正确\n• 网络是否连通\n• 是否需要代理"
            else:
                msg = f"验证失败\n\n详情：{last_error or '未知错误'}"

            self.root.after(0, lambda: messagebox.showerror(
                "连接测试失败",
                f"经过 {max_retries} 次尝试后仍无法连接\n\n{msg}"
            ))

        # 启动测试线程
        threading.Thread(target=test_thread, daemon=True).start()

    def save_config(self):
        """保存配置文件 - 带备份保护，保留 requirement_template 等顶层字段"""
        # 先备份旧配置
        if CONFIG_PATH.exists():
            try:
                shutil.copy(CONFIG_PATH, CONFIG_BACKUP_PATH)
            except IOError as e:
                print(f"备份配置失败：{e}")

        # 加载已有配置，保留顶层字段（如 requirement_template）
        existing = {}
        if CONFIG_PATH.exists():
            try:
                with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                    existing = json.load(f)
            except (json.JSONDecodeError, IOError):
                pass

        # 更新 job_requirements，保留其他顶层字段
        existing["job_requirements"] = self.job_rules
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(existing, f, ensure_ascii=False, indent=4)

    def on_job_selected(self, event):
        """岗位选择改变"""
        job_name = self.config_job_combo.get()
        if job_name in self.job_rules:
            rule = self.job_rules[job_name]
            self.load_job_to_form(rule)
            self.requirement_template_btn.state(['disabled'])
            # 显示详细结果区域
            self.result_detail_frame.pack(fill="both", expand=True, padx=int(25 * self.dpi_scale * self.zoom_factor), pady=int(15 * self.dpi_scale * self.zoom_factor))

    def load_job_to_form(self, rule):
        """将岗位配置加载到表单（包含话术模板）"""
        # 岗位名称使用 combo 中选中的名称（而不是 rule 中的 job_title）
        job_name = self.config_job_combo.get()
        self.job_name_var.set(job_name)
        self.min_exp_var.set(str(rule.get("min_exp", 0)))
        self.max_age_var.set(str(rule.get("max_age", 35)))
        self.edu_var.set(rule.get("edu", "不限"))
        self.work_location_var.set(rule.get("work_location", ""))
        salary_min = rule.get("salary_min")
        salary_max = rule.get("salary_max")
        self.salary_min_var.set(str(salary_min) if salary_min is not None else "")
        self.salary_max_var.set(str(salary_max) if salary_max is not None else "")

        # 加载技能列表（带权重）
        self.skills_data = []
        keywords = rule.get("keywords", [])
        for kw in keywords:
            if isinstance(kw, dict):
                self.skills_data.append({
                    "name": kw.get("name", ""),
                    "weight": kw.get("weight", 1),
                    "source": "配置"
                })
            else:
                self.skills_data.append({
                    "name": kw,
                    "weight": 1,
                    "source": "配置"
                })
        self.refresh_skills_tree()

        # 加载必要条件
        self.required_conditions_data = []
        required = rule.get("required_conditions", [])
        if isinstance(required, list):
            for cond in required:
                self.required_conditions_data.append(cond)
        self.refresh_required_listbox()

        # 加载打招呼话术模板
        self.greet_template = rule.get("greet_template") or ""
        self.greet_template_text.delete("1.0", tk.END)
        self.greet_template_text.insert("1.0", self.greet_template)

        # 加载原始招聘需求到需求文档解析框
        self.requirement_text.delete("1.0", tk.END)
        original_req = rule.get("original_requirement", "")
        if original_req:
            self.requirement_text.insert("1.0", original_req)

    def refresh_skills_tree(self):
        """刷新技能树显示（带颜色标记）"""
        for item in self.skills_tree.get_children():
            self.skills_tree.delete(item)
        for skill in self.skills_data:
            # 根据权重设置颜色标记
            weight = skill.get("weight", 1)
            if weight >= 3:
                tag = 'high_weight'  # 绿色
            elif weight >= 2:
                tag = 'mid_weight'   # 橙色
            else:
                tag = 'low_weight'   # 灰色
            self.skills_tree.insert("", "end", values=(skill["name"], weight, skill["source"]), tags=(tag,))

    def refresh_required_listbox(self):
        """刷新必要条件列表显示"""
        self.required_listbox.delete(0, tk.END)
        for cond in self.required_conditions_data:
            if isinstance(cond, dict):
                cond_type = cond.get("type", "or").upper()
                items = ", ".join(cond.get("items", []))
                self.required_listbox.insert(tk.END, f"{cond_type}: {items}")
            else:
                self.required_listbox.insert(tk.END, str(cond))

    def add_skill(self):
        """添加技能"""
        skill_name = self.new_skill_var.get().strip()

        if not skill_name:
            messagebox.showwarning("警告", "请输入技能名称")
            return
        try:
            weight = int(self.new_skill_add_weight_var.get())
            if weight < 1 or weight > 3:
                raise ValueError()
        except ValueError:
            messagebox.showwarning("警告", "权重必须是 1-3 之间的数字")
            return

        # 检查是否已存在
        for s in self.skills_data:
            if s["name"].lower() == skill_name.lower():
                messagebox.showwarning("警告", "该技能已存在")
                return

        self.skills_data.append({"name": skill_name, "weight": weight, "source": "手动"})
        self.refresh_skills_tree()
        self.new_skill_var.set("")
        messagebox.showinfo("成功", f"已添加技能：{skill_name}（权重{weight}）")

    def delete_skill(self):
        """删除选中技能"""
        selection = self.skills_tree.selection()
        if not selection:
            messagebox.showwarning("警告", "请先在列表中选择要删除的技能")
            return
        if messagebox.askyesno("确认删除", f"确定要删除选中的 {len(selection)} 个技能吗？"):
            for item in selection:
                values = self.skills_tree.item(item, "values")
                skill_name = values[0]
                self.skills_data = [s for s in self.skills_data if s["name"] != skill_name]
            self.refresh_skills_tree()
            self.selected_skill_var.set("")

    def on_skill_selected(self, event):
        """技能被选中时，自动填充权重值到输入框"""
        selection = self.skills_tree.selection()
        if selection:
            values = self.skills_tree.item(selection[0], "values")
            skill_name = values[0]
            weight = values[1]
            self.selected_skill_var.set(skill_name)
            self.new_skill_weight_var.set(str(weight))
        else:
            self.selected_skill_var.set("未选择")

    def update_skill_weight(self):
        """更新选中技能的权重"""
        selection = self.skills_tree.selection()
        if not selection:
            messagebox.showwarning("警告", "请先在列表中选择要更新的技能")
            return

        try:
            weight = int(self.new_skill_weight_var.get())
            if weight < 1 or weight > 3:
                raise ValueError()
        except ValueError:
            messagebox.showwarning("警告", "权重必须是 1-3 之间的数字")
            return

        for item in selection:
            values = self.skills_tree.item(item, "values")
            skill_name = values[0]
            for s in self.skills_data:
                if s["name"] == skill_name:
                    s["weight"] = weight
                    break
        self.refresh_skills_tree()
        messagebox.showinfo("成功", f"已更新技能权重为 {weight}")

    def add_required_condition(self):
        """添加必要条件"""
        cond_type = self.required_cond_type_var.get()
        raw = self.new_required_var.get().strip()
        if not raw:
            messagebox.showwarning("警告", "请输入关键词")
            return

        if cond_type == "简单匹配":
            # 简单字符串匹配
            self.required_conditions_data.append(raw)
        elif cond_type == "OR（满足任一）":
            items = [s.strip() for s in raw.replace("，", ",").split(",") if s.strip()]
            if not items:
                messagebox.showwarning("警告", "请输入至少一个关键词")
                return
            self.required_conditions_data.append({"type": "or", "items": items})
        elif cond_type == "AND（全部满足）":
            items = [s.strip() for s in raw.replace("，", ",").split(",") if s.strip()]
            if not items:
                messagebox.showwarning("警告", "请输入至少一个关键词")
                return
            self.required_conditions_data.append({"type": "and", "items": items})

        self.refresh_required_listbox()
        self.new_required_var.set("")

    def delete_required_condition(self):
        """删除选中条件"""
        selection = self.required_listbox.curselection()
        if not selection:
            messagebox.showwarning("警告", "请选择要删除的条件")
            return
        for index in reversed(selection):
            self.required_conditions_data.pop(index)
        self.refresh_required_listbox()

    def _validate_salary_input(self, *args):
        """实时验证薪资输入框内容（仅允许数字或空）"""
        for var, entry in [(self.salary_min_var, self.salary_min_entry),
                           (self.salary_max_var, self.salary_max_entry)]:
            text = var.get()
            if text == "":
                # 空值合法，恢复默认样式
                entry.configure(foreground=self.colors['text_primary'])
            elif not text.isdigit():
                entry.configure(foreground='red')
            else:
                entry.configure(foreground=self.colors['text_primary'])

    def _insert_requirement_template(self):
        """插入招聘需求模板到输入框（模板文本从 job_config.json 读取）"""
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                config = json.load(f)
            template = config.get("requirement_template", "")
        except Exception:
            template = ""
        if not template:
            messagebox.showwarning("警告", "配置文件中未找到 requirement_template 模板")
            return
        self.requirement_text.delete("1.0", tk.END)
        self.requirement_text.insert("1.0", template)

    def parse_requirement(self):
        """解析需求文档"""
        requirement_text = self.requirement_text.get("1.0", tk.END).strip()
        if not requirement_text:
            messagebox.showwarning("警告", "请输入招聘需求文档内容")
            return

        try:
            # 直接调用 doc_parser.generate_config_from_text 生成完整配置
            from doc_parser import generate_config_from_text, parse_job_requirements

            # 先调试：记录原始文本和中间结果
            debug_log_path = BASE_DIR / "parse_debug.log"
            parsed_detail = parse_job_requirements(requirement_text)
            with open(debug_log_path, 'w', encoding='utf-8') as f:
                f.write(f"=== 学历解析调试日志 ===\n")
                f.write(f"需求文档长度: {len(requirement_text)}\n")
                f.write(f"需求文档是否含'博士': {'博士' in requirement_text}\n")
                f.write(f"需求文档是否含'硕士': {'硕士' in requirement_text}\n")
                f.write(f"需求文档是否含'本科': {'本科' in requirement_text}\n")
                f.write(f"parse_job_requirements 结果: edu={parsed_detail['edu']}\n")
                f.write(f"\n=== 原始需求文档 ===\n{requirement_text}\n")

            config = generate_config_from_text(requirement_text, merge_existing=False)
            job_title = list(config["job_requirements"].keys())[0]
            job_config = config["job_requirements"][job_title]

            # 填充基本信息
            # 规范化岗位名称：去除多余空格
            job_title = re.sub(r'\s+', ' ', job_title).strip()
            self.job_name_var.set(job_title)
            # 更新选择岗位下拉框，显示提取到的新岗位名称
            self.config_job_combo.set(job_title)

            # 设置经验
            self.min_exp_var.set(str(job_config.get("min_exp", 0)))
            self.max_age_var.set(str(job_config.get("max_age", 35)))

            # 设置学历
            self.edu_var.set(job_config.get("edu", "本科"))

            # 设置工作地点
            self.work_location_var.set(job_config.get("work_location", ""))

            # 设置薪资范围
            salary_min = job_config.get("salary_min")
            salary_max = job_config.get("salary_max")
            self.salary_min_var.set(str(salary_min) if salary_min is not None else "")
            self.salary_max_var.set(str(salary_max) if salary_max is not None else "")

            # 加载技能列表（带权重）- 直接使用 doc_parser 生成的结果
            self.skills_data = []
            keywords = job_config.get("keywords", [])
            for kw in keywords:
                if isinstance(kw, dict):
                    self.skills_data.append({
                        "name": kw.get("name", ""),
                        "weight": kw.get("weight", 1),
                        "source": "解析"
                    })
                else:
                    self.skills_data.append({
                        "name": kw,
                        "weight": 1,
                        "source": "解析"
                    })
            self.refresh_skills_tree()

            # 加载必要条件
            self.required_conditions_data = []
            required_conditions = job_config.get("required_conditions", [])
            for cond in required_conditions:
                self.required_conditions_data.append(cond)
            self.refresh_required_listbox()

            # 显示解析结果
            skills_count = len(self.skills_data)
            required_count = len(self.required_conditions_data)
            parsed_min_exp = job_config.get("min_exp", 0)
            parsed_edu = job_config.get("edu", "本科")
            parsed_location = job_config.get("work_location", "")
            loc_part = f"，地点={parsed_location}" if parsed_location else ""
            summary_base = f"岗位={job_title}, 经验={parsed_min_exp}年，学历={parsed_edu}{loc_part}, 技能={skills_count}个，必要条件={required_count}条"

            # 关键字不足警告
            if skills_count == 0:
                self.parse_result_label.config(
                    text=f"⚠ 解析成功但无技术关键字：{summary_base}",
                    foreground=self.colors['warning']
                )
                messagebox.showwarning(
                    "关键字缺失",
                    f"解析成功，但未提取到任何技术关键字。\n\n"
                    f"没有技术关键字无法精确筛选简历，筛选将仅依赖\n"
                    f"经验和学历，匹配精度会大幅下降。\n\n"
                    f"建议：\n"
                    f"1. 完善招聘需求文档，详细列出技术栈要求\n"
                    f"2. 在下方「技能关键词」区域手工添加关键字"
                )
            elif skills_count <= 5:
                self.parse_result_label.config(
                    text=f"⚠ 关键字较少：{summary_base}",
                    foreground=self.colors['warning']
                )
                messagebox.showwarning(
                    "关键字偏少",
                    f"仅提取到 {skills_count} 个技术关键字（建议 6 个以上）。\n\n"
                    f"关键字偏少会导致评分区分度不足，\n"
                    f"无法有效排序候选人。\n\n"
                    f"建议：\n"
                    f"1. 完善招聘需求文档，补充更多技术栈要求\n"
                    f"2. 在下方「技能关键词」区域手工添加关键字"
                )
            else:
                self.parse_result_label.config(
                    text=f"✓ 解析成功：{summary_base}"
                )

            # 显示详细结果区域
            self.result_detail_frame.pack(fill="both", expand=True, padx=int(25 * self.dpi_scale * self.zoom_factor), pady=int(15 * self.dpi_scale * self.zoom_factor))

        except Exception as e:
            messagebox.showerror("解析失败", f"解析需求文档时出错：{e}")
            self.parse_result_label.config(text=f"✗ 解析失败：{e}", foreground=self.colors['danger'])

    def add_job(self):
        """新建岗位"""
        self.reset_job_form()
        self.job_name_var.set("新岗位")
        self.config_job_combo.set("")  # 清空岗位选择
        self.requirement_template_btn.state(['!disabled'])

    def delete_job(self):
        """删除岗位"""
        job_name = self.config_job_combo.get()
        if job_name in self.job_rules:
            if messagebox.askyesno("确认", f"确定要删除岗位 '{job_name}' 吗？"):
                del self.job_rules[job_name]
                self.save_config()
                self.config_job_combo['values'] = list(self.job_rules.keys())
                self.config_job_combo.set('')
                self.reset_job_form()

    def save_current_job(self):
        """保存当前岗位配置"""
        job_name = self.job_name_var.get().strip()
        if not job_name:
            messagebox.showwarning("警告", "岗位名称不能为空")
            return

        # 规范化岗位名称：去除多余空格
        normalized_job_name = re.sub(r'\s+', ' ', job_name).strip()

        # 检查是否已存在相同（规范化后）的岗位
        existing_key_to_delete = None
        for key in self.job_rules.keys():
            normalized_key = re.sub(r'\s+', ' ', key).strip()
            if normalized_key.lower() == normalized_job_name.lower():
                existing_key_to_delete = key
                break

        if existing_key_to_delete and existing_key_to_delete != job_name:
            if messagebox.askyesno("岗位已存在", f"检测到重复岗位：'{existing_key_to_delete}'\n是否覆盖更新？"):
                del self.job_rules[existing_key_to_delete]
            else:
                return

        # 从 skills_data 构建带权重的 keywords 列表
        keywords = [{"name": s["name"], "weight": s["weight"]} for s in self.skills_data]

        # 从 required_conditions_data 构建必要条件列表
        required_conditions = list(self.required_conditions_data)  # 已是正确格式（str 或 dict）

        # 获取打招呼话术模板
        greet_template = self.greet_template_text.get("1.0", tk.END).strip()

        # 获取原始招聘需求（从需求文档解析框）
        original_requirement = self.requirement_text.get("1.0", tk.END).strip()

        # 验证薪资输入格式（非空则必须为数字）
        salary_min = None
        salary_max = None
        salary_min_str = self.salary_min_var.get().strip()
        salary_max_str = self.salary_max_var.get().strip()
        if salary_min_str:
            try:
                salary_min = int(salary_min_str)
            except ValueError:
                messagebox.showwarning("警告", "薪资范围最低值必须为数字（如：12）")
                return
        if salary_max_str:
            try:
                salary_max = int(salary_max_str)
            except ValueError:
                messagebox.showwarning("警告", "薪资范围最高值必须为数字（如：15）")
                return

        self.job_rules[normalized_job_name] = {
            "min_exp": int(self.min_exp_var.get()),
            "edu": self.edu_var.get(),
            "max_age": int(self.max_age_var.get()) if self.max_age_var.get().strip() else None,
            "work_location": self.work_location_var.get().strip() or None,
            "salary_min": salary_min,
            "salary_max": salary_max,
            "keywords": keywords,
            "required_conditions": required_conditions,
            "greet_template": greet_template if greet_template else None,
            "original_requirement": original_requirement if original_requirement else None
        }

        self.save_config()
        self.config_job_combo['values'] = list(self.job_rules.keys())
        self.config_job_combo.set(normalized_job_name)
        messagebox.showinfo("成功", "岗位配置已保存")

    def reset_job_form(self):
        """重置表单"""
        self.job_name_var.set("")
        self.min_exp_var.set("3")
        self.max_age_var.set("35")
        self.edu_var.set("本科")
        self.work_location_var.set("")
        self.salary_min_var.set("")
        self.salary_max_var.set("")
        self.skills_data = []
        self.refresh_skills_tree()
        self.required_conditions_data = []
        self.refresh_required_listbox()
        self.requirement_text.delete("1.0", tk.END)
        self.parse_result_label.config(text="")
        self.greet_template_text.delete("1.0", tk.END)
        self.greet_template = ""

    def load_config_dialog(self):
        """打开配置对话框"""
        filename = filedialog.askopenfilename(title="选择配置文件", filetypes=[("JSON 文件", "*.json"), ("所有文件", "*.*")])
        if filename:
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                # 支持新旧两种格式
                if "job_requirements" in config:
                    self.job_rules = config["job_requirements"]
                elif "jobs" in config:
                    self.job_rules = config["jobs"]
                else:
                    self.job_rules = {}
                self.save_config()
                self.config_job_combo['values'] = list(self.job_rules.keys())
                messagebox.showinfo("成功", "配置已加载")
            except Exception as e:
                messagebox.showerror("错误", f"加载配置失败：{e}")

    def save_config_dialog(self):
        """保存配置对话框"""
        filename = filedialog.asksaveasfilename(title="保存配置文件", defaultextension=".json", filetypes=[("JSON 文件", "*.json"), ("所有文件", "*.*")])
        if filename:
            try:
                config = {"jobs": self.job_rules}
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(config, f, ensure_ascii=False, indent=4)
                messagebox.showinfo("成功", "配置已保存")
            except Exception as e:
                messagebox.showerror("错误", f"保存配置失败：{e}")

    def import_config(self):
        """导入配置"""
        self.load_config_dialog()

    def export_config(self):
        """导出配置"""
        self.save_config_dialog()

    def clear_log(self):
        """清空日志"""
        self.log_text.config(state="normal")
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state="disabled")

    def append_log(self, message):
        """追加日志"""
        self.log_queue.put(message)

    def run_on_ui(self, callback):
        """在 Tk 主线程执行 UI 更新（线程安全）。

        后台线程不能直接调用 root.after()，改用队列 + 主线程轮询。
        """
        self.ui_queue.put(callback)

    def _process_ui_queue(self):
        """处理 UI 更新队列（由主线程定时器调用）"""
        try:
            while True:
                callback = self.ui_queue.get_nowait()
                try:
                    callback()
                except Exception as e:
                    print(f"[UI 队列] 回调执行失败: {e}")
        except queue.Empty:
            pass
        self.root.after(50, self._process_ui_queue)

    def set_browser_ui(self, indicator_text=None, indicator_color=None, help_text=None, start_state=None):
        """线程安全更新浏览器状态控件，并缓存状态文本供后台线程判断。"""
        if indicator_text is not None:
            self._browser_status_text = indicator_text
        if help_text is not None:
            self._browser_status_help_text = help_text

        def apply_update():
            if indicator_text is not None:
                self.browser_status_indicator.config(text=indicator_text, foreground=indicator_color)
            if help_text is not None:
                self.browser_status_help.config(text=help_text)
            if start_state is not None:
                self.start_btn.config(state=start_state)

        self.run_on_ui(apply_update)

    def update_log(self):
        """更新日志显示"""
        try:
            while True:
                message = self.log_queue.get_nowait()
                self.log_text.config(state="normal")
                self.log_text.insert(tk.END, message + "\n")
                self.log_text.see(tk.END)
                self.log_text.config(state="disabled")
        except queue.Empty:
            pass
        self.root.after(100, self.update_log)

    def _auto_check_selectors(self):
        """连接成功后自动检查选择器健康状态（仅在 check() 工作线程中调用）

        每次新连接到推荐牛人页面时执行一次，有异常弹窗提醒。
        """
        if self._selectors_auto_checked:
            return
        if not self.browser_connected or not self.browser_page:
            return
        self._selectors_auto_checked = True

        try:
            from bossmaster import check_selectors_health
            results = check_selectors_health(self.browser_page)

            ok_count = sum(1 for r in results if r['status'] == 'ok')
            warn_count = sum(1 for r in results if r['status'] == 'warn')
            fail_count = sum(1 for r in results if r['status'] == 'fail')

            self.append_log(f"选择器自动检查：{ok_count} 正常 / {warn_count} 警告 / {fail_count} 失败")

            for r in results:
                icon = {'ok': '✅', 'warn': '⚠️', 'fail': '❌'}.get(r['status'], '?')
                self.append_log(f"  {icon} [{r['group']}] {r['name']}: {r['detail']}")

            if warn_count + fail_count > 0:
                self.append_log("⚠️ 选择器异常可能导致扫描功能不正常，可编辑 selectors.json 修复")
                # 主线程弹窗提醒（线程安全）
                self.run_on_ui(lambda: messagebox.showwarning(
                    "选择器异常",
                    f"选择器检查发现 {fail_count} 个失败、{warn_count} 个警告，"
                    f"可能导致扫描功能不正常。\n\n"
                    f"可编辑 selectors.json 修复，详见日志。"
                ))
            else:
                self.append_log("✅ 所有选择器工作正常")
        except Exception as e:
            self.append_log(f"选择器自动检查失败：{e}")

    def _reactivate_and_navigate(self, page, target_url):
        """激活已有的 Chrome 进程并导航到目标页面。

        当 Chrome 关闭窗口但未退出时（macOS 常见），调试端口仍然可用，
        通过 AppleScript 激活 Chrome 窗口后直接导航，避免杀进程重启。

        Returns:
            导航成功返回新的/更新后的 page 对象，失败返回 None。
        """
        # macOS: 用 AppleScript 激活 Chrome 窗口
        if sys.platform == 'darwin':
            try:
                subprocess.run([
                    'osascript', '-e',
                    'tell application "Google Chrome" to activate'
                ], capture_output=True, timeout=3)
                time.sleep(1)
            except Exception:
                pass

        # 尝试 page.get() 直接导航（比 new_tab 更可靠）
        try:
            page.get(target_url)
            time.sleep(2)
            return page
        except Exception:
            return None

    def check_browser_connection(self, silent=False):
        """检测浏览器连接状态

        Args:
            silent: True 时只更新 UI 不写日志（用于自动轮询）
        """
        if getattr(self, '_browser_check_running', False):
            # 手动点击优先：标记待处理，当前 silent 检查结束后自动重试
            if not silent:
                self._pending_manual_check = True
                self.append_log("⏳ 正在执行其他检测，稍后自动重试...")
            return
        self._browser_check_running = True

        def check():
            try:
                if not silent:
                    self.append_log("正在检测浏览器连接...")

                # 已有可用连接，直接复用，不做端口检查
                if self.browser_page is not None:
                    try:
                        prev_help = self._browser_status_help_text
                        # page.url 可能阻塞（Chrome 已关闭时 WebSocket 断开），加超时保护
                        page_url_result = [None]
                        page_url_exception = [None]
                        def _get_existing_url():
                            try:
                                page_url_result[0] = self.browser_page.url
                            except Exception as e:
                                page_url_exception[0] = e
                        url_t = threading.Thread(target=_get_existing_url, daemon=True)
                        url_t.start()
                        url_t.join(timeout=1)
                        if url_t.is_alive():
                            raise TimeoutError("browser_page.url 访问超时")
                        if page_url_exception[0] is not None:
                            raise page_url_exception[0]
                        current_url = page_url_result[0] or ''
                        if 'zhipin.com/web/chat/recommend' in current_url.lower():
                            self.browser_connected = True
                            self.set_browser_ui("🟢 已连接", self.colors['success'], "已连接到 BOSS 直聘推荐牛人页面", "normal")
                            if prev_help != "已连接到 BOSS 直聘推荐牛人页面":
                                self.append_log("✅ 已连接到 BOSS 直聘推荐牛人页面")
                        elif 'zhipin.com' in current_url.lower() or 'boss' in current_url.lower():
                            self.browser_connected = False
                            self.set_browser_ui("🟡 需导航", self.colors['warning'], "浏览器已连接，请导航到 BOSS 直聘推荐牛人页面", "disabled")
                            if prev_help != "浏览器已连接，请导航到 BOSS 直聘推荐牛人页面":
                                self.append_log("⚠️ 浏览器已连接，请导航到 BOSS 直聘推荐牛人页面")
                        else:
                            self.browser_connected = False
                            self.set_browser_ui("🟡 需导航", self.colors['warning'], "浏览器已连接，请导航到 BOSS 直聘推荐牛人页面", "disabled")
                            if prev_help != "浏览器已连接，请导航到 BOSS 直聘推荐牛人页面":
                                self.append_log("⚠️ 浏览器已连接，请导航到 BOSS 直聘推荐牛人页面")
                        return
                    except Exception:
                        # 页面对象已失效，清理后走完整检测流程
                        self.browser_page = None
                        self.browser_connected = False
                        self._selectors_auto_checked = False  # 页面失效，下次连接重新检查选择器

                # 没有可用连接，检查 Chrome 调试端口
                # 优先读取上次持久化的端口号
                addr = getattr(self, 'browser_address', None)
                if not addr:
                    try:
                        saved_port = CHROME_DEBUG_PORT_FILE.read_text(encoding='utf-8').strip()
                        if saved_port.isdigit():
                            addr = f'127.0.0.1:{saved_port}'
                    except OSError:
                        pass
                if not addr:
                    addr = '127.0.0.1:9222'
                host, port = addr.rsplit(':', 1)
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(1)
                port_open = s.connect_ex((host, int(port))) == 0
                s.close()

                if not port_open:
                    prev_state = self._browser_status_text
                    self.browser_connected = False
                    self.set_browser_ui("🔴 未连接", self.colors['danger'], start_state="disabled")

                    # 自动启动 Chrome（仅在手动点击时）
                    if not silent:
                        self.set_browser_ui(help_text="正在启动 Chrome 浏览器...")
                        self.append_log("正在启动 Chrome 浏览器...")

                        # 找到 Chrome 可执行文件
                        if sys.platform == 'darwin':
                            candidates = [
                                '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
                                os.path.expanduser('~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'),
                            ]
                        else:
                            candidates = [
                                os.path.expandvars(r'%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe'),
                                r'C:\Program Files\Google\Chrome\Application\chrome.exe',
                                r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
                            ]
                        chrome_path = next((p for p in candidates if os.path.exists(p)), None)
                        if not chrome_path:
                            self.set_browser_ui(help_text="未找到 Chrome 浏览器，请安装后重试")
                            self.append_log("❌ 未找到 Chrome 浏览器")
                            return

                        # 自动选一个空闲端口，避免 9222 被占用
                        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        s.bind(('127.0.0.1', 0))
                        debug_port = s.getsockname()[1]
                        s.close()

                        # 清理 Chrome 锁文件，保留登录态（SingletonLock/Socket/Cookie
                        # 是上次异常退出残留的，删掉即可，不影响 cookies）
                        profile_dir = BASE_DIR / '.chrome_profile'
                        profile_dir.mkdir(parents=True, exist_ok=True)
                        for lock_file in ['SingletonLock', 'SingletonSocket', 'SingletonCookie']:
                            lock_path = profile_dir / lock_file
                            if lock_path.exists():
                                try:
                                    lock_path.unlink()
                                except Exception:
                                    pass

                        # 用 subprocess 直接启动 Chrome（不依赖 DrissionPage 的启动逻辑）
                        self.append_log(f"正在启动 Chrome（调试端口 {debug_port}）...")
                        subprocess.Popen(
                            [
                                chrome_path,
                                f'--remote-debugging-port={debug_port}',
                                f'--user-data-dir={profile_dir}',
                                '--no-first-run',
                                '--no-default-browser-check',
                            ],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                        )

                        # 持久化端口号，下次启动时可复用
                        try:
                            CHROME_DEBUG_PORT_FILE.write_text(str(debug_port), encoding='utf-8')
                        except OSError:
                            pass

                        # 轮询等待端口就绪
                        port_ready = False
                        for i in range(30):
                            time.sleep(1)
                            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                            s.settimeout(0.5)
                            if s.connect_ex(('127.0.0.1', debug_port)) == 0:
                                s.close()
                                port_ready = True
                                break
                            s.close()
                            if i == 0:
                                self.append_log("⏳ 等待 Chrome 就绪...")
                            elif i % 5 == 4:
                                self.append_log(f"⏳ 等待 Chrome 就绪... ({i+1}/30)")

                        if not port_ready:
                            self.set_browser_ui("🔴 未连接", self.colors['danger'], "Chrome 启动超时，请关闭所有 Chrome 窗口后重试")
                            self.append_log("❌ Chrome 启动超时，调试端口未开启")
                            return

                        # 端口已开，用 DrissionPage 连接
                        time.sleep(2)
                        try:
                            from DrissionPage import ChromiumPage, ChromiumOptions
                            co = ChromiumOptions()
                            co.set_address(f'127.0.0.1:{debug_port}')

                            # 整个连接+导航放入线程超时保护，防止 Chrome 被杀后 DrissionPage 阻塞
                            startup_result = [None]
                            startup_exception = [None]

                            def _connect_and_navigate():
                                try:
                                    p = ChromiumPage(co)
                                    u = p.url
                                    if 'zhipin.com/web/chat/recommend' not in u.lower():
                                        p.get('https://www.zhipin.com/web/chat/recommend')
                                        time.sleep(2)
                                        u = p.url
                                    startup_result[0] = (p, u)
                                except Exception as e:
                                    startup_exception[0] = e

                            st = threading.Thread(target=_connect_and_navigate, daemon=True)
                            st.start()
                            st.join(timeout=6)
                            if st.is_alive():
                                raise TimeoutError("Chrome 连接超时")
                            if startup_exception[0] is not None:
                                raise startup_exception[0]

                            page, current_url = startup_result[0]
                            if 'zhipin.com/web/chat/recommend' in current_url.lower():
                                self.browser_connected = True
                                self.browser_page = page
                                self.browser_address = page.address
                                self.set_browser_ui("🟢 已连接", self.colors['success'], "已连接到 BOSS 直聘推荐牛人页面", "normal")
                                self.append_log("✅ 已连接到 BOSS 直聘推荐牛人页面")
                            else:
                                self.browser_connected = True
                                self.browser_page = page
                                self.browser_address = page.address
                                self.set_browser_ui("🟡 需导航", self.colors['warning'], "浏览器已连接，请导航到 BOSS 直聘推荐牛人页面", "disabled")
                                self.append_log("⚠️ 浏览器已连接，请导航到 BOSS 直聘推荐牛人页面")
                        except Exception as e:
                            self.browser_connected = False
                            self.browser_page = None
                            self._selectors_auto_checked = False
                            self.set_browser_ui("🔴 未连接", self.colors['danger'], "未检测到 Chrome 浏览器", "disabled")
                            self.append_log(f"❌ 未检测到 Chrome 浏览器：{e}")
                        return
                    else:
                        self.set_browser_ui(help_text="未检测到 Chrome，请确保浏览器已启动")
                        if prev_state != "🔴 未连接":
                            self.append_log("❌ 未检测到 Chrome 调试端口")
                    return

                from DrissionPage import ChromiumPage, ChromiumOptions

                try:
                    # 将整个 ChromiumPage 构造 + page.url 放入线程超时保护
                    # ChromiumPage() 构造函数和 page.url 都可能在 Chrome 已死时阻塞
                    co = ChromiumOptions()
                    co.set_address(addr)

                    page_result = [None]
                    url_result = [None]
                    connect_exception = [None]

                    def _connect_and_get_url():
                        try:
                            p = ChromiumPage(co)
                            page_result[0] = p
                            url_result[0] = p.url
                        except Exception as e:
                            connect_exception[0] = e

                    conn_thread = threading.Thread(target=_connect_and_get_url, daemon=True)
                    conn_thread.start()
                    conn_thread.join(timeout=3)
                    if conn_thread.is_alive():
                        raise TimeoutError("ChromiumPage 连接超时")
                    if connect_exception[0] is not None:
                        raise connect_exception[0]

                    page = page_result[0]
                    current_url = url_result[0]
                    if not current_url:
                        current_url = ''

                    # Chrome 进程还在但窗口已关闭时，page.url 可能是 about:blank
                    # 直接在现有进程里导航到 BOSS 直聘，不杀进程不重启
                    target_url = 'https://www.zhipin.com/web/chat/recommend'
                    if current_url in ('about:blank', ''):
                        if not silent:
                            self.append_log("⚠️ Chrome 进程存在但无有效页面，正在激活并导航...")
                            nav_page = self._reactivate_and_navigate(page, target_url)
                            if nav_page is not None:
                                self.browser_connected = True
                                self.browser_page = nav_page
                                self.browser_address = page.address
                                try:
                                    nav_url = nav_page.url or ''
                                except Exception:
                                    nav_url = ''
                                if 'zhipin.com/web/chat/recommend' in nav_url.lower():
                                    self.set_browser_ui("🟢 已连接", self.colors['success'], "已连接到 BOSS 直聘推荐牛人页面", "normal")
                                    self.append_log("✅ 已连接到 BOSS 直聘推荐牛人页面")
                                else:
                                    self.set_browser_ui("🟡 需导航", self.colors['warning'], "已激活 Chrome，正在加载页面...", "disabled")
                                    self.append_log("⚠️ 已激活 Chrome，请等待页面加载完成")
                            else:
                                self.browser_connected = False
                                self.browser_page = None
                                self.set_browser_ui("🟡 需导航", self.colors['warning'], "请手动打开 Chrome 窗口", "disabled")
                                self.append_log("⚠️ 无法激活 Chrome 页面，请手动打开 Chrome 窗口后点击重试")
                        else:
                            # 自动轮询：不尝试导航，避免 page.get() 挂起
                            self.browser_connected = False
                            self.browser_page = None
                            prev_state = self._browser_status_text
                            self.set_browser_ui("🟡 需导航", self.colors['warning'], "Chrome 进程存在但无有效页面", "disabled")
                            if prev_state != "🟡 需导航":
                                self.append_log("⚠️ Chrome 进程存在但无有效页面，请点击按钮激活")
                        # 处理完毕，不再往下走 URL 检查
                        return

                    if 'zhipin.com/web/chat/recommend' in current_url.lower():
                        prev_connected = self.browser_connected
                        self.browser_connected = True
                        self.browser_page = page
                        self.browser_address = page.address
                        self.set_browser_ui("🟢 已连接", self.colors['success'], "已连接到 BOSS 直聘推荐牛人页面", "normal")
                        if not silent or not prev_connected:
                            self.append_log("✅ 已连接到 BOSS 直聘推荐牛人页面")
                    elif 'zhipin.com' in current_url.lower() or 'boss' in current_url.lower():
                        prev_state = self._browser_status_text
                        self.browser_connected = False
                        self.browser_page = page
                        self.browser_address = page.address
                        self.set_browser_ui("🟡 需导航", self.colors['warning'], "浏览器已连接，请导航到 BOSS 直聘推荐牛人页面", "disabled")
                        if not silent or prev_state != "🟡 需导航":
                            self.append_log("⚠️ 浏览器已连接，请导航到 BOSS 直聘推荐牛人页面")
                    else:
                        prev_state = self._browser_status_text
                        self.browser_connected = False
                        self.browser_page = page
                        self.browser_address = page.address
                        self.set_browser_ui("🟡 需导航", self.colors['warning'], "浏览器已连接，请导航到 BOSS 直聘推荐牛人页面", "disabled")
                        if not silent or prev_state != "🟡 需导航":
                            self.append_log("⚠️ 浏览器已连接，请导航到 BOSS 直聘推荐牛人页面")

                except Exception as e:
                    prev_state = self._browser_status_text
                    self.browser_connected = False
                    self.browser_page = None  # 清理失效的 page 对象
                    self._selectors_auto_checked = False
                    self.set_browser_ui("🔴 未连接", self.colors['danger'], "未检测到 Chrome 浏览器", "disabled")
                    if not silent or prev_state != "🔴 未连接":
                        self.append_log(f"❌ 未检测到 Chrome 浏览器：{e}")

                    # 手动点击时，尝试杀掉彻底挂掉的调试 Chrome 进程并重启
                    if not silent:
                        self.append_log("⚠️ 正在尝试清理残留的调试 Chrome 进程...")
                        killed = False
                        try:
                            port_num = int(port)
                            if sys.platform == 'darwin' or sys.platform.startswith('linux'):
                                # 找到包含 remote-debugging-port=PORT 的 Chrome 进程 PID
                                result = subprocess.run(
                                    ['pgrep', '-f', f'remote-debugging-port={port_num}'],
                                    capture_output=True, text=True, timeout=3
                                )
                                pids = result.stdout.strip().split('\n')
                                for pid in pids:
                                    if pid.isdigit():
                                        try:
                                            os.kill(int(pid), 15)  # SIGTERM
                                            killed = True
                                        except ProcessLookupError:
                                            pass
                            elif sys.platform == 'win32':
                                # Windows: 用 wmic 找到包含调试端口的 Chrome 进程
                                result = subprocess.run(
                                    ['wmic', 'process', 'where',
                                     f"CommandLine like '%remote-debugging-port={port_num}%'",
                                     'get', 'ProcessId'],
                                    capture_output=True, text=True, timeout=5
                                )
                                for line in result.stdout.strip().split('\n'):
                                    pid = line.strip()
                                    if pid.isdigit():
                                        subprocess.run(['taskkill', '/PID', pid],
                                                     timeout=2, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                                        killed = True
                        except Exception as kill_err:
                            self.append_log(f"清理残留进程失败：{kill_err}")

                        if killed:
                            time.sleep(1)
                            self.append_log("✅ 已清理残留的调试 Chrome 进程，2秒后自动重新启动...")
                            self._pending_chrome_restart = True
                        else:
                            self.append_log("⚠️ Chrome 调试端口被占用但无法清理，请手动关闭所有 Chrome 窗口后重试")
                            self.set_browser_ui("🔴 未连接", self.colors['danger'],
                                              "请关闭所有 Chrome 窗口后点击重试", "disabled")

            except ImportError:
                self.set_browser_ui("🔴 错误", self.colors['danger'], "未安装 DrissionPage，请运行：pip install DrissionPage")
                self.append_log("❌ DrissionPage 未安装")
            finally:
                # 连接成功后自动检查选择器（仅首次）
                if self.browser_connected and self.browser_page and not self._selectors_auto_checked:
                    try:
                        self._auto_check_selectors()
                    except Exception:
                        pass  # 选择器检查失败不影响主流程
                self._browser_check_running = False
                # 注意：不在此处调用 root.after()（后台线程不安全）
                # _pending_manual_check 标志保留为 True，由主线程的 auto-poll 拾取

        thread = threading.Thread(target=check)
        thread.daemon = True
        thread.start()

    def _start_browser_auto_check(self):
        """每 2 秒自动检测浏览器状态"""
        if self._browser_auto_check_id is not None:
            return  # 已在运行

        def poll():
            # 如果有被阻塞的手动检测请求，在主线程中安全触发
            if getattr(self, '_pending_manual_check', False):
                self._pending_manual_check = False
                self.check_browser_connection(silent=False)
            # 如果有待处理的 Chrome 重启请求
            elif getattr(self, '_pending_chrome_restart', False):
                self._pending_chrome_restart = False
                self.check_browser_connection(silent=False)
            else:
                self.check_browser_connection(silent=True)
            self._browser_auto_check_id = self.root.after(2000, poll)

        self._browser_auto_check_id = self.root.after(500, poll)  # 首次 0.5s 后检测，之后每 2s

    def _stop_browser_auto_check(self):
        """停止自动检测"""
        if self._browser_auto_check_id is not None:
            self.root.after_cancel(self._browser_auto_check_id)
            self._browser_auto_check_id = None

    def update_progress(self):
        """更新进度条显示"""
        try:
            # 处理进度队列
            while True:
                progress_data = self.progress_queue.get_nowait()
                current = progress_data.get('current', 0)
                total = progress_data.get('total', 100)
                percentage = min(100, int((current / total) * 100)) if total > 0 else 0
                self.progress_var.set(percentage)
                desc = progress_data.get('desc', '')
                self.progress_label.config(text=f"{percentage}%  {desc}")
        except queue.Empty:
            pass

        # 处理岗位切换确认队列
        try:
            confirm_data = self.confirm_queue.get_nowait()
            event = confirm_data['event']
            current_idx = confirm_data['current_idx']
            total = confirm_data['total']
            next_job_name = confirm_data['next_job_name']

            result = messagebox.askokcancel(
                "岗位切换确认",
                f"请手动切换到下一个岗位的推荐页面\n\n"
                f"进度：{current_idx}/{total}\n"
                f"下一个岗位：{next_job_name}\n\n"
                f"请在 BOSS 直聘页面手动切换到该岗位的推荐页面后，\n"
                f"点击「确定」继续，或点击「取消」停止扫描。"
            )
            event.result = result
            event.set()
        except queue.Empty:
            pass

        self.root.after(200, self.update_progress)

    def _bind_run_canvas_width(self, canvas_frame):
        """绑定 run_canvas 内部窗口宽度，使其跟随 canvas 宽度"""
        window_id = getattr(self, '_run_canvas_window_id', None)
        if window_id is None:
            return
        def on_resize(event):
            self.run_canvas.itemconfig(window_id, width=event.width)
        canvas_frame.bind("<Configure>", on_resize)

    @staticmethod
    def _parse_salary_exp(summary):
        """从候选人摘要中解析薪资和工作年限

        Returns:
            (salary: str, exp: str) — 如 ("15K", "5年")
        """
        salary = ''
        exp = ''
        if not summary:
            return salary, exp
        first_line = summary.split('\n')[0].strip() if '\n' in summary else summary.strip()
        if '面议' in first_line:
            salary = '面议'
        else:
            salary_match = re.search(r'^(\d+(?:-\d+)?)[Kk 千]', first_line)
            if salary_match:
                salary = salary_match.group(1) + 'K'
        exp_match = re.search(r'(\d+)\s*年', summary)
        if exp_match:
            exp = exp_match.group(1) + '年'
        return salary, exp

    @staticmethod
    def _center_window_on_screen(window, width, height):
        """将子窗口相对于屏幕居中（不依赖父窗口位置）"""
        window.update_idletasks()
        x = (window.winfo_screenwidth() - width) // 2
        y = (window.winfo_screenheight() - height) // 2
        window.geometry(f"+{max(0, x)}+{max(0, y)}")

    def start_run(self):
        """开始运行"""
        if self.is_running:
            return

        if not self.browser_connected:
            messagebox.showwarning("未连接", "请先连接到 BOSS 直聘推荐页面后再运行")
            return

        if self.browser_page is not None:
            try:
                current_url = self.browser_page.url
                if 'zhipin.com/web/chat/recommend' not in current_url.lower():
                    messagebox.showwarning("页面错误", "请将浏览器导航到 BOSS 直聘推荐页面后再运行")
                    return
            except Exception:
                messagebox.showwarning("连接丢失", "浏览器连接已丢失，请重新检测/连接")
                return
        else:
            messagebox.showwarning("未连接", "请先检测/连接浏览器")
            return

        self.is_running = True
        self.stop_event.clear()
        self.status_label.config(text="🟡 运行中...", foreground=self.colors['warning'])
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")

        self.append_log(f"[{datetime.now().strftime('%H:%M:%S')}] ▶ 开始运行...")

        self.worker_thread = threading.Thread(target=self.run_worker)
        self.worker_thread.daemon = True
        self.worker_thread.start()

    def stop_run(self):
        """停止运行"""
        self.is_running = False
        self.stop_event.set()
        self.status_label.config(text="🔴 已停止", foreground=self.colors['danger'])
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.append_log(f"[{datetime.now().strftime('%H:%M:%S')}] ⏹ 已停止")

    def run_worker(self):
        """运行工作线程"""
        import sys
        from datetime import datetime

        old_stdout = sys.stdout
        try:
            class LogRedirector:
                def __init__(self, callback):
                    self.callback = callback
                    self.buffer = ""

                def write(self, text):
                    self.buffer += text
                    while '\n' in self.buffer:
                        line, self.buffer = self.buffer.split('\n', 1)
                        if line.strip():
                            self.callback(f"[{datetime.now().strftime('%H:%M:%S')}] {line}")

                def flush(self):
                    if self.buffer.strip():
                        self.callback(f"[{datetime.now().strftime('%H:%M:%S')}] {self.buffer}")
                    self.buffer = ""

            log_redirector = LogRedirector(self.append_log)
            sys.stdout = log_redirector

            rounds = int(self.rounds_var.get())
            # 将中文打招呼等级映射为程序参数
            greet_level_text = self.greet_level_var.get()
            no_greet = greet_level_text == "不打招呼（仅筛选）"
            greet_level = "strong" if greet_level_text == "仅强烈推荐" else "normal"

            from bossmaster import load_job_config, ChromiumPage, time, run_smart_scan
            import argparse

            self.append_log(f">>> BOSS 直聘候选人智能提取工具 v{__version__} [图形界面模式]")
            self.append_log(f"滚动轮次：{rounds}, 自动打招呼：{greet_level_text}")

            # 获取选择的岗位
            selected_job = self.job_select_var.get()
            job_arg = None if selected_job == "全部岗位" else selected_job

            # 构造命令行参数
            ai_eval_enabled = self.ai_eval_var.get()
            ai_api_config = None
            ai_api_key = None
            if ai_eval_enabled:
                try:
                    ai_api_config = self.api_config
                    from security import get_api_key
                    ai_api_key = get_api_key(self.api_config.get('api_provider', ''))
                    if not ai_api_key:
                        self.append_log("AI 评估需要 API Key，但未配置，将跳过")
                        ai_eval_enabled = False
                    else:
                        model_name = self.api_config.get('model', 'unknown')
                        self.append_log(f"AI 辅助评估已启用（模型：{model_name}）")
                except Exception as e:
                    self.append_log(f"加载 API 配置失败：{e}，跳过 AI 评估")
                    ai_eval_enabled = False

            args = argparse.Namespace(
                clear=False,
                job=job_arg,
                greet=not no_greet,
                re_greet=False,
                greet_level=greet_level,
                greet_names=None,
                list_candidates=False,
                rounds=rounds,
                verbose=False,
                ai_eval=ai_eval_enabled,
                api_config=ai_api_config,
                api_key=ai_api_key,
            )

            if job_arg:
                self.append_log(f"[初次扫描模式] 指定岗位：{job_arg}")
            else:
                self.append_log("[初次扫描模式] 处理全部岗位")
            self.append_log("请手动导航到 BOSS 直聘推荐页面...")
            self.append_log("等待 3 秒...")
            time.sleep(3)

            self.append_log("开始扫描候选人...")

            # 进度回调 — 将 bossmaster 的进度报告送入队列
            def on_progress(percentage, description):
                self.progress_queue.put({
                    'current': percentage,
                    'total': 100,
                    'desc': description,
                })

            def confirm_callback(current_idx, total, next_job_name):
                """岗位切换确认 — 阻塞工作线程直到用户在 GUI 中确认"""
                event = threading.Event()
                event.result = False
                self.confirm_queue.put({
                    'event': event,
                    'current_idx': current_idx,
                    'total': total,
                    'next_job_name': next_job_name,
                })
                # 轮询等待，支持 stop_event 中断
                while not event.is_set():
                    if self.stop_event.is_set():
                        event.result = False
                        break
                    event.wait(timeout=0.5)
                return event.result

            def captcha_callback(detail):
                """验证码弹窗通知 — 阻塞工作线程直到用户在 GUI 中响应

                返回:
                    True: 用户选择继续等待验证完成
                    False: 用户选择跳过验证等待（中止当前操作）
                """
                result = [False]
                done = threading.Event()

                def show_dialog():
                    answer = messagebox.askyesno(
                        "检测到安全验证弹窗",
                        f"程序检测到安全验证弹窗\n（{detail}）\n\n"
                        "请在浏览器中手动完成验证。\n\n"
                        "点击「是」继续等待验证完成\n"
                        "点击「否」跳过验证等待，停止当前操作",
                        parent=self.root,
                    )
                    result[0] = answer
                    done.set()

                self.root.after(0, show_dialog)
                # 轮询等待，支持 stop_event 中断
                while not done.is_set():
                    if self.stop_event.is_set():
                        result[0] = False
                        done.set()
                        break
                    done.wait(timeout=0.5)
                return result[0]

            # 调用 run_smart_scan 并传入参数和进度回调
            run_smart_scan(args, progress_callback=on_progress, confirm_callback=confirm_callback,
                           stop_event=self.stop_event, existing_page=self.browser_page,
                           captcha_callback=captcha_callback)

        except KeyboardInterrupt:
            self.append_log("用户取消岗位切换，已停止")
        except Exception as e:
            self.append_log(f"运行出错：{e}")
            import traceback
            self.append_log(traceback.format_exc())
        finally:
            sys.stdout = old_stdout
            self.is_running = False
            self.append_log(f"[{datetime.now().strftime('%H:%M:%S')}] ✔ 运行完成")

            def finish_ui():
                self.status_label.config(text="🟢 就绪", foreground=self.colors['success'])
                self.start_btn.config(state="normal")
                self.stop_btn.config(state="disabled")
                self.progress_var.set(0)
                self.progress_label.config(text="就绪")
                self.root.after(100, self.refresh_results)

            self.run_on_ui(finish_ui)

    def on_closing(self):
        """窗口关闭处理 - 安全等待工作线程结束"""
        if self.is_running:
            if messagebox.askokcancel("退出", "程序正在运行，确定要强行退出吗？\n未保存的进度可能会丢失。"):
                self.is_running = False
                # 等待工作线程结束（最多 5 秒）
                if hasattr(self, 'worker_thread') and self.worker_thread and self.worker_thread.is_alive():
                    self.worker_thread.join(timeout=5)
                self.root.destroy()
        else:
            self.root.destroy()

    def on_run_job_selected(self, event=None):
        """运行页选择岗位后，提醒切换到 BOSS 对应发布职位"""
        selected = self.job_select_var.get()
        if selected and selected != "全部岗位":
            messagebox.showinfo(
                "提示",
                f"请在 BOSS 直聘「推荐牛人」页面，切换到「{selected}」职位后再开始运行。",
                parent=self.root,
            )

    def refresh_results(self):
        """刷新结果 - 增强版：支持表头排序、颜色标记和岗位过滤"""
        try:
            if CANDIDATES_PATH.exists():
                with open(CANDIDATES_PATH, 'r', encoding='utf-8') as f:
                    candidates = json.load(f)

                # 岗位过滤
                selected_job = self.result_job_var.get()
                if selected_job != "全部岗位":
                    candidates = [c for c in candidates if c.get('job_name', '') == selected_job.replace(" ", "")]

                # 计算新的指标
                total = len(candidates)

                # 强烈推荐：匹配分>=75
                strong_list = [c for c in candidates if c.get('match_score', 0) >= 75]
                strong_total = len(strong_list)
                strong_greeted = sum(1 for c in strong_list if c.get('greet_sent', False))

                # 推荐：匹配分>=65 且<75
                recommended_list = [c for c in candidates if 65 <= c.get('match_score', 0) < 75]
                recommended_total = len(recommended_list)
                recommended_greeted = sum(1 for c in recommended_list if c.get('greet_sent', False))

                # 通过筛选 = 强烈推荐 + 推荐
                passed_total = strong_total + recommended_total
                passed_greeted = strong_greeted + recommended_greeted

                # 更新统计卡片
                self.result_stats_vars['passed'].set(str(passed_total))
                self.result_stats_vars['strong'].set(str(strong_total))
                self.result_stats_vars['recommended'].set(str(recommended_total))
                # 更新已打招呼数
                self.result_stats_greeted['passed'].set(f"{passed_greeted} 已打招呼")
                self.result_stats_greeted['strong'].set(f"{strong_greeted} 已打招呼")
                self.result_stats_greeted['recommended'].set(f"{recommended_greeted} 已打招呼")

                for item in self.result_tree.get_children():
                    self.result_tree.delete(item)

                sorted_candidates = sorted(candidates, key=lambda x: x.get('match_score', 0), reverse=True)

                # 配置颜色标记 tag
                self.result_tree.tag_configure('strong_recommend', background=self.colors['bg_tree_tag_high'])
                self.result_tree.tag_configure('recommend', background=self.colors['bg_tree_tag_mid'])
                self.result_tree.tag_configure('pending', background=self.colors['bg_tree_tag_low'])

                for c in sorted_candidates[:100]:
                    score = c.get('match_score', 0)
                    if score < 55:
                        continue  # 低于 55 分不显示
                    level = "强烈推荐" if score >= 75 else ("推荐" if score >= 65 else "待定")
                    status = "已招呼" if c.get('greet_sent', False) else "未招呼"

                    # 根据推荐等级设置颜色标记
                    if score >= 75:
                        tag = 'strong_recommend'
                    elif score >= 65:
                        tag = 'recommend'
                    else:
                        tag = 'pending'

                    # 从 summary 中解析工作年限和薪资
                    salary, exp = self._parse_salary_exp(c.get('summary', ''))

                    # AI 评估调整值
                    ai_adj = c.get('llm_adjustment')
                    if ai_adj is not None and c.get('llm_evaluated'):
                        ai_text = f"+{ai_adj}" if ai_adj > 0 else str(ai_adj)
                    else:
                        ai_text = "—"

                    self.result_tree.insert("", "end", values=(
                        c.get('name', ''),
                        exp,
                        salary,
                        c.get('skill_match_ratio', ''),
                        score,
                        ai_text,
                        level,
                        status
                    ), tags=(tag,))

                # 存储原始数据用于排序和详情展示
                self.result_tree_data = sorted_candidates[:100]
                self.all_candidates = candidates  # 存储全部数据用于详情展示
        except Exception as e:
            self.append_log(f"加载结果失败：{e}")

        # 绑定表头排序（只绑定一次）
        if not hasattr(self, '_sort_bound'):
            self._bind_treeview_sorting()
            self._bind_treeview_context_menu()
            self._sort_bound = True

    def _bind_treeview_sorting(self):
        """绑定 Treeview 表头排序功能"""
        # 设置中文表头显示
        column_headers = {
            "name": "姓名",
            "exp": "工作年限",
            "salary": "薪资",
            "score": "匹配分",
            "level": "推荐指数",
            "ai_eval": "AI评估",
            "status": "状态",
            "skills": "技能匹配"
        }
        columns = self.result_tree['columns']
        for col in columns:
            # 为每个表头添加点击事件，使用中文显示
            header_text = column_headers.get(col, col)
            self.result_tree.heading(col, text=header_text, command=lambda c=col: self._sort_treeview(c))

    def _sort_treeview(self, col):
        """按指定列排序 Treeview"""
        try:
            # 获取当前数据
            items = [(self.result_tree.set(item, col), item) for item in self.result_tree.get_children()]

            # 尝试数值排序
            def sort_key(val):
                try:
                    # 移除单位（如"年"、"K"）
                    val_clean = val.replace('年', '').replace('K', '').replace('千', '')
                    if '-' in val_clean:
                        # 范围值取平均
                        parts = val_clean.split('-')
                        return (float(parts[0]) + float(parts[1])) / 2
                    return float(val_clean)
                except (ValueError, TypeError):
                    return 0 if val == '' else 999999

            items.sort(key=sort_key)

            # 移动项
            for index, (val, item) in enumerate(items):
                self.result_tree.move(item, '', index)

            # 切换排序方向（可选优化：下次点击反向排序）
            if not hasattr(self, '_sort_reverse'):
                self._sort_reverse = False
            self._sort_reverse = not self._sort_reverse

        except Exception as e:
            pass

    def _bind_treeview_context_menu(self):
        """绑定 Treeview 右键菜单"""
        self.result_tree.bind('<Button-3>', self._show_context_menu)

    def _show_context_menu(self, event):
        """显示右键菜单"""
        # 选中点击项
        item = self.result_tree.identify_row(event.y)
        if item:
            self.result_tree.selection_set(item)

            # 创建菜单
            context_menu_font = (FONT_FAMILY, int(16 * self.dpi_scale * self.zoom_factor))
            menu = tk.Menu(self.root, tearoff=0, font=context_menu_font)
            icon_detail = self.icons.button('clipboard', self.colors['text_primary'])
            icon_greet = self.icons.button('play', self.colors['success'])
            icon_trash_menu = self.icons.button('trash', self.colors['text_primary'])
            icon_export_menu = self.icons.button('export', self.colors['text_primary'])
            menu.add_command(label=" 查看详情", image=icon_detail, compound=tk.LEFT, command=lambda: self._show_candidate_detail(item))

            # 打招呼：仅对未打招呼的候选人显示
            values = self.result_tree.item(item, 'values')
            if values and '未招呼' in str(values):
                menu.add_command(label=" 打招呼", image=icon_greet, compound=tk.LEFT, command=lambda: self._greet_single_candidate(item))

            menu.add_command(label=" 移除此人", image=icon_trash_menu, compound=tk.LEFT, command=lambda: self._remove_candidate(item))
            menu.add_separator()
            menu.add_command(label=" 导出选中", image=icon_export_menu, compound=tk.LEFT, command=lambda: self._export_selected())

            # 保持引用防止 GC
            menu._icon_refs = [icon_detail, icon_greet, icon_trash_menu, icon_export_menu]

            # 显示菜单
            menu.tk_popup(event.x_root, event.y_root)

    def _format_candidate_detail(self, c):
        """格式化候选人详情为结构化文本（替代原始 JSON dump）"""
        from bossmaster import extract_summary_info

        summary = c.get('summary', '')
        info = extract_summary_info(summary)

        lines = []
        lines.append("═" * 50)
        lines.append(f"  姓名：{c.get('name', '未知')}")
        lines.append(f"  岗位：{c.get('job_name', '未知')}")

        # 核心信息速览
        core_parts = []
        age = info.get('age')
        if age:
            core_parts.append(f"{age} 岁")
        exp = info.get('exp_years')
        if exp:
            core_parts.append(f"{exp} 年")
        salary = info.get('salary')
        if salary:
            core_parts.append(f"期望薪资 {salary}")
        status = info.get('job_status')
        if status:
            core_parts.append(status)
        if core_parts:
            lines.append(f"  {'｜'.join(core_parts)}")

        # 学历/学校/专业 — 顺序：学校·专业·学历
        edu_parts = []
        edu = info.get('education')
        # 从 summary 提取学校和专业（BOSS 格式为"河海大学计算机科学与技术本科"，无分隔符）
        # 学校名以"大学"或"学院"结尾，后面是专业名，最后是学历等级
        edu_entry_pat = re.compile(r'(.+(?:大学|学院))(.+?)(本科|硕士|博士|大专|MBA|EMBA)\s*$')
        edu_nopat = re.compile(r'(.+(?:大学|学院))(本科|硕士|博士|大专|MBA|EMBA)\s*$')
        for sline in summary.split('\n'):
            sline = sline.strip()
            m = edu_entry_pat.match(sline)
            if m:
                school, major, _ = m.group(1), m.group(2), m.group(3)
                edu_parts.append(school)
                if major:
                    edu_parts.append(major)
                break
            m2 = edu_nopat.match(sline)
            if m2:
                edu_parts.append(m2.group(1))
                break
        # 学历等级放最后
        if edu:
            edu_parts.append(edu)
        if edu_parts:
            lines.append(f"  {'·'.join(edu_parts)}")

        lines.append(f"  geek_id：{c.get('geek_id', '')}")
        lines.append("═" * 50)

        # 评分信息
        lines.append("")
        lines.append("【评分信息】")
        score = c.get('match_score', 0)
        level = "强烈推荐" if score >= 75 else ("推荐" if score >= 65 else "待定")
        lines.append(f"  匹配分：{score}（{level}）")
        lines.append(f"  技能匹配：{c.get('skill_match_ratio', '—')}")
        if c.get('greet_sent'):
            lines.append(f"  状态：已打招呼")
        else:
            lines.append(f"  状态：未打招呼")

        # AI 评估信息
        lines.append("")
        if c.get('llm_evaluated'):
            lines.append("【AI 评估】")
            lines.append(f"  原始规则分：{c.get('rule_score', '—')}")
            adj = c.get('llm_adjustment', 0)
            sign = "+" if adj > 0 else ""
            lines.append(f"  AI 调整值：{sign}{adj}")
            lines.append(f"  调整后分数：{score}")
            lines.append(f"  评估模型：{c.get('llm_model', '未知')}")
            lines.append("")
            lines.append(f"  AI评估：")
            reason = c.get('llm_reason', '无')
            # 自动换行
            while len(reason) > 40:
                lines.append(f"    {reason[:40]}")
                reason = reason[40:]
            lines.append(f"    {reason}")
        else:
            lines.append("【AI 评估】未启用")

        # 技能匹配详情
        skill_matches = c.get('skill_matches', [])
        if skill_matches:
            lines.append("")
            ratio = c.get('skill_match_ratio', '')
            lines.append(f"【技能匹配详情 {ratio}】")
            for sm in skill_matches:
                if isinstance(sm, dict):
                    sname = sm.get('name', '')
                    sweight = sm.get('weight', 1)
                    lines.append(f"  ✓ {sname}（权重{sweight}）")
                else:
                    lines.append(f"  ✓ {sm}")

        # 候选人摘要
        if summary:
            lines.append("")
            lines.append("【候选人摘要】")
            for sline in summary.split('\n'):
                lines.append(f"  {sline}")

        return '\n'.join(lines)

    def _show_candidate_detail(self, item):
        """显示候选人详情"""
        try:
            values = self.result_tree.item(item, 'values')
            if not values:
                return

            # 创建详情窗口
            detail_window = tk.Toplevel(self.root)
            detail_window.title("候选人详情")
            detail_window.transient(self.root)
            detail_window.grab_set()
            detail_window.withdraw()

            # 标题
            title = f"姓名：{values[0]} | 匹配分：{values[4]} | {values[6]}"
            ttk.Label(detail_window, text=title, font=(FONT_FAMILY, 16), foreground=self.colors['primary']).pack(pady=15)

            # 详情文本
            text_widget = tk.Text(detail_window, wrap='word', font=(FONT_FAMILY, 14))
            text_widget.pack(fill='both', expand=True, padx=20, pady=10)
            self.bind_text_context_menu(text_widget, editable=False)

            # 查找对应候选人数据
            for i, c in enumerate(self.result_tree_data):
                if c.get('name') == values[0]:
                    detail_text = self._format_candidate_detail(c)
                    text_widget.insert('1.0', detail_text)
                    break

            # 相对父窗口居中（与模型列表弹窗相同实现）
            detail_window.update_idletasks()
            px = self.root.winfo_x()
            py = self.root.winfo_y()
            pw = self.root.winfo_width()
            ph = self.root.winfo_height()
            w, h = 700, 580
            x = px + (pw - w) // 2
            y = py + (ph - h) // 2
            detail_window.geometry(f"{w}x{h}+{max(0, x)}+{max(0, y)}")
            detail_window.deiconify()

        except Exception as e:
            messagebox.showerror("错误", f"查看详情失败：{e}")

    def _greet_single_candidate(self, item):
        """对单个候选人打招呼（在后台线程执行）"""
        values = self.result_tree.item(item, 'values')
        if not values:
            return

        name = values[0]
        score = values[4]

        # 查找候选人数据
        candidate = None
        geek_id = None
        if hasattr(self, 'result_tree_data'):
            for c in self.result_tree_data:
                if c.get('name') == name and str(c.get('match_score', '')) == str(score):
                    candidate = c
                    geek_id = c.get('geek_id')
                    break

        if not geek_id:
            messagebox.showwarning("警告", f"未找到候选人 {name} 的数据")
            return

        # 确认操作
        job_name = candidate.get('job_name', '未知岗位')
        if not messagebox.askyesno("确认打招呼",
                                   f"确定要向 {name}（{candidate.get('recommend_level', '')}，{score}分）打招呼吗？\n\n"
                                   f"岗位：{job_name}\n"
                                   f"请确保浏览器已在该岗位的推荐牛人页面。",
                                   parent=self.root):
            return

        # 立即更新表格状态为"打招呼中..."，给用户即时反馈
        self.result_tree.set(item, 'status', '打招呼中...')
        self.result_tree.update_idletasks()

        # 后台线程执行打招呼
        def greet_worker():
            try:
                # 浏览器未连接时自动尝试重连（读取持久化端口）
                if not self.browser_page:
                    self.append_log(f"[打招呼] 浏览器未连接，正在尝试重连...")
                    def _revert_connecting():
                        try:
                            self.result_tree.set(item, 'status', '未招呼')
                        except Exception:
                            pass
                    if not self._try_reconnect_browser():
                        self.append_log(f"[打招呼] ❌ 浏览器重连失败，请先在「运行控制」页连接浏览器")
                        self.root.after(0, _revert_connecting)
                        self.root.after(0, lambda: messagebox.showwarning(
                            "浏览器未连接",
                            "无法连接到 Chrome 浏览器。\n请切换到「运行控制」页点击「检测/连接浏览器」。",
                            parent=self.root))
                        return
                    self.append_log(f"[打招呼] ✅ 浏览器重连成功")

                from bossmaster import send_greeting_on_list_page
                self.append_log(f"[打招呼] 正在向 {name} 打招呼...")
                success, msg = send_greeting_on_list_page(
                    self.browser_page, geek_id, stop_event=self.stop_event
                )
                if success:
                    self.append_log(f"[打招呼] ✅ {name} — {msg}")
                    # 更新 JSON 中的 greet_sent 状态
                    candidate['greet_sent'] = True
                    self._update_greet_status(geek_id, job_name, True)
                    # 同步更新 Excel 文件
                    self._regenerate_excel()
                    # 刷新结果页和首页统计
                    self.root.after(0, self.refresh_results)
                    self.root.after(0, self.refresh_home_stats)
                else:
                    self.append_log(f"[打招呼] ❌ {name} 失败：{msg}")
                    # 恢复表格状态（item 可能已被刷新删除，需 try/except）
                    def _revert_status():
                        try:
                            self.result_tree.set(item, 'status', '未招呼')
                        except Exception:
                            pass
                    self.root.after(0, _revert_status)
                    # 沟通次数上限
                    if "上限" in msg or "次数" in msg:
                        self.root.after(0, lambda: messagebox.showwarning(
                            "沟通次数已达上限",
                            "BOSS 直聘今日沟通次数已用完，请明天再试。",
                            parent=self.root))
            except Exception as e:
                self.append_log(f"[打招呼] ❌ {name} 异常：{e}")
                def _revert_status_exc():
                    try:
                        self.result_tree.set(item, 'status', '未招呼')
                    except Exception:
                        pass
                self.root.after(0, _revert_status_exc)

        threading.Thread(target=greet_worker, daemon=True).start()

    def _try_reconnect_browser(self) -> bool:
        """尝试重连浏览器（读取持久化端口，不启动新 Chrome）

        用于筛选结果页打招呼等场景：用户可能没去过运行控制页，
        但 Chrome 已经在运行（上次扫描启动的）。

        Returns:
            True 表示连接成功，self.browser_page 已赋值
        """
        import socket
        try:
            # 读取持久化端口
            addr = getattr(self, 'browser_address', None)
            if not addr:
                try:
                    saved_port = CHROME_DEBUG_PORT_FILE.read_text(encoding='utf-8').strip()
                    if saved_port.isdigit():
                        addr = f'127.0.0.1:{saved_port}'
                except OSError:
                    pass
            if not addr:
                addr = '127.0.0.1:9222'

            host, port = addr.rsplit(':', 1)
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1)
            port_open = s.connect_ex((host, int(port))) == 0
            s.close()

            if not port_open:
                return False

            # 端口开放，尝试 DrissionPage 连接
            from DrissionPage import ChromiumPage, ChromiumOptions
            co = ChromiumOptions()
            co.set_address(f'{host}:{port}')
            page = ChromiumPage(co)

            self.browser_page = page
            self.browser_address = page.address
            self.browser_connected = True
            return True

        except Exception as e:
            self.append_log(f"[浏览器] 重连失败：{e}")
            self.browser_page = None
            self.browser_connected = False
            return False

    def _update_greet_status(self, geek_id, job_name, greet_sent):
        """更新 candidates_all.json 中指定候选人的打招呼状态"""
        try:
            if not CANDIDATES_PATH.exists():
                return
            with open(CANDIDATES_PATH, 'r', encoding='utf-8') as f:
                candidates = json.load(f)
            updated = False
            for c in candidates:
                if c.get('geek_id') == geek_id and c.get('job_name', '').replace(" ", "") == job_name.replace(" ", ""):
                    c['greet_sent'] = greet_sent
                    updated = True
                    break
            if updated:
                with open(CANDIDATES_PATH, 'w', encoding='utf-8') as f:
                    json.dump(candidates, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.append_log(f"[打招呼] 更新状态失败：{e}")

    def _regenerate_excel(self):
        """打招呼后同步更新 Excel 文件（静默，不弹窗）"""
        try:
            if not CANDIDATES_PATH.exists():
                return
            from bossmaster import export_to_excel
            with open(CANDIDATES_PATH, 'r', encoding='utf-8') as f:
                candidates = json.load(f)
            export_to_excel(candidates, str(CANDIDATES_XLSX_PATH))
        except Exception as e:
            self.append_log(f"[Excel] 同步更新失败：{e}")

    def _remove_candidate(self, item):
        """移除选中候选人"""
        if messagebox.askyesno("确认删除", "确定要移除该候选人吗？"):
            try:
                values = self.result_tree.item(item, 'values')
                name = values[0]
                score = values[4]

                # 通过 name+score 精确定位候选人，获取 geek_id
                target_geek_id = None
                if hasattr(self, 'result_tree_data'):
                    for c in self.result_tree_data:
                        if c.get('name') == name and str(c.get('match_score', '')) == str(score):
                            target_geek_id = c.get('geek_id')
                            break

                if not target_geek_id:
                    messagebox.showerror("错误", f"未找到候选人：{name}")
                    return

                # 从数据中移除（用 geek_id 精确匹配，避免同名误删）
                if hasattr(self, 'result_tree_data'):
                    self.result_tree_data = [c for c in self.result_tree_data if c.get('geek_id') != target_geek_id]

                # 从 JSON 文件中移除
                if CANDIDATES_PATH.exists():
                    with open(CANDIDATES_PATH, 'r', encoding='utf-8') as f:
                        candidates = json.load(f)
                    candidates = [c for c in candidates if c.get('geek_id') != target_geek_id]
                    with open(CANDIDATES_PATH, 'w', encoding='utf-8') as f:
                        json.dump(candidates, f, ensure_ascii=False, indent=2)

                    # 从树中移除
                    self.result_tree.delete(item)

                    # 刷新统计
                    self.refresh_results()

                    messagebox.showinfo("成功", f"已移除：{name}")
            except Exception as e:
                messagebox.showerror("错误", f"移除失败：{e}")

    def _export_selected(self):
        """导出选中的候选人"""
        selection = self.result_tree.selection()
        if not selection:
            messagebox.showwarning("警告", "请先选择要导出的候选人")
            return

        # 获取选中项的数据
        selected_data = []
        for item in selection:
            values = self.result_tree.item(item, 'values')
            for c in self.result_tree_data:
                if c.get('name') == values[0]:
                    selected_data.append(c)
                    break

        # 导出到文件
        file_path = filedialog.asksaveasfilename(
            title="保存选中的候选人",
            defaultextension=".json",
            filetypes=[("JSON 文件", "*.json"), ("所有文件", "*.*")],
            initialfile=f"selected_candidates_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )

        if file_path:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(selected_data, f, ensure_ascii=False, indent=2)
            messagebox.showinfo("成功", f"已导出 {len(selected_data)} 个候选人")

    def export_excel(self):
        """导出 Excel"""
        try:
            from bossmaster import export_to_excel
            if CANDIDATES_PATH.exists():
                with open(CANDIDATES_PATH, 'r', encoding='utf-8') as f:
                    candidates = json.load(f)

                # 弹出文件保存对话框
                file_path = filedialog.asksaveasfilename(
                    title="保存 Excel 文件",
                    defaultextension=".xlsx",
                    filetypes=[("Excel 文件", "*.xlsx")],
                    initialfile=f"candidates_all_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
                )

                if file_path:
                    export_to_excel(candidates, file_path)
                    messagebox.showinfo("成功", f"Excel 文件已导出：{file_path}")
            else:
                messagebox.showwarning("警告", "没有候选人数据")
        except Exception as e:
            messagebox.showerror("错误", f"导出失败：{e}")

    def open_json(self):
        """打开 JSON 文件"""
        if CANDIDATES_PATH.exists():
            os.startfile(str(CANDIDATES_PATH))
        else:
            messagebox.showwarning("警告", "文件不存在")

    def clear_candidates(self):
        """清空候选人数据"""
        if not CANDIDATES_PATH.exists():
            messagebox.showinfo("提示", "暂无候选人数据")
            return

        # 读取当前岗位过滤条件
        selected_job = self.result_job_var.get() if hasattr(self, 'result_job_var') else "全部岗位"
        is_all_jobs = selected_job == "全部岗位"

        # 统计已打招呼人数
        greeted_count = 0
        try:
            with open(CANDIDATES_PATH, 'r', encoding='utf-8') as f:
                _candidates = json.load(f)
            if is_all_jobs:
                greeted_count = sum(1 for c in _candidates if c.get('greet_sent'))
            else:
                job_name = selected_job.replace(" ", "")
                greeted_count = sum(1 for c in _candidates if c.get('greet_sent') and c.get('job_name', '') == job_name)
        except (OSError, json.JSONDecodeError):
            pass

        # 构建确认对话框
        dialog = tk.Toplevel(self.root)
        dialog.title("清空候选人")
        dialog.transient(self.root)
        dialog.withdraw()

        dialog_width = 460
        dialog_height = 300
        self._center_window(dialog, dialog_width, dialog_height)

        # 标题
        ttk.Label(dialog, text="清空候选人数据",
                  font=(FONT_FAMILY, int(16 * self.dpi_scale * self.zoom_factor)),
                  foreground=self.colors['danger']).pack(pady=(int(20 * self.dpi_scale * self.zoom_factor), int(10 * self.dpi_scale * self.zoom_factor)))

        # 选项
        choice_var = tk.StringVar(value="all" if is_all_jobs else "current")

        radio_frame = ttk.Frame(dialog, style='TFrame')
        radio_frame.pack(fill="x", padx=int(30 * self.dpi_scale * self.zoom_factor))

        # 配置大号 RadioButton 样式
        dialog_rb_font = (FONT_FAMILY, int(14 * self.dpi_scale * self.zoom_factor))
        style = ttk.Style()
        style.configure('ClearDialog.TRadiobutton', font=dialog_rb_font)
        style.configure('ClearDialog.TCheckbutton', font=dialog_rb_font)

        rb_current = ttk.Radiobutton(radio_frame,
                                     text=f"清空当前岗位数据（{selected_job}）",
                                     variable=choice_var, value="current",
                                     style='ClearDialog.TRadiobutton')
        rb_current.pack(anchor="w", pady=int(5 * self.dpi_scale * self.zoom_factor))
        if is_all_jobs:
            rb_current.config(state="disabled")

        rb_all = ttk.Radiobutton(radio_frame,
                                 text="清空全部数据（所有岗位）",
                                 variable=choice_var, value="all",
                                 style='ClearDialog.TRadiobutton')
        rb_all.pack(anchor="w", pady=int(5 * self.dpi_scale * self.zoom_factor))

        # 分隔线
        ttk.Separator(dialog, orient="horizontal").pack(
            fill="x", padx=int(30 * self.dpi_scale * self.zoom_factor),
            pady=(int(10 * self.dpi_scale * self.zoom_factor), int(6 * self.dpi_scale * self.zoom_factor)))

        # 保留已打招呼复选框
        keep_greeted_var = tk.BooleanVar(value=True)
        cb_frame = ttk.Frame(dialog, style='TFrame')
        cb_frame.pack(fill="x", padx=int(30 * self.dpi_scale * self.zoom_factor),
                       pady=(int(12 * self.dpi_scale * self.zoom_factor), 0))
        cb_text = f"保留已打招呼的候选人（{greeted_count} 人）" if greeted_count > 0 else "保留已打招呼的候选人（无）"
        cb_greeted = ttk.Checkbutton(cb_frame, text=cb_text,
                                      variable=keep_greeted_var,
                                      style='ClearDialog.TCheckbutton')
        cb_greeted.pack(anchor="w")
        if greeted_count == 0:
            cb_greeted.config(state="disabled")
            keep_greeted_var.set(False)

        # 提示
        ttk.Label(dialog, text="操作前会自动备份数据文件，清空后不可恢复",
                  font=(FONT_FAMILY, int(13 * self.dpi_scale * self.zoom_factor)),
                  foreground=self.colors['text_muted']).pack(pady=(int(12 * self.dpi_scale * self.zoom_factor), 0))

        # 按钮
        btn_frame = ttk.Frame(dialog, style='TFrame')
        btn_frame.pack(pady=int(15 * self.dpi_scale * self.zoom_factor))

        def do_clear():
            choice = choice_var.get()
            keep_greeted = keep_greeted_var.get()
            dialog.destroy()

            confirm_msg = "确定要清空候选人数据吗？\n\n操作前会自动备份，但清空后不可恢复。"
            if keep_greeted and greeted_count > 0:
                confirm_msg = f"确定要清空候选人数据吗？\n\n已打招呼的 {greeted_count} 人将被保留。\n操作前会自动备份，但清空后不可恢复。"
            if not messagebox.askyesno("确认", confirm_msg):
                return

            try:
                # 备份
                backup_path = CANDIDATES_PATH.with_suffix('.json.bak')
                shutil.copy2(CANDIDATES_PATH, backup_path)
                self.append_log(f"已备份候选人数据到 {backup_path.name}")

                with open(CANDIDATES_PATH, 'r', encoding='utf-8') as f:
                    candidates = json.load(f)

                kept_count = 0

                if choice == "current":
                    # 清空当前岗位
                    job_name = selected_job.replace(" ", "")
                    other_jobs = [c for c in candidates if c.get('job_name', '') != job_name]
                    current_job = [c for c in candidates if c.get('job_name', '') == job_name]

                    if keep_greeted:
                        kept = [c for c in current_job if c.get('greet_sent')]
                        removed_list = [c for c in current_job if not c.get('greet_sent')]
                        candidates = other_jobs + kept
                        kept_count = len(kept)
                    else:
                        candidates = other_jobs
                        removed_list = current_job

                    removed = len(removed_list)

                    with open(CANDIDATES_PATH, 'w', encoding='utf-8') as f:
                        json.dump(candidates, f, ensure_ascii=False, indent=2)

                    log_msg = f"已清空岗位「{selected_job}」的 {removed} 条候选人数据"
                    info_msg = f"已清空 {removed} 条候选人数据"
                    if kept_count > 0:
                        log_msg += f"，保留 {kept_count} 条已打招呼记录"
                        info_msg += f"，保留 {kept_count} 条已打招呼记录"
                    self.append_log(log_msg)
                    messagebox.showinfo("完成", info_msg)
                else:
                    # 清空全部
                    if keep_greeted:
                        kept = [c for c in candidates if c.get('greet_sent')]
                        removed = len(candidates) - len(kept)
                        candidates = kept
                        kept_count = len(kept)
                    else:
                        removed = len(candidates)
                        candidates = []

                    with open(CANDIDATES_PATH, 'w', encoding='utf-8') as f:
                        json.dump(candidates, f, ensure_ascii=False, indent=2)

                    log_msg = f"已清空全部 {removed} 条候选人数据"
                    info_msg = f"已清空全部 {removed} 条候选人数据"
                    if kept_count > 0:
                        log_msg += f"，保留 {kept_count} 条已打招呼记录"
                        info_msg += f"，保留 {kept_count} 条已打招呼记录"
                    self.append_log(log_msg)
                    messagebox.showinfo("完成", info_msg)

                # 同步 Excel
                self._regenerate_excel()

                # 刷新所有相关页面
                self.refresh_results()
                self.refresh_home_stats()
                self.refresh_stats()

            except Exception as e:
                messagebox.showerror("错误", f"清空失败：{e}")

        ttk.Button(btn_frame, text="确定", command=do_clear).pack(side="left", padx=int(10 * self.dpi_scale * self.zoom_factor))
        ttk.Button(btn_frame, text="取消", command=dialog.destroy).pack(side="left", padx=int(10 * self.dpi_scale * self.zoom_factor))

        dialog.deiconify()

    def show_help(self):
        """显示帮助"""
        help_text = """BOSS 简历筛选器 - 使用说明

1. 岗位配置：
   - 选择或新建岗位
   - 配置经验、学历、技能要求
   - 保存配置

2. 运行控制：
   - 设置滚动轮次（推荐 50-200）
   - 选择打招呼等级
   - 点击"开始运行"

3. 筛选结果：
   - 查看候选人列表
   - 导出 Excel 文件

注意事项：
- 需要 Chrome 浏览器
- 程序启动后需手动导航到 BOSS 直聘推荐页面
- 定期备份 candidates_all.json 文件"""
        messagebox.showinfo("使用说明", help_text)

    def show_about(self):
        """显示关于弹窗"""
        import webbrowser

        dialog = tk.Toplevel(self.root)
        dialog.title("关于 BOSS 简历筛选器")
        dialog.transient(self.root)
        dialog.resizable(False, False)

        # 居中显示
        dialog.update_idletasks()
        w, h = 480, 420
        x = self.root.winfo_x() + (self.root.winfo_width() - w) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - h) // 2
        dialog.geometry(f"{w}x{h}+{x}+{y}")

        # 标题
        tk.Label(dialog, text="BOSS 简历筛选器",
                 font=('Microsoft YaHei UI', 18, 'bold')).pack(pady=(25, 5))

        # 版本号
        tk.Label(dialog, text=f"v{__version__}",
                 font=('Microsoft YaHei UI', 11),
                 foreground=self.colors.get('text_secondary', '#666')).pack(pady=(0, 15))

        # 功能描述
        tk.Label(dialog, text="智能候选人筛选 · 自动打招呼 · Excel 导出",
                 font=('Microsoft YaHei UI', 10)).pack(pady=(0, 5))

        tk.Label(dialog, text="基于 DrissionPage 的 BOSS 直聘自动化工具",
                 font=('Microsoft YaHei UI', 10),
                 foreground=self.colors.get('text_secondary', '#666')).pack(pady=(0, 15))

        # 分隔线
        ttk.Separator(dialog, orient="horizontal").pack(fill="x", padx=40, pady=10)

        # GitHub 项目链接
        github_url = "https://github.com/yaoyouzhong/boss-resume-filter"
        github_frame = tk.Frame(dialog)
        github_frame.pack(pady=(5, 2))
        tk.Label(github_frame, text="GitHub: ",
                 font=('Microsoft YaHei UI', 10)).pack(side="left")
        github_label = tk.Label(github_frame, text=github_url,
                                font=('Microsoft YaHei UI', 10),
                                foreground="#1E88E5", cursor="hand2")
        github_label.pack(side="left")
        github_label.bind("<Button-1>",
                          lambda e: webbrowser.open(github_url))

        # Issue 反馈
        issue_url = "https://github.com/yaoyouzhong/boss-resume-filter/issues"
        issue_frame = tk.Frame(dialog)
        issue_frame.pack(pady=(2, 10))
        tk.Label(issue_frame, text="反馈: ",
                 font=('Microsoft YaHei UI', 10)).pack(side="left")
        issue_label = tk.Label(issue_frame, text="问题反馈与建议",
                               font=('Microsoft YaHei UI', 10),
                               foreground="#1E88E5", cursor="hand2")
        issue_label.pack(side="left")
        issue_label.bind("<Button-1>",
                         lambda e: webbrowser.open(issue_url))

        # 环境信息
        tk.Label(dialog,
                 text=f"Python {sys.version.split()[0]} · Tk {tk.TkVersion} · {sys.platform.title()}",
                 font=('Microsoft YaHei UI', 9),
                 foreground=self.colors.get('text_muted', '#999')).pack(pady=(5, 15))

        # 按钮区
        btn_frame = tk.Frame(dialog)
        btn_frame.pack(pady=(5, 10))

        tk.Button(btn_frame, text="检查更新", width=12,
                  font=('Microsoft YaHei UI', 10),
                  command=lambda: (dialog.destroy(),
                                   updater.check_and_update_gui(self.root, silent=False))
                  ).pack(side="left", padx=10)

        tk.Button(btn_frame, text="关闭", width=12,
                  font=('Microsoft YaHei UI', 10),
                  command=dialog.destroy).pack(side="left", padx=10)

        # ESC 关闭
        dialog.bind('<Escape>', lambda e: dialog.destroy())
        dialog.grab_set()

    def show_changelog(self):
        """显示更新日志（版本列表 + 详情分栏）"""
        import sys
        # PyInstaller --add-data 解压到 _MEIPASS，优先从那里读取
        meipass = getattr(sys, '_MEIPASS', None)
        changelog_path = (Path(meipass) / "CHANGELOG.md") if meipass else None
        if not changelog_path or not changelog_path.exists():
            changelog_path = BASE_DIR / "CHANGELOG.md"
        if not changelog_path.exists():
            messagebox.showinfo("更新日志", "CHANGELOG.md 文件不存在")
            return

        try:
            content = changelog_path.read_text(encoding="utf-8")
        except Exception as e:
            messagebox.showerror("错误", f"读取更新日志失败：{e}")
            return

        # 解析版本段落
        versions = []  # list of (version_tag, subtitle, full_section_text)
        current_version = None
        current_lines = []
        for line in content.splitlines():
            if line.startswith("## v"):
                if current_version:
                    versions.append((current_version, current_lines[0], "\n".join(current_lines)))
                rest = line[3:].strip()
                tag = rest.split("—")[0].split("–")[0].split()[0].strip()
                current_version = tag
                current_lines = [line]
            elif current_version:
                current_lines.append(line)
        if current_version:
            versions.append((current_version, current_lines[0], "\n".join(current_lines)))

        if not versions:
            messagebox.showinfo("更新日志", "CHANGELOG.md 中没有版本记录")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title("更新日志")
        dialog.transient(self.root)
        dialog.withdraw()

        dw, dh = 940, 620
        self.root.update_idletasks()
        rx = self.root.winfo_rootx()
        ry = self.root.winfo_rooty()
        rw = self.root.winfo_width()
        rh = self.root.winfo_height()
        x = rx + (rw - dw) // 2
        y = ry + (rh - dh) // 2
        dialog.geometry(f"{dw}x{dh}+{x}+{y}")

        fs = self.dpi_scale * self.zoom_factor

        # ---- 左侧版本列表（深色侧边栏风格）----
        sidebar_bg = '#2D3748'
        left_frame = tk.Frame(dialog, bg=sidebar_bg, width=int(160 * fs))
        left_frame.pack(side="left", fill="y")
        left_frame.pack_propagate(False)

        # 标题
        tk.Label(left_frame, text="版本历史", bg=sidebar_bg, fg='#E2E8F0',
                 font=(FONT_FAMILY, int(14 * fs), 'bold')).pack(
            anchor="center", padx=int(16 * fs), pady=(int(20 * fs), int(12 * fs)))

        # 版本列表
        listbox_font = (FONT_FAMILY, int(12 * fs))
        listbox = tk.Listbox(left_frame, width=16, font=listbox_font,
                             bg=sidebar_bg, fg='#CBD5E0',
                             selectbackground=self.colors['primary'],
                             selectforeground='#FFFFFF',
                             borderwidth=0, highlightthickness=0,
                             activestyle='none',
                             selectborderwidth=0,
                             justify='center',
                             relief='flat')
        listbox.pack(fill="both", expand=True, padx=int(12 * fs), pady=int(4 * fs))

        for tag, title_line, _ in versions:
            listbox.insert("end", tag)

        # 左侧边栏底部：关于链接
        about_label = tk.Label(left_frame, text="关于",
                               bg=sidebar_bg, fg='#A0AEC0',
                               font=(FONT_FAMILY, int(10 * fs)),
                               cursor="hand2")
        about_label.pack(padx=int(12 * fs), pady=(int(8 * fs), int(12 * fs)))
        about_label.bind("<Button-1>", lambda e: (dialog.destroy(), self.show_about()))

        # ---- 右侧详情 ----
        right_outer = tk.Frame(dialog, bg=self.colors['bg_main'])
        right_outer.pack(side="left", fill="both", expand=True)

        # 顶部标题栏
        header_frame = tk.Frame(right_outer, bg=self.colors['bg_card'], height=int(72 * fs))
        header_frame.pack(fill="x")
        header_frame.pack_propagate(False)

        version_title = tk.Label(header_frame, text="",
                                 font=(FONT_FAMILY, int(16 * fs), 'bold'),
                                 fg=self.colors['text_primary'], bg=self.colors['bg_card'])
        version_title.pack(anchor="w", padx=int(20 * fs), pady=(int(14 * fs), 0))

        version_subtitle = tk.Label(header_frame, text="",
                                    font=(FONT_FAMILY, int(11 * fs)),
                                    fg=self.colors['text_muted'], bg=self.colors['bg_card'])
        version_subtitle.pack(anchor="w", padx=int(20 * fs))

        # 分隔线
        tk.Frame(right_outer, bg=self.colors['border'], height=1).pack(fill="x")

        # 内容区
        content_frame = tk.Frame(right_outer, bg=self.colors['bg_main'])
        content_frame.pack(fill="both", expand=True)

        text_widget = tk.Text(content_frame, wrap="word", borderwidth=0,
                              font=('Microsoft YaHei UI', int(11 * fs)),
                              bg=self.colors['bg_main'], fg=self.colors['text_primary'],
                              padx=int(12 * fs), pady=int(12 * fs),
                              selectbackground=self.colors['primary'],
                              relief='flat', highlightthickness=0)
        text_widget.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(content_frame, orient="vertical", command=text_widget.yview)
        scrollbar.pack(side="right", fill="y")
        text_widget.configure(yscrollcommand=scrollbar.set)

        # 配置 tag 样式
        title_font = (FONT_FAMILY, int(13 * fs), 'bold')
        section_font = (FONT_FAMILY, int(12 * fs), 'bold')
        item_font = ('Microsoft YaHei UI', int(11 * fs))
        text_widget.tag_configure("title", font=title_font, foreground=self.colors['primary'])
        text_widget.tag_configure("section_new", font=section_font, foreground=self.colors['success'])
        text_widget.tag_configure("section_opt", font=section_font, foreground=self.colors['primary'])
        text_widget.tag_configure("section_ui", font=section_font, foreground=self.colors['purple'])
        text_widget.tag_configure("section_fix", font=section_font, foreground=self.colors['danger'])
        text_widget.tag_configure("section_build", font=section_font, foreground=self.colors['warning'])
        text_widget.tag_configure("item", font=item_font, foreground=self.colors['text_secondary'])
        text_widget.tag_configure("item_bold", font=(item_font[0], item_font[1], 'bold'), foreground=self.colors['text_primary'])

        # 分类名 → tag 映射
        section_map = {
            '新增功能': 'section_new',
            '行为优化': 'section_opt',
            '性能优化': 'section_opt',
            'UI 改进': 'section_ui',
            'UI改进': 'section_ui',
            'Bug 修复': 'section_fix',
            'Bug修复': 'section_fix',
            '构建改进': 'section_build',
        }

        def show_version(index):
            tag, title_line, section = versions[index]
            # 更新顶部标题
            version_title.config(text=tag)
            # 提取副标题（## v2.7 — LLM 智能评估... → LLM 智能评估...）
            if "—" in title_line:
                sub = title_line.split("—", 1)[1].strip()
            elif "–" in title_line:
                sub = title_line.split("–", 1)[1].strip()
            else:
                sub = ""
            version_subtitle.config(text=sub)

            text_widget.configure(state="normal")
            text_widget.delete("1.0", "end")
            for line in section.splitlines():
                if line.startswith("## "):
                    # 跳过标题行（header 栏已显示版本号和副标题）
                    continue
                elif line.startswith("### "):
                    section_name = line[4:].strip()
                    stag = section_map.get(section_name, 'section_opt')
                    text_widget.insert("end", "\n" + section_name + "\n", stag)
                elif line.startswith("- "):
                    item_text = line[2:]
                    # 整行统一 item tag，标题部分叠加 item_bold（同字号加粗）
                    if item_text.startswith("**"):
                        end_pos = item_text.find("**", 2)
                        if end_pos > 0:
                            title_part = item_text[2:end_pos]
                            rest = item_text[end_pos + 2:]
                            full_text = "  • " + title_part + rest + "\n\n"
                            line_start = text_widget.index("end")
                            text_widget.insert("end", full_text, "item")
                            # 标题部分叠加 bold tag（4 = len("  • ")）
                            bold_start = f"{line_start} + 4 chars"
                            bold_end = f"{line_start} + {4 + len(title_part)} chars"
                            text_widget.tag_add("item_bold", bold_start, bold_end)
                        else:
                            text_widget.insert("end", "  • " + item_text + "\n\n", "item")
                    else:
                        text_widget.insert("end", "  • " + item_text + "\n\n", "item")
            text_widget.configure(state="disabled")
            text_widget.yview_moveto(0)

        def on_select(event):
            sel = listbox.curselection()
            if sel:
                show_version(sel[0])

        listbox.bind("<<ListboxSelect>>", on_select)

        # 默认选中第一个版本（最新）
        listbox.selection_set(0)
        show_version(0)

        dialog.deiconify()


def main():
    root = tk.Tk()

    # 先隐藏窗口
    root.withdraw()

    # 创建应用（会初始化界面）
    app = BossFilterGUI(root)

    # 窗口居中显示
    root.update_idletasks()
    width = root.winfo_width()
    height = root.winfo_height()
    x = (root.winfo_screenwidth() - width) // 2
    y = (root.winfo_screenheight() - height) // 2
    root.geometry(f'{width}x{height}+{x}+{y}')

    # 显示窗口
    root.deiconify()

    root.mainloop()


if __name__ == "__main__":
    main()
