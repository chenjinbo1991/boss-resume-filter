# BOSS 简历筛选器 - 项目规范

## 项目结构

```text
boss-resume-filter/
├── bossmaster.py         # BOSS 直聘自动筛选主程序（核心）
├── filtering.py          # 纯筛选规则模块（评分、硬条件、薪资/经验/城市解析）
├── llm_eval.py           # LLM 辅助评估模块（prompt 构建、API 调用、批量评估）
├── storage.py            # 候选人数据持久化模块（去重、原子写入、备份恢复）
├── gui_main.py           # 图形界面主程序（v2.9.1）
├── gui_dialogs.py        # 独立对话框模块（更新日志、模型选择）
├── updater.py            # 自动更新模块（Gitee/GitHub 双源检查、下载替换、完整性校验、启动时自动检查）
├── icons.py              # 图标绘制模块（Pillow 矢量图标，31个图标函数 + IconCache）
├── doc_parser.py         # 文档解析器（简历解析）
├── security.py           # API Key 安全存储模块（keyring 加密）
├── migrate_keys.py       # API Key 迁移工具（明文→加密）
├── constants.py          # 共享常量（评分模型参数、阈值、学历档位、滚动参数、城市列表）
├── paths.py              # 路径工具（get_base_dir、ensure_config_files、路径常量）
├── build.py              # PyInstaller 打包脚本（支持 --release 一键发布）
├── latest.json           # 版本清单（Gitee 更新源，build.py --release 自动维护）
├── job_config.json       # 岗位筛选规则配置
├── api_config.json       # AI 模型配置（不含明文 Key）
├── selectors.json        # 页面选择器配置（CSS/XPath/关键词，DOM 变化时修改）
├── candidates_all.json   # 累积的候选人数据
├── candidates_all.xlsx   # Excel 导出文件
├── gui.bat               # GUI 启动脚本
├── install.bat           # 安装脚本
├── requirements.txt      # Python 依赖
├── CLAUDE.md             # 本文件（Claude 专用项目规范）
├── AGENTS.md             # Codex 专用项目规范（内容与本文件一致）
├── README.md             # 项目主文档
├── CHANGELOG.md          # 更新日志
├── GUI 使用说明.md        # 图形界面详细说明
├── README_文件管理.md      # 数据文件管理说明
├── DEPLOYMENT.md         # 部署说明（新电脑配置）
├── PACKAGING.md          # 打包指南
├── tests/                # 测试脚本目录
├── scripts/              # 辅助脚本目录
│   └── watch_progress.py # 发布进度监控脚本（轮询 .build_progress.json）
└── .build_progress.json  # 发布进度文件（build.py 实时更新，供外部监控）
```

## 运行命令

### 命令行模式

- 安装依赖：`pip install -r requirements.txt`
- 自动打招呼：`python bossmaster.py --greet`
- 指定岗位：`python bossmaster.py --job "高级 Java 工程师" --greet`
- 补打招呼：`python bossmaster.py --re-greet`
- 打招呼等级：`python bossmaster.py --greet --greet-level strong`（仅强烈推荐）或 `normal`（默认，强烈推荐+推荐）
- 清空历史：`python bossmaster.py --clear --greet`
- 清空保留已沟通：`python bossmaster.py --clear --keep-greeted --greet`（清空时保留已打招呼的候选人）
- 输出详细评分：`python bossmaster.py --greet --verbose`
- AI 辅助评估：`python bossmaster.py --greet --ai-eval`（对通过筛选的候选人进行 LLM 二次评分）

### 图形界面模式（推荐）

- 双击 `gui.bat` 或 `python gui_main.py`
- 侧边栏底部版本号可点击，弹出更新日志对话框查看 CHANGELOG.md 内容

### 测试验证

- 稳定单元回归：`python tests/run_unit_tests.py`
- 导入烟测：`python tests/test_import.py`
- 浏览器、BOSS 页面、人工登录、网络/API 测试只放在 `tests/manual/`，不纳入默认回归
- 历史调试脚本放在 `tests/archive/`，默认不维护、不保证可运行

### 打包发布

#### 版本号规范（必须遵守）

- **格式**：大版本 `X.Y`（如 v2.9），补丁版本 `X.Y.Z`（如 v2.8.12）。**禁止** `X.Y.0`
- **更新位置**（必须同步）：
  1. `gui_main.py` 的 `__version__`（不带 `v` 前缀，如 `__version__ = "2.9"`）
  2. `CHANGELOG.md` 新版本标题（`## vX.Y — 标题`），含分类：新增功能/体验优化/问题修复（至少一个）
  3. `README.md` 顶部版本标识 + 版本历史段落 + gui_main.py 注释
  4. `CLAUDE.md` 和 `AGENTS.md` 项目结构中的 gui_main.py 注释
- 发布前 `build.py --check` 验证一致性

#### 发布命令

- `python build.py --check`：仅发布前检查，不打包不提交不推送
- `python build.py`：自动打包（Windows EXE / macOS .app+ZIP+DMG），`IS_MAC`/`IS_WIN` 自动检测
- `python build.py --release [--auto] [--version X.Y]`：打包→提交→tag→推送确认→GitHub Release 上传→Gitee 同步
- `__version__` 在 `gui_main.py` 中定义，唯一版本号来源；`build.py` 通过 AST 解析提取
- 智能跳过打包：`.build_state.json` 构建指纹未变时复用产物，`--force-build` 强制重建
- 打包命令：Windows `--onefile --noconsole --runtime-tmpdir %LOCALAPPDATA%`；macOS `--onedir --windowed`；DMG 用 `dmgbuild`
- 打包前 `_preflight_checks()` 验证依赖、敏感文件、源码编译、CHANGELOG 同步、回归测试
- 新增/修改 `requirements.txt` 依赖时同步更新 `build.py:REQUIRED_IMPORTS`；`build.py` 显式收集 Tk 运行库防 `No module named 'tkinter'`
- Release 模式只自动提交 `--version` 引起的版本号变化，其他变更须先手工提交
- 推送前 `input()` 确认 [y/N]；tag 冲突时自动 `--force`（master 除外）

## 代码规范

- 使用 type hints
- 关键函数写 docstring
- 异常处理要具体，不要裸 except；核心模块用 `except Exception:` 兜底，scripts/ 逐步收敛中

## 敏感信息

- .env 文件不进 git
- 候选人数据含个人隐私，本地存储要加密
- API Key 加密存储在系统钥匙串（Windows DPAPI / macOS Keychain），`api_config.json` 不含明文
- API Key 按服务商统一管理，同一服务商的所有模型共享一个 Key

## 核心逻辑

### 打招呼机制

- 按钮位于 `operate-side` 区域，文本："继续沟通"（已匹配）、"立即沟通"（新候选人）
- 过滤规则：只过滤「当前岗位已匹配且打过招呼」的候选人；中断时兜底保存
- 打招呼等级：`--greet-level strong`（仅 ≥75）或 `normal`（默认，≥65）
- 智能滚动定位 `_find_card_by_scroll()` 三阶段搜索；沟通上限检测 `_detect_limit_popup()`

### 停止机制

- StopRequested 异常 + threading.Event 穿透所有关键循环；停止时自动保存进度并导出 Excel

### 浏览器自动检测

- 运行页每 2 秒轮询 Chrome 连接状态；手动检测时自动启动 Chrome（动态端口 + 独立 profile，保留登录态）
- `_browser_check_running` 互斥标志防重复启动；端口预检防止自动启动

### 反爬对抗

- **随机延迟**：`_human_delay(center, spread)` 所有 sleep 带随机抖动
- **验证码检测**：`_detect_captcha()` 关键词 + CSS 选择器检测，暂停等待用户完成验证（5 分钟超时）

### 去重机制

- 基于 `(geek_id, job_name)` 复合键去重，保留分数高的记录，合并打招呼状态
- `storage.py:save_candidates_all()` 使用 O(n) 算法；`bossmaster.py` 保留同名导入兼容旧调用

### 保存策略

- 正常流程：岗位处理完毕时统一保存；异常中断：立即兜底保存
- 淘汰过滤：保存前过滤低于 55 分的候选人
- 原子性写入：`.tmp` + `os.replace()`；备份恢复：`.bak` 自动回退

### 滚动提前终止

三策略：`atBottom` 标记、文本匹配"到底"/"没有更多"、连续 5 轮无新候选人兜底。批量提取：`_extract_cards_batch()` 单次 JS 提取所有卡片

### 评分体系

- 四维模型：`基础25 + 技能(0~50) + 经验超额(0~15) + 学历档次(0~10)`（参数定义在 `constants.py`）
- 英文关键词用 `\b` 单词边界匹配，避免子串误匹配
- 推荐等级：>=75 强烈推荐, >=65 推荐, >=55 待定
- 淘汰原因排序：学历→经验→年龄→地点→薪资→评分→其他
- 硬条件检查顺序：学历→经验→年龄→地点→薪资→必要条件→技术关键词
- 实现位置：`filtering.py:filter_candidate()`

### AI 辅助评估

- 对 ≥55 分候选人 LLM 二次评估（最多 50 人/次），调整分 ±10 叠加规则评分
- 调整后重算推荐等级；并发 3 路 + 429 限流退避；实现位置：`llm_eval.py`

### 必要条件

- 三种模式：简单匹配（子串）、OR（任一）、AND（全部），全角逗号自动归一化
- 底层 `check_required_condition()` 支持字符串和 JSON 格式

### 薪资范围筛选

- 候选人期望最低薪资 >= 岗位薪资上限 + 1K → 过滤；面议或缺失时跳过

### 工作地点筛选

- 候选人城市匹配岗位配置，支持多地点（`/`、`、` 分隔），空时不启用

### 数据统计看板

- 按岗位聚合，4 张汇总卡片 + 明细 Treeview；只统计 ≥55 分；支持时间范围过滤

### 页面选择器配置（selectors.json）

- 所有 DOM 交互选择器集中配置，带 `{geek_id}` 占位符；浏览器连接后自动健康检查

## AI 模型配置

### 支持的服务商

通义千问 (Qwen)、DeepSeek、Kimi (月之暗面)、智谱 (Zhipu)、MiniMax、小米 (Xiaomi)、阶跃星辰 (StepFun)、OpenAI、Anthropic (Claude)、自定义 (Custom)

### 配置管理

- api_config.json 存储多服务商配置（不含明文 Key），API Key 加密存储在系统钥匙串
- 支持动态获取模型列表、双击切换已保存模型、测试连接（并行双策略）
- 新电脑部署：首次启动检测 API Key 缺失并引导重新配置

### 模型列表搜索与新增检测

- 选择模型对话框内置搜索框；`fetched_models` 字段存储上次列表，对比找出新增模型（绿色高亮 + 弹窗提醒）和下线模型（弹窗提醒）
- 对话框支持 EXTENDED 多选（Ctrl+点击切换、Shift+点击范围、Ctrl+A 全选）；右键菜单可批量测试连通性
- 连通性测试多线程并行，识别常见业务错误（未开通/配额超限/免费额度用完）给出人性化提示
- 实现位置：`gui_main.py:fetch_model_list()`、`gui_main.py:show_model_dialog()`

## 自动更新

- 启动时延迟 3 秒检查，**自适应冷却**（发现新版本 24h / 无更新 4h / 失败 15min 指数退避）；Gitee 优先 → GitHub fallback（Gitee "无更新"时 GitHub 复核防漏报）
- **Gitee 源**（8s 超时）：`latest.json`；**GitHub 源**（10s 超时）：GitHub Releases API
- 下载链接：`latest.json` 的 `downloads_cn` 优先（国内快）；弹窗支持「立即更新」和「稍后提醒」
- **Windows**：下载 EXE → 校验 SHA256 → `update.bat` 替换重启；脚本须清理 `_PYI_*` 环境变量 + `PYINSTALLER_RESET_ENVIRONMENT=1` 防 DLL 缺失
- **macOS**：.app 运行→下载 ZIP 替换重启；源码→`git pull`
- `latest.json` 的 `assets` 记录产物 `size`/`sha256` 供校验
- **Gitee Release 上传**：`_gitee_upload_local()` 本地产物 + `_sync_gitee_from_github()` CI 产物，3 路并行；5 次重试 + 600s 超时，4xx 不重试
- **Gitee Token**：环境变量 `GITEE_TOKEN`，未设置时跳过上传
- 实现位置：`updater.py`（客户端），`build.py`（上传）

## 踩坑警示

### macOS .app 路径解析

`sys.executable` 在 .app 中指向 `.app/Contents/MacOS/BOSS_ResumeFilter`，配置文件在 .app 旁边，需向上追溯 3 层。Windows EXE 直接用 `sys.executable.parent`。路径逻辑统一在 `paths.py:get_base_dir()` 中维护。

### PyInstaller 版本号读取

不能从 `sys._MEIPASS` 读取 `gui_main.py` 源文件，因为源码被编译进 PYZ 归档，文件不存在。应该直接 `import gui_main` 读取模块属性，兼容所有打包模式（源码 / Windows EXE / macOS .app）。

### DMG 图标布局控制

`hdiutil create` 无法控制图标位置，Finder AppleScript 在 macOS 13+ 不稳定。最终方案：使用 `dmgbuild` Python 库。

### CHANGELOG 分类校验

`build.py` 的 `_check_changelog()` 要求至少有一个分类（新增功能/体验优化/问题修复），且存在的分类按规范顺序排列。

**分类原则**：

- **新增功能**：用户可感知的新能力
- **体验优化**：现有功能的改进，包括新功能开发过程中产生的问题修复（不算 bug）
- **问题修复**：**仅指旧版本中已存在且影响用户的 bug**，不包括当前版本新功能引入的问题

### DMG 安装后配置文件缺失

DMG 只含 .app + Applications 快捷方式，配置文件不在 DMG 中。`_get_base_dir()` 首次启动时检测配置文件不存在则从 `sys._MEIPASS` 复制。

### Tk 对话框 `wait_window()` 嵌套事件循环崩溃

`wait_window()` 在 `root.after()` 回调中创建嵌套事件循环，macOS 上与 Cocoa scroll hook 和浏览器轮询冲突导致崩溃。正确做法是用 `grab_set()` 实现模态（不阻塞主事件循环），`protocol("WM_DELETE_WINDOW")` + `_close_dialog()` 清理引用。`self.root.update()` 也有重入风险，应移除。

### Windows DPI 缩放（DPI Unaware 方案）

**保持 DPI Unaware**，不启用任何 DPI 感知。Windows 后台自动按系统缩放倍数放大 Tk 渲染内容。用 `EnumDisplaySettingsW(None, -1)` 获取物理像素宽度计算真实 `display_scale`。**所有 UI 元素统一使用同一个缩放比例**，分开缩放会导致布局错乱。macOS 不受影响。

### macOS Tk 8.6 字体物理像素减半

Apple Silicon 报告 DPI 72，Intel Mac venv 报告 96（系统 Tk 8.5 报告 144 不受影响）。阈值 `< 80` 区分需补偿环境：

```python
if sys.platform == 'darwin':
    self.font_boost = 1.65 if self.root.winfo_fpixels('1i') < 80 else 1.0
else:
    self.font_boost = 1.0
self.font_scale = self.dpi_scale * self.zoom_factor * self.font_boost
```

`font_scale` 仅用于字体，布局/间距/图标/窗口/rowheight 仍用 `dpi_scale × zoom_factor`。

### 字体常量与 Combobox 规范

- `FONT_FAMILY`/`FONT_FAMILY_SEMIBOLD` 跨平台字体常量（Windows: Microsoft YaHei UI, macOS: PingFang SC, Linux: Helvetica）
- 7 个字体变量：`font_title`(28pt) / `font_section`(16pt) / `font_label`(13pt) / `font_stat`(36pt) / `font_stat_label`(15pt) / `font_log`(11pt) / `font_table`(12pt)
- `font_scale`（含 font_boost）用于字体；`dpi_scale × zoom_factor` 用于布局/间距/图标/rowheight
- Combobox 下拉列表字体：`option_add('*TCombobox*Listbox.font', font, 80)`；所有 Combobox 禁用滚轮：`bind_class('TCombobox', '<MouseWheel>', lambda e: 'break')`

### macOS aqua 主题 ttk 控件灰色背景

macOS aqua 的 ttk 控件默认背景是 `systemWindowBackgroundColor`（灰色），三层原因：

1. **`ttk.LabelFrame` 灰色**：`Labelframe.border` 硬编码灰色，`style.configure` 无效。解决方案：用 `_create_card()` 替代
2. **`ttk.Label` 灰色**：`style.configure('TLabel', background=self.colors['bg_card'])` 解决
3. **输入框灰色**：macOS aqua 忽略 `style.configure` 的 `fieldbackground`，只有 `style.map` 有效：

```python
style.map('TCombobox', fieldbackground=[('readonly', bg_card), ('!disabled', bg_card)])
style.map('TSpinbox', fieldbackground=[('!disabled', bg_card)])
style.map('TEntry', fieldbackground=[('!disabled', bg_card)])
```

架构约定：

- `TFrame` 默认白底（`bg_card`），页面级灰底容器用 `Page.TFrame`（`bg_main`）
- `_create_scroll_container` 的容器 frame 必须加 `style='TFrame'`
- `_create_page_header(parent, title, subtitle=None)` 统一创建页面标题

### Gitee Release API 限制

PATCH release 必须带 `tag_name` 和 `body`（只传 `name` 返回 400）。releases 列表不返回附件 ID，删除附件需通过 `GET /releases/{id}/attach_files`。版本号参数需先移除 `v` 前缀（`v2.9` → `2.9`），否则 tag 变成 `vv2.9`。

### provider 显示名称与内部键不一致

GUI 中 `api_provider_var.get()` 返回显示名称（如「通义千问」），但 `get_api_key()` / keyring 存的是内部键（如 `qwen`）。调用前必须通过 `DISPLAY_TO_KEY` 映射转换，否则 keyring 查不到 Key。

### 更新弹窗必须使用 GUI 缩放参数

`updater.py` 的 `show_update_dialog()` 接收 `gui` 参数，使用 `gui.font_scale`/`gui.dpi_scale`/`gui.zoom_factor` 计算字体和布局。不能硬编码字号，否则高 DPI 下字体模糊或过小。更新内容从远端 `CHANGELOG.md` 提取（Gitee → GitHub fallback），不用 `latest.json` 的 `release_notes`（后者可能是简化版）。Text 控件参数（`wrap="char"`、`lmargin1`、`lmargin2`、`spacing1/2/3`）必须与主界面版本历史一致，否则排版错乱。
