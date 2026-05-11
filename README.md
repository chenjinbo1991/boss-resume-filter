# 📋 BOSS 简历筛选器

基于 DrissionPage 的 BOSS 直聘候选人自动筛选工具，支持自动滚动获取候选人、智能匹配筛选、自动打招呼功能。

## ✨ 功能特性

### 核心功能
- **自动获取候选人**: 从 BOSS 直聘推荐页面 (`/web/chat/recommend`) 自动滚动获取候选人信息
- **智能匹配筛选**: 根据岗位配置 (经验/学历/技能关键词) 自动评分筛选
- **自动打招呼**: 对符合要求的候选人自动发送消息
- **中断恢复**: 支持 Ctrl+C 中断，已打招呼的候选人状态自动保存，下次运行不重复
- **即时保存**: 每处理一个候选人立即保存，数据不丢失
- **Excel 导出**: 自动生成带颜色标识的 Excel 文件（多工作表 + 统计摘要）
- **图形界面**: 提供友好的 GUI 界面，支持可视化配置和操作（推荐新手使用）

### v3.0 新增功能
- **多 AI 服务商支持**: qwen、deepseek、kimi、zhipu、minimax、xiaomi、stepfun、openai、anthropic
- **API Key 加密存储**: 使用系统钥匙串（Windows DPAPI）加密，配置文件中不含明文 Key
- **模型列表动态获取**: 根据 API Key 自动获取可用模型列表
- **模型一键切换**: 双击已保存模型或点击按钮快速切换
- **API Key 安全显示**: 支持明文/密文切换（👁️ 按钮）
- **测试连接优化**: 高可用设计（全新 Session + 并行双策略），成功率近 100%
- **高 DPI 自适应**: 支持 4K 屏幕，界面清晰锐利
- **新电脑部署引导**: 自动检测并引导配置缺失的 API Key

### 筛选规则
| 条件类型 | 说明 |
|----------|------|
| 硬条件 | 工作经验、学历、必须技能关键词 |
| 软条件 | 加分技能关键词匹配度 |
| 推荐等级 | 强烈推荐 (75-100 分)、推荐 (65-74 分)、待定 (45-59 分) |

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

编辑 `job_config.json` 文件，配置各岗位的筛选规则：

```json
{
  "高级 Java 工程师": {
    "min_exp": 5,
    "edu": "本科",
    "keywords": ["Java", "Spring Boot", "MySQL", "Redis"]
  },
  "Python 开发工程师": {
    "min_exp": 3,
    "edu": "本科",
    "keywords": ["Python", "Django", "MySQL"]
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

# 指定滚动轮次（减少滚动次数）
python bossmaster.py --greet --rounds 20

# 输出详细评分信息（查看技能匹配详情）
python bossmaster.py --greet --verbose
```

### 4. 查看结果

程序运行后会生成：
- `candidates_all.json` - 全量候选人数据（累积、去重）
- `candidates_all.xlsx` - Excel 导出文件（多工作表 + 统计摘要）

### 5. 中断恢复

运行中按 `Ctrl+C` 中断时：
- 已打招呼的候选人会立即保存状态
- 下次运行时自动跳过已打招呼的候选人
- 不会重复发送消息

## 📁 项目结构

```
boss-resume-filter/
├── bossmaster.py         # BOSS 直聘自动筛选主程序（核心）
├── gui_main.py           # 图形界面主程序（v3.0）
├── doc_parser.py         # 文档解析器（简历解析）
├── main.py               # 命令行入口
├── security.py           # API Key 安全存储模块
├── gui.bat               # GUI 启动脚本
├── job_config.json       # 岗位筛选规则配置
├── api_config.json       # AI 模型配置（不含明文 Key）
├── candidates_all.json   # 累积的候选人数据（累积、去重）
├── candidates_all.xlsx   # Excel 导出文件（多工作表 + 统计摘要）
├── CLAUDE.md             # AI 协作规范
├── README.md             # 项目主文档
├── GUI 使用说明.md        # 图形界面详细说明
├── DEPLOYMENT.md         # 部署说明
├── PACKAGING.md          # 打包指南
├── requirements.txt      # Python 依赖
├── install.bat           # 安装脚本
├── tests/                # 测试脚本目录
└── scripts/              # 辅助脚本目录
```

## 📊 匹配规则

### 硬条件（一票否决）
| 条件 | 说明 |
|------|------|
| 工作经验 | ≥ 岗位要求的最低年限 |
| 学历 | ≥ 岗位要求的最低学历（本科/硕士/博士） |
| 必须技能 | 岗位 keywords 的匹配度 |

### 软条件（加权打分）
根据岗位 keywords 的匹配数量加权计算，满分 40 分。

### 推荐指数
| 等级 | 分数 | 操作 |
|------|------|------|
| 强烈推荐 | 75-100 | 自动打招呼（可配置为仅此等级） |
| 推荐 | 65-74 | 自动打招呼（默认） |
| 待定 | 45-59 | 不自动打招呼 |

### 打招呼逻辑
- 按钮位置：候选人卡片的 `operate-side` 区域
- 按钮文本："继续沟通"（已匹配）、"立即沟通"（新候选人）
- 自动重试：失败时自动重试一次
- **中断恢复**：打招呼前立即保存状态，中断后不重复
- **去重机制**：基于 `geek_id` 去重，保留分数高的记录

## ⚠️ 注意事项

1. **浏览器要求**: 需要安装 Chrome 浏览器
2. **手动导航**: 程序启动后需手动导航到 BOSS 直聘推荐页面
3. **网络稳定**: 保持网络连接稳定，避免中断
4. **数据备份**: 定期备份 `candidates_all.json` 文件
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
