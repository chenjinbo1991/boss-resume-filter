"""
GUI 对话框模块 - 从 gui_main.py 提取的独立对话框
"""
import sys
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path


def show_changelog_dialog(gui):
    """显示更新日志对话框（版本列表 + 详情分栏）

    Args:
        gui: BossFilterGUI 实例
    """
    # PyInstaller --add-data 解压到 _MEIPASS，优先从那里读取
    meipass = getattr(sys, '_MEIPASS', None)
    changelog_path = (Path(meipass) / "CHANGELOG.md") if meipass else None
    if not changelog_path or not changelog_path.exists():
        from paths import BASE_DIR
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

    dialog = tk.Toplevel(gui.root)
    dialog.title("更新日志")
    dialog.transient(gui.root)
    dialog.withdraw()

    fs = gui.dpi_scale * gui.zoom_factor
    changelog_fs = gui.font_scale * 0.88
    from gui_main import _clamp, _place_window_centered, FONT_FAMILY
    dialog_scale = _clamp(fs, 1.0, 1.50)
    dw = int(940 * dialog_scale)
    dh = int(620 * dialog_scale)
    _place_window_centered(dialog, dw, dh, parent=gui.root)

    # ---- 左侧版本列表（深色侧边栏风格）----
    sidebar_bg = '#2D3748'
    left_frame = tk.Frame(dialog, bg=sidebar_bg, width=int(190 * fs))
    left_frame.pack(side="left", fill="y")
    left_frame.pack_propagate(False)

    # 标题
    title_frame = tk.Frame(left_frame, bg=sidebar_bg)
    title_frame.pack(fill="x", padx=int(16 * fs), pady=(int(18 * fs), int(8 * fs)))
    tk.Label(title_frame, text="版本历史", bg=sidebar_bg, fg='#E2E8F0',
             font=(FONT_FAMILY, int(14 * changelog_fs), 'bold')).pack(anchor="center")
    tk.Label(title_frame, text=f"共 {len(versions)} 个版本", bg=sidebar_bg, fg='#A0AEC0',
             font=(FONT_FAMILY, int(11 * changelog_fs))).pack(anchor="center", pady=(int(2 * fs), 0))
    if len(versions) > 20:
        tk.Label(title_frame, text="可滚动查看", bg=sidebar_bg, fg='#718096',
                 font=(FONT_FAMILY, int(9 * changelog_fs))).pack(anchor="center")

    # 版本列表
    list_container = tk.Frame(left_frame, bg=sidebar_bg)
    list_container.pack(fill="both", expand=True, padx=int(16 * fs), pady=(int(4 * fs), int(6 * fs)))

    # wrapper 撑满容器高度（显示全部版本），内容水平居中
    list_wrapper = tk.Frame(list_container, bg=sidebar_bg)
    list_wrapper.pack(fill="both", expand=True)

    # Canvas + Label 方案（Listbox 不支持逐行字体）
    canvas_bg = sidebar_bg
    list_canvas = tk.Canvas(list_wrapper, bg=canvas_bg, highlightthickness=0, borderwidth=0)
    list_inner = tk.Frame(list_canvas, bg=canvas_bg)
    canvas_window_id = list_canvas.create_window(0, 0, window=list_inner, anchor='nw')
    list_inner.bind('<Configure>', lambda e: list_canvas.configure(scrollregion=list_canvas.bbox('all')))
    list_canvas.bind('<Configure>', lambda e: list_canvas.itemconfigure(canvas_window_id, width=e.width))
    list_scrollbar = tk.Scrollbar(list_wrapper, orient="vertical",
                                  command=list_canvas.yview,
                                  width=max(8, int(8 * fs)),
                                  bg='#718096',
                                  activebackground='#CBD5E0',
                                  troughcolor='#1F2937',
                                  borderwidth=0, highlightthickness=0, relief='flat')
    list_canvas.configure(yscrollcommand=list_scrollbar.set)
    list_scrollbar.pack(side="right", fill="y")
    list_canvas.pack(fill="both", expand=True)

    def _canvas_mousewheel(event):
        list_canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")
        return "break"
    list_canvas.bind("<MouseWheel>", _canvas_mousewheel)
    list_inner.bind("<MouseWheel>", _canvas_mousewheel)
    if sys.platform != 'win32':
        def _cb_scroll_up(e): list_canvas.yview_scroll(-1, "units"); return "break"
        def _cb_scroll_down(e): list_canvas.yview_scroll(1, "units"); return "break"
        list_canvas.bind("<Button-4>", _cb_scroll_up)
        list_canvas.bind("<Button-5>", _cb_scroll_down)
        list_inner.bind("<Button-4>", _cb_scroll_up)
        list_inner.bind("<Button-5>", _cb_scroll_down)

    row_frames = []
    selected_row_idx = [0]

    for idx, (tag, title_line, _) in enumerate(versions):
        is_patch = tag.count('.') >= 2  # X.Y.Z 是补丁版本
        font_size = int(10 * changelog_fs) if is_patch else int(12 * changelog_fs)
        row_bg = '#243041' if idx % 2 == 0 else sidebar_bg
        row_fg = '#718096' if is_patch else ('#F8FAFC' if idx == 0 else '#E2E8F0')

        row_frame = tk.Frame(list_inner, bg=row_bg)
        row_frame.pack(fill='x', pady=0)
        lbl = tk.Label(row_frame, text=f"  {tag}", bg=row_bg, fg=row_fg,
                       font=(FONT_FAMILY, font_size), anchor='w')
        lbl.pack(fill='x', ipady=int(2 * fs))
        row_frames.append((row_frame, lbl, row_bg, row_fg, idx))

        def make_select_handler(i):
            def handler(event=None):
                select_version(i)
            return handler
        def _enter(e, rf=row_frame, lb=lbl):
            if selected_row_idx[0] != rf._idx:
                rf.config(bg=gui.colors['primary'])
                lb.config(bg=gui.colors['primary'], fg='#FFFFFF')
        def _leave(e, rf=row_frame, lb=lbl, rb=row_bg, rfg=row_fg):
            if selected_row_idx[0] != rf._idx:
                rf.config(bg=rb)
                lb.config(bg=rb, fg=rfg)
        row_frame._idx = idx
        for widget in (row_frame, lbl):
            widget.bind('<Button-1>', make_select_handler(idx))
            widget.bind('<Enter>', _enter)
            widget.bind('<Leave>', _leave)

    def select_version(idx):
        selected_row_idx[0] = idx
        for rf, lb, orig_bg, orig_fg, i in row_frames:
            if i == idx:
                rf.config(bg=gui.colors['primary'])
                lb.config(bg=gui.colors['primary'], fg='#FFFFFF')
            else:
                rf.config(bg=orig_bg)
                lb.config(bg=orig_bg, fg=orig_fg)
        show_version(idx)

    # 左侧边栏底部：关于链接
    about_label = tk.Label(left_frame, text="关于",
                           bg=sidebar_bg, fg='#A0AEC0',
                           font=(FONT_FAMILY, int(12 * changelog_fs)),
                           cursor="hand2")
    about_label.pack(padx=int(12 * fs), pady=(int(8 * fs), int(12 * fs)))
    about_label.bind("<Button-1>", lambda e: gui.show_about())

    # ---- 右侧详情 ----
    right_outer = tk.Frame(dialog, bg=gui.colors['bg_main'])
    right_outer.pack(side="left", fill="both", expand=True)

    # 顶部标题栏
    header_frame = tk.Frame(right_outer, bg=gui.colors['bg_card'], height=int(72 * fs))
    header_frame.pack(fill="x")
    header_frame.pack_propagate(False)

    version_title = tk.Label(header_frame, text="",
                             font=(FONT_FAMILY, int(16 * changelog_fs), 'bold'),
                             fg=gui.colors['text_primary'], bg=gui.colors['bg_card'])
    version_title.pack(anchor="w", padx=int(20 * fs), pady=(int(14 * fs), 0))

    version_subtitle = tk.Label(header_frame, text="",
                                font=(FONT_FAMILY, int(11 * changelog_fs)),
                                fg=gui.colors['text_muted'], bg=gui.colors['bg_card'])
    version_subtitle.pack(anchor="w", padx=int(20 * fs))

    # 分隔线
    tk.Frame(right_outer, bg=gui.colors['border'], height=1).pack(fill="x")

    # 内容区
    content_frame = tk.Frame(right_outer, bg=gui.colors['bg_main'])
    content_frame.pack(fill="both", expand=True)

    text_widget = tk.Text(content_frame, wrap="char", borderwidth=0,
                          font=(FONT_FAMILY, int(12 * changelog_fs)),
                          bg=gui.colors['bg_main'], fg=gui.colors['text_primary'],
                          padx=int(12 * fs), pady=int(12 * fs),
                          spacing1=0, spacing2=1, spacing3=2,
                          selectbackground=gui.colors['primary'],
                          relief='flat', highlightthickness=0)
    text_widget.pack(side="left", fill="both", expand=True)

    scrollbar = ttk.Scrollbar(content_frame, orient="vertical", command=text_widget.yview)
    detail_scrollbar_job = None

    def update_detail_scrollbar(first, last):
        scrollbar.set(first, last)
        try:
            needs_scroll = float(first) > 0.0 or float(last) < 1.0
        except ValueError:
            needs_scroll = True
        if needs_scroll:
            if not scrollbar.winfo_ismapped():
                scrollbar.pack(side="right", fill="y")
        else:
            if scrollbar.winfo_ismapped():
                scrollbar.pack_forget()

    def refresh_detail_scrollbar():
        nonlocal detail_scrollbar_job
        detail_scrollbar_job = None
        text_widget.update_idletasks()
        first, last = text_widget.yview()
        update_detail_scrollbar(first, last)

    def schedule_detail_scrollbar_refresh(delay_ms=50):
        nonlocal detail_scrollbar_job
        if detail_scrollbar_job:
            dialog.after_cancel(detail_scrollbar_job)
        detail_scrollbar_job = dialog.after(delay_ms, refresh_detail_scrollbar)

    text_widget.configure(yscrollcommand=update_detail_scrollbar)

    # 配置 tag 样式
    title_font = (FONT_FAMILY, int(14 * changelog_fs), 'bold')
    section_font = (FONT_FAMILY, int(13 * changelog_fs), 'bold')
    item_font = (FONT_FAMILY, int(12 * changelog_fs))
    item_left_margin = int(18 * fs)
    item_wrap_margin = int(36 * fs)
    text_widget.tag_configure("title", font=title_font, foreground=gui.colors['primary'])
    text_widget.tag_configure("section_new", font=section_font, foreground=gui.colors['success'])
    text_widget.tag_configure("section_opt", font=section_font, foreground=gui.colors['primary'])
    text_widget.tag_configure("section_ui", font=section_font, foreground=gui.colors['purple'])
    text_widget.tag_configure("section_fix", font=section_font, foreground=gui.colors['danger'])
    text_widget.tag_configure("section_build", font=section_font, foreground=gui.colors['warning'])
    text_widget.tag_configure("item", font=item_font, foreground=gui.colors['text_secondary'],
                              lmargin1=item_left_margin, lmargin2=item_wrap_margin)
    text_widget.tag_configure("item_bold", font=(item_font[0], item_font[1], 'bold'), foreground=gui.colors['text_primary'])

    # 分类名 → tag 映射
    section_map = {
        '新增功能': 'section_new',
        '体验优化': 'section_opt',
        '行为优化': 'section_opt',
        '性能优化': 'section_opt',
        'UI 改进': 'section_ui',
        'UI改进': 'section_ui',
        '问题修复': 'section_fix',
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
                text_widget.insert("end", "\n" + section_name + "\n\n", stag)
            elif line.startswith("- "):
                item_text = line[2:]
                # 整行统一 item tag，标题部分叠加 item_bold（同字号加粗）
                if item_text.startswith("**"):
                    end_pos = item_text.find("**", 2)
                    if end_pos > 0:
                        title_part = item_text[2:end_pos]
                        rest = item_text[end_pos + 2:]
                        full_text = "• " + title_part + rest + "\n"
                        line_start = text_widget.index("end")
                        text_widget.insert("end", full_text, "item")
                        # 标题部分叠加 bold tag（2 = len("• ")）
                        bold_start = f"{line_start} + 2 chars"
                        bold_end = f"{line_start} + {2 + len(title_part)} chars"
                        text_widget.tag_add("item_bold", bold_start, bold_end)
                    else:
                        text_widget.insert("end", "• " + item_text + "\n", "item")
                else:
                    text_widget.insert("end", "• " + item_text + "\n", "item")
        text_widget.configure(state="disabled")
        text_widget.yview_moveto(0)
        schedule_detail_scrollbar_refresh()

    # 默认选中第一个版本（最新）
    select_version(0)

    # 内容创建完成后再按实际窗口尺寸复位一次，避免初始布局请求导致视觉中心偏移。
    dialog.update_idletasks()
    _place_window_centered(dialog, dw, dh, parent=gui.root)
    dialog.deiconify()
    schedule_detail_scrollbar_refresh(100)
