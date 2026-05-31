# BOSS 简历筛选器 - 项目规范

## 项目结构
```
boss-resume-filter/
├── bossmaster.py         # BOSS 直聘自动筛选主程序（核心）
├── filtering.py          # 纯筛选规则模块（评分、硬条件、薪资/经验/城市解析）
├── llm_eval.py           # LLM 辅助评估模块（prompt 构建、API 调用、批量评估）
├── storage.py            # 候选人数据持久化模块（去重、原子写入、备份恢复）
├── gui_main.py           # 图形界面主程序（v2.8.12）
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
- **格式要求**：大版本 `X.Y`（如 v2.9），补丁版本 `X.Y.Z`（如 v2.8.12）
- **禁止**：大版本写成 `X.Y.0`（如 v2.9.0），必须省略末尾的 `.0`
- **历史惯例**：v2.0、v2.1、v2.2...v2.8、v2.9 均为两位数；v2.8.1~v2.8.12 为补丁版本
- **更新位置**（版本号变更时必须同步）：
  - `gui_main.py` 的 `__version__` 变量
  - `CHANGELOG.md` 的新版本标题
  - `README.md` 顶部版本标识 + 新增版本段落 + 项目结构中的 gui_main.py 注释
  - `CLAUDE.md` 项目结构中的 gui_main.py 注释

#### 版本号更新检查清单
更新版本号时，必须按以下顺序检查并更新：

1. **gui_main.py**
   - 位置：第 6 行 `__version__ = "X.Y"`
   - 格式：不带 `v` 前缀，如 `__version__ = "2.9"`

2. **CHANGELOG.md**
   - 在文件顶部（`# 更新日志` 之后）添加新版本段落
   - 格式：`## vX.Y — 版本标题`（大版本）或 `## vX.Y.Z — 版本标题`（补丁版本）
   - 包含三个分类：新增功能、体验优化、问题修复（至少一个）
   - 示例：`## v2.9 — 模型管理增强 + 新建岗位引导`

3. **README.md**
   - **顶部版本标识**：更新 `> **当前版本：vX.Y**` 行
   - **版本历史**：在 `## 版本历史` 部分添加新版本段落
     - 格式：`### vX.Y 版本标题` 或 `### vX.Y.Z 版本标题`
     - 内容从 CHANGELOG.md 对应版本复制，但省略"新增功能/体验优化/问题修复"等分类标题
   - **项目结构**：更新 gui_main.py 注释中的版本号
     - 格式：`├── gui_main.py          # 图形界面主程序（vX.Y）`

4. **CLAUDE.md**
   - **项目结构**：更新 gui_main.py 注释中的版本号
     - 格式：`├── gui_main.py           # 图形界面主程序（vX.Y）`

5. **验证一致性**
   - 运行 `build.py --check` 进行发布前检查
   - 确认所有文件中的版本号一致
   - 确认格式正确（大版本 X.Y，补丁版本 X.Y.Z）

**常见错误**：
- ❌ 将大版本写成 `v2.9.0`（应该写 `v2.9`）
- ❌ 只更新了 gui_main.py 但忘记更新 CHANGELOG.md
- ❌ CHANGELOG.md 中缺少分类（新增功能/体验优化/问题修复）
- ❌ README.md 版本历史中的版本标题格式错误（应该是 `### vX.Y` 而不是 `### v2.9.0`）

#### 发布命令
- `python build.py --check`：仅发布前检查，不打包不提交不推送
- `python build.py`：自动使用 pack_venv 打包（Windows EXE / macOS .app+ZIP+DMG），`IS_MAC`/`IS_WIN` 自动检测
- `python build.py --release [--auto] [--version X.Y]`：打包→提交→tag→推送确认→GitHub Release 上传→Gitee 同步（`--auto` 跳过确认，`--version` 自动更新 `__version__`）
- `__version__` 在 `gui_main.py` 中定义，唯一版本号来源；`build.py` 通过 AST 解析提取
- **智能跳过打包**：`.build_state.json` 构建指纹（源码/配置/依赖/CHANGELOG/打包命令/平台/Python版本）未变时复用现有产物，`--force-build` 强制重建
- **发布范围开关**：`--no-gitee` 跳过 Gitee；`--no-ci-sync` 跳过跨平台 CI 重建
- **实时进度跟踪**：`ReleaseProgress` ANSI 终端原地重绘进度表（6 步状态+耗时），非 TTY 降级逐行打印；状态变化写入 `.build_progress.json` 供 `scripts/watch_progress.py` 轮询
- **网络操作重试**：GitHub 上传/删除/下载、Release 创建/编辑、git push 均 3 次重试（间隔 5s）
- **打包命令**：Windows `--onefile --noconsole --runtime-tmpdir %LOCALAPPDATA%`；macOS `--onedir --windowed`；DMG 用 `dmgbuild` 生成
- **GitHub Actions 补齐**：tag 推送后 CI 只构建缺失平台产物（`.github/workflows/release.yml`），CI 模式用 `--ci --release`
- **覆盖发布按需重建对端**：`_needs_cross_platform_rebuild()` 判断是否触发 CI（tests/scripts/docs/*.md/build.py 跳过）
- **Release 上传去重**：上传前比较远端同名附件大小和 SHA256，一致则跳过
- **CHANGELOG 规范**：面向用户避免技术细节；按"新增功能/体验优化/问题修复"分类；CHANGELOG 和 README 版本历史必须同步
- `--release` 从 CHANGELOG 对应版本段落提取 Release 标题和说明；缺少或不按顺序分类时中断
- 打包产物：job_config.json/api_config.json/selectors.json/CHANGELOG.md 内嵌 EXE，dist 额外放 job_config.json 供编辑
- 打包前 `_preflight_checks()` 验证依赖、敏感文件、明文 Key、源码编译、CHANGELOG 同步、稳定单元回归和导入烟测
- 新增/修改 `requirements.txt` 依赖时同步更新 `build.py:REQUIRED_IMPORTS`
- `build.py` 显式收集 Anaconda Tcl/Tk 运行库，防 `No module named 'tkinter'`
- Release 模式只自动提交 `--version` 引起的版本号变化，其他变更须先手工提交
- 推送前 `input()` 确认 [y/N]；tag 冲突时自动 `--force`（master 除外）

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
- 打招呼按钮位于 `operate-side` 区域，按钮文本："继续沟通"（已匹配）、"立即沟通"（新候选人）
- 过滤规则：只过滤「当前岗位已匹配且打过招呼」的候选人；中断时兜底保存
- 打招呼等级：`--greet-level strong`（仅 ≥75）或 `normal`（默认，≥65）
- 智能滚动定位：`_find_card_by_scroll()` 三阶段搜索（当前位置→滚到顶部→逐步向下 800px/步）
- 沟通上限检测：`_detect_limit_popup()` 单次 JS 调用检测 16 个限制关键词
- 多岗位间切换：GUI 弹出确认对话框；CLI 等待 Enter

### 停止机制（v2.2）
- StopRequested 异常 + threading.Event 穿透所有关键循环；停止时自动保存进度并导出 Excel

### 浏览器自动检测（v2.5）
- 运行页自动每 2 秒轮询 Chrome 连接状态
- 手动点击"检测/连接浏览器"时自动启动 Chrome：动态端口 + 独立 profile + subprocess + socket 轮询等待就绪（最长 30s）
- Chrome 启动时仅清理锁文件，保留 profile 维持登录态
- `_browser_check_running` 互斥标志同步置位，消除手动点击与 auto-poll 竞态
- 端口预检（`socket.connect_ex`）防止自动启动浏览器
- 启动失败分类处理：`FileNotFoundError` → 提示安装；其他 → 提示检查安装
- 实现位置：`gui_main.py:check_browser_connection()`、`gui_main.py:_start_browser_auto_check()`

### 反爬对抗（v2.4 健壮性）
- **随机延迟抖动**：`_human_delay(center, spread)` 辅助函数，所有 `time.sleep` 带随机抖动
- **安全验证阻断**：`_detect_captcha()` 单次 JS 调用检测 10 个验证码关键词 + 9 个 CSS 选择器，TreeWalker 排除隐藏元素。检测到后 `_wait_for_captcha_resolution()` 暂停等待用户完成验证（5 分钟超时，支持 stop_event 中断）；GUI 通过 `captcha_callback` 弹窗通知
- 实现位置：`bossmaster.py:_human_delay()`、`bossmaster.py:_detect_captcha()`、`bossmaster.py:_wait_for_captcha_resolution()`

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
三策略：(1) `get_frame_scroll_info()` 检查 `atBottom` 标记；(2) DrissionPage 文本匹配"到底"/"没有更多"；(3) 连续 5 轮无新候选人兜底。**批量提取优化**：`_extract_cards_batch()` 单次 JS 提取所有卡片数据，每轮从 ~90 次降到 ~4 次请求

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
- 对通过筛选的所有候选人（≥55 分）调用 LLM 二次评估，最多 50 人/次
- LLM 返回 `{"adjustment": ±10, "reason": "..."}` JSON，叠加到规则评分上，clamp 到 [0, 100]
- 调整后分数重算推荐等级，直接影响打招呼决策
- 候选人记录新增字段：`rule_score`/`llm_evaluated`/`llm_adjustment`/`llm_reason`/`llm_model`
- GUI 运行页「启用 AI 辅助评估」开关，默认关闭；CLI `--ai-eval` 标志
- 429 限流指数退避（2s→4s→8s），其他异常保留原始分数
- **并发调用**：`ThreadPoolExecutor` 默认 3 路，每次调用后 1s+ 随机抖动；支持 stop_event 中断
- 实现位置：`llm_eval.py:evaluate_batch()`、`llm_eval.py:_call_llm_api()`

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
- 从需求文档提取关键词，分为硬约束（tech_condition_keywords）和软技能（soft_skills）
- **文本预处理**：`_preprocess_text()` 统一处理全角→半角、去零宽字符、去 emoji、压缩空白
- **英文技能边界匹配**：`(?<![A-Za-z0-9_])...(?![A-Za-z0-9_])` 防止 Go 误匹配 Google
- **职位名称后缀**：工程师/开发/架构/专家/经理/总监/研发/负责人/分析师/设计师/运维/测试/DBA/产品
- **年龄提取**：6 条正则覆盖各种写法（35岁以下/不超过40岁/≤35岁/25-35岁等）
- **经验提取**：中文数字（三年/五年）+ 阿拉伯数字；支持至少/不低于/不少于/具有X年以上
- **段落分离**：支持多种标题变体（硬性条件/职位描述/职位要求/软性条件），顺序可互换
- **学历语境排除**：`_edu_bonus_patterns` 排除"博士优先"/"硕士学历优先"等加分语境
- **工作地点提取**：支持多种关键词，兜底扫描排除公司总部城市误匹配
- 薪资范围提取见下方"薪资范围筛选"

### 薪资范围筛选（v2.4 新增，v2.8.11 增强）
- `doc_parser.py`：`_extract_salary_range()` 支持 5 类格式：标签前缀（薪资:15-25K）、年薪制（自动÷12）、无标签范围、单边下限（15K起）、面议变体
- `filtering.py`：`_parse_candidate_salary_range()` 解析候选人 summary 第一行薪资
- `filter_candidate()` 硬性条件 #2.6：候选人期望最低薪资 >= 岗位薪资上限 + 1K → 过滤
- 岗位 salary_min/max 均为 None 时跳过；候选人"面议"时跳过

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

### 新建岗位步骤引导条
- 岗位配置页点击「新建」后显示 4 步引导：① 填入需求 → ② 解析文档 → ③ 检查结果 → ④ 保存配置
- 步骤条位于岗位选择行下方（用 `pack(after=...)` 定位，避免追加到末尾）
- 状态颜色：当前步骤蓝色（primary）、已完成绿色 ✓（success）、未到灰色（muted）
- **推进时机**：点击新建→①；填入模板→②；解析成功→③；**滚动页面到底部**→④
- 滚动检测：包装 canvas 的 `yscrollcommand` 回调，`float(bottom) >= 0.95` 视为到底
- 保存成功时先全绿 ✓ 闪烁 800ms 再隐藏引导条；选择已有岗位或删除岗位时隐藏
- "点此新增岗位→" 呼吸动画提示：正弦函数颜色插值（success 色与背景色之间），50ms/帧，约 3 秒周期
- 岗位 Combobox 宽度 28（原 40），新建按钮绿色图标（`success`）
- 实现位置：`gui_main.py:_update_job_step()`、`gui_main.py:_bind_job_step_advance()`、`gui_main.py:add_job()`

### 数据统计看板
- 侧边栏"数据统计"页（`create_stats_page()`），按岗位维度聚合
- 过滤：岗位下拉框 + 时间范围（今天/本周/全部）；切换到统计页自动刷新
- 4 张汇总卡片 + 岗位明细 Treeview（岗位/总人数/强烈推荐/推荐/待定/已打招呼/优质率/打招呼率/平均分）
- 统计口径统一：只统计 ≥55 分的候选人；优质率 = (强烈推荐+推荐) / 总人数
- 时间过滤基于 `batch_timestamp` 字段（`%Y%m%d_%H%M%S` 格式字符串比较）

### 页面切换性能优化
三个缓存机制：滚轮绑定缓存（`_mousewheel_bound` 标记）、job_config 读取缓存（mtime 指纹）、Treeview 刷新缓存（`(mtime, size)` + 过滤条件指纹）

### 页面选择器配置（selectors.json）
- 所有 BOSS 页面 DOM 交互选择器集中在 `selectors.json`，DOM 变化时修改即可
- 选择器分组：`candidate_card`/`name_extraction`/`greet_button`/`iframe`/`scroll`/`captcha_detection`/`limit_detection`
- 带 `{geek_id}` 占位符的模板选择器，运行时 `.format()` 注入
- 浏览器连接后自动健康检查：`bossmaster.py:check_selectors_health(page)`

## AI 模型配置（v2.0 新增）
### 支持的服务商
通义千问 (Qwen)、DeepSeek、Kimi (月之暗面)、智谱 (Zhipu)、MiniMax、小米 (Xiaomi)、阶跃星辰 (StepFun)、OpenAI、Anthropic (Claude)、自定义 (Custom)

### 配置管理
- api_config.json 存储多服务商配置（不含明文 Key）
- API Key 加密存储在系统钥匙串（通过 security.py 管理）
- 支持双击切换已保存的模型
- 支持根据 API Key 动态获取模型列表
- 测试连接：高可用设计（全新 Session + 并行双策略 + 宽松超时）
- 新电脑部署：首次启动检测 API Key 缺失并引导重新配置

### 模型列表搜索与新增检测
- 选择模型对话框内置搜索框，实时模糊匹配（大小写不敏感），占位文字"输入关键词搜索模型..."
- **新增模型检测**：`api_config.json` 的 `fetched_models` 字段按 provider 存储每次获取的模型列表
- 获取模型后与上次列表对比，找出新增模型（`set(models) - previous_models`）
- 新增模型在列表中以绿色（`success`）高亮显示，对话框顶部显示"✦ 发现 N 个新增模型（绿色标记）"
- 有新增模型时先弹 messagebox 列出名称（最多 10 个），再打开选择对话框
- 默认选中第一个新增模型（方便直接回车确认）
- 当前使用模型显示使用 `PROVIDER_DISPLAY` 映射（中文服务商名），格式：`通义千问 (Qwen) / qwen3.7-max`
- 实现位置：`gui_main.py:fetch_model_list()`、`gui_main.py:show_model_dialog()`

## 自动更新（v2.8）
- 启动时延迟 3 秒自动检查最新版本，**4 小时冷却**（`.last_update_check` 文件记录时间戳，避免频繁启动时重复网络请求）
- **检查顺序**：Gitee 优先 → Gitee 失败回退 GitHub → Gitee 返回"无更新"时 GitHub 复核（防止镜像同步延迟漏报新版本）
- **Gitee 源**（国内快，8s 超时）：`https://gitee.com/yaoyouzhong/boss-resume-filter/raw/master/latest.json`
- **GitHub 源**（fallback，10s 超时）：`https://api.github.com/repos/yaoyouzhong/boss-resume-filter/releases/latest`
- **下载链接**：`latest.json` 中 `downloads_cn` 字段存储 Gitee 国内下载链接，优先使用；无则回退到 GitHub
- 有新版本时弹窗显示更新内容（从 Release body 读取），支持「立即更新」和「稍后提醒」
- **更新弹窗字体统一**：`updater.py` 使用 `FONT_FAMILY` 和 `FONT_FAMILY_SEMIBOLD` 常量（与 gui_main.py 一致），避免硬编码字体名
- **Windows**：下载新 EXE（有元数据时校验文件大小和 SHA256，不匹配则报错）→ 生成 `update.bat` 脚本 → 启动脚本 → 退出当前程序 → 脚本替换 EXE 并重启；旧 EXE 保留为 `.old` 备份，新版本成功启动后自动清理（`cleanup_windows_update_backup()`，`gui_main.py` 启动后 10 秒触发）
- Windows 更新脚本启动新 EXE 前必须清理 `_PYI_*` 环境变量并设置 `PYINSTALLER_RESET_ENVIRONMENT=1`，避免 PyInstaller onefile 继承旧 `_MEI...` 解包目录导致 `python312.dll` 缺失；不要在更新脚本中主动删除 `%LOCALAPPDATA%\_MEI*`
- **macOS**：
  - 从 .app 运行：下载 ZIP → 解压 → 生成 shell 脚本替换 .app → 重启应用
  - 从源码运行：执行 `git pull`（降级方案）
- 手动检查更新：左下角版本号 → 更新日志页面 → 左侧「关于」→ 关于页面 → 「检查更新」按钮
- `latest.json` 由 `build.py:update_latest_json()` 在发布时自动更新并提交，Gitee 镜像同步后即可供国内用户检测；`latest.json` 的 `assets` 字段记录产物元数据（`size`、`sha256`），Windows 记录 EXE，macOS 同时记录 ZIP 和 DMG，供客户端校验下载完整性
- **Gitee Release 上传**：`build.py --release` 在 GitHub 上传后，`_gitee_upload_local()` 上传本地产物 → `_sync_gitee_from_github()` 等 CI 完成后下载对端产物再并行上传 Gitee（`ThreadPoolExecutor` 3 路）；上传成功后更新 `latest.json` 的 `downloads_cn` 字段
- **Gitee 上传鲁棒性**：`requests.Session` + `HTTPAdapter` 自动重试 429/5xx（3 次指数退避）；上传 5 次重试（5/10/20/40s）+ 600s 超时；**4xx 客户端错误直接抛出不重试**；批量操作前 `_gitee_ping()` 预检连通性；增量上传（大小+SHA256 比对）；覆盖发布同步标题和正文
- **Gitee Token**：环境变量 `GITEE_TOKEN`（https://gitee.com/profile/personal_access_tokens 生成，勾选 projects 权限），未设置时跳过 Gitee 上传
- 实现位置：`updater.py`（客户端检查），`gui_main.py:__init__()` 调用 `updater.auto_check_on_startup()`；`build.py:_gitee_upload_local()`、`build.py:_sync_gitee_from_github()`

## 踩坑警示

### macOS .app 路径解析
`sys.executable` 在 .app 中指向 `.app/Contents/MacOS/BOSS_ResumeFilter`，配置文件在 .app 旁边，需向上追溯 3 层。Windows EXE 直接用 `sys.executable.parent`。路径逻辑统一在 `paths.py:get_base_dir()` 中维护。

### PyInstaller 版本号读取
不能从 `sys._MEIPASS` 读取 `gui_main.py` 源文件，因为源码被编译进 PYZ 归档，文件不存在。应该直接 `import gui_main` 读取模块属性，兼容所有打包模式（源码 / Windows EXE / macOS .app）。

### DMG 图标布局控制
`hdiutil create` 无法控制图标位置，Finder AppleScript 在 macOS 13+ 不稳定。最终方案：使用 `dmgbuild` Python 库。

### CHANGELOG 分类校验
`build.py` 的 `_check_changelog()` 要求至少有一个分类（新增功能/体验优化/问题修复），且存在的分类按规范顺序排列。

### DMG 安装后配置文件缺失
DMG 只含 .app + Applications 快捷方式，配置文件不在 DMG 中。`_get_base_dir()` 首次启动时检测配置文件不存在则从 `sys._MEIPASS` 复制。

### macOS Dock 图标点击恢复窗口
`tk::mac::Reopen`（旧命令）在 Tk macOS 上不触发，delegate 方法注入、`sendEvent:` swizzle、frontmost 轮询等方案均不可行。最终可用方案：通过 `root.createcommand('tk::mac::ReopenApplication', callback)` 注册回调（注意是 `ReopenApplication` 不是 `Reopen`），配合 `deiconify()` + `lift()` + `focus_force()` 恢复窗口。实现位置：`gui_main.py:_setup_macos_reopen_handler()`、`gui_main.py:_restore_main_window()`

### Tk 对话框 `wait_window()` 嵌套事件循环崩溃
`wait_window()` 在 `root.after()` 回调中创建嵌套事件循环，macOS 上与 Cocoa scroll hook（`NSView.scrollWheel:` swizzle）和浏览器轮询（2 秒间隔的 `root.after()`）冲突，导致应用异常崩溃退出。正确做法是用 `grab_set()` 实现模态（不阻塞主事件循环），用 `protocol("WM_DELETE_WINDOW")` + 统一 `_close_dialog()` 清理引用。同理 `self.root.update()` 在主线程中强制处理事件有重入风险，应移除。实现位置：`gui_main.py:fetch_model_list()` → `show_model_dialog()`。

### Tk Listbox 不支持 spacing1/spacing2/spacing3
`tk.Listbox` 不接受 `spacing1`、`spacing2`、`spacing3` 参数——这些是 `tk.Text` 专属选项。传入会抛 `TclError: unknown option "-spacing1"`。调整 Listbox 行间距只能通过修改字体大小实现。

### `pack_propagate(False)` 必须同时指定 width 和 height
设置 `frame.pack_propagate(False)` 后，如果只设 `width` 不设 `height`（或反过来），frame 会在未指定维度上坍缩为 0，导致子控件不可见。搭配 `place(relx=0.5, rely=0.5)` 更危险——place 不传播尺寸，父 frame 高度始终为 0。正确做法：同时设 `width` 和 `height`，或在内部用 pack + `expand=True` 的内容 frame 撑开。

### Windows DPI 缩放（DPI Unaware 方案）
**保持 DPI Unaware**，不启用任何 DPI 感知。`SetProcessDpiAwarenessContext(-4)` 和 System DPI Aware 均不可行（Tk 8.6 字体渲染与位图缩放不匹配）。

DPI Unaware 模式下：
- `winfo_fpixels('1i')` 返回 ~96（虚拟化 DPI），`winfo_screenwidth()` 返回虚拟像素
- Windows 后台自动按系统缩放倍数放大 Tk 渲染内容（字体略模糊但布局正确）
- 用 `EnumDisplaySettingsW(None, -1)` 获取物理像素宽度，除以虚拟宽度得到真实 `display_scale`
- 高 DPI（>130%）时乘以 `high_dpi_reduction`（当前 0.6）
- **所有 UI 元素统一使用同一个缩放比例**，分开缩放会导致布局错乱
- 实现位置：`gui_main.py:_get_primary_physical_width()`、`gui_main.py:_calculate_effective_scale()`、`gui_main.py:BossFilterGUI.__init__()`
- macOS 不受影响：`winfo_screenwidth()` 返回物理像素

### macOS Tk 8.6 字体物理像素减半
Tk 8.6 在 Apple Silicon（M1/M2/M3/M4，Anaconda/Homebrew Python）报告 DPI 72；Intel Mac venv 报告 DPI 96（系统 Tk 8.5 报告 144 不受影响）。阈值 `< 80` 区分需补偿环境。

补偿逻辑（`gui_main.py:BossFilterGUI.__init__()`）：
```python
if sys.platform == 'darwin':
    _tk_dpi_raw = self.root.winfo_fpixels('1i')
    self.font_boost = 1.65 if _tk_dpi_raw < 80 else 1.0
else:
    self.font_boost = 1.0
self.font_scale = self.dpi_scale * self.zoom_factor * self.font_boost
```

- `font_scale` 仅用于字体，布局/间距/图标/窗口/rowheight 仍用 `dpi_scale × zoom_factor`
- 实现位置：`gui_main.py:BossFilterGUI.__init__()`、`gui_main.py:setup_styles()`

### 字体常量与 Combobox 规范
- `FONT_FAMILY`/`FONT_FAMILY_SEMIBOLD` 跨平台字体常量（Windows: Microsoft YaHei UI, macOS: PingFang SC, Linux: Helvetica）
- 7 个字体变量：`font_title`(28pt) / `font_section`(16pt) / `font_label`(13pt) / `font_stat`(36pt) / `font_stat_label`(15pt) / `font_log`(11pt) / `font_table`(12pt)
- `font_scale`（含 font_boost）用于字体；`dpi_scale × zoom_factor` 用于布局/间距/图标/rowheight
- Combobox 下拉列表字体：`option_add('*TCombobox*Listbox.font', font, 80)`；所有 Combobox 禁用滚轮：`bind_class('TCombobox', '<MouseWheel>', lambda e: 'break')`

### macOS aqua 主题 ttk 控件灰色背景（2026-05-27）
macOS aqua 主题的 ttk 控件默认背景是 `systemWindowBackgroundColor`（灰色），三层原因叠加导致大面积灰色残留：

1. **`ttk.LabelFrame` 内容区灰色**：`Labelframe.border` 元素硬编码灰色背景，`style.configure` 无效。解决方案：用 `_create_card()` 替代所有 `LabelFrame`
2. **`ttk.Label` 默认背景灰色**：`style.configure('TLabel', background=self.colors['bg_card'])` 解决
3. **`ttk.Combobox`/`TSpinbox`/`TEntry` 输入框灰色**：macOS aqua 忽略 `style.configure` 的 `fieldbackground`，只有 `style.map` 有效：
```python
style.map('TCombobox', fieldbackground=[('readonly', bg_card), ('!disabled', bg_card)])
style.map('TSpinbox', fieldbackground=[('!disabled', bg_card)])
style.map('TEntry', fieldbackground=[('!disabled', bg_card)])
```

架构约定：
- `TFrame` 默认白底（`bg_card`），页面级灰底容器用 `Page.TFrame`（`bg_main`）
- `_create_scroll_container` 的容器 frame 必须加 `style='TFrame'`
- `_create_page_header(parent, title, subtitle=None)` 统一创建页面标题（白底 + 左侧 4px 蓝色竖线）
- 实现位置：`gui_main.py:setup_styles()`、`gui_main.py:_create_card()`、`gui_main.py:_create_page_header()`

### Gitee Release API 限制
1. **PATCH release 必须带 `tag_name` 和 `body`**：只传 `name` 返回 400 `"body is missing"`
2. **releases 列表不返回附件 ID**：删除附件需通过 `GET /releases/{id}/attach_files` 获取
实现位置：`build.py:_gitee_find_or_create_release()`、`build.py:_gitee_delete_asset()`

### Windows ttk.Button foreground 不生效
Windows `vista` 主题的 `ttk.Button` 不尊重 `style.configure` 设置的 `foreground` 颜色，白色文字在默认灰色背景上不可见。需要自定义颜色按钮时改用 `tk.Button`（直接设 `bg`/`fg`/`activebackground`/`activeforeground`），或保持 `ttk.Button` 默认样式只通过图标颜色区分。

### Tk Canvas yscrollcommand 返回字符串
`canvas.cget("yscrollcommand")` 返回 Tcl 命令字符串（如 `"::scrollbar1.set"`），不是 Python 可调用对象。需要包装 `yscrollcommand` 回调时，应遍历 canvas 父容器找到同级 `ttk.Scrollbar`，取其 `.set` 方法作为原始回调。回调参数 `(top, bottom)` 也是字符串，需 `float()` 转换后才能比较。

### Gitee 上传参数处理
`build.py --gitee-upload` 接受版本号参数时，需先移除用户可能输入的 `v` 前缀（如 `v2.9` → `2.9`），否则构建 tag 时会变成 `vv2.9` 导致找不到对应 release。另外，PATCH release 时如果 `release_notes` 为空，不能传空字符串（Gitee 返回 400 `"发行版的描述不能为空"`），应保留 Gitee 原有 body 不变。实现位置：`build.py:main()` 的 `--gitee-upload` 分支、`build.py:_gitee_find_or_create_release()`。
