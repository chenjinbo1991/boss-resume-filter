# BOSS 简历筛选器 - 项目规范

## 项目结构
```
boss-resume-filter/
├── bossmaster.py         # BOSS 直聘自动筛选主程序（核心）
├── gui_main.py           # 图形界面主程序（v2.0）
├── doc_parser.py         # 文档解析器（简历解析）
├── main.py               # 命令行入口
├── job_config.json       # 岗位筛选规则配置
├── api_config.json       # AI 模型配置（多服务商支持）
├── candidates_all.json   # 累积的候选人数据
├── candidates_all.xlsx   # Excel 导出文件
├── gui.bat               # GUI 启动脚本
├── install.bat           # 安装脚本
├── requirements.txt      # Python 依赖
├── templates/            # 模板文件
│   ├── 需求文档示例.md
│   └── 简化需求模板.md
├── CLAUDE.md             # 本文件
├── README.md             # 项目主文档
├── GUI 使用说明.md        # 图形界面详细说明
├── tests/                # 测试脚本目录
└── scripts/              # 辅助脚本目录
```

## 运行命令
### 命令行模式
- 安装依赖：`pip install -r requirements.txt`
- 自动打招呼：`python bossmaster.py --greet`
- 指定岗位：`python bossmaster.py --job "高级 Java 工程师" --greet`
- 补打招呼：`python bossmaster.py --re-greet`
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
- API Key 支持明文/密文切换显示

## 核心逻辑
### 打招呼机制
- 打招呼按钮位于 `operate-side` 区域（与 `card-inner` 并列的兄弟元素）
- 按钮文本："继续沟通"（已匹配）、"立即沟通"（新候选人）
- 每成功一个招呼立即保存，支持中断恢复
- 过滤规则：只过滤「当前岗位已匹配且打过招呼」的候选人

### 去重机制
- 基于 `geek_id` 去重，保留分数高的记录
- 合并打招呼状态（greet_sent）
- save_candidates_all 使用 O(n) 算法（字典替代列表查找）

### 批量保存优化
- 成功打招呼：立即保存
- 失败打招呼：攒够 5 个再写文件（减少 IO）

## AI 模型配置（v2.0 新增）
### 支持的服务商
qwen、deepseek、kimi、zhipu、minimax、xiaomi、stepfun、openai、anthropic、custom

### 配置管理
- api_config.json 存储多服务商配置
- 支持双击切换已保存的模型
- 支持根据 API Key 动态获取模型列表
- 测试连接：高可用设计（全新 Session + 并行双策略 + 宽松超时）
