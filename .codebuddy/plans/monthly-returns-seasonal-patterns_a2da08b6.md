---
name: monthly-returns-seasonal-patterns
overview: 修复月度涨跌幅排序（升序）、用真实数据计算季节性规律，并扩大历史数据覆盖范围以支撑有统计意义的季节分析。
todos:
  - id: fix-sort-db-helper
    content: 修改 db_helper.py 中 get_all_monthly_changes() 的 SQL 排序为 ORDER BY date ASC
    status: completed
  - id: fix-sort-reinject
    content: 修改 reinject_from_db.py 第48行 kline_monthly 查询排序为 ORDER BY code, date ASC
    status: completed
  - id: add-unique-index
    content: 在 db_helper.py 初始化中添加 kline_daily 和 kline_monthly 的 UNIQUE INDEX，支持 INSERT OR REPLACE
    status: completed
  - id: change-upsert-to-accumulate
    content: 将 upsert_kline_daily 和 upsert_kline_monthly 从 DELETE+INSERT 改为 INSERT OR REPLACE 累积模式
    status: completed
    dependencies:
      - add-unique-index
  - id: increase-fetch-limit
    content: 将 sync_all.py 中 fetch_kline 的默认 limit 从 200 扩大到 2000
    status: completed
  - id: add-seasonal-pct-func
    content: 在 sync_all.py 中新增 _calc_seasonal_pct() 函数，从 kline_monthly 按月计算真实平均涨跌幅百分比
    status: completed
  - id: replace-default-seasonal
    content: 修改 sync_all.py Step 7，用 _calc_seasonal_pct() 真实计算结果替换 DEFAULT_SEASONAL 硬编码
    status: completed
    dependencies:
      - add-seasonal-pct-func
---

## 用户需求

在K线走势功能中，实现月度涨跌幅与季节性规律的正确数据处理逻辑。

## 核心功能

1. **月度涨跌幅排序修正**：月度涨跌幅数据严格按月份从旧到新升序排列展示，修正当前 DESC 排序问题
2. **季节性规律真实计算**：季节性规律（月均涨跌幅%）直接依赖于月度涨跌幅数据按月分组求均值，替代当前硬编码假数据
3. **扩大数据覆盖范围**：将日K拉取量从 200 扩大至 2000 条，覆盖约 8 年数据，确保季节性分析具备统计意义（每月至少 3-8 个数据点）
4. **存储模式改为累积**：upsert_kline_daily/monthly 从 DELETE+INSERT 改为 INSERT OR REPLACE，防止每次同步覆盖历史数据

## 技术栈

- 后端：Python + SQLite（db_helper.py / sync_all.py / reinject_from_db.py）
- 前端：原生 JavaScript + Chart.js（kline.js，无需改动）
- 数据流：NeoData API fetch_kline(limit=2000) → kline_daily → 聚合 → kline_monthly → _calc_seasonal_pct() → seasonal 表 → server.py 注入 → 前端渲染

## 实现方案

### 当前问题分析

```
数据覆盖不足                      存储模式缺陷                     排序 + 计算错误
┌──────────────────┐    ┌──────────────────────────┐    ┌──────────────────────────┐
│ fetch_kline(200) │    │ DELETE FROM kline_monthly │    │ get_all_monthly_changes  │
│ ≈ 10个月交易日    │    │ INSERT new bars          │    │ ORDER BY date DESC (BUG) │
│                  │    │ → 每次覆盖，数据无法积累   │    │                          │
│ 季节性分析：      │    │                          │    │ DEFAULT_SEASONAL         │
│ 每月0~1个数据点   │    │ DB唯一约束：无           │    │ = [0.8,-2.5,...] (硬编码) │
│ → 统计无意义      │    │ → 需添加 UNIQUE(code,date)│    │ → 非真实数据             │
└──────────────────┘    └──────────────────────────┘    └──────────────────────────┘
```

### 修复策略（6 项修改，按依赖关系排序）

**修改1 — 排序方向修正**：

- `db_helper.py:778` `get_all_monthly_changes()`：`ORDER BY date DESC` → `ORDER BY date ASC`
- `reinject_from_db.py:48`：`ORDER BY code, date DESC` → `ORDER BY code, date ASC`

**修改2 — 扩大数据拉取范围**：

- `sync_all.py:54` `fetch_kline` 默认 limit：`200` → `2000`，覆盖约 8 年交易日

**修改3 — 存储模式改为累积**：

- `db_helper.py:801-806` `upsert_kline_daily`：DELETE+INSERT → `INSERT OR REPLACE`
- `db_helper.py:808-813` `upsert_kline_monthly`：DELETE+INSERT → `INSERT OR REPLACE`
- 前提：需要确保 `kline_daily` 和 `kline_monthly` 表有 UNIQUE(code, date) 约束
- `migrate_to_sqlite.py:30-34`：需要在表定义上添加 UNIQUE 约束（或通过 ALTER TABLE 添加）

**修改4 — 季节性规律真实计算**：

- 新增 `_calc_seasonal_pct(code)` 函数：从 `kline_monthly` 按月分组求算术平均，返回 12 个原始百分比值
- 复用 `_calc_seasonal_from_db()` 的数据分组逻辑，但输出原始均值而非缩放因子
- `sync_all.py:535` Step 7：用 `_calc_seasonal_pct(code)` 替换 `DEFAULT_SEASONAL` 硬编码

### 实现细节

#### 数据库唯一约束变更

当前 `kline_daily` 和 `kline_monthly` 表仅有索引 `idx_kd_code_date` / `idx_km_code_date`，无 UNIQUE 约束。INSERT OR REPLACE 依赖 UNIQUE 约束才能正确去重。

**方案**：在 `migrate_to_sqlite.py` 中将索引改为 UNIQUE 约束，或在 `db_helper.py` init 函数中通过 `CREATE UNIQUE INDEX IF NOT EXISTS` 创建唯一索引。采用后者可在不重建表的前提下实现。

```sql
-- 在 db_helper.py 的数据库初始化中添加
CREATE UNIQUE INDEX IF NOT EXISTS idx_kd_code_date_u ON kline_daily(code, date);
CREATE UNIQUE INDEX IF NOT EXISTS idx_km_code_date_u ON kline_monthly(code, date);
```

#### _calc_seasonal_pct 函数设计

```python
def _calc_seasonal_pct(code: str) -> list:
    """从 kline_monthly 按月计算真实平均涨跌幅百分比，返回12个浮点数。"""
    db = get_db()
    rows = db.execute(
        "SELECT date, change_pct FROM kline_monthly WHERE code=? AND change_pct != 0 ORDER BY date",
        [code]
    ).fetchall()
    db.close()
    month_stats = defaultdict(list)
    for r in rows:
        m = int(r[0][5:7])  # 从 "YYYY-MM-DD" 提取月份
        month_stats[m].append(r[1])
    return [round(sum(month_stats.get(m, [])) / len(month_stats[m]), 2) if month_stats.get(m) else 0.0
            for m in range(1, 13)]
```

#### sync_all.py 关键修改点

```python
# 调用处修改 (line 84)
kdata = fetch_kline(f'{mkt}{code}', limit=2000)  # 从 limit=200 改为传入 2000
```

```python
# Step 7 修改 (line 531-537)
# 删除：DEFAULT_SEASONAL = [0.8, -2.5, 1.2, 0.5, -1.0, 2.3, 3.5, -1.8, 1.5, 2.8, -1.2, 3.0]
# 替换 upsert_seasonal(code, DEFAULT_SEASONAL) 为：
real_seasonal = _calc_seasonal_pct(code)
upsert_seasonal(code, real_seasonal)
```

#### 性能与风险考量

- **首次 2000 条拉取**：单只股票约 2-4 秒，多只股票通过 ThreadPoolExecutor 并行，总耗时在可接受范围
- **INSERT OR REPLACE 性能**：比 DELETE+INSERT 略慢（需检查唯一约束），但 2000 行规模下差异可忽略
- **向后兼容**：`_calc_seasonal_from_db()` 保持不变；前端 kline.js 无需改动；`get_all_monthly_changes()` 返回格式不变
- **迁移安全**：首次运行新 `upsert_kline_monthly` 前需确保唯一索引存在，否则 INSERT OR REPLACE 会退化为普通 INSERT 导致重复数据。建议在 `db_helper.py` 的 `get_db()` 或初始化函数中添加索引创建逻辑

## 使用的技能

### Skill: using-superpowers

- **目的**：确保在实现计划时遵循最佳实践，使用场景化技能进行代码审查和验证
- **预期结果**：在代码实现前完成 plan 生成，执行时通过 subagent-driven-development 协调多文件修改

### SubAgent: code-explorer

- **目的**：在实现阶段深度探索相关代码文件，确保修改点的精确性和完整性
- **预期结果**：验证所有 6 个修改点前后文正确，不遗漏影响范围