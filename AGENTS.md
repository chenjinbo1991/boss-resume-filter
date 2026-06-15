# BOSS 简历筛选器 - 项目规范

## 项目结构

```text
boss-resume-filter/
├── bossmaster.py         # BOSS 直聘自动筛选主程序（核心）
├── filtering.py          # 纯筛选规则模块（评分、硬条件、薪资/经验/城市解析）
├── llm_eval.py           # LLM 辅助评估模块（prompt 构建、API 调用、批量评估）
├── job_ai_parser.py      # 岗位需求 AI 增强解析模块（基于正则初稿补充优化）
├── storage.py            # 候选人数据持久化模块（去重、原子写入、备份恢复）
├── gui_main.py           # 图形界面主程序（v2.11.1）
├── gui_dialogs.py        # 独立对话框模块（更新日志、关于弹窗、CHANGELOG 渲染）
├── changelog_parser.py   # CHANGELOG 解析模块（版本段落提取、标题解析）
├── updater.py            # 自动更新模块（Gitee/GitHub 双源检查、下载替换、完整性校验、启动时自动检查）
├── icons.py              # 图标绘制模块（Pillow 矢量图标，33个图标函数 + IconCache）
├── doc_parser.py         # 招聘需求文档解析器（JD → 必要条件 + 职位要求）
├── security.py           # API Key 安全存储模块（keyring 加密，按 provider+base_url 组合存储）
├── migrate_keys.py       # API Key 迁移工具（明文→加密）
├── constants.py          # 共享常量（评分模型参数、阈值、学历档位、滚动参数、城市列表）
├── paths.py              # 路径工具（get_base_dir、ensure_config_files、路径常量）
├── build.py              # PyInstaller 打包脚本（支持 --release 一键发布）
├── latest.json           # 版本清单（Gitee 更新源，build.py --release 自动维护）
├── job_config.json       # 岗位筛选规则配置
├── api_config.json       # AI 模型配置（不含明文 Key）
├── selectors.json        # 页面选择器配置（CSS/XPath/关键词，DOM 变化时修改）
├── ui_config.json        # UI 尺寸与缩放配置
├── tests/                # 测试脚本目录
├── scripts/              # 辅助脚本（发布监控、PPT 生成、截图等）
│   └── watch_progress.py # 发布进度监控脚本（轮询 .build_progress.json）
├── pyinstaller-hooks/    # PyInstaller 自定义 hook（控制模块收集范围，减小产物体积）
├── GUI 使用说明.md       # 图形界面操作说明
├── DEPLOYMENT.md         # 部署说明（新电脑首次部署步骤）
└── PACKAGING.md          # 打包指南（跨平台支持、体积基线、build.py 参数）
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
  3. `README.md` 顶部版本标识 + 版本历史段落（只保留最近 2-3 个版本，更早版本由 CHANGELOG.md 承载）+ gui_main.py 注释
  4. `CLAUDE.md` 和 `AGENTS.md` 项目结构中的 gui_main.py 注释
- 发布前 `build.py --check` 验证一致性

#### 发布命令

- `python build.py --check`：仅发布前检查，不打包不提交不推送；覆盖 README/CHANGELOG 当前版本、历史版本、发布分类校验和条目质量审查
- `python build.py --sync-release-notes`：修正 CHANGELOG 后同步 GitHub + Gitee Release 说明，不重新打包
- `python build.py`：自动打包（Windows EXE / macOS .app+ZIP+DMG），`IS_MAC`/`IS_WIN` 自动检测
- `python build.py --release [--auto] [--version X.Y]`：打包→提交→tag→推送确认→GitHub Release 上传→Gitee 同步
- **发布前必须先执行 `/neat-freak` skill**，完成文档与代码的洁癖级审查同步，再进入 `build.py --release`
- `__version__` 在 `gui_main.py` 中定义，唯一版本号来源；`build.py` 通过 AST 解析提取
- 智能跳过打包：`.build_state.json` 构建指纹未变时复用产物，`--force-build` 强制重建
- 打包命令：Windows `--onefile --noconsole --runtime-tmpdir %LOCALAPPDATA%`；macOS `--onedir --windowed`；DMG 用 `dmgbuild`
- 打包前 `_preflight_checks()` 验证依赖、敏感文件、源码编译、CHANGELOG/README 同步、CLAUDE.md 行数（≤300）、回归测试
- 新增/修改 `requirements.txt` 依赖时同步更新 `build.py:REQUIRED_IMPORTS`；`build.py` 显式收集 Tk 运行库防 `No module named 'tkinter'`
- Release 模式只自动提交 `--version` 引起的版本号变化，其他变更须先手工提交
- 推送前 `input()` 确认 [y/N]；tag 冲突时自动 `--force`（master 除外）

#### 打包体积优化（当前 Windows 约 36.4MB，macOS ZIP/DMG 约 31-33MB）

- **PIL**：精确 `--hidden-import` 仅收集 Image/ImageDraw/ImageTk，排除 `_avif`/`_webp`
- **babel locale-data**：自定义 hook（`pyinstaller-hooks/hook-babel.py`）排除全部 1086 个 locale .dat，按需添加 9 个（zh/en 系列）
- **排除模块**：保留 `scipy`、`lxml.objectify` 等无运行期入口模块；`pandas` 不再是直接打包依赖，Excel 导出保持 `openpyxl` 直写；`numpy`/`numpy.libs` 仅为 openpyxl 可选支持和环境残留，打包时应排除；**不要排除** `sqlite3`（DataRecorder/DrissionPage 顶层依赖）、`lxml.html`（DrissionPage 顶层依赖）
- **体积判断**：Windows 使用 `--onefile` 单文件 EXE，通常比 macOS `--onedir` 后的 ZIP/DMG 大；不要用 macOS 32MB 反推 Windows 也必须接近 32MB。当前 Windows EXE 约 36.4MB、macOS ZIP/DMG 约 31-33MB 属正常范围。
- 修改 build.py 时注意保持上述优化，避免体积回退
- **CI 跨平台重建**：`build.py`、`pyinstaller-hooks/` 和核心源码/配置变更会触发对端平台 CI 重建；macOS 对端产物必须同时有 ZIP 和 DMG，否则 CI 需重建

## 代码规范

- 使用 type hints
- 关键函数写 docstring
- 异常处理要具体，不要裸 except；核心模块用 `except Exception:` 兜底，scripts/ 逐步收敛中

## 敏感信息

- .env 文件不进 git
- 候选人数据含个人隐私，本地存储要加密
- API Key 加密存储在系统钥匙串（Windows DPAPI / macOS Keychain），`api_config.json` 不含明文
- API Key 按 provider + base_url 组合存储，同一服务商不同接入方式（API / Token Plan）独立管理

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

### 候选人提取

三级提取链路：**API 直调**（`_build_recommend_api_pagination_from_page()` 从当前页面 URL 读取 jobId 直接调用推荐接口分页）→ **监听兜底**（`_start_recommend_api_listener()` + `page.refresh()` 触发接口，会重置岗位）→ **DOM 提取**（`_extract_cards_batch()` 滚动提取）。API 直调不触发页面刷新，是默认首选。`_read_recommend_page_identity()` 用于刷新前后比对岗位标识，防止兜底方案静默抓取错误岗位。`filter_candidate()` 接受可选 `structured_fields` 参数，优先使用结构化值，fallback 到正则文本解析。薪资正则 `[kK]?` 末尾 K 可选，兼容 "15-25" 无后缀格式。

### 滚动提前终止

三策略：`atBottom` 标记、文本匹配"到底"/"没有更多"、连续 5 轮无新候选人兜底。批量提取：`_extract_cards_batch()` 单次 JS 提取所有卡片

### 评分体系

- 四维模型：`基础25 + 技能(0~50) + 经验超额(0~15) + 学历档次(0~10)`（参数定义在 `constants.py`）
- 英文关键词用 `\b` 单词边界匹配，避免子串误匹配
- 推荐等级：>=75 强烈推荐, >=65 推荐, >=55 待定
- 淘汰原因排序：学历→经验→年龄→地点→薪资→评分→其他
- 硬条件检查顺序：学历→经验→年龄→地点→薪资→必要条件→技术关键词
- 评分输出：`score_breakdown`（各项分拆）、`score_explanation`（文本解释）、`keyword_evidence`（命中证据含原文片段）
- 人工反馈：`feedback_status`（合适/误推/误杀/放弃）、`feedback_note`、`feedback_updated_at`；去重时保留反馈字段
- 跟进状态：`followup_status`（未沟通/已打招呼/已回复/待约面/已约面/不合适/已归档）、`followup_note`、`followup_updated_at`；去重时保留
- 黑名单：`blacklisted`、`blacklist_reason`、`blacklisted_at`；按 `geek_id` 跨岗位屏蔽，后续扫描、统计和 Excel 导出跳过，清空候选人时保留
- 实现位置：`filtering.py:filter_candidate()`

### AI 辅助评估

- 对 ≥55 分候选人 LLM 二次评估，按规则评分降序处理，调整分 ±10 叠加规则评分
- 调整后重算推荐等级；默认并发 5 路 + 429 限流退避；默认不再限制 50 人；实现位置：`llm_eval.py`
- **简历二次评估**：导入候选人简历（PDF/Word）后，基于完整简历做第二轮 LLM 评估（再调 ±10），三次评估叠加：`final = rule_score + llm_adjustment + resume_adjustment`；GUI 支持导入简历、撤回评估；Excel 新增"简历评估"和"简历评估理由"列

### 必要条件

- 三种模式：简单匹配（子串）、OR（任一）、AND（全部），全角逗号自动归一化
- 底层 `check_required_condition()` 支持字符串和 JSON 格式

### 薪资范围筛选

- 候选人期望最低薪资 >= 岗位薪资上限 + 1K → 过滤；面议或缺失时跳过

### 工作地点筛选

- 候选人城市匹配岗位配置，支持多地点（`/`、`、` 分隔），空时不启用

### 数据统计看板

- 按岗位聚合，4 张汇总卡片 + 明细 Treeview；只统计 ≥55 分；支持时间范围过滤
- 明细 Treeview 9 列精简展示：岗位名称、筛选分布（总数+强推/推荐/待定）、已打招呼(率)、已反馈、合适率、误推率、已回复(率)、已约面(率)、平均分
- 合适率/误推率只按有效人工反馈计算（合适/误推/误杀/放弃）；已回复/已约面列内嵌百分比（按已打招呼及后续状态计算）

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
- **Gitee Release 上传**：`_gitee_upload_local()` 上传本地产物，`_sync_gitee_from_github()` 下载并同步 CI 对端产物；大文件（EXE/ZIP/DMG，>=20MB）串行，小文件最多 3 路并发；上传/下载超时 600s，4xx 不重试；Windows 发布同步 Mac 产物时 ZIP 优先于 DMG
- **Gitee Token**：环境变量 `GITEE_TOKEN`，未设置时跳过上传
- 实现位置：`updater.py`（客户端），`build.py`（上传）

## 踩坑警示

### macOS .app 路径解析与首次配置

`sys.executable` 在 .app 中指向 `.app/Contents/MacOS/BOSS_ResumeFilter`，配置文件在 .app 旁边，需向上追溯 3 层。DMG 只含 .app 和 Applications 快捷方式，配置文件不在 DMG 中，首次启动时从 `sys._MEIPASS` 复制。Windows EXE 直接用 `sys.executable.parent`。路径逻辑统一在 `paths.py:get_base_dir()` 中维护。

### PyInstaller 版本号读取

不能从 `sys._MEIPASS` 读取 `gui_main.py` 源文件，因为源码被编译进 PYZ 归档，文件不存在。应该直接 `import gui_main` 读取模块属性，兼容所有打包模式（源码 / Windows EXE / macOS .app）。

### Tk 对话框 `wait_window()` 嵌套事件循环崩溃

`wait_window()` 在 `root.after()` 回调中创建嵌套事件循环，macOS 上与 Cocoa scroll hook 和浏览器轮询冲突导致崩溃。正确做法是用 `grab_set()` 实现模态（不阻塞主事件循环），`protocol("WM_DELETE_WINDOW")` + `_close_dialog()` 清理引用。`self.root.update()` 也有重入风险，应移除。

### CHANGELOG 分类原则

三类：新增功能 / 体验优化 / 问题修复。问题修复仅指旧版本已存在且影响用户的 bug，不含当前版本新功能引入的问题。

CHANGELOG 只包含用户可感知的变更，以下内容不应出现：新功能开发过程中的中间 UI 调整（属于新功能本身）、打包脚本/CI/发布流程优化（用户无感知）、当前版本新功能引入的 bug 修复（不算「问题修复」）。`build.py --check` 会自动审查条目质量。

### Windows DPI 缩放（System DPI Aware 方案）

**保持 System DPI Aware**，启动时调用 `_enable_high_dpi_awareness()`，优先用 `SetProcessDPIAware()` / `SetProcessDpiAwareness(1)`，避免 Windows 对 Tk 窗口做位图缩放导致字体模糊。不要启用 Per-Monitor DPI V2；Tk 8.6 在 V2 下坐标和布局容易错乱。

`_resolve_display_scale()` 同时兼容两种环境：System DPI Aware 下 Tk 已报告真实 DPI，优先使用 `root.tk.call('tk', 'scaling')` 推导的 DPI；DPI Unaware 或异常回退时，用 `EnumDisplaySettingsW(None, -1)` 获取物理像素宽度，与 Tk 虚拟屏幕宽度比值计算真实 `display_scale`。**布局/间距/图标/窗口/rowheight 统一使用 `dpi_scale × zoom_factor`，字体使用 `font_scale`**，不要把不同区域拆成各自的缩放公式。macOS 不受 Windows DPI 感知设置影响。

### macOS Tk 8.6 字体物理像素减半

Apple Silicon 报告 DPI 72，Intel Mac venv 报告 96（系统 Tk 8.5 报告 144 不受影响）。阈值 `< 80` 区分需补偿环境：`self.font_boost = 1.65 if (sys.platform == 'darwin' and self.root.winfo_fpixels('1i') < 80) else 1.0`，然后 `self.font_scale = self.dpi_scale * self.zoom_factor * self.font_boost`。`font_scale` 仅用于字体，布局/间距/图标/窗口/rowheight 仍用 `dpi_scale × zoom_factor`。

### 字体常量与 Combobox 规范

- `FONT_FAMILY`/`FONT_FAMILY_SEMIBOLD` 跨平台字体常量（Windows: Microsoft YaHei UI, macOS: PingFang SC, Linux: Helvetica）
- 7 个字体变量：`font_title`(28pt) / `font_section`(16pt) / `font_label`(13pt) / `font_stat`(36pt) / `font_stat_label`(15pt) / `font_log`(11pt) / `font_table`(12pt)
- `font_scale`（含 font_boost）用于字体；`dpi_scale × zoom_factor` 用于布局/间距/图标/rowheight
- Combobox 下拉列表字体：`option_add('*TCombobox*Listbox.font', font, 80)`；所有 Combobox 禁用滚轮：`bind_class('TCombobox', '<MouseWheel>', lambda e: 'break')`

### macOS aqua 主题 ttk 控件灰色背景

macOS aqua 的 ttk 控件默认背景是 `systemWindowBackgroundColor`（灰色），三层原因：

1. **`ttk.LabelFrame` 灰色**：`Labelframe.border` 硬编码灰色，`style.configure` 无效。解决方案：用 `_create_card()` 替代
2. **`ttk.Label` 灰色**：`style.configure('TLabel', background=self.colors['bg_card'])` 解决
3. **输入框灰色**：macOS aqua 忽略 `style.configure` 的 `fieldbackground`，必须用 `style.map`（Combobox `readonly`、Spinbox/Entry `!disabled`）

架构约定：

- `TFrame` 默认白底（`bg_card`），页面级灰底容器用 `Page.TFrame`（`bg_main`）
- `_create_scroll_container` 的容器 frame 必须加 `style='TFrame'`
- `_create_page_header(parent, title, subtitle=None)` 统一创建页面标题

### Gitee Release API 限制

PATCH release 必须带 `tag_name` 和 `body`（只传 `name` 返回 400）。releases 列表不返回附件 ID，删除附件需通过 `GET /releases/{id}/attach_files`。版本号参数需先移除 `v` 前缀（`v2.9` → `2.9`），否则 tag 变成 `vv2.9`。

### CI 模式下 babel locale-data 路径查找

CI 用 `.venv-ci`，本地打包用 `pack_venv`。`build.py` 中 babel locale-data 搜索路径必须同时覆盖两种虚拟环境目录，否则 CI 构建的 Mac 产物缺少 locale .dat，`tkcalendar.DateEntry` 运行时 `FileNotFoundError`。

### provider 显示名称与内部键不一致

GUI `api_provider_var.get()` 返回显示名称（「通义千问」），keyring 存内部键（`qwen`）。调用前必须通过 `DISPLAY_TO_KEY` 映射转换。`get_api_key(provider, base_url)` 按 provider + base_url 组合查找，新 key 找不到时自动回退旧格式（仅 provider）。

### 更新弹窗必须使用 GUI 缩放参数

`updater.py` 的 `show_update_dialog()` 接收 `gui` 参数，使用 `gui.font_scale`/`gui.dpi_scale`/`gui.zoom_factor` 计算字体和布局。不能硬编码字号，否则高 DPI 下字体模糊或过小。更新内容从远端 `CHANGELOG.md` 提取（Gitee → GitHub fallback），不用 `latest.json` 的 `release_notes`。

### API 监听依赖 page.refresh 触发完整数据

`extract_candidates_by_comprehensive_analysis()` 启动 `_start_recommend_api_listener()` 后必须 `page.refresh()` 才能触发完整的推荐接口调用（返回全部候选人结构化数据）。微滚动只能触发部分数据（约 28%），后续滚动不触发新 API 请求。`page.refresh()` 会重置岗位筛选到默认岗位，这是当前接受的代价。
