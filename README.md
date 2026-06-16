# 📋 BOSS 简历筛选器

基于 DrissionPage 的 BOSS 直聘候选人筛选工具，支持招聘需求解析、候选人自动获取、智能筛选、AI 辅助评估、自动打招呼、人工反馈、跟进状态、候选人黑名单和数据复盘。

> 当前发布版本：v2.11.3 安全扫描模式与页面跑偏检测（版本号 v2.11.3）

## ✨ 功能特性

### 核心功能
- **智能需求解析**: 正则基础解析招聘需求；已配置 AI 时自动增强基本信息、技能关键词、优先项和必要条件，未配置时保持离线正则解析
- **自动获取候选人**: 从 BOSS 直聘推荐页面自动滚动获取候选人信息，支持批量提取和去重
- **多维度智能筛选**: 经验、学历、年龄、薪资范围、工作地点、必要条件等硬条件 + 技能关键词评分模型，自动打分排序
- **AI 智能评估**: 对通过筛选的候选人进行 LLM 二次评估，也可导入完整简历做二次复核，辅助招聘决策
- **筛选结果可解释**: 记录评分拆解、评分解释和关键词命中证据，候选人详情和 Excel 导出都能查看分数来源
- **自动打招呼**: 对符合要求的候选人自动发送消息，支持手动打招呼功能
- **人工反馈与跟进闭环**: 支持标记合适、误推、误杀、放弃，维护候选人跟进状态和备注
- **候选人黑名单**: 面试后确认不合适的候选人可加入黑名单，后续扫描、统计和 Excel 导出自动屏蔽
- **数据统计看板**: 按岗位查看筛选质量、打招呼效果、反馈结果和跟进转化，支持时间范围过滤
- **Excel 导出**: 自动生成带颜色标识的 Excel 文件（多工作表 + 统计摘要）
- **图形界面 + 命令行**: 图形界面侧边栏导航，可视化配置岗位规则、AI 模型、筛选参数；命令行模式支持自动化运行和批量操作
- **跨平台支持**: 支持 Windows 和 macOS

### v2.11.3 安全扫描模式与页面跑偏检测

**新增功能**

- **安全扫描模式开关**：图形界面运行控制页新增”安全扫描”复选框，默认开启；开启后跳过 API 直调，使用 listener + refresh 一次捕获数据，稳定性优先
- **候选人读取上限**：关闭安全扫描时显示读取上限设置，可配置单次 API 直调最多读取人数（默认 80，范围 20-500），达到上限自动停止翻页
- **页面跑偏检测**：扫描和打招呼前自动检查浏览器是否仍在推荐牛人页面，页面被意外切换时停止本轮运行并提醒切回

**体验优化**

- **提取链路默认更稳**：GUI 默认跳过 API 直调，使用 listener + refresh 一次捕获数据，失败后回退 DOM 滚动提取；关闭安全扫描后走 API 直调优先，支持 `--dom-only` 仅 DOM 提取和 `--listener-first` 跳过 API 直调（extraction_mode）；API 遇到 403/412/429 等风控状态立即停止
- **API 分页和打招呼节奏放缓**：API 分页默认约 5-8 秒随机间隔；自动打招呼按批次暂停，整体节奏更接近人工操作
- **安全扫描联动参数**：开启安全扫描时滚动默认 100 轮（推荐 50-200）；关闭后切到 API 模式，默认 30 轮（推荐 30-50），并显示读取上限（max_rounds、max_candidates、spinbox）
- **更新日志远端修正**：更新日志弹窗现在从远端 Release Notes 获取当前版本说明，本地内容先显示、后台自动更新；读取失败时静默保留本地内容

### v2.11.2 反风控增强

**新增功能**

- **安全验证弹窗处理**：打招呼时自动检测验证码/安全验证弹窗，提示用户手动完成验证；验证完成后停止本轮自动打招呼，避免连续动作继续触发风控
- **自动打招呼上限提醒**：每轮自动打招呼最多 20 人，达到上限时弹窗提示已处理人数、剩余人数，以及下次扫描会自动跳过已打招呼候选人继续处理
- **验证码诊断包**：遇到验证码时自动保存诊断 JSON，并尽量保存页面截图，方便后续根据用户现场分析弹窗形态和选择器变化

**体验优化**

- **候选人提取链路更保守**：优先使用 API 直调分页；只有 API 直调失败后才启动 API listener 并刷新页面；仍失败时再回退 DOM 提取，减少不必要的刷新和监听动作
- **API 风控状态立即停止**：接口返回 403、412、429 等明确风控状态时立即停止本轮扫描，不再继续刷新页面或 DOM 兜底，避免扩大风险
- **API 分页和打招呼节奏放缓**：API 分页增加随机间隔；自动打招呼按批次暂停，整体节奏更接近人工操作
- **打招呼顺序更稳定**：自动打招呼按页面扫描顺序点击，不再按评分重排点击，降低虚拟列表大幅跳转带来的失败和风控风险
- **验证码识别范围扩展**：补充极验、captcha、verify 等常见安全验证选择器，提高弹窗识别覆盖率
- **更新日志远端修正**：更新日志弹窗先显示本地内置内容，再后台读取当前版本远端 Release Notes；读取成功后自动替换当前版本说明，失败时静默保留本地内容

**问题修复**

- **AI 评估状态显示修复**：运行控制页首次打开时 AI 评估状态显示不准确，现在正确反映 API Key 配置状态

### v2.11.1 界面启动与稳定性补丁

**新增功能**

- **简历导入格式扩展**：简历二次评估新增 TXT、Markdown、RTF、HTML 格式支持，纯文本和 HTML 无需额外依赖，RTF 需安装 striprtf（仅 22KB）
- **统计时间筛选扩展**：数据统计看板新增”本月”时间范围，方便按月查看筛选效果

**体验优化**

- **启动和切页更顺畅**：启动后只创建首页，运行控制、筛选结果、统计和模型配置页按需创建并错峰预热，减少首次进入重页面的卡顿
- **模型配置页减少等待**：启动和首次打开模型配置页时不再同步等待系统钥匙串，API Key 改为后台读取后回填

**问题修复**

- **退出保存更稳**：异常退出、中断或停止时自动保存进度并导出 Excel；停止打招呼时立即响应，不再继续处理剩余候选人
- **筛选条件修复**：修正”面议”出现在非薪资字段时薪资判断被跳过的问题；岗位未设年龄上限时不再默认限制 35 岁
- **技术条件匹配修复**：技术条件改为精确匹配，避免短关键词（如”Go”、”C”）误命中无关文本
- **数据恢复更稳**：候选人数据损坏时优先从备份恢复；去重合并保留最新的反馈和跟进记录

### v2.10 及更早版本

> 完整版本历史见 [CHANGELOG.md](CHANGELOG.md)

## 🚀 快速开始

### 方式一：下载安装包（普通用户推荐）

#### Windows

1. 从 [GitHub Release](https://github.com/yaoyouzhong/boss-resume-filter/releases/latest) 或 [Gitee Release](https://gitee.com/yaoyouzhong/boss-resume-filter/releases) 下载 `BOSS_ResumeFilter.exe`
2. 双击 `BOSS_ResumeFilter.exe` 启动程序
3. 首次使用时，按界面引导完成浏览器连接、岗位配置和 API 配置；运行结果可在「筛选结果」和「数据统计」中查看

#### macOS

1. 从 [GitHub Release](https://github.com/yaoyouzhong/boss-resume-filter/releases/latest) 或 [Gitee Release](https://gitee.com/yaoyouzhong/boss-resume-filter/releases) 下载 `BOSS_ResumeFilter.dmg`
2. 双击打开 DMG，将 `BOSS_ResumeFilter.app` 拖到 Applications 文件夹
3. 首次打开时，右键点击 `BOSS_ResumeFilter.app`，选择「打开」，在安全提示中再次点击「打开」
4. 后续可直接双击启动

> 程序启动后会自动检查更新。新电脑首次使用需要在「岗位配置」→「API 配置」中重新输入 API Key。
> 普通用户不需要安装 Python；只有源码运行和命令行模式才需要安装依赖。

### 方式二：源码运行图形界面（开发/调试）

适合需要改代码、排查问题或临时运行源码版本的场景：

```bash
cd boss-resume-filter
pip install -r requirements.txt

# Windows 可双击 gui.bat，或直接运行：
python gui_main.py
```

### 方式三：命令行运行（高级用法）

命令行模式适合自动化、批量任务或调试筛选逻辑。普通用户优先使用 EXE/App 图形界面。

#### 1. 安装依赖

```bash
cd boss-resume-filter
pip install -r requirements.txt
```

#### 2. 配置岗位规则

推荐先在图形界面中配置岗位规则。需要批量维护时，也可以直接编辑 `job_config.json`：

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

#### 3. 运行筛选

```bash
# 自动打招呼模式
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

# 旧式深度扫描等价写法（不走 API 直调，滚动 100 轮）
python bossmaster.py --greet --listener-first --rounds 100

# 指定单次 API 直调最多读取候选人数
python bossmaster.py --greet --max-candidates 80

# 输出详细评分信息（查看技能匹配详情）
python bossmaster.py --greet --verbose

# AI 辅助评估（对通过筛选的候选人进行 LLM 二次评分）
python bossmaster.py --greet --ai-eval
```

#### 4. 查看结果

程序运行后会生成：
- `candidates_all.json` - 全量候选人数据（累积、去重）
- `candidates_all.xlsx` - Excel 导出文件（多工作表 + 统计摘要）

#### 5. 中断恢复

运行中按 `Ctrl+C` 中断时：
- 自动保存当前进度
- 下次运行时自动跳过已打招呼的候选人
- 已加入黑名单的候选人会按 `geek_id` 跨岗位屏蔽，不再进入评分、AI 评估、自动打招呼、统计和 Excel 导出
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
├── gui_main.py            # 图形界面主程序（v2.11.3）
├── gui_dialogs.py        # 独立对话框模块（更新日志、关于弹窗、CHANGELOG 渲染）
├── changelog_parser.py   # CHANGELOG 解析模块（版本段落提取、标题解析）
├── updater.py            # 自动更新模块（Gitee/GitHub 双源检查、下载替换、完整性校验、启动时自动检查）
├── icons.py              # 图标绘制模块（Pillow 矢量图标，33个图标函数 + IconCache）
├── doc_parser.py         # 招聘需求文档解析器（JD → 必要条件 + 职位要求）
├── security.py           # API Key 安全存储模块（keyring 加密，按 provider+base_url 组合存储）
├── migrate_keys.py       # API Key 迁移工具（明文→加密）
├── build.py              # PyInstaller 打包脚本（支持 --release 一键发布）
├── latest.json           # 版本清单（Gitee 更新源，build.py --release 自动维护）
├── gui.bat               # GUI 启动脚本
├── job_config.json       # 岗位筛选规则配置
├── api_config.json       # AI 模型配置（不含明文 Key）
├── selectors.json        # 页面选择器配置（CSS/XPath/关键词，DOM 变化时修改）
├── ui_config.json        # UI 尺寸与缩放配置
├── candidates_all.json   # 累积的候选人数据（累积、去重）
├── candidates_all.xlsx   # Excel 导出文件（多工作表 + 统计摘要）
├── CLAUDE.md             # AI 协作规范（Claude / Codex 通用）
├── AGENTS.md             # Codex 专用项目规范（内容与 CLAUDE.md 一致）
├── README.md             # 项目主文档
├── CHANGELOG.md          # 更新日志（嵌入 EXE，运行时从 _MEIPASS 读取）
├── docs/                 # 用户操作说明、PDF、PPTX 和配套素材
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
| 学历 | ≥ 岗位要求的最低学历；要求本科时疑似非统招（自考/成教/专升本/电大等）标记风险，需人工确认后再沟通 |
| 工作经验 | ≥ 岗位要求的最低年限 |
| 年龄 | 候选人年龄不超过岗位配置的上限；未配置或无法识别时不启用年龄过滤 |
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
| 推荐 | 65-74 | 启用“强烈推荐 + 推荐”时自动打招呼 |
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
- 对通过筛选的候选人按规则评分降序评估，默认不再限制 50 人
- 默认并发 5 路；候选人较多时会增加模型调用量和运行时间
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
| 未找到沟通按钮 | 页面未进入推荐候选人列表，或 BOSS 页面按钮文本变化 | 确认浏览器在对应岗位的推荐页面后重试；若页面结构变化，需更新选择器或代码 |
| 元素没有位置及大小 | DOM 更新导致 | 代码已处理，自动重试 |
| 候选人提取失败 | 页面未加载 | 等待页面完全加载后再运行 |
| Excel 导出失败 | 源码运行时缺少依赖，或安装包文件损坏 | 源码运行先执行 `pip install -r requirements.txt`；安装包异常时重新下载 |
| 重复打招呼 | 历史数据未正确保存或候选人状态异常 | 先确认 `candidates_all.json` 是否正常保存；必要时在图形界面中按岗位清理数据后重新运行 |
| 测试连接失败 | 网络波动或 API Key 无效 | 重试 1-2 次；检查 API Key 是否正确；查看日志详情 |
| 模型列表为空 | API 不支持 models 接口 | 手动输入模型名称；或联系服务商确认 |
| 切换模型后 API Key 为空 | 配置未正确保存 | 重新保存模型配置；检查 api_config.json 权限 |

## 📝 License

MIT
