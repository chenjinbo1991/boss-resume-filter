# BOSS 简历筛选器 - 项目规范

## 项目结构
```
boss-resume-filter/
├── bossmaster.py         # BOSS 直聘自动筛选主程序（核心）
├── gui_main.py           # 图形界面主程序（v3.0）
├── doc_parser.py         # 文档解析器（简历解析）
├── main.py               # 命令行入口
├── security.py           # API Key 安全存储模块（keyring 加密）
├── migrate_keys.py       # API Key 迁移工具（明文→加密）
├── build.py              # PyInstaller 打包脚本
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
- 每成功一个招呼立即保存，支持中断恢复
- 过滤规则：只过滤「当前岗位已匹配且打过招呼」的候选人
- 打招呼等级：`--greet-level strong`（仅强烈推荐 ≥75）或 `normal`（默认，强烈推荐+推荐 ≥60）
- GUI 中「打招呼等级」下拉框对初次扫描和补打招呼均生效

### 去重机制
- 基于 `geek_id` 去重，保留分数高的记录
- 合并打招呼状态（greet_sent）
- save_candidates_all 使用 O(n) 算法（字典替代列表查找）

### 批量保存优化
- 成功打招呼：立即保存
- 失败打招呼：攒够 5 个再写文件（减少 IO）

### 滚动提前终止
- 文本提示检测（策略1）：每轮滚动前用 DrissionPage `@@text():关键字` 模糊匹配"到底"/"没有更多"等提示文字，命中即停
- 连续空轮次兜底（策略2）：连续 5 轮无新候选人自动终止，不依赖特定文案
- 实现位置：`extract_candidates_by_comprehensive_analysis()` 函数

### 评分体系（v2.5 重构）
- 四维评分模型：`基础30 + 技能(0~35) + 经验超额(0~20) + 学历档次(0~15)`
- 英文关键词用 `\b` 单词边界匹配，避免子串误匹配（如 AI 不再匹配 email）
- 经验超额加分：超出 min_exp 部分每年 +4 分，20 分封顶
- 学历档次加分：博士+15, 985/211硕士+13, 硕士+10, 985/211本科+8, 统招本科+5
- 找不到工作经验不再淘汰（警告后放行），但也不加分
- 推荐等级阈值：>=75 强烈推荐, >=60 推荐, >=45 待定
- 实现位置：`filter_candidate()`, `_keyword_found()`, `_calc_edu_bonus()`

### 需求解析规则（doc_parser.py）
- 从需求文档中提取关键词，分为硬约束（tech_condition_keywords）和软技能（soft_skills）两类
- 已排除泛化关键词：数据库（零区分信号，几乎所有后端简历都有）
- 保留了精准词：向量数据库（AI/RAG 相关）
- 英文关键词按长度降序匹配，优先匹配长词（如 Spring Cloud 优先于 Spring）

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
