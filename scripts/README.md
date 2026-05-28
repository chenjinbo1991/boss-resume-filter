# scripts 目录说明

本目录只放辅助脚本，不属于稳定回归入口，也不属于主程序运行路径。主程序能力优先在仓库根目录模块中维护，例如 `bossmaster.py`、`gui_main.py`、`filtering.py`、`updater.py`。

默认验收命令仍然是：

```powershell
python tests/run_unit_tests.py
python tests/test_import.py
```

## 使用规则

- 新增脚本前先判断能否放进主程序、`tests/manual/` 或 `tests/archive/`；只有确实是本地辅助工具时才放这里。
- 脚本必须能说明用途、依赖、运行前提和输出结果；不要只留下临时试验代码。
- 依赖浏览器、BOSS 登录、真实网络、反爬调试或人工操作的脚本，默认视为手工工具，不进入稳定回归。
- 不再有效但仍有历史参考价值的脚本，后续应迁移到 `tests/archive/` 或单独的归档目录；迁移前不要删除。
- 运行脚本时默认从仓库根目录执行，避免相对路径写到错误位置。

## 当前脚本分组

### 可保留的本地辅助工具

- `config_generator.py`：交互式生成 `job_config.json` 的早期配置工具。现在 GUI 已承担主要配置入口，保留作命令行备用。
- `open_url.py`：打开 BOSS 直聘页面的极简辅助脚本。
- `manual_guide.py`：纯文本手动提取职位信息说明。
- `manual_extraction_guide.py`：生成更完整的手动职位提取指南。
- `enhanced_manual_guide.py`：增强版手动提取指南，内容与 `manual_extraction_guide.py` 有重复，后续可合并。
- `js_extraction_helper.py`：输出可在浏览器控制台执行的职位提取 JavaScript。

### BOSS 职位提取实验脚本

这些脚本依赖浏览器、登录态、页面 DOM 或网络请求，不保证随 BOSS 前端变化长期可用。

- `fetch_jobs_sync.py`：早期职位获取流程，偏向手动登录和 Playwright 浏览器启动。
- `extract_jobs.py`：从职位管理页面提取职位信息的早期 Playwright 实现。
- `extract_jobs_safe.py`：通过页面内 JavaScript 提取职位信息的实验版本。
- `extract_jobs_api.py`：尝试从网络/API 请求提取职位信息的实验版本。
- `inspect_page.py`：检查 BOSS 职位管理页面 HTML 结构的调试工具。

### 反爬/RPA 早期方案

这些脚本属于方案探索，不是当前稳定主线。不要把其中逻辑直接搬进主程序；如需恢复，先重新验证 BOSS 当前页面、登录和反爬行为。

- `rpa_simulation.py`：人工操作模拟方案说明和原型。
- `rpa_advanced.py`：基于 Selenium / undetected-chromedriver 的高级 RPA 原型。
- `bypass_antispider.py`：反爬绕过实验脚本。
- `bossmaster_fixed.py`：早期候选人提取/筛选修复版本，主线已迁移到根目录 `bossmaster.py` 等模块。

### 一次性历史脚本

- `analyze_candidates.py`：针对固定候选人 JSON 文件名的一次性统计脚本。当前仓库中没有这些输入文件，默认不维护。

## 后续整理建议

下一步可以在不影响历史的前提下做两件事：

- 把重复的手动指南合并成一个脚本或文档。
- 把明确不再维护的实验脚本迁移到归档目录，并同步修正 `tests/manual/` 中的旧路径引用。
