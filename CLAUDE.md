# BOSS 简历筛选器 - 项目规范

## 项目结构
```
boss-resume-filter/
├── bossmaster.py         # BOSS 直聘自动筛选主程序（核心）
├── gui_main.py           # 图形界面主程序（v2.4）
├── icons.py              # 图标绘制模块（Pillow 矢量图标，21个图标函数 + IconCache）
├── doc_parser.py         # 文档解析器（简历解析）
├── security.py           # API Key 安全存储模块（keyring 加密）
├── migrate_keys.py       # API Key 迁移工具（明文→加密）
├── build.py              # PyInstaller 打包脚本（支持 --release 一键发布）
├── job_config.json       # 岗位筛选规则配置
├── api_config.json       # AI 模型配置（不含明文 Key）
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
- 输出详细评分：`python bossmaster.py --greet --verbose`

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
- `python build.py`：自动使用 pack_venv 打包为单文件 EXE（~47MB），打包前自动验证依赖完整性
- `python build.py --release`：打包 → 提交 → 打 tag → 推送确认 → GitHub Release 上传（一键发布）
- `python build.py --release --version 2.5`：自动更新 `__version__` + 一键发布
- `__version__` 在 `gui_main.py` 中定义，是唯一版本号来源；`build.py` 通过 AST 解析提取并核对
- dist 目录输出：`BOSS_ResumeFilter.exe` + `README.md` + `job_config.json`
- job_config.json 和 api_config.json 内嵌到 EXE 中，dist 中额外放置 job_config.json 供用户编辑
- 打包/发布前 `_preflight_checks()` 会验证依赖、敏感文件跟踪、`api_config.json` 明文 Key、源码编译、稳定单元回归和导入烟测
- Release 模式不再 `git add -A`；只允许自动提交 `--version` 引起的 `gui_main.py` 版本号变化，其他变更必须先手工提交
- 推送前 `input()` 确认 [y/N]，不确认则保留本地提交和 tag；tag 冲突时自动 `--force`（master 除外）

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
- 沟通上限检测：`_detect_limit_popup()` 单次 JS 调用检测 16 个限制关键词（"今日沟通次数已用完"等），同时检查 page 和 iframe。检测到上限后停止后续打招呼并提示用户
- 页面导航等待时间统一为 3 秒
- 多岗位间切换：GUI 模式弹出确认对话框，用户确认后才继续（不再使用倒计时）；CLI 模式等待 Enter 确认

### 停止机制（v2.2）
- StopRequested 异常 + threading.Event 信号穿透所有关键循环（滚动轮次/筛选/打招呼）
- GUI「停止」按钮设置 stop_event，工作线程在下次循环检查点立即停止
- 停止时自动保存当前进度并导出 Excel

### 浏览器自动检测（v2.2）
- 进入运行页自动每 2 秒轮询 Chrome 调试端口（127.0.0.1:9222）
- 端口检测先于 ChromiumPage() 调用，端口不通时区分场景：定时轮询跳过（silent），手动点击按钮则自动启动 Chrome
- Chrome 启动失败时分类处理：FileNotFoundError → 提示安装 Chrome；其他 chrome 相关异常 → 提示检查安装
- 离开运行页自动停止轮询

### 反爬对抗（v2.4 健壮性）

- **随机延迟抖动**：`_human_delay(center, spread)` 辅助函数，所有 `time.sleep` 调用带随机抖动（不同场景不同 spread），降低行为指纹识别风险。倒计时显示保持精确 1s
- **安全验证阻断**：`_detect_captcha()` 单次 JS 调用检测 11 个验证码关键词（"请完成安全验证"/"滑块验证"/"拖拽拼图"等），同时检查 7 个常见验证码容器 CSS 选择器。在滚动扫描每轮开始、打招呼点击后、打招呼循环失败时三处调用，命中即停止自动化并提示人工处理
- 实现位置：`bossmaster.py:_human_delay()`、`bossmaster.py:_detect_captcha()`

### 去重机制
- 基于 `(geek_id, job_name)` 复合键去重，保留分数高的记录
- 合并打招呼状态（greet_sent）
- save_candidates_all 使用 O(n) 算法（字典替代列表查找）

### 保存策略
- 正常流程：岗位处理完毕时统一保存（减少 IO）
- 异常中断：KeyboardInterrupt / StopRequested 时立即兜底保存
- 原子性写入：先写 `candidates_all.json.tmp`，成功后再 `os.replace()` 覆盖，防止中途崩溃导致数据文件损坏

### 滚动提前终止
- 文本提示检测（策略1）：每轮滚动**后**用 DrissionPage `@text():关键字` 模糊匹配"到底"/"没有更多"等提示文字，命中即停。检测移到滚动之后执行，避免误匹配页面常驻 footer 文本
- 连续空轮次兜底（策略2）：连续 10 轮无新候选人自动终止，不依赖特定文案。同时滚动 window 和可能的滚动容器元素（`.candidate-list` 等），单次滚动 800px
- 实现位置：`extract_candidates_by_comprehensive_analysis()` 函数

### 评分体系（v2.1 重构）
- 四维评分模型：`基础30 + 技能(0~35) + 经验超额(0~20) + 学历档次(0~15)`
- 英文关键词用 `\b` 单词边界匹配，避免子串误匹配（如 AI 不再匹配 email）
- 经验超额加分：超出 min_exp 部分每年 +4 分，20 分封顶
- 学历档次加分：博士+15, 985/211硕士+13, 硕士+10, 985/211本科+8, 统招本科+5
- 找不到工作经验不再淘汰（警告后放行），但也不加分
- 推荐等级阈值：>=75 强烈推荐, >=65 推荐, >=55 待定
- 实现位置：`filter_candidate()`, `_keyword_found()`, `_calc_edu_bonus()`
- 淘汰原因合并：学历不符/经验不足/地点不符/薪资不匹配/评分不足 按大类合并，括号内动态显示实际招聘要求
- 淘汰原因排序：学历不符/不足 → 经验不足 → 地点不符 → 薪资不匹配 → 评分不足(按分数段) → 其他，同类内按数量降序
- 硬条件检查顺序（v2.4）：学历 → 经验 → 工作地点 → 薪资范围 → 必要条件 → 技术关键词

### 必要条件（v2.4 UI 重构）
- GUI 使用下拉框选择条件类型 + 逗号分隔关键词，无需手写 JSON
- 三种模式：简单匹配（子串搜索）、OR（满足任一，大小写不敏感）、AND（全部满足）
- 全角逗号（，）自动归一化为半角逗号分隔
- 底层 `check_required_condition()` 支持三种格式：字符串、`{"type":"or","items":[...]}`、`{"type":"and","items":[...]}`
- 实现位置：`bossmaster.py:check_required_condition()`、`gui_main.py:add_required_condition()`

### 薪资输入验证（v2.4）
- `StringVar.trace_add('write', callback)` 实时检测：非数字字符红色高亮，空值/合法数字恢复默认色
- 保存时 `int()` 二次解析，非法值弹窗警告并阻止保存

### 需求解析规则（doc_parser.py）
- 从需求文档中提取关键词，分为硬约束（tech_condition_keywords）和软技能（soft_skills）两类
- 已排除泛化关键词：数据库（零区分信号，几乎所有后端简历都有）
- 保留了精准词：向量数据库（AI/RAG 相关）
- 英文关键词按长度降序匹配，优先匹配长词（如 Spring Cloud 优先于 Spring）
- 工作地点提取：`_extract_work_location()` → `_resolve_city()` "XX市"→"XX" 归一化，支持多地点
- 薪资范围提取：`_extract_salary_range()` 匹配"薪资范围：12k-15k"、"月薪：15K-25K"，返回(min_k, max_k)

### 薪资范围筛选（v2.4 新增）
- `doc_parser.py`：`_extract_salary_range()` 匹配"薪资范围：12k-15k"等模式
- `bossmaster.py`：`_parse_candidate_salary_range()` 解析候选人 summary 第一行薪资
- `filter_candidate()` 硬性条件检查 #2.6：候选人期望最低薪资 >= 岗位薪资上限 + 2K → 过滤
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
