# BOSS 简历筛选器 - 项目规范

## 项目结构
```
boss-resume-filter/
├── bossmaster.py         # BOSS 直聘自动筛选主程序（核心）
├── filtering.py          # 纯筛选规则模块（评分、硬条件、薪资/经验/城市解析）
├── llm_eval.py           # LLM 辅助评估模块（prompt 构建、API 调用、批量评估）
├── storage.py            # 候选人数据持久化模块（去重、原子写入、备份恢复）
├── gui_main.py           # 图形界面主程序（v2.8.11）
├── updater.py            # 自动更新模块（Gitee/GitHub 双源检查、下载替换、完整性校验、启动时自动检查）
├── icons.py              # 图标绘制模块（Pillow 矢量图标，31个图标函数 + IconCache）
├── doc_parser.py         # 文档解析器（简历解析）
├── security.py           # API Key 安全存储模块（keyring 加密）
├── migrate_keys.py       # API Key 迁移工具（明文→加密）
├── constants.py          # 共享常量（评分阈值、城市列表）
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
├── CLAUDE.md             # 本文件
├── README.md             # 项目主文档
├── CHANGELOG.md          # 更新日志
├── GUI 使用说明.md        # 图形界面详细说明
├── README_文件管理.md      # 数据文件管理说明
├── DEPLOYMENT.md         # 部署说明（新电脑配置）
├── PACKAGING.md          # 打包指南
├── tests/                # 测试脚本目录
└── scripts/              # 辅助脚本目录
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
- `python build.py --check`：仅执行发布前检查，不打包、不提交、不推送
- `python build.py`：自动使用 pack_venv 打包（Windows 生成单文件 EXE，macOS 生成 .app + ZIP + DMG）
- `python build.py --release`：打包 → 提交 → 打 tag → 推送确认 → GitHub Release 上传（一键发布）
- `python build.py --release --auto`：全自动模式，跳过推送确认，用于 Claude Code 等非交互环境
- `python build.py --release --version 2.5`：自动更新 `__version__` + 一键发布
- `__version__` 在 `gui_main.py` 中定义，是唯一版本号来源；`build.py` 通过 AST 解析提取并核对
- **Windows**：dist 目录输出 `BOSS_ResumeFilter.exe` + `README.md` + `job_config.json`
- **macOS**：dist 目录输出 `BOSS_ResumeFilter.app`（应用包）+ `BOSS_ResumeFilter_mac.zip`（自动更新用）+ `BOSS_ResumeFilter.dmg`（用户安装用）
- `build.py` 自动检测平台（`IS_MAC`/`IS_WIN`），无需额外参数
- macOS 打包使用 `--onedir --windowed` 生成 .app，Windows 使用 `--onefile --noconsole --runtime-tmpdir %LOCALAPPDATA%` 生成 EXE（`%LOCALAPPDATA%` 替代默认 `%TEMP%`，规避企业电脑临时目录策略限制导致的 PyInstaller 解压失败）
- macOS DMG 使用系统自带 `hdiutil` 生成，ZIP 使用 Python `zipfile` 模块
- **GitHub Actions 自动补齐打包**：推送 tag 后 CI 检查 Release 已有产物，只构建缺失的平台（`.github/workflows/release.yml`）；本地 Mac 发布时上传 DMG+ZIP → CI 构建 EXE；本地 Windows 发布时上传 EXE → CI 构建 DMG+ZIP；CI 只负责构建和上传 GitHub Release，不上传 Gitee；CI 模式使用 `--ci --release` 跳过虚拟环境切换和 git 操作
- **覆盖发布按需重建对端**：`build.py --release` 上传当前平台产物后，自动检测变更是否需要重建对端（通过 `_needs_cross_platform_rebuild()` 判断）；纯文档或测试文件变更跳过 CI 重建，共享模块变更才触发 `gh workflow run release.yml`（Windows 发布删旧 DMG/ZIP，macOS 发布删旧 EXE）
- job_config.json、api_config.json、selectors.json 和 CHANGELOG.md 内嵌到 EXE 中，dist 中额外放置 job_config.json 供用户编辑
- CHANGELOG.md 通过 `--add-data` 打包进 EXE，`gui_main.py:show_changelog()` 优先从 `sys._MEIPASS` 读取（PyInstaller 解压目录），回退到 `BASE_DIR`
- 打包/发布前 `_preflight_checks()` 会验证依赖、敏感文件跟踪、`api_config.json` 明文 Key、源码编译、**CHANGELOG 同步**（核心代码有变更时 CHANGELOG.md 必须更新）、稳定单元回归和导入烟测
- `build.py` 会显式收集 Anaconda Python 的 Tcl/Tk 运行库，防止 EXE 启动时报 `No module named 'tkinter'`
- `--release` 会从 `CHANGELOG.md` 对应版本段落提取 GitHub Release 标题和说明；缺少对应版本或未按"新增功能 / 体验优化 / 问题修复"顺序分类时直接中断
- CHANGELOG 面向用户，避免技术细节：描述"做了什么"和"对用户的好处"，不描述实现原理、内部模块、函数名、技术栈；Bug 修复只写现象和结果，不写根因和修复方案；分类用用户视角（"体验优化"而非"行为优化/构建改进"）；功能归类要准确反映适用范围；只记录原始需求和原始 bug，不记录开发过程中自己引入又修掉的问题
- **CHANGELOG 和 README 必须同步**：修改 CHANGELOG.md 的任何版本条目时，必须同步更新 README.md 中对应版本的条目。README 版本历史的条目数量、分类（新增功能/体验优化/问题修复）必须与 CHANGELOG 完全一致，不允许遗漏。build.py --release 的发布前检查会自动核对
- Release 模式不再 `git add -A`；只允许自动提交 `--version` 引起的 `gui_main.py` 版本号变化，其他变更必须先手工提交
- 推送前 `input()` 确认 [y/N]，不确认则保留本地提交和 tag；`--auto` 模式跳过确认直接推送；tag 冲突时自动 `--force`（master 除外）

## 代码规范
- 使用 type hints
- 关键函数写 docstring
- 异常处理要具体，不要裸 except（已规范化为具体异常类型）

## 敏感信息
- .env 文件不进 git
- 候选人数据含个人隐私，本地存储要加密
- API Key 加密存储在系统钥匙串（Windows DPAPI / macOS Keychain），`api_config.json` 不含明文
- API Key 按服务商统一管理，同一服务商的所有模型共享一个 Key

## 核心逻辑
### 打招呼机制
- 打招呼按钮位于 `operate-side` 区域（与 `card-inner` 并列的兄弟元素）
- 按钮文本："继续沟通"（已匹配）、"立即沟通"（新候选人）
- 中断时兜底保存，支持中断恢复
- 过滤规则：只过滤「当前岗位已匹配且打过招呼」的候选人
- 打招呼等级：`--greet-level strong`（仅强烈推荐 ≥75）或 `normal`（默认，强烈推荐+推荐 ≥65）
- GUI 中「自动打招呼」下拉框对初次扫描和补打招呼均生效
- 智能滚动定位：`_find_card_by_scroll()` 三阶段搜索（当前位置 → 滚到顶部 → 逐步向下 800px/步，最多 40 轮），同时滚动 window 和列表容器元素，确保虚拟列表中不在可视区的卡片也能被定位到
- 沟通上限检测：`_detect_limit_popup()` 单次 JS 调用检测 16 个限制关键词（"今日沟通次数已用完"等），同时检查 page 和 iframe。检测到上限后停止后续打招呼并提示用户
- 页面导航等待时间统一为 3 秒
- 多岗位间切换：GUI 模式弹出确认对话框，用户确认后才继续（不再使用倒计时）；CLI 模式等待 Enter 确认

### 停止机制（v2.2）
- StopRequested 异常 + threading.Event 信号穿透所有关键循环（滚动轮次/筛选/打招呼）
- GUI「停止」按钮设置 stop_event，工作线程在下次循环检查点立即停止
- 停止时自动保存当前进度并导出 Excel

### 浏览器自动检测（v2.5）
- 进入运行页自动每 2 秒轮询 Chrome 连接状态
- 手动点击"检测/连接浏览器"时自动启动 Chrome：动态端口（socket.bind(0)）+ 独立 profile（`.chrome_profile/`）+ subprocess 启动 + socket 轮询等待端口就绪（最长 30s）
- Chrome 启动时仅清理锁文件（SingletonLock/Socket/Cookie），保留 profile 目录以维持登录态和 cookies
- `_browser_check_running` 互斥标志在 `check_browser_connection()` 入口**同步**置位（不等线程启动），消除手动点击与 auto-poll 的竞态
- 手动点击被 auto-poll 阻塞时设 `_pending_manual_check` 标志，auto-poll 结束后通过 `root.after(100)` 自动重新触发
- 健康检查路径（复用 `self.browser_page`）用 `prev_help` 对比检测状态变更，无论 silent 或 manual 模式都在状态变化时输出日志
- 所有浏览器状态变更的日志消息与 UI `browser_status_help` 提示文本保持一致
- 端口预检（`socket.connect_ex`）防止自动启动浏览器
- Chrome 启动失败时分类处理：`FileNotFoundError` → 提示安装 Chrome；其他 chrome 相关异常 → 提示检查安装
- 实现位置：`gui_main.py:check_browser_connection()`、`gui_main.py:_start_browser_auto_check()`

### 反爬对抗（v2.4 健壮性）

- **随机延迟抖动**：`_human_delay(center, spread)` 辅助函数，所有 `time.sleep` 调用带随机抖动（不同场景不同 spread），降低行为指纹识别风险。倒计时显示保持精确 1s
- **安全验证阻断**：`_detect_captcha()` 单次 JS 调用检测 10 个验证码弹窗专属关键词（"请完成安全验证"/"滑块验证"/"拖拽拼图"等，已排除"验证码"等泛化词），同时检查 9 个常见验证码容器 CSS 选择器。JS 使用 TreeWalker 只遍历可见文本节点，向上遍历检查 `getComputedStyle` 排除 `display:none` / `visibility:hidden` / `opacity:0` 的隐藏元素，并通过 `getBoundingClientRect` 检查视口位置排除屏幕外元素，避免误报。在滚动扫描每轮开始、打招呼点击后、打招呼循环失败时三处调用。检测到验证码后调用 `_wait_for_captcha_resolution()` 暂停程序并每 3 秒轮询验证状态，用户在浏览器中完成验证后自动恢复运行；支持 stop_event 中断和 5 分钟超时保护；GUI 模式通过 `captcha_callback` 弹出对话框通知用户，提供「继续等待」和「跳过验证」选项
- 实现位置：`bossmaster.py:_human_delay()`、`bossmaster.py:_detect_captcha()`、`bossmaster.py:_wait_for_captcha_resolution()`；`gui_main.py:captcha_callback`

### 去重机制
- 基于 `(geek_id, job_name)` 复合键去重，保留分数高的记录
- 合并打招呼状态（greet_sent）
- `storage.py:save_candidates_all()` 使用 O(n) 算法（字典替代列表查找）；`bossmaster.py` 保留同名导入兼容旧调用

### 保存策略
- 正常流程：岗位处理完毕时统一保存（减少 IO）
- 异常中断：KeyboardInterrupt / StopRequested 时立即兜底保存
- 淘汰过滤：保存前自动过滤低于 55 分的淘汰候选人，不写入 `candidates_all.json`
- 原子性写入：先写 `candidates_all.json.tmp`，成功后再 `os.replace()` 覆盖，防止中途崩溃导致数据文件损坏
- 备份恢复：保存前复制旧 `candidates_all.json` 为 `candidates_all.json.bak`；加载主文件失败时自动尝试从 `.bak` 恢复

### 滚动提前终止
- 滚动位置检测（策略1）：`get_frame_scroll_info()` 检查 `atBottom` 标记，单次 JS 调用无 DOM 查找开销
- 文本提示检测（策略2）：滚动位置到底后，再用 DrissionPage `@text():关键字` 模糊匹配"到底"/"没有更多"提示文字做二次确认
- 连续空轮次兜底（策略3）：连续 5 轮无新候选人自动终止，不依赖特定文案。同时滚动 window 和可能的滚动容器元素（`.candidate-list` 等），单次滚动 800px
- **批量提取优化**：`_extract_cards_batch()` 单次 JS 调用提取所有卡片数据（geek_id、文本、姓名），替代逐卡片的 N+1 网络调用，每轮从 ~90 次降到 ~4 次网络请求，耗时从 1.5-2.5s 降到 0.5-0.8s
- 实现位置：`extract_candidates_by_comprehensive_analysis()` 函数

### 评分体系（v2.1 重构，v2.7 调整权重）
- 四维评分模型：`基础25 + 技能(0~50) + 经验超额(0~15) + 学历档次(0~10)`
- 英文关键词用 `\b` 单词边界匹配，避免子串误匹配（如 AI 不再匹配 email）
- 经验超额加分：超出 min_exp 部分每年 +3 分，15 分封顶
- 学历档次加分：博士+10, 985/211硕士+9, 硕士+7, 985/211本科+6, 统招本科+3
- 找不到工作经验不再淘汰（警告后放行），但也不加分
- 推荐等级阈值：>=75 强烈推荐, >=65 推荐, >=55 待定
- 实现位置：`filtering.py:filter_candidate()`, `filtering.py:_keyword_found()`, `filtering.py:_calc_edu_bonus()`；`bossmaster.py` 保留同名导入兼容旧调用
- 淘汰原因合并：学历不符/经验不足/年龄不符/地点不符/薪资不匹配/评分不足 按大类合并，括号内动态显示实际招聘要求
- 淘汰原因排序：学历不符/不足 → 经验不足 → 年龄不符 → 地点不符 → 薪资不匹配 → 评分不足(按分数段) → 其他，同类内按数量降序
- 硬条件检查顺序（v2.5）：学历 → 经验 → 年龄 → 工作地点 → 薪资范围 → 必要条件 → 技术关键词

### AI 辅助评估（v2.7）
- 对通过筛选的所有候选人（≥55 分）调用 LLM 做二次评估，最多 50 人/次
- LLM 返回 `{"adjustment": ±10, "reason": "..."}` JSON，调整值叠加到规则评分上，clamp 到 [0, 100]
- 调整后的分数重算推荐等级（≥75 强烈推荐, ≥65 推荐, ≥55 待定），直接影响打招呼决策
- 候选人记录新增字段：`rule_score`（原始规则分）、`llm_evaluated`、`llm_adjustment`、`llm_reason`、`llm_model`
- GUI 运行页「启用 AI 辅助评估」开关，默认关闭；结果表增加「AI评估」列显示调整值
- CLI：`--ai-eval` 标志启用
- API 配置复用 `api_config.json` + `security.py` keyring，不额外配置
- 429 限流指数退避（2s→4s→8s），其他异常 graceful fallback（保留原始分数）
- **并发调用**：`evaluate_batch()` 使用 `ThreadPoolExecutor` 默认 3 路并发（`max_workers=3`），每次调用后仍保留 1s+ 随机抖动防限流；支持 stop_event 中断和取消剩余任务
- 实现位置：`llm_eval.py:evaluate_batch()`、`llm_eval.py:_evaluate_single()`、`llm_eval.py:_call_llm_api()`、`bossmaster.py:smart_scan_candidates()` 阶段 1.5

### 必要条件（v2.4 UI 重构）
- GUI 使用下拉框选择条件类型 + 逗号分隔关键词，无需手写 JSON
- 三种模式：简单匹配（子串搜索）、OR（满足任一，大小写不敏感）、AND（全部满足）
- 全角逗号（，）自动归一化为半角逗号分隔
- 底层 `check_required_condition()` 支持三种格式：字符串、`{"type":"or","items":[...]}`、`{"type":"and","items":[...]}`
- 实现位置：`filtering.py:check_required_condition()`、`gui_main.py:add_required_condition()`；`bossmaster.py` 保留同名导入兼容旧调用

### 薪资输入验证（v2.4）
- `StringVar.trace_add('write', callback)` 实时检测：非数字字符红色高亮，空值/合法数字恢复默认色
- 保存时 `int()` 二次解析，非法值弹窗警告并阻止保存

### 需求解析规则（doc_parser.py）
- 从需求文档中提取关键词，分为硬约束（tech_condition_keywords）和软技能（soft_skills）两类
- 已排除泛化关键词：数据库（零区分信号，几乎所有后端简历都有）
- 保留了精准词：向量数据库（AI/RAG 相关）
- 英文关键词按长度降序匹配，优先匹配长词（如 Spring Cloud 优先于 Spring）
- **文本预处理**：`_preprocess_text()` 统一处理全角数字/英文→半角、全角标点→半角（减号/冒号/波浪号/括号/逗号）、去零宽字符、去 emoji、压缩连续空白；在 `parse_job_requirements()`、`_extract_salary_range()`、`_extract_work_location()` 三个入口调用
- **英文技能单词边界匹配**：纯英文技能（Go、API、C# 等）使用 `(?<![A-Za-z0-9_])...(?![A-Za-z0-9_])` 边界，防止 Go 误匹配 Google、C# 误匹配 CSharpDoc；中文上下文（中文旁无空格）仍可正常匹配
- **职位名称后缀**：`工程师|开发|架构|专家|经理|总监|研发|负责人|分析师|设计师|运维|测试|DBA|产品`，统一为 `_title_suffix` 变量；支持 `招聘：`/`岗位名称：` 前缀
- **年龄提取**：6 条正则覆盖 `35岁以下`/`不超过40岁`/`35周岁以内`/`≤35岁`/`25-35岁`（取上限）/`年龄35以下`（省略岁字）
- **经验提取**：支持中文数字（`三年`/`五年`/`两年`，映射表 `_cn_num_map`）+ 阿拉伯数字；支持 `至少X年`/`不低于X年`/`不少于X年`/`具有X年以上`；辅助函数 `_to_int()` 统一转换
- **段落分离**：支持多种标题变体，用正则统一匹配：
  - 硬性条件：`硬性条件|硬性要求|基本条件|必备条件|必须满足|必须条件`
  - 职位描述：`职位描述|岗位职责|工作内容|主要职责|工作职责`
  - 职位要求：`职位要求|任职要求|岗位要求|应聘要求|能力要求|我们希望你`
  - 软性条件：`软性条件|加分项|优先条件|加分条件|优先考虑`
  - 支持两个段落标题出现顺序互换（职位描述在前/职位要求在前均可）
- **学历语境排除**：统一 `_edu_bonus_patterns` 常量（15 条），`required_section` 和 `job_desc_section` 共用，排除 `博士优先`/`博士学历优先`/`有博士学历者`/`硕士学历优先` 等加分语境误判为最低学历门槛
- **工作地点提取**：`_extract_work_location()` 支持 `工作地点|工作城市|工作地|办公地|办公地点|入职城市|派驻|base地?|坐标` 关键词；兜底扫描按行排除 `总部|公司位于|集团位于|坐落于` 上下文，防止公司总部城市被误匹配为工作地
- 薪资范围提取：`_extract_salary_range()` 支持多种格式（见下方"薪资范围筛选"）

### 薪资范围筛选（v2.4 新增，v2.8.11 增强）
- `doc_parser.py`：`_extract_salary_range()` 支持 5 类格式：
  - **标签前缀**：薪资/薪酬/待遇/月薪/底薪/工资 + 冒号 + 范围，首个K可省略（`薪资：15-25K`）
  - **年薪制**：年薪/年包 X-Y万 → 自动÷12转月薪（`年薪20-35万` → `(16, 29)`）
  - **无标签范围**：`15-25K` / `15000-25000元`（需附近有薪资关键词，避免匹配"3-5年"）
  - **单边下限**：`15K起` / `15000以上` / `不低于15K` / `保底15K` / `起薪15K`
  - **面议变体**：按行检测 `面议`/`可谈`/`open`/`面谈`/`从优`，同行有薪资关键词则跳过
- `filtering.py`：`_parse_candidate_salary_range()` 解析候选人 summary 第一行薪资
- `filter_candidate()` 硬性条件检查 #2.6：候选人期望最低薪资 >= 岗位薪资上限 + 1K → 过滤
- 岗位 salary_min/salary_max 均为 None 时跳过；候选人"面议"时跳过
- 淘汰原因格式：`"薪资不匹配：岗位最高{max}K，候选人期望最低{min}K"`

### 工作地点筛选（v2.3 新增）
- `filter_candidate()` 硬性条件检查 #2.5：地点匹配
- 候选人城市从 summary 中提取（"意向城市"/"期望城市"/"所在城市" 模式）
- 支持多地点配置（`/`、`、` 分隔），任一匹配即通过
- work_location 为空时不启用过滤，向后兼容

### 招聘需求模板（v2.3 新增）
- `job_config.json` 顶层 `requirement_template` 字段存储模板文本
- GUI「招聘需求示例」按钮默认禁用，仅"新建岗位"模式下可点击
- 点击后一键填充模板到需求输入框
- **需求输入框样式**：白底（`#FFFFFF`）+ 聚焦时 2px 蓝色边框（`highlightcolor=primary`），未聚焦时浅灰边框（`highlightbackground=border`）；空时显示灰色占位提示文字"在此粘贴招聘需求文档..."，获焦自动消失、清空自动恢复；通过 `_get_requirement_text()` 读取内容（自动过滤占位文字）

### 数据统计看板
- 侧边栏"数据统计"页（`create_stats_page()`），按岗位维度聚合筛选和打招呼数据
- 过滤条件：岗位过滤下拉框 + 时间范围（今天/本周/全部）
- **自动刷新**：切换到统计页时自动刷新；数据变更（筛选完成、打招呼、清空、删除候选人）时如果在统计页则同步刷新，无需手动刷新按钮
- 4 张汇总卡片：总候选人、强烈推荐、推荐、已打招呼（带彩色圆形图标）
- 岗位明细 Treeview：岗位名称、总人数、强烈推荐、推荐、待定、已打招呼、优质率、打招呼率、平均分
- 统计口径统一：首页统计卡片、首页明细弹窗、数据统计页汇总卡片、岗位明细表均只统计 ≥55 分的候选人
- 数据来源：`candidates_all.json`
- 优质率 = (强烈推荐 + 推荐) / 总人数
- 时间过滤基于 `batch_timestamp` 字段（`%Y%m%d_%H%M%S` 格式字符串比较）

### 页面切换性能优化
切换页面时的三个缓存机制，避免每次切页都触发耗时操作：
- **滚轮绑定缓存**：`_bind_mousewheel()` 首次绑定后给 Canvas 加 `_mousewheel_bound` 标记，后续调用直接跳过，避免递归遍历所有子控件重复 `bind()`
- **job_config 读取缓存**：`_get_job_rules_cached()` 用文件 mtime 做指纹，mtime 未变则跳过磁盘 IO，供 `show_page_home/run/result/stats` 四个页面复用
- **Treeview 刷新缓存**：`refresh_results()` 和 `refresh_stats()` 用 `(mtime, size)` + 当前过滤条件做指纹，数据未变且过滤条件未变则跳过 Treeview 全量重建（删全行再逐行插入 100 行 × 8 列 = 800+ 次 Treeview 操作）

### 候选人明细弹窗
- 点击统计指标数字（筛选结果页的"通过/强烈推荐/推荐"人数、首页统计卡片的数字）弹出明细窗口
- 表格列：姓名、工作年限、薪资、匹配分、推荐指数、状态、技能匹配
- 右键菜单：查看详情（结构化详情窗口）、打招呼（仅未招呼候选人，智能滚动定位后后台线程执行）、移除此人（从列表和 JSON 删除并刷新，弹窗保持打开并更新统计）
- 详情弹窗：`_format_candidate_detail()` 输出结构化文本，核心信息速览（年龄/工作年限/薪资/求职状态，`extract_summary_info()` 解析）、教育信息（学校·专业·学历，正则 `(.+(?:大学|学院))(.+?)(学历等级)$` 匹配无分隔符格式）、评分信息、AI 评估（评估理由/调整值/原始分/模型）、技能匹配详情（含匹配数/总数）、候选人摘要
- 弹窗模态化：`transient(self.root)` + `grab_set()` 确保弹窗打开期间主窗口不可操作
- 弹窗相对主窗口居中（`_center_window()`），字体与主界面统一（`self.font_table` / `self.font_label`）
- 实现位置：`gui_main.py:_format_candidate_detail()`、`gui_main.py:_greet_single_candidate()`、`gui_main.py:show_result_stat_detail()`、`gui_main.py:show_stat_detail()`

### 筛选结果列表
- 显示 ≥55 分的所有候选人（强烈推荐 + 推荐 + 待定），按匹配分降序排列
- 统计卡片"通过筛选"仅计 ≥65 分（强烈推荐+推荐），与列表总数不同属正常设计
- 待定候选人（55-64 分）用 `pending` tag 标记低色背景，支持右键打招呼（依赖智能滚动定位）
- **岗位+日期双重过滤**：岗位下拉框 + 开始/结束日期日历控件（`tkcalendar.DateEntry`，下拉选日期），两个日期默认均为今天，直接按控件显示日期过滤（无激活标志，所见即所得）。用户从日历控件选择日期后自动刷新结果，日期自动校验：起始日期不能晚于终止日期（选了更早的日期会自动调整另一端）、两个日期均不能超过今天（选了未来日期会自动拉回今天）。「重置日期」按钮一键恢复为今天。互斥关闭机制避免两个日历面板同时展开。基于 `batch_timestamp` 前 8 位（`YYYYMMDD`）字符串比较
- 实现位置：`gui_main.py:create_result_page()`、`gui_main.py:refresh_results()`、`gui_main.py:_validate_date_range()`、`gui_main.py:_get_result_date_filter()`、`gui_main.py:_clear_result_dates()`

### 页面选择器配置（selectors.json）
- 所有与 BOSS 直聘页面 DOM 交互的选择器集中在 `selectors.json`
- 当 BOSS 前端 DOM 结构变化时，修改 `selectors.json` 即可，无需改代码
- 选择器分组：`candidate_card`（卡片定位）、`name_extraction`（姓名提取）、`greet_button`（打招呼按钮）、`iframe`（推荐列表 iframe）、`scroll`（滚动控制）、`captcha_detection`（验证码检测）、`limit_detection`（限制弹窗检测）
- 带 `{geek_id}` 占位符的模板选择器，运行时通过 `.format()` 注入实际值
- 加载机制：`bossmaster.py:load_selectors()` 首次调用后缓存，`_sel(group, key, default)` 带默认值访问
- 选择器自动检查：浏览器连接到推荐牛人页面后自动执行一次健康检查，有异常弹窗提醒；断开重连后重新检查
- 健康检查函数：`bossmaster.py:check_selectors_health(page)` 返回诊断报告列表

## AI 模型配置（v2.0 新增）
### 支持的服务商
qwen、deepseek、kimi、zhipu、minimax、xiaomi、stepfun、openai、anthropic、custom

### 配置管理
- api_config.json 存储多服务商配置（不含明文 Key）
- API Key 加密存储在系统钥匙串（通过 security.py 管理）
- 支持双击切换已保存的模型
- 支持根据 API Key 动态获取模型列表
- 测试连接：高可用设计（全新 Session + 并行双策略 + 宽松超时）
- 新电脑部署：首次启动检测 API Key 缺失并引导重新配置

## 自动更新（v2.8）
- 启动时延迟 3 秒自动检查最新版本，**4 小时冷却**（`.last_update_check` 文件记录时间戳，避免频繁启动时重复网络请求）
- **检查顺序**：Gitee 优先 → Gitee 失败回退 GitHub → Gitee 返回"无更新"时 GitHub 复核（防止镜像同步延迟漏报新版本）
- **Gitee 源**（国内快，8s 超时）：`https://gitee.com/yaoyouzhong/boss-resume-filter/raw/master/latest.json`
- **GitHub 源**（fallback，10s 超时）：`https://api.github.com/repos/yaoyouzhong/boss-resume-filter/releases/latest`
- **下载链接**：`latest.json` 中 `downloads_cn` 字段存储 Gitee 国内下载链接，优先使用；无则回退到 GitHub
- 有新版本时弹窗显示更新内容（从 Release body 读取），支持「立即更新」和「稍后提醒」
- **Windows**：下载新 EXE（有元数据时校验文件大小和 SHA256，不匹配则报错）→ 生成 `update.bat` 脚本 → 启动脚本 → 退出当前程序 → 脚本替换 EXE 并重启；旧 EXE 保留为 `.old` 备份，新版本成功启动后自动清理（`cleanup_windows_update_backup()`，`gui_main.py` 启动后 10 秒触发）
- **macOS**：
  - 从 .app 运行：下载 ZIP → 解压 → 生成 shell 脚本替换 .app → 重启应用
  - 从源码运行：执行 `git pull`（降级方案）
- 手动检查更新：左下角版本号 → 更新日志页面 → 左侧「关于」→ 关于页面 → 「检查更新」按钮
- `latest.json` 由 `build.py:update_latest_json()` 在发布时自动更新并提交，Gitee 镜像同步后即可供国内用户检测；`latest.json` 的 `assets` 字段记录产物元数据（`size`、`sha256`），Windows 记录 EXE，macOS 同时记录 ZIP 和 DMG，供客户端校验下载完整性
- **Gitee Release 上传**：`build.py --release` 在 GitHub Release 上传后，分两步同步 Gitee：(1) `_gitee_get_release_cache()` 获取 Release 缓存信息；(2) `_gitee_upload_local()` 上传本地平台产物（EXE/DMG+config+readme）；(3) `_sync_gitee_from_github()` 轮询等待 CI 完成 → 并行下载对端产物到本地 → 并行上传全部产物到 Gitee（`ThreadPoolExecutor` 3 路并发）；上传成功后自动更新 `latest.json` 的 `downloads_cn` 字段并提交推送。发布过程显示详细进度（7 步主流程 + 子步骤），每步完成后显示耗时
- **Gitee 上传鲁棒性**：所有 Gitee API 调用使用 `requests.Session` + `HTTPAdapter` 自动重试（429/5xx，3 次指数退避）；`_gitee_find_or_create_release()` 和 `_gitee_delete_asset()` 额外包装手动重试（3 次，间隔 5/10/15s）；`_gitee_upload_single()` 5 次重试（间隔 5/10/20/40s，总等待 75s）+ 600s 超时；批量操作前 `_gitee_ping()` 预检 API 连通性（3 次 HEAD 请求）
- **Gitee 增量上传**：上传前获取远端附件的 size 和 created_at，与本地文件比对：大小一致且本地 mtime 不超过远端创建时间 5 分钟 → 跳过；否则删旧重传。避免重复上传和单文件失败后全量重传
- **Gitee 覆盖发布**：重新发布同一版本时，增量比对后只重传有变化的文件；同时同步 Release 标题和正文（均以 CHANGELOG 为准）；附件信息通过 `attach_files` API 获取（releases 列表 API 不返回 ID/size）
- **Gitee Token 配置**：在 https://gitee.com/profile/personal_access_tokens 生成私人令牌（勾选 projects 权限），设置为环境变量 `GITEE_TOKEN`；未设置时跳过 Gitee 上传，不影响 GitHub Release
- 实现位置：`updater.py`（独立模块），`gui_main.py:__init__()` 调用 `updater.auto_check_on_startup()`；`build.py:_gitee_upload_local()`、`build.py:_sync_gitee_from_github()`

## 踩坑警示

### macOS .app 路径解析
`sys.executable` 在 .app 中指向 `.app/Contents/MacOS/BOSS_ResumeFilter`，不是 .app 的父目录。`job_config.json` 等配置文件在 .app 旁边，需要向上追溯 3 层：
```python
if sys.platform == 'darwin' and exe_dir.name == 'MacOS':
    return exe_dir.parent.parent.parent  # .app 的父目录
```
Windows EXE 直接用 `sys.executable.parent` 即可。路径逻辑统一在 `paths.py:get_base_dir()` 中维护，所有模块（`gui_main.py`、`updater.py`、`bossmaster.py`）从这里导入，修改只需改一处。

### PyInstaller 版本号读取
不能从 `sys._MEIPASS` 读取 `gui_main.py` 源文件，因为源码被编译进 PYZ 归档，文件不存在。应该直接 `import gui_main` 读取模块属性，兼容所有打包模式（源码 / Windows EXE / macOS .app）。

### DMG 图标布局控制
直接用 `hdiutil create` 无法控制图标位置。尝试过 AppleScript 设置 Finder 布局（挂载 RW DMG → 设置位置 → 转换为 RO），但 Finder AppleScript 在 macOS 13+ 不稳定，经常报错。最终方案：使用 `dmgbuild` Python 库，直接生成带正确 `.DS_Store` 的 DMG，无需挂载和 AppleScript。

### CHANGELOG 分类校验
`build.py` 的 `_check_changelog()` 原本要求三个分类（新增功能 / 体验优化 / 问题修复）都有内容，但补丁版本通常只有"问题修复"。改为：至少有一个分类，且存在的分类按规范顺序排列（新增功能 → 体验优化 → 问题修复）。

### DMG 安装后配置文件缺失
DMG 只包含 .app + Applications 快捷方式，`job_config.json`/`selectors.json`/`api_config.json` 不在 DMG 中（虽然通过 `--add-data` 嵌入了 `sys._MEIPASS`）。用户安装后 .app 旁边没有配置文件，导致首次启动岗位配置为空。解决方案：`_get_base_dir()` 首次启动时检测配置文件是否存在，不存在则从 `sys._MEIPASS` 复制到可写位置。

### macOS Dock 图标点击恢复窗口
`tk::mac::Reopen`（旧命令）在 Tk macOS 上不触发，delegate 方法注入、`sendEvent:` swizzle、frontmost 轮询等方案均不可行。最终可用方案：通过 `root.createcommand('tk::mac::ReopenApplication', callback)` 注册回调（注意是 `ReopenApplication` 不是 `Reopen`），配合 `deiconify()` + `lift()` + `focus_force()` 恢复窗口。实现位置：`gui_main.py:_setup_macos_reopen_handler()`、`gui_main.py:_restore_main_window()`

### Tk 对话框 `wait_window()` 嵌套事件循环崩溃
`wait_window()` 在 `root.after()` 回调中创建嵌套事件循环，macOS 上与 Cocoa scroll hook（`NSView.scrollWheel:` swizzle）和浏览器轮询（2 秒间隔的 `root.after()`）冲突，导致应用异常崩溃退出。正确做法是用 `grab_set()` 实现模态（不阻塞主事件循环），用 `protocol("WM_DELETE_WINDOW")` + 统一 `_close_dialog()` 清理引用。同理 `self.root.update()` 在主线程中强制处理事件有重入风险，应移除。实现位置：`gui_main.py:fetch_model_list()` → `show_model_dialog()`。

### Tk Listbox 不支持 spacing1/spacing2/spacing3
`tk.Listbox` 不接受 `spacing1`、`spacing2`、`spacing3` 参数——这些是 `tk.Text` 专属选项。传入会抛 `TclError: unknown option "-spacing1"`。调整 Listbox 行间距只能通过修改字体大小实现。

### `pack_propagate(False)` 必须同时指定 width 和 height
设置 `frame.pack_propagate(False)` 后，如果只设 `width` 不设 `height`（或反过来），frame 会在未指定维度上坍缩为 0，导致子控件不可见。搭配 `place(relx=0.5, rely=0.5)` 更危险——place 不传播尺寸，父 frame 高度始终为 0。正确做法：同时设 `width` 和 `height`，或在内部用 pack + `expand=True` 的内容 frame 撑开。

### Windows DPI 缩放（DPI Unaware 方案）
`SetProcessDpiAwarenessContext(-4)` 在 64 位 Python 上默认失败——ctypes 不自动做符号扩展，`-4` 被截断为 32 位 `0xFFFFFFFC`，Windows 返回错误码 87 (INVALID_PARAMETER)。修复：设置 `argtypes = [wintypes.HANDLE]`，用 `ctypes.c_void_p(-4)` 传入。但即使修复成功，Tk 8.6 在 Per Monitor DPI V2 模式下内部坐标系与物理像素不匹配，导致布局错乱。

**System DPI Aware 也不可行**（2026-05-26 验证）：Tk 8.6 的字体渲染使用 `size × real_dpi/72` 计算物理像素，而 Windows 位图缩放使用不同的映射方式。单一 `effective_scale` 无法同时匹配字体和布局——字体清晰时窗口过小，窗口正常时字体过大。Tk 8.7（8.7a5，尚在 alpha）可能解决此问题，当前 Python 3.12/3.13 均内置 Tk 8.6。

最终方案：**保持 DPI Unaware**，不启用任何 DPI 感知。DPI Unaware 模式下：
- `winfo_fpixels('1i')` 返回 ~96（虚拟化 DPI），`winfo_screenwidth()` 返回虚拟像素
- Windows 在后台自动按系统缩放倍数放大 Tk 渲染内容（字体略有模糊但布局正确）
- 用 `EnumDisplaySettingsW(None, -1)` 获取主显示器物理像素宽度（绕过虚拟化），除以 Tk 虚拟宽度，得到真实 `display_scale`
- 高 DPI（>130%）时乘以 `high_dpi_reduction`（当前 0.6），避免 UI 占满屏幕
- **所有 UI 元素统一使用同一个缩放比例**（窗口、字体、间距、图标），分开缩放会导致布局错乱
- 实现位置：`gui_main.py:_get_primary_physical_width()`、`gui_main.py:_calculate_effective_scale()`、`gui_main.py:BossFilterGUI.__init__()`
- macOS 不受影响：`winfo_screenwidth()` 返回物理像素，Retina 缩放由窗口系统处理

### macOS Tk 8.6 字体物理像素减半
Tk 8.6 在部分 Mac 环境下报告的 DPI 低于预期，导致字体物理像素偏小。Apple Silicon（M1/M2/M3/M4，Anaconda/Homebrew Python）报告 DPI 72；Intel Mac 的 venv 环境报告 DPI 约 96（系统 Tk 8.5 报告 DPI 144，不受影响）。阈值 `< 80` 可区分这两类需补偿的环境与正常环境。

检测逻辑（`gui_main.py:BossFilterGUI.__init__()`）：
```python
if sys.platform == 'darwin':
    _tk_dpi_raw = self.root.winfo_fpixels('1i')
    self.font_boost = 1.65 if _tk_dpi_raw < 80 else 1.0
else:
    self.font_boost = 1.0
self.font_scale = self.dpi_scale * self.zoom_factor * self.font_boost
```

- `font_scale` 仅用于字体大小，布局/间距/图标/窗口/rowheight 仍用 `dpi_scale × zoom_factor`
- 阈值 `< 80`：DPI 72（Apple Silicon）和 DPI 96（Intel Mac venv）触发补偿，DPI 144（Intel Mac 系统 Tk 8.5）不触发
- 实现位置：`gui_main.py:BossFilterGUI.__init__()`、`gui_main.py:setup_styles()`

### 字体常量与 Combobox 规范
- `FONT_FAMILY` 和 `FONT_FAMILY_SEMIBOLD` 是跨平台字体常量（Windows: Microsoft YaHei UI, macOS: PingFang SC, Linux: Helvetica），所有 UI 字体定义统一引用这两个常量，不硬编码字体名
- 字体变量 7 个（2026-05-27 精简后）：`font_title`(28pt) / `font_section`(16pt) / `font_label`(13pt，通用：表单标签、按钮、下拉框) / `font_stat`(36pt) / `font_stat_label`(15pt) / `font_log`(11pt) / `font_table`(12pt)
- 字体缩放使用 `self.font_scale`（含 macOS font_boost），布局/间距/图标/rowheight 使用 `self.dpi_scale * self.zoom_factor`（不含 font_boost）
- Combobox 下拉列表字体通过 `option_add('*TCombobox*Listbox.font', font, 80)` 设置，优先级 80 确保覆盖默认样式
- 所有 Combobox 禁用鼠标滚轮：`bind_class('TCombobox', '<MouseWheel>', lambda e: 'break')`（同时绑定 Button-4/Button-5 兼容 Linux）

### macOS aqua 主题 ttk 控件灰色背景（2026-05-27）
macOS aqua 主题的 ttk 控件默认背景是 `systemWindowBackgroundColor`（灰色），三层原因叠加导致大面积灰色残留：

1. **`ttk.LabelFrame` 内容区灰色**：`Labelframe.border` 元素硬编码 `systemWindowBackgroundColor`，`style.configure` 设 `background` 只管 widget 级，border 元素不管。解决方案：用 `_create_card(parent, title, ...)` 替代所有 `LabelFrame`，内部用 `tk.Frame` 白底 + `highlightbackground` 边框 + 标题行（浅灰 `#F7F8FA` 背景 + 左侧 2px 蓝色竖线 + 底部分隔线区分内容区），标题用 `self.font_label` 与页面统一
2. **`ttk.Label` 默认背景灰色**：`style.configure('TLabel')` 没设 `background` 时继承 aqua 默认灰。解决方案：`style.configure('TLabel', background=self.colors['bg_card'])`
3. **`ttk.Combobox`/`TSpinbox`/`TEntry` 输入框灰色**：macOS aqua 原生渲染忽略 `style.configure` 设的 `fieldbackground`，只有 `style.map` 按状态映射有效。解决方案：
```python
style.map('TCombobox', fieldbackground=[('readonly', bg_card), ('!disabled', bg_card)])
style.map('TSpinbox', fieldbackground=[('!disabled', bg_card)])
style.map('TEntry', fieldbackground=[('!disabled', bg_card)])
```

架构约定：
- `TFrame` 默认白底（`bg_card`），页面级灰底容器用 `Page.TFrame`（`bg_main`）
- `_create_scroll_container` 的容器 frame 必须加 `style='TFrame'`，否则用 ttk 默认灰
- `_create_page_header(parent, title, subtitle=None)` 统一创建页面标题（白底 + 左侧 4px 蓝色竖线）
- 实现位置：`gui_main.py:setup_styles()`、`gui_main.py:_create_card()`、`gui_main.py:_create_page_header()`

### Gitee Release API 限制
Gitee API 与 GitHub 有两处关键差异，覆盖发布时容易踩坑：
1. **PATCH release 必须带 `tag_name` 和 `body`**：只传 `name` 会返回 400 `"body is missing"`。更新标题时必须同时传 `tag_name`（原值）和 `body`（`release.get("body", "")` 保留现有正文）
2. **releases 列表不返回附件 ID**：`GET /repos/{owner}/{repo}/releases` 的 `assets` 数组只有 `browser_download_url` 和 `name`，没有 `id`。删除附件需要通过专门的 `GET /releases/{id}/attach_files` 接口获取附件 ID
实现位置：`build.py:_gitee_find_or_create_release()`、`build.py:_gitee_delete_asset()`
