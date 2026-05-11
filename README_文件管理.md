# BOSS 直聘候选人筛选 - 文件管理说明

## 文件结构

### 每次运行产生的文件
```
candidates_all.json    # 全量数据（累积、去重、覆盖）
candidates_all.xlsx    # Excel 导出（覆盖）
```

**注意**：不再产生带时间戳的中间文件，每次运行只更新这两个文件。

### 字段说明
| 字段 | 说明 |
|------|------|
| 岗位 | 候选人匹配的岗位名称 |
| 姓名 | 候选人姓名 |
| 匹配分 | 综合评分（0-100） |
| 推荐指数 | 强烈推荐/推荐/待定 |
| 是否打招呼 | 是/否 |
| 技能匹配 | 技能匹配比例 |
| geek_id | 候选人唯一 ID |
| 批次 | 本次运行的时间戳 |
| 详细信息 | 候选人摘要 |

## 运行参数

```bash
# 增量跑批（自动过滤当前岗位已匹配且打过招呼的候选人，对≥65 分的新候选人打招呼）
python bossmaster.py --greet

# 指定岗位
python bossmaster.py --job 高级 Java 工程师 --greet

# 清空历史后重新跑
python bossmaster.py --clear --greet

# 补打招呼：给已匹配但未打招呼的候选人发送消息
python bossmaster.py --re-greet

# 只跑指定轮次（减少滚动次数）
python bossmaster.py --greet --rounds 20
```

## 输出文件

每次运行固定生成：
- `candidates_all.json` - 全量数据（累积、去重）
- `candidates_all.xlsx` - Excel 导出（覆盖旧文件）

## 打招呼逻辑

### 推荐指数规则
评分采用四维模型：基础30 + 技能(0~35) + 经验超额(0~20) + 学历档次(0~15)

| 分数 | 推荐指数 |
|------|----------|
| 75-100 | 强烈推荐 |
| 65-75 | 推荐 |
| 45-60 | 待定 |

### 打招呼按钮定位
打招呼按钮位于候选人卡片的 `operate-side` 区域（与 `card-inner` 并列的兄弟元素），而非卡片内部。
系统按以下顺序查找按钮：
1. 在候选人卡片的父元素中查找包含 "继续沟通"（已匹配）、"立即沟通"（新候选人）、"打招呼"、"开始沟通" 的元素
2. 查找 class 包含 `btn btn-continue` 的元素
3. 回退到在卡片内部查找

### 增量模式（`--greet`）
1. 加载 `candidates_all.json` 检查历史数据
2. **过滤规则**：只过滤「当前岗位已匹配且打过招呼」的候选人，其他情况保留
   - 当前岗位已匹配但未打招呼 → 保留（补打招呼）
   - 其他岗位已匹配 → 保留（允许一人多岗）
   - 新候选人 → 保留
3. 对「强烈推荐」和「推荐」（≥65 分）的候选人自动打招呼
4. 已打过招呼的候选人自动跳过
5. **立即保存**：每成功发送一个招呼，立即更新 `candidates_all.json`，防止中断丢失进度
6. 每个岗位处理完后再次保存新增的候选人

### 补打招呼模式（`--re-greet`）
- 直接读取 `candidates_all.json`
- 给所有「强烈推荐」和「推荐」但未打招呼的候选人发送消息
- **立即保存**：每成功发送一个招呼，立即更新打招呼状态

## 清理旧文件

运行清理脚本删除旧的带时间戳文件：
```bash
cleanup_old_files.bat
```

或手动删除：
```bash
# 删除带时间戳的旧文件（保留 candidates_all.*）
for /f "delims=" %i in ('dir /b candidates_*.json ^| findstr /v "^candidates_all\.json$"') do @del /q "%i"
for /f "delims=" %i in ('dir /b candidates_*.xlsx ^| findstr /v "^candidates_all\.xlsx$"') do @del /q "%i"
```

## 数据流转

```
每次运行 → 加载 candidates_all.json（检查打招呼状态）
        → 过滤「当前岗位已匹配且打过招呼」的候选人
        → 扫描新候选人并筛选
        → 对≥65 分的新候选人/未打招呼的候选人发送消息
        → 更新 candidates_all.json（累积、去重、更新打招呼状态）
        → 生成 candidates_all.xlsx（覆盖）
```
