---
name: monthly-returns-seasonal-patterns
overview: 修复月度涨跌幅的排序顺序（升序），并将季节性规律从硬编码默认值改为基于真实月度涨跌幅数据计算月均涨跌幅%。
todos:
  - id: fix-sort-db-helper
    content: 修改 db_helper.py 中 get_all_monthly_changes() 的 SQL 排序为 ORDER BY date ASC
    status: pending
  - id: fix-sort-reinject
    content: 修改 reinject_from_db.py 第48行 kline_monthly 查询排序为 ORDER BY code, date ASC
    status: pending
  - id: add-seasonal-pct-func
    content: 在 sync_all.py 中新增 _calc_seasonal_pct() 函数，从 kline_monthly 按月计算真实平均涨跌幅百分比
    status: pending
  - id: replace-default-seasonal
    content: 修改 sync_all.py Step 7，用 _calc_seasonal_pct() 真实计算结果替换 DEFAULT_SEASONAL 硬编码写入 seasonal 表
    status: pending
    dependencies:
      - add-seasonal-pct-func
---

## 用户需求

在K线走势功能中，实现月度涨跌幅与季节性规律的正确数据处理逻辑。

## 核心功能

1. **月度涨跌幅排序修正**：月度涨跌幅数据必须严格按照月份从旧到新的时间顺序进行升序排列展示，确保图表的时间轴方向与直觉一致
2. **季节性规律真实计算**：季节性规律（月均涨跌幅%）必须直接依赖于上述已计算出的月度涨跌幅数据进行统计与求均值计算，替代当前硬编码的假数据，确保数据的准确性与逻辑关联

## 技术栈

- 后端：Python + SQLite (db_helper.py / sync_all.py / reinject_from_db.py)
- 前端：原生 JavaScript + Chart.js (kline.js)
- 数据流：kline_monthly 表 → Python 计算 → seasonal 表 → server.py 注入 → DATA 对象 → 前端 Chart.js 渲染

## 实现方案

### 当前数据流问题分析

```
kline_monthly表                        seasonal表
┌──────────┬────────────┐             ┌───────┬────────────────┐
│ date     │ change_pct │     Step7   │ code  │ factors (JSON) │
│ 2024-01  │    +2.3    │  ────────→  │601166 │ [0.8,-2.5,...]│
│ 2024-02  │    -1.5    │  硬编码写入 │       │ ← 非真实数据   │
│ ...      │    ...     │             │       │                │
└──────────┴────────────┘             └───────┴────────────────┘

monthly_changes数据流
kline_monthly → db_helper.get_all_monthly_changes() → DESC排序 → server.py → 前端
                                                        ↑BUG: 应为ASC
```

### 修复策略

三处精确修改，使数据流贯通：

**修改1 — 排序方向修正**：

- `db_helper.py` `get_all_monthly_changes()`：`ORDER BY date DESC` → `ORDER BY date ASC`
- `reinject_from_db.py` 第48行：`ORDER BY code, date DESC` → `ORDER BY code, date ASC`

**修改2 — 季节性规律真实计算**：

- 新增 `_calc_seasonal_pct()` 函数，从 `kline_monthly` 表读取 `change_pct`，按月分组求均值，返回12个原始百分比值（如 [+2.3, -1.5, +0.8, ...]）
- `sync_all.py` Step 7 中用 `_calc_seasonal_pct(code)` 替换 `DEFAULT_SEASONAL`
- 保留已有 `_calc_seasonal_from_db()` 函数不变（用于预测信号的缩放因子计算）

### 实现细节

#### 执行要点

1. **`_calc_seasonal_pct()` 函数**：仿照 `_calc_seasonal_from_db()` 结构，抽取 `kline_monthly` 中 `change_pct`，按月分组求算术平均，返回 `[float, ...]` 共12个值（1月~12月），月份无数据时用 `0` 填充
2. **排序修改要点**：仅改 SQL 排序方向，不改数据结构或其他逻辑
3. **`sync_all.py` Step 7**：将 `upsert_seasonal(code, DEFAULT_SEASONAL)` 替换为 `upsert_seasonal(code, _calc_seasonal_pct(code))`，删除 `DEFAULT_SEASONAL` 常量

#### 性能考量

- `_calc_seasonal_pct()` 与 `_calc_seasonal_from_db()` 查询相同的 `kline_monthly` 表，可考虑合并为一次查询。但由于 Step 7 与 Step 5-6 分离执行，且每只股票每月数据量很小（通常 < 100 行），两次查询对性能影响可忽略
- 排序方向从 DESC 改为 ASC 不影响查询性能，数据库索引可同样利用

#### 日志与错误处理

- `_calc_seasonal_pct()` 对无数据股票返回全零数组，避免 None/异常导致流程中断
- 复用现有 `upsert_seasonal()` 的错误静默处理（`except Exception: pass`）

#### 向后兼容

- `_calc_seasonal_from_db()` 保持不变，预测信号功能不受影响
- 前端 `kline.js` 无需修改，`DATA.seasonal[code]` 读取的数据语义不变（12个浮点数数组），仅数值从硬编码变为真实计算值
- `get_all_monthly_changes()` 返回格式不变 `[[date, change_pct], ...]`，仅顺序变化