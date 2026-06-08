# 📋 BOSS 简历筛选器

基于 DrissionPage 的 BOSS 直聘候选人自动筛选工具，支持智能需求解析、智能匹配筛选、自动滚动获取候选人、自动打招呼功能。

> 当前发布版本：v2.10 筛选复盘闭环（版本号 v2.10）

## ✨ 功能特性

### 核心功能
- **智能需求解析**: 正则基础解析招聘需求；已配置 AI 时自动增强基本信息、技能关键词、优先项和必要条件，未配置时保持离线正则解析
- **自动获取候选人**: 从 BOSS 直聘推荐页面自动滚动获取候选人信息，支持批量提取和去重
- **多维度智能筛选**: 经验、学历、年龄、薪资范围、工作地点、必要条件六维硬条件 + 技能关键词四维评分模型，自动打分排序
- **AI 智能评估**: 对通过筛选的候选人进行 LLM 二次评估，辅助招聘决策
- **自动打招呼**: 对符合要求的候选人自动发送消息，支持手动打招呼功能
- **数据统计看板**: 按岗位查看筛选和打招呼数据，支持时间范围过滤
- **Excel 导出**: 自动生成带颜色标识的 Excel 文件（多工作表 + 统计摘要）
- **图形界面 + 命令行**: 图形界面侧边栏导航，可视化配置岗位规则、AI 模型、筛选参数；命令行模式支持自动化运行和批量操作
- **跨平台支持**: 支持 Windows 和 macOS

### v2.10 筛选复盘闭环

**新增功能**

- **筛选结果可解释**：候选人记录新增评分拆解、评分解释和关键词命中证据，详情页和 Excel 导出都能查看分数来源
- **人工反馈闭环**：筛选结果支持标记合适、误推、误杀、放弃和备注，反馈会写入候选人数据、详情页和 Excel 摘要
- **候选人跟进状态**：筛选结果支持更新未沟通、已打招呼、已回复、待约面、已约面等跟进状态，并同步到详情页和 Excel 摘要
- **数据统计复盘指标**：岗位明细新增已反馈、合适率、误推率、已回复、回复率、已约面和约面率，便于判断筛选质量和跟进转化

### v2.9.3 需求解析精度优化

**体验优化**

- **AI 解析更稳定**：网络不稳定或模型响应慢时，会自动重试或回退到本地解析，不再直接报错
- **解析结果更精准**：泛化词（如"人工智能"、"证券行业"、"数据清洗"等）不再被误识别为技能关键词
- **基础条件自动归类**：学历要求、工作年限等基础条件自动归入基本信息，不再混入必要条件
- **优先项权重更合理**：优先项（如"证券经验优先"）的加分权重不再被过度放大
- **弹窗模块边界更清晰**：关于弹窗、版本历史和更新弹窗共用更新日志解析与渲染逻辑，减少重复代码

**问题修复**

- **AI Agent 变体匹配**：修复"智能体"、"大模型 Agent"、"Langchain"等写法无法正确匹配的问题
- **工作地点匹配**：修复 AI 返回的地点格式不统一导致筛选失败的问题
- **Mac 筛选结果按钮位置**：修复筛选结果页"重置日期"按钮位置不协调的问题
- **Mac 更新弹窗按钮不可见**：修复 Mac 上更新提醒弹窗底部按钮被遮挡的问题

### v2.9.1 及更早版本

> 完整版本历史见 [CHANGELOG.md](CHANGELOG.md)

## 🚀 快速开始

### 方式一：图形界面（推荐）

```bash
# 双击启动
gui.bat

# 或命令行启动
python gui_main.py
```

### 方式二：命令行

### 1. 安装依赖

```bash
cd boss-resume-filter
pip install -r requirements.txt
```

### 2. 配置岗位规则

编辑 `job_config.json` 文件，配置各岗位的筛选规则。支持通过 GUI 界面可视化配置，也可直接编辑 JSON 文件：

```jsonc
{
  // 岗位名称（作为 key，命令行 --job 参数使用）
  "中高级AI工程师": {
    "min_exp": 4,                    // 最低工作年限（年）
    "edu": "本科",                    // 最低学历（博士/硕士/本科/大专）
    "max_age": 35,                   // 最大年龄（岁）
    "work_location": "南京",          // 工作地点（支持多城市，用 / 分隔）
    "salary_min": 12,                // 岗位薪资下限（K，候选人期望最低薪资低于此值会被过滤）
    "salary_max": 15,                // 岗位薪资上限（K）
    "keywords": [                    // 技能关键词（用于评分打分）
      {"name": "Spring Cloud", "weight": 2},  // weight 1=普通，2=2倍权重，3=3倍权重
      {"name": "SpringBoot", "weight": 1},
      {"name": "Spring AI", "weight": 2},
      {"name": "MySQL", "weight": 2},
      {"name": "Redis", "weight": 1},
      {"name": "Java", "weight": 1},
      {"name": "Python", "weight": 1},
      {"name": "LLM", "weight": 2},
      {"name": "智能体", "weight": 2},
      {"name": "Langchain", "weight": 2}
    ],
    "required_conditions": [         // 必要条件（不满足则直接淘汰）
      "统招本科"                      // 支持简单匹配、OR、AND 三种模式
    ],
    "greet_template": null,          // 自定义打招呼话术（null 使用默认话术）
    "original_requirement": "..."    // 原始招聘需求文本（GUI 自动填充）
  }
}
```

### 3. 运行筛选

```bash
# 自动打招呼模式（推荐）
python bossmaster.py --greet

# 指定岗位
python bossmaster.py --job "高级 Java 工程师" --greet

# 补打招呼（给已匹配但未打招呼的候选人）
python bossmaster.py --re-greet

# 清空历史后重新跑
python bossmaster.py --clear --greet

# 清空历史但保留已打招呼的候选人
python bossmaster.py --clear --keep-greeted --greet

# 指定滚动轮次（减少滚动次数）
python bossmaster.py --greet --rounds 20

# 输出详细评分信息（查看技能匹配详情）
python bossmaster.py --greet --verbose

# AI 辅助评估（对通过筛选的候选人进行 LLM 二次评分）
python bossmaster.py --greet --ai-eval
```

### 4. 查看结果

程序运行后会生成：
- `candidates_all.json` - 全量候选人数据（累积、去重）
- `candidates_all.xlsx` - Excel 导出文件（多工作表 + 统计摘要）

### 5. 中断恢复

运行中按 `Ctrl+C` 中断时：
- 自动保存当前进度
- 下次运行时自动跳过已打招呼的候选人
- 不会重复发送消息

## 🧪 测试

稳定单元回归不依赖浏览器、网络、人工登录或真实 `job_config.json`：

```bash
python tests/run_unit_tests.py
python tests/test_import.py
```

需要 Chrome、BOSS 页面、人工登录或真实网络/API 的脚本放在 `tests/manual/`；历史调试脚本放在 `tests/archive/`，默认不作为回归测试。

## 📁 项目结构

```
boss-resume-filter/
├── bossmaster.py         # BOSS 直聘自动筛选主程序（核心）
├── filtering.py          # 纯筛选规则模块（评分、硬条件、薪资/经验/城市解析）
├── llm_eval.py           # LLM 辅助评估模块（prompt 构建、API 调用、批量评估）
├── job_ai_parser.py      # 岗位需求 AI 增强解析模块（基于正则初稿补充优化）
├── storage.py            # 候选人数据持久化模块（去重、原子写入、备份恢复）
├── constants.py          # 共享常量（评分模型参数、阈值、学历档位、滚动参数、城市列表）
├── paths.py              # 路径工具（get_base_dir、ensure_config_files、路径常量）
├── gui_main.py            # 图形界面主程序（v2.9.3）
├── gui_dialogs.py        # 独立对话框模块（更新日志、关于弹窗、CHANGELOG 渲染）
├── changelog_parser.py   # CHANGELOG 解析模块（版本段落提取、标题解析）
├── updater.py            # 自动更新模块（Gitee/GitHub 双源检查、下载替换、完整性校验、启动时自动检查）
├── icons.py              # 图标绘制模块（Pillow 矢量图标，31个图标函数 + IconCache）
├── doc_parser.py         # 文档解析器（简历解析）
├── security.py           # API Key 安全存储模块（keyring 加密，按 provider+base_url 组合存储）
├── migrate_keys.py       # API Key 迁移工具（明文→加密）
├── build.py              # PyInstaller 打包脚本（支持 --release 一键发布）
├── latest.json           # 版本清单（Gitee 更新源，build.py --release 自动维护）
├── gui.bat               # GUI 启动脚本
├── job_config.json       # 岗位筛选规则配置
├── api_config.json       # AI 模型配置（不含明文 Key）
├── selectors.json        # 页面选择器配置（CSS/XPath/关键词，DOM 变化时修改）
├── candidates_all.json   # 累积的候选人数据（累积、去重）
├── candidates_all.xlsx   # Excel 导出文件（多工作表 + 统计摘要）
├── CLAUDE.md             # AI 协作规范（Claude / Codex 通用）
├── AGENTS.md             # Codex 专用项目规范（内容与 CLAUDE.md 一致）
├── README.md             # 项目主文档
├── CHANGELOG.md          # 更新日志（嵌入 EXE，运行时从 _MEIPASS 读取）
├── GUI 使用说明.md        # 图形界面详细说明
├── README_文件管理.md      # 数据文件管理说明
├── DEPLOYMENT.md         # 部署说明
├── PACKAGING.md          # 打包指南
├── requirements.txt      # Python 依赖
├── install.bat           # 安装脚本
├── tests/                # 测试脚本目录
├── scripts/              # 辅助脚本目录
│   └── watch_progress.py # 发布进度监控脚本
├── pyinstaller-hooks/    # PyInstaller 自定义 hook（控制模块收集范围，减小产物体积）
└── .build_progress.json  # 发布进度文件（build.py 实时更新，供外部监控）
```

## 📊 匹配规则

### 硬条件（一票否决）
| 条件 | 说明 |
|------|------|
| 学历 | ≥ 岗位要求的最低学历；要求本科时自动排除非统招（自考/成教/专升本/电大等） |
| 工作经验 | ≥ 岗位要求的最低年限 |
| 工作地点 | 候选人城市在配置地点范围内（支持多地点） |
| 薪资范围 | 候选人期望最低薪资 < 岗位薪资上限 + 1K |
| 必要条件 | 简历文本匹配配置的必要关键词（支持简单匹配/OR/AND 三种模式） |
| 技术关键词 | 岗位 keywords 的匹配度（硬约束关键词不能为空） |

### 软条件（加权打分）
采用四维评分模型：基础25 + 技能(0~50) + 经验超额(0~15) + 学历档次(0~10)，区间 25-100 分。

### 推荐指数
| 等级 | 分数 | 操作 |
|------|------|------|
| 强烈推荐 | 75-100 | 自动打招呼（可配置为仅此等级） |
| 推荐 | 65-74 | 自动打招呼（默认） |
| 待定 | 55-64 | 不自动打招呼 |

> 开启 AI 辅助评估后，LLM 会对候选人做二次评分（±10 分调整），调整后的分数重算推荐等级，直接影响打招呼决策。

### AI 辅助评估（大模型二次评估）
对通过筛选的候选人（≥55 分）调用 LLM 进行二次评估，辅助招聘决策。

**启用方式：**
- GUI：运行页勾选「启用 AI 辅助评估」开关
- CLI：添加 `--ai-eval` 参数，如 `python bossmaster.py --greet --ai-eval`

**评估流程：**
1. 筛选阶段：对每个候选人进行规则评分（四维评分模型）
2. AI 评估阶段：对通过筛选的候选人（≥55 分）调用 LLM 二次评估
3. 分数调整：LLM 返回调整值（**-10 到 +10 分**），叠加到规则评分上，调整后总分限制在 0-100 分
4. 等级重算：调整后的分数重新计算推荐等级（≥75 强烈推荐, ≥65 推荐, ≥55 待定）
5. 打招呼决策：基于调整后的分数决定是否自动打招呼

**评估结果展示：**
- GUI 结果表：新增「AI评估」列，显示调整值（如 +7、-3）
- 候选人详情：显示 AI 评估理由、调整值、原始规则分、使用的模型
- Excel 导出：包含 AI 评估相关字段

**配置说明：**
- 使用 `api_config.json` 中的 AI 模型配置（复用筛选功能的配置，无需额外配置）
- 每次最多评估 50 人，超出部分跳过
- 支持 stop_event 中断，429 限流自动指数退避

### 打招呼逻辑
- 按钮位置：候选人卡片的 `operate-side` 区域
- 按钮文本："继续沟通"（已匹配）、"立即沟通"（新候选人）
- 自动重试：失败时自动重试一次
- **中断恢复**：中断时兜底保存，中断后不重复
- **去重机制**：基于 `(geek_id, job_name)` 复合键去重，保留分数高的记录

## ⚠️ 注意事项

1. **浏览器要求**: 需要安装 Chrome 浏览器（程序可自动启动 Chrome 并导航到推荐页面）
2. **手动导航**: 如果浏览器未自动导航到推荐页面，请手动导航到 BOSS 直聘推荐页面
3. **网络稳定**: 保持网络连接稳定，避免中断
4. **数据备份**: 程序保存时会生成 `candidates_all.json.bak`，仍建议定期备份 `candidates_all.json`
5. **中文数字支持**: 自动识别"三年"、"十二年"等中文数字格式

## 🔧 故障排查

| 问题 | 可能原因 | 解决方案 |
|------|----------|----------|
| 未找到沟通按钮 | 按钮文本变化 | 检查按钮是否为"继续沟通"，更新代码 |
| 元素没有位置及大小 | DOM 更新导致 | 代码已处理，自动重试 |
| 候选人提取失败 | 页面未加载 | 等待页面完全加载后再运行 |
| Excel 导出失败 | 缺少依赖 | `pip install pandas openpyxl` |
| 重复打招呼 | 中断后未恢复状态 | 检查 `candidates_all.json` 中是否有 `greeting_in_progress` 标记，删除后重新运行 |
| 测试连接失败 | 网络波动或 API Key 无效 | 重试 1-2 次；检查 API Key 是否正确；查看日志详情 |
| 模型列表为空 | API 不支持 models 接口 | 手动输入模型名称；或联系服务商确认 |
| 切换模型后 API Key 为空 | 配置未正确保存 | 重新保存模型配置；检查 api_config.json 权限 |

## 📝 License

MIT
