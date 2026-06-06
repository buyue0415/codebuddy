# 模块12: 数据迁移与系统审计

> **核心文件**: ~~`scripts/migrate_to_sqlite.py`~~ (一次性迁移，已完成) | `scripts/audit_system.py` (审计)

---

## 子模块 A: 数据迁移

### A.1 功能概述

一次性将 V0.5 的 JSON 文件存储迁移到 SQLite 数据库，创建完整的 17 表 Schema。**已执行完成**，后续增量维护由 [同步引擎](./03-sync-engine.md) 和 [数据库访问层](./02-database-layer.md) 负责。

### A.2 执行步骤（已执行，仅参考）

```
1. 删除旧 stock.db（如存在）
2. 创建 WAL 模式 + 外键约束的数据库
3. 创建 17 张表 + 7 个索引
4. 逐表迁移数据:
   a_stocks.json → stocks 表
   watchlist.json → watchlist 表
   system_data.json → kline_daily, kline_monthly, quotes, daily_predictions, ...
   broker_statement.json → positions, closed_positions, trades, dividends
```

### A.3 源文件依赖

| 文件 | 用途 | 状态 |
|------|------|------|
| `data/system_data.json` | 核心数据（K线/预测/学习/持仓/新闻/报告） | ✅ 保留（旧版兼容读） |
| `data/a_stocks.json` | A 股全列表 | ✅ 保留 |
| `data/watchlist.json` | 自选股 | ✅ 保留 |
| `data/broker_statement.json` | 券商对账单 | ✅ 保留 |

---

## 子模块 B: 系统审计

### B.1 功能概述

巡检系统数据完整性，打印每只自选股在各数据维度的状态摘要，用于日常健康检查和问题排查。

**当前行为**: `audit_system.py` V0.9 版本直接查询 SQLite，输出自选股全维度数据摘要。

### B.2 审计维度

| 维度 | 检查内容 | 缺失标识 |
|------|---------|---------|
| quotes | 价格 / 涨跌幅 | `?` |
| kline_daily | K 线条数 / 日期范围 | `MISSING` |
| daily_predictions | 预测数量 / 最新日期 / 回填状态 | `NO predictions` / `pending` |
| learning_params | update_count / mw_beta / lr | `MISSING` |
| accuracy_stats | 近 20 日方向命中统计 | `0/0` |
| 其他 | positions/trades/news/expert_reports/kline 数量 | 摘要统计 |

### B.3 输出

标准输出，格式化的审计报表。可通过 `GET /api/audit` 在 Web 端查看。

### B.4 依赖关系

| 方向 | 模块 |
|------|------|
| **依赖** | `data/stock.db`（SQLite 直接查询） |
| **依赖** | `scripts/db_helper.py`（数据读取） |
| **触发** | `GET /api/audit` → `run_script("audit_system.py")` |
| **性质** | 巡检工具，不影响任何数据 |
