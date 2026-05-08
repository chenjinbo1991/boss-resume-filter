# 更新日志

## 2026-05-08 - API Key 安全架构升级

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
