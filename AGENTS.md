# BOSS 简历筛选器 - AI Agent 快速参考

> 本文档是 AI Agent 的快速参考。完整规则、踩坑警示、实现细节见 [CLAUDE.md](CLAUDE.md)。

## 项目结构

```
boss-resume-filter/
├── bossmaster.py         # 主程序（核心逻辑）
├── filtering.py          # 筛选规则
├── llm_eval.py           # LLM 辅助评估
├── storage.py            # 数据持久化
├── gui_main.py           # 图形界面（v2.9）
├── updater.py            # 自动更新
├── icons.py              # 图标绘制
├── doc_parser.py         # 需求文档解析
├── security.py           # API Key 加密存储
├── build.py              # 打包发布脚本
├── latest.json           # 版本清单
├── job_config.json       # 岗位规则配置
├── api_config.json       # AI 模型配置
├── selectors.json        # 页面选择器
├── candidates_all.json   # 候选人数据
└── tests/                # 测试脚本
```

## 运行命令

### 命令行模式
```bash
pip install -r requirements.txt                    # 安装依赖
python bossmaster.py --greet                       # 自动打招呼
python bossmaster.py --job "高级 Java" --greet     # 指定岗位
python bossmaster.py --re-greet                    # 补打招呼
python bossmaster.py --clear --greet               # 清空后打招呼
```

### 测试
```bash
python tests/run_unit_tests.py    # 稳定单元回归
python tests/test_import.py       # 导入烟测
```

### 打包发布
```bash
python build.py --check           # 发布前检查
python build.py                   # 仅打包
python build.py --release         # 一键发布（需确认）
python build.py --release --auto  # 全自动模式
```

## 关键规则

### 版本号格式（必须遵守）
- **大版本**：`X.Y`（如 v2.9），**禁止**写成 `X.Y.0`
- **补丁版本**：`X.Y.Z`（如 v2.8.12）
- 更新位置：`gui_main.py`、`CHANGELOG.md`、`README.md`、`CLAUDE.md`
- 详见 CLAUDE.md "版本号规范"

### 代码规范
- 使用 type hints
- 关键函数写 docstring
- 异常处理要具体，不要裸 except

### 敏感信息
- `.env` 文件不进 git
- API Key 加密存储在系统钥匙串，`api_config.json` 不含明文
- API Key 按服务商统一管理

## 核心逻辑速查

| 功能 | 实现位置 | 说明 |
|------|---------|------|
| 打招呼 | `bossmaster.py` | 智能滚动定位、沟通上限检测 |
| 停止机制 | `bossmaster.py` | StopRequested + threading.Event |
| 浏览器检测 | `gui_main.py` | 自动轮询、自动启动 Chrome |
| 反爬对抗 | `bossmaster.py` | 随机延迟、验证码阻断 |
| 去重 | `storage.py` | (geek_id, job_name) 复合键 |
| 保存策略 | `storage.py` | 原子写入、备份恢复 |
| 评分体系 | `filtering.py` | 四维模型、学历加分 |
| AI 评估 | `llm_eval.py` | LLM 二次评估、并发调用 |
| 需求解析 | `doc_parser.py` | 关键词提取、薪资/地点解析 |
| 自动更新 | `updater.py` | Gitee/GitHub 双源检查 |
| 发布流程 | `build.py` | 打包、tag、GitHub/Gitee 上传 |

## 常见坑点（详见 CLAUDE.md "踩坑警示"）

1. **macOS .app 路径**：`sys.executable` 在 .app 中指向 `Contents/MacOS/`，配置文件需向上追溯 3 层
2. **PyInstaller 版本号**：不能从 `sys._MEIPASS` 读源码，应 `import gui_main` 读模块属性
3. **Tk 对话框崩溃**：`wait_window()` 在 `root.after()` 中会创建嵌套事件循环导致崩溃，用 `grab_set()` 替代
4. **Windows DPI 缩放**：保持 DPI Unaware，不要启用 DPI 感知
5. **macOS 字体**：Tk 8.6 在 Apple Silicon 报告 DPI 72，需 `font_boost = 1.65` 补偿
6. **Gitee API**：PATCH release 必须带 `tag_name` 和 `body`；`--gitee-upload` 参数需移除 `v` 前缀

## 文档索引

- [CLAUDE.md](CLAUDE.md) — 完整项目规范、踩坑警示
- [README.md](README.md) — 用户文档、版本历史
- [CHANGELOG.md](CHANGELOG.md) — 更新日志
- [DEPLOYMENT.md](DEPLOYMENT.md) — 部署说明
- [PACKAGING.md](PACKAGING.md) — 打包指南
- [GUI 使用说明.md](GUI%20使用说明.md) — GUI 详细说明
