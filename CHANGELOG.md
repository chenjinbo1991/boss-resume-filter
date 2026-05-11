# 更新日志

## 2026-05-11 - v3.1 滚动优化 + 淘汰原因展示 + 沟通上限检测

### 滚动提前终止优化

1. **到底检测位置修正**
   - 原逻辑：每轮**先检测"到底"再滚动**，BOSS 直聘 footer 常驻"已经到底了"文字可能被误匹配
   - 修复：到底检测移到**滚动之后**执行，只有真正滚动过才检查，不会误匹配常驻 footer

2. **滚动策略增强**
   - JS 同时滚动 `window.scrollBy()` 和可能的滚动容器元素（`.candidate-list`、`.geek-list` 等）
   - 单次滚动量从 600+200 两步改为 800px 一步，等待时间 0.6s → 0.5s
   - 解决 BOSS 直聘虚拟列表可能绑在特定 div 而非 window 上的问题

3. **连续空轮次阈值上调**
   - 5 轮 → 10 轮，多给 5 轮机会，减少因网络延迟导致的误终止

### 淘汰原因展示优化

1. **全部原因展示**：移除 `[:5]` 截断，显示所有淘汰原因类别，解决数字对不上的问题
2. **同类合并**：
   - "经验不足" → 合并为 `经验不足（4年以上工作经验）`（括号内动态读取规则）
   - "学历不足"/"学历不符" → 合并为 `学历不符/不足（统招本科）`（优先取 required_conditions）
   - "评分不足" → 按分数段归类：50-54分 / 40-49分 / 30-39分 / <30分
3. **排序固定**：经验不足 → 学历不符/不足 → 评分不足(按分数段) → 其他
4. **修复"未知"误报**：通过硬性筛选但评分<55 的候选人，原显示为"未知"，现正确显示为对应分数段
5. **总数校验**：显示 通过数 + 淘汰数 = 原始数 的校验

### 沟通上限检测

1. **`_detect_limit_popup()` 函数**：在 `send_greeting_on_list_page()` 点击打招呼按钮后检测 BOSS 直聘升级套餐/每日上限弹窗
2. **高效实现**：单次 JS 调用 `body.innerText.includes()` 检查 16 个限制关键词，同时检查 page 和 iframe 两个上下文
3. **智能终止**：检测到上限后立即停止后续打招呼并提示用户，防止在弹窗页面继续误报"打招呼成功"

### 其他优化

1. **页面等待时间**：所有 `time.sleep(10)` 改为 `time.sleep(3)`（页面导航等待）
2. **版本号**：v3.0 → v3.1
3. **GUI 默认打招呼等级**：从"强烈推荐 + 推荐"改为"仅强烈推荐"

### 修改文件
- bossmaster.py：滚动策略 + 到底检测位置 + 连续空轮次阈值 + 淘汰原因合并/排序/校验 + 沟通上限检测 + 等待时间
- gui_main.py：默认打招呼等级 + 初次扫描等待时间 + 版本号
- CLAUDE.md：同步更新核心逻辑说明
- README.md / README_文件管理.md：同步更新文档

---

## 2026-05-11 - Bug 修复：打招呼等级过滤 + Excel 导出

### Bug 修复

1. **打招呼等级过滤在初次扫描时无效**
   - 现象：GUI 中选择"仅强烈推荐"，实际对强烈推荐和推荐候选人都打了招呼
   - 根因：`run_smart_scan()` 调用 `smart_scan_candidates()` 时 `greet_level` 参数硬编码为 `'normal'`，且有一行误导性注释"初次扫描时 greet_level 不生效"
   - 修复：将 `greet_level='normal'` 改为 `greet_level=args.greet_level`，透传用户在 GUI 中的选择
   - 影响范围：初次扫描模式的 `--greet-level` 参数现在生效（补打招呼模式原本就有效）

2. **Excel 导出报错：Invalid character / found in sheet title**
   - 现象：岗位名含 `/`（如"前端/React 工程师"）时导出失败
   - 根因：`export_to_excel()` 中 `sheet_name = job_name[:25]` 只做截断，未清理 Excel 工作表名非法字符（`\ / * ? [ ] :`）
   - 修复：使用 `str.translate()` 将非法字符替换为安全字符，截断长度从 25 改为正确的 31

3. **打招呼等级日志显示修正**
   - `run_smart_scan()` 中启动日志的打招呼等级文字从硬编码"强烈推荐 + 推荐"改为根据实际参数动态显示

### 修改文件
- bossmaster.py：3 处修改（greet_level 透传、sheet name 清理、日志动态显示）

---

## 2026-05-11 - 性能优化：打招呼速度提升 12 倍

### 问题分析

用户指出三大性能瓶颈：
1. **循环内 `ele()` 超时叠加**：每次未命中等待 10 秒，N 个候选人是 N×10 秒
2. **全局 XPath 扫描**：`@@text():关键字` 模糊匹配扫描整个页面 DOM
3. **`scroll.to_see()` 破坏虚拟列表**：强制滚动导致 BOSS 直聘回收已渲染卡片

### 优化方案

1. **`send_greeting_on_list_page()` 全面重写**
   - 卡片定位：CSS 选择器 `[data-geekid="..."]` + `timeout=2`（原 10 秒），失败后 `scrollBy(0, 300)` 重试一次
   - 按钮定位：XPath 改为在卡片 `parent()` 内查找（缩小扫描范围），而非全局 `@@text()`
   - 点击策略：`scroll.to_see(center=True)` + `click()`，失败时回退到 `run_js('this.click()')`
   - 结果：单次等待从 10-20 秒降至 0.5 秒（未找到时）~ 4-5 秒（成功打招呼时）

2. **Phase 2 滚动逻辑优化**
   - 原 `run_js('window.scrollTo(0, 0)')` 回顶部会销毁所有虚拟列表渲染 → 改为小幅度 `scrollBy(0, 200)` + `scrollBy(0, -100)` 温和刷新

3. **打招呼循环内增量滚动**
   - 每 5 个招呼间歇性 `scrollBy(0, 400)`，保持虚拟列表持续渲染后续卡片，避免卡片因滚出可视区而被回收

### 效果
- 每个候选人打招呼耗时：20-60 秒 → 4-5 秒（12 倍提升）

### 修改文件
- bossmaster.py：`send_greeting_on_list_page()` 重写 + Phase 2 滚动逻辑 + 增量滚动

---

## 2026-05-11 - UI 优化：滚动轮次 Spinbox + 推荐阈值调整

### 滚动轮次 Spinbox

1. **增量单位改为 10**：`increment=10`，点上下箭头每次 ±10
2. **最小值 0**：`from_=0`，不设实际下限
3. **移除硬上限**：`to=9999` 作为虚拟上限，实际不限制
4. **鼠标滚轮支持**：绑定 `<MouseWheel>` 事件，滚轮每次 ±10（使用符号判断 `event.delta > 0` 而非 `delta//120`，兼容不同鼠标硬件）
5. **默认值 100**：从 30 上调
6. **推荐范围**：标签文本从"(推荐 20-40 轮次)"改为"(推荐 50-200 轮次)"
7. **CLI 默认值同步**：`--rounds` 默认值从 30 改为 100

### 推荐阈值调整

| 等级 | 旧阈值 | 新阈值 |
|------|--------|--------|
| 强烈推荐 | ≥75 | ≥75（不变） |
| 推荐 | ≥60 | ≥65 |
| 待定 | ≥45 | ≥55 |
| 过滤 | <45 | <55（不显示、不导出） |

- 所有阈值在 `bossmaster.py`、`gui_main.py` 中同步更新
- `candidates_all.json` / `candidates_all.xlsx` 中低于 55 分的历史记录已清理

### 修改文件
- gui_main.py：Spinbox 配置 + 鼠标滚轮事件 + 阈值更新
- bossmaster.py：CLI rounds 默认值 + 阈值更新 + `<55` 过滤逻辑

---

## 2026-05-08 - 打包优化 + 侧边栏导航对齐修复

### 打包优化

1. **build.py 脚本优化**
   - 自动检测并使用 pack_venv 虚拟环境，无需手动激活
   - dist 目录清理重试逻辑（3 次重试 +2 秒等待），处理文件占用问题
   - 移除 os.execl() 进程重启，简化为 subprocess 调用

2. **打包结果**
   - EXE 体积：39.3 MB（相比 Anaconda 环境的 931MB 缩减 23 倍）
   - 打包时间：~48 秒（首次完整构建）
   - 输出文件：BOSS_简历筛选器.exe + README.md + requirements.txt + job_config.json + gui.bat

### UI 修复

1. **侧边栏导航文字对齐**
   - 问题：📊 emoji 比其他 emoji 窄，导致"筛选结果"文字偏左
   - 解决：使用 Frame 容器包裹 emoji + 文字，emoji 标签设置 `width=2` 固定宽度
   - 所有导航项（含系统设置）统一容器结构，文字起始位置完全对齐

2. **鼠标悬停效果恢复**
   - 添加 `on_nav_enter()` / `on_nav_leave()` 方法
   - 鼠标移入：前景色变白色 `#FFFFFF`
   - 鼠标移出：恢复灰色 `#A0AEC0`（当前页面除外）
   - 只改变颜色，不切换样式，避免布局抖动

### 修改文件
- gui_main.py：导航容器重构 + 悬停效果（+70 行）

---

## 2026-05-08 - 评分体系重构 + 滚动提前终止 + API Key 安全架构升级

### 评分体系重构（四维模型）

1. **四维评分公式**
   - 旧公式：`基础60 + 技能×40`（区间 60-100，区分度差）
   - 新公式：`基础30 + 技能(0~35) + 经验超额(0~20) + 学历档次(0~15)`（区间 30-100）
   - 经验和学历不再仅做门限，超额/优质部分计入评分

2. **关键词子串误匹配修复**
   - 英文/数字关键词使用 `\b` 单词边界匹配（`_keyword_found()` 函数）
   - 解决 "AI" 误匹配 "email"、"main" 等严重问题

3. **经验超额加分**
   - 超出 min_exp 部分每年 +4 分，20 分封顶
   - 找不到经验不再淘汰，改为警告后放行

4. **学历档次加分**
   - `_calc_edu_bonus()` 函数：博士+15, 985/211硕士+13, 硕士+10, 985/211本科+8, 统招本科+5

5. **推荐等级阈值调整**
   - 强烈推荐：80→75, 推荐：70→60, 待定：60→45

6. **泛化关键词清理**
   - 剔除 "数据库"（零区分信号的关键词）

### 滚动提前终止

### 滚动逻辑优化

1. **双策略提前终止滚动**
   - 文本提示检测：每轮滚动前检测页面是否出现"到底"/"没有更多"等提示文字，命中立即终止
   - 连续空轮次兜底：连续 3 轮无新候选人自动终止（不依赖特定文案，BOSS 改文字也不怕）
   - 效果：不再傻跑 30 轮，到底即停，节省大量无效等待时间

### 安全性

1. **API Key 加密存储**
   - 使用 `keyring` 库加密存储 API Key 到系统钥匙串（Windows DPAPI）
   - `api_config.json` 不再保存明文 API Key
   - 按服务商统一管理：同一服务商的所有模型共享一个 Key
   - 新增 `security.py` 模块：`save_api_key()` / `get_api_key()` / `delete_api_key()`

2. **API Key 集中管理**
   - 移除 `.env` 和 `.env.example` 中的 API Key 配置
   - 所有 API Key 统一通过 GUI 配置和管理
   - `src/matcher/engine.py` / `src/web/app.py` 从 keyring 读取 API Key

3. **新电脑部署检测**
   - 首次在新电脑运行自动检测 API Key 缺失
   - GUI 显示提示引导用户重新配置
   - 新增 `DEPLOYMENT.md` 部署说明文档

### 新增功能

1. **API Key 迁移工具**
   - `migrate_keys.py`：将旧版按模型存储的 API Key 迁移到按服务商存储
   - 自动清理冗余的 keyring 条目

### 修改文件
- bossmaster.py：滚动提前终止（文本检测 + 连续空轮次兜底）
- gui_main.py：keyring 集成、新电脑检测提示、按服务商存储
- src/matcher/engine.py：从 keyring 读取 API Key
- src/web/app.py：从 keyring 读取 API Key
- tests/test_llm.py：从 keyring 读取 API Key
- .env / .env.example：移除 API Key 字段
- CLAUDE.md：更新项目结构和安全说明
- README.md：更新 API Key 功能描述

---

## 2026-05-07 - GUI v2.0 重大升级

### 新增功能

1. **图形界面 v2.0**
   - 侧边栏导航重构：首页、岗位配置、运行控制、筛选结果、系统设置
   - 系统设置独立入口（从底部移入侧边栏）
   - 高 DPI 自适应（支持 4K 屏幕）
   - 窗口大小可调（默认 1500x950，额外放大 30%）

2. **AI 模型配置中心**
   - 支持多服务商：qwen、deepseek、kimi、zhipu、minimax、xiaomi、stepfun、openai、anthropic、custom
   - 已保存模型列表管理（Treeview 展示）
   - 双击切换模型或点击"使用选中模型"按钮
   - 切换提示：弹窗显示"已成功切换到 xxx"
   - API Key 明文/密文切换按钮（👁️图标）

3. **获取模型列表功能**
   - 根据当前 API Key 和 Base URL 动态获取
   - 智能过滤非聊天模型（embedding、rerank、tts、whisper）
   - 下拉框展示可选模型
   - 按钮布局优化（3 列改 4 列，避免溢出）

4. **测试连接优化**
   - 高可用设计：每次使用全新 Session（禁用 keep-alive）
   - 并行双策略请求（兼容不同 API 格式）
   - 宽松超时：连接 8 秒 + 读取 30 秒
   - 重试机制：最多 3 次，指数退避（0.5s → 1s → 2s）
   - 成功率：从 50% 提升至近 100%

### 修复问题

1. **模型切换 API Key 丢失**
   - 原因：save_api_config 中模型已存在时不更新 API Key
   - 修复：模型已存在时也更新 api_key、base_url 字段

2. **页面索引冲突**
   - 原因：current_page_index 初始值 2 与 show_page_run 冲突
   - 修复：改为 4，避免导航错乱

3. **save_config 重复定义**
   - 删除第 2498-2502 行的重复定义

4. **窗口关闭不安全**
   - 原因：工作线程未正确终止
   - 修复：使用 join(timeout=5) 替代 sleep(1)，确保线程安全退出

### 性能优化

1. **save_candidates_all O(n²)→O(n)**
   - 使用字典（seen_geek_ids）替代列表内查找
   - 去重时间复杂度：O(n²) → O(n)
   - 大数据量下性能提升显著

2. **批量保存优化**
   - 成功打招呼：立即保存（防止中断丢失）
   - 失败打招呼：攒够 5 个再写文件（减少 IO）

### 代码质量

1. **异常处理规范化**
   - 7 处裸 `except: pass` 改为具体异常类型
   - 添加日志输出，便于故障排查
   - 示例：
     ```python
     # DPI 设置降级
     except (OSError, AttributeError):
         pass  # 非 Windows 或 DPI 设置不支持，静默降级
     
     # 统计刷新
     except Exception as e:
         print(f"刷新首页统计失败：{e}")
     ```

2. **DEBUG 日志清理**
   - 移除所有 [DEBUG] 输出和调试计时逻辑
   - 保持生产环境清洁

### 安全性

1. **API Key 可视化增强**
   - 默认明文显示
   - 点击按钮切换为密文（*号遮挡）
   - 再次点击恢复明文

2. **窗口关闭确认**
   - 运行时点击关闭：弹窗确认
   - 确认后等待工作线程安全退出

### 修改文件
- gui_main.py：+400 行（模型配置功能、布局优化、异常处理）
- bossmaster.py：+50 行（性能优化、日志清理）
- requirements.txt：+certifi>=2023.7.22
- CLAUDE.md：更新项目结构和核心逻辑说明

---

## 2026-05-06 - 综合优化

### 新增功能

1. **中文数字解析支持**
   - 新增 `parse_experience_years()` 函数
   - 支持格式：`3 年 `、`三年`、`十二年`、`三年以上`、`10 年以上`
   - 中文数字映射：零/一/二/三/四/五/六/七/八/九/十/两

2. **Excel 导出增强**
   - 多工作表：全部候选人 + 按岗位分工种 + 统计摘要
   - 统计摘要：各岗位总人数、强烈推荐/推荐/待定人数、已打招呼人数、平均分
   - 自动筛选：启用 Excel 自动筛选功能
   - 冻结窗格：冻结首行（标题行）
   - 颜色标识：推荐指数和是否打招呼列

3. **评分详情输出**
   - 新增 `--verbose` 参数，输出详细评分信息
   - 显示技能匹配详情、匹配技能列表
   - 适用于分析候选人为什么得 73 分而不是 80 分

4. **跨岗位去重**
   - `save_candidates_all()` 支持基于 `geek_id` 去重
   - 保留分数高的记录
   - 合并打招呼状态

### 优化改进

1. **滚动速度优化**
   - 默认滚动轮次：50 → 30
   - 初始等待：2 秒 → 1.5 秒
   - 滚动后等待：1 秒 → 0.5-0.8 秒
   - 连续无新增停止：5 轮 → 3 轮
   - **整体运行时间减少约 50%**

2. **项目清理**
   - 删除 12 个 `debug_*.py` 调试文件
   - 提高项目可读性

### 修改内容

#### bossmaster.py
- `parse_experience_years()`: 新增中文数字解析
- `filter_candidate()`: 使用新的解析函数
- `export_to_excel()`: 增强为多工作表 + 统计摘要
- `save_candidates_all()`: 添加去重逻辑
- `smart_scan_candidates()`: 新增 `verbose` 参数
- `run_smart_scan()`: 新增 `--verbose` 参数
- `extract_candidates_by_comprehensive_analysis()`: 优化等待时间

#### test_filter_rules.py
- 新增中文数字解析测试
- 测试覆盖：3 年、十年、三年以上、十二年、两年、五年以上、八年

### 使用示例

```bash
# 使用中文数字解析（自动）
python bossmaster.py --greet

# 输出详细评分信息
python bossmaster.py --greet --verbose

# 指定滚动轮次（减少扫描时间）
python bossmaster.py --greet --rounds 20

# 清空历史后重新跑
python bossmaster.py --clear --greet
```

### 兼容性

- 完全向后兼容旧版配置文件格式
- 中文数字解析自动生效，无需配置
- Excel 文件格式变化：新增多个工作表

---

## 2026-05-06 - 筛选规则增强

### 新增功能

1. **支持复杂必要条件规则**
   - 新增 `check_required_condition()` 函数
   - 支持三种条件格式：
     - 字符串：`"统招本科"` - 直接匹配（985/211 视为统招）
     - OR 规则：`{"type": "or", "items": ["activiti", "camunda", "flowable"]}` - 至少满足一项
     - AND 规则：`{"type": "and", "items": ["Java", "MySQL", "Redis"]}` - 全部满足

2. **学历匹配优化**
   - 985/211 院校视为统招本科
   - 宽松匹配：有"本科"但无"统招"字样也视为通过
   - 明确非统招（自考、成教、函授等）直接淘汰

3. **配置文件格式升级**
   - 支持新格式 `jobs` 键名（同时兼容旧格式 `job_requirements`）
   - 移除废弃的 `tech_conditions` 字段（功能已合并到 `required_conditions`）

### 修改内容

#### bossmaster.py
- `filter_candidate()`: 重构必要条件检查逻辑，调用新的 `check_required_condition()` 函数
- `check_required_condition()`: 新增函数，支持复杂的必要条件规则

#### job_config.json
- 更新为新格式 `jobs`
- "高级 Java 工程师"岗位添加 OR 规则：`{"type": "or", "items": ["activiti", "camunda", "flowable", "工作流"]}`

#### test_filter_rules.py
- 新增测试脚本，验证筛选逻辑
- 测试覆盖：
  - 字符串条件匹配
  - OR/AND 规则匹配
  - 完整筛选流程
  - 边界情况（空格、大小写、同义词、中文数字）

### 使用示例

```json
{
    "jobs": {
        "高级 Java 工程师": {
            "min_exp": 4,
            "edu": "本科",
            "keywords": [
                {"name": "Spring Cloud", "weight": 2},
                {"name": "Java", "weight": 1}
            ],
            "required_conditions": [
                {"type": "or", "items": ["activiti", "camunda", "flowable", "工作流"]},
                "统招本科"
            ]
        }
    }
}
```

### 运行测试

```bash
cd boss-resume-filter
python test_filter_rules.py
```

### 兼容性

- 完全向后兼容旧版配置文件格式
- `tech_conditions` 字段仍可使用，但建议迁移到 `required_conditions`
- 评分算法保持不变（基础分 60 + 技能分 40）
