# 模块12: 数据迁移与系统审计

> **核心文件**: `scripts/migrate_to_sqlite.py` (迁移), `scripts/audit_system.py` (审计)

---

## 子模块 A: 数据迁移

### A.1 功能概述

一次性将 V0.5 的 JSON 文件存储迁移到 SQLite 数据库，创建完整的 17 表 Schema。**仅为一次性执行脚本**，后续增量维护由 [同步引擎](./03-sync-engine.md) 和 [数据库访问层](./02-database-layer.md) 负责。

### A.2 执行步骤

```
1. 删除旧 stock.db（如存在）
2. 创建 WAL 模式 + 外键约束的数据库
3. 创建 17 张表 + 7 个索引
4. 逐表迁移数据:
   a_stocks.json → stocks 表
   watchlist.json → watchlist 表
   system_data.json → kline_daily, kline_monthly, quotes, daily_predictions,
                       prediction_hourly, prediction_signals, learning_params,
                       accuracy_stats, trades, positions, closed_positions,
                       dividends, news, expert_reports, seasonal
   broker_statement.json → positions, closed_positions, trades, dividends
```

### A.3 数据完整性处理

| 场景 | 处理 |
|------|------|
| `watchlist_codes` 标记 | `stocks.watchlist` 字段设为 1 |
| 预测迁移 | 同时迁移 `prediction_hourly` 和 `prediction_signals` 关联表 |
| 布尔值转换 | `dir_hit`/`range_hit` → `1`/`0`/`NULL` |
| hourly_hit 索引映射 | 按 block 名称映射到 4 个固定位置 |

### A.4 源文件依赖

| 文件 | 用途 |
|------|------|
| `data/system_data.json` | 核心数据（K线/预测/学习/持仓/新闻/报告） |
| `data/a_stocks.json` | A 股全列表 |
| `data/watchlist.json` | 自选股 |
| `data/broker_statement.json` | 券商对账单 |

### A.5 异常处理

无 try/except — 一次性脚本，失败则中断以确保数据完整性。

---

## 子模块 B: 系统审计

### B.1 功能概述

巡检系统数据完整性，打印每只自选股在各数据维度的状态摘要，用于日常健康检查和问题排查。

> ⚠️ **注意**: `audit_system.py` 读取的是 `data/system_data.json`（遗留 JSON），不直接查询 SQLite。

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
| **依赖** | `data/system_data.json` |
| **触发** | `GET /api/audit` → `run_script("audit_system.py")` |
| **性质** | 巡检工具，不影响任何数据 |
