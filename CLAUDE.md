# BOSS 简历筛选器 - 项目规范

## 项目结构

```text
boss-resume-filter/
├── bossmaster.py         # BOSS 直聘自动筛选主程序（核心）
├── filtering.py          # 纯筛选规则模块（评分、硬条件、薪资/经验/城市解析）
├── llm_eval.py           # LLM 辅助评估模块（prompt 构建、API 调用、批量评估）
├── job_ai_parser.py      # 岗位需求 AI 增强解析模块（基于正则初稿补充优化）
├── storage.py            # 候选人数据持久化模块（去重、原子写入、备份恢复）
├── gui_main.py           # 图形界面主程序（v2.11.3）
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

#### CHANGELOG 核实规范（双向验证）
- **正向**（CHANGELOG → 代码）：`build.py --check` 自动化覆盖条目质量和 README 同步
- **反向**（代码 → CHANGELOG）：`git diff` 逐文件扫描 5 类用户可见变更（UI 文本、新配置、行为变更、新数据、删除/限制），与 CHANGELOG 交叉比对；三个分类各自独立验证，不假设任何分类已完整

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
- **API 熔断**：`ApiRiskBlocked` 异常，BOSS API 返回 403/412/429 时立即停止扫描，不降级 DOM
- **API 读取限速**：API 直调默认约 5-8 秒随机间隔；单次最多读取 `API_CANDIDATE_LIMIT_DEFAULT`（默认 80）人，达到上限停止继续翻页
- **打招呼限速**：每 `GREET_BATCH_SIZE` 人暂停随机间隔；每轮上限 `AUTO_GREET_RUN_LIMIT`（默认 20）

> **重要架构约束**：BOSS 直聘推荐页使用 `srcdoc` iframe（非 `src` URL），导致 `iframe.run_js('return location.href')` 始终返回 `about:srcdoc`。这意味着：
> 
> - Listener 监听 (`page.listen`) 无法捕获 API 调用（数据嵌在服务端渲染的 HTML 中，无客户端请求）
> - API 直调 (`_build_recommend_api_pagination_from_page()`) 无法从 iframe URL 读取 `jobId`
> - 实际有效的数据提取方式是 **纯 DOM 滚动提取** (`_extract_cards_batch()`)

### 去重机制

- 基于 `(geek_id, job_name)` 复合键去重，保留分数高的记录，合并打招呼状态
- `storage.py:save_candidates_all()` 使用 O(n) 算法；`bossmaster.py` 保留同名导入兼容旧调用

### 保存策略

- 正常流程：岗位处理完毕时统一保存；异常中断：立即兜底保存
- 淘汰过滤：保存前过滤低于 55 分的候选人
- 原子性写入：`.tmp` + `os.replace()`；备份恢复：`.bak` 自动回退

### 候选人提取

候选人提取使用 **DOM 滚动提取**（`_extract_cards_batch()`），通过滚动页面逐批加载候选人卡片并解析 DOM 结构。提取流程：

1. 滚动页面触发懒加载
2. 等待新卡片渲染
3. 批量提取当前可见的所有卡片
4. 去重合并到候选人列表
5. 重复直到触底或达到轮次上限

> **为什么不用 API 监听/直调？** BOSS 直聘推荐页使用 `srcdoc` iframe，`iframe.run_js('return location.href')` 始终返回 `about:srcdoc`，无法获取 jobId 参数。同时页面数据由服务端渲染嵌入 HTML，无客户端 API 调用可供监听。代码中保留了 `_start_recommend_api_listener()` 和 `_build_recommend_api_pagination_from_page()` 等函数，但在当前 BOSS 页面结构下均无效。

`filter_candidate()` 接受可选 `structured_fields` 参数，优先使用结构化值，fallback 到正则文本解析。薪资正则 `[kK]?` 末尾 K 可选，兼容 "15-25" 无后缀格式。

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
- **简历二次评估**：导入候选人简历（PDF/Word/TXT/MD/RTF/HTML）后，基于完整简历做第二轮 LLM 评估（再调 ±10），三次评估叠加：`final = rule_score + llm_adjustment + resume_adjustment`；GUI 支持导入简历、撤回评估；Excel 新增"简历评估"和"简历评估理由"列

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

## 低频专项说明

低频踩坑、平台差异和专项背景放在 `.agent/notes.md`。这是项目级稳定说明，可以进 git；不要把会话记忆、临时调试日志或自动生成的 agent 记忆放进去。
