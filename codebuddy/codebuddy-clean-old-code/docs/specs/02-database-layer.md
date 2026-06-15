# 02 — 数据库与存储方案

> **核心文件**: `scripts/db_helper.py` (75KB) | **数据库**: `data/stock.db`
> **模式**: WAL（Write-Ahead Log）| **表数**: 20+

---

## 1. 业务需求说明书

### 1.1 业务背景

系统所有业务数据（行情、K线、预测、持仓、交易、新闻等）需要统一持久化存储。选型要求：轻量（单文件）、零配置、本地运行、支持并发读写。

### 1.2 核心目标

| 目标 | 说明 |
|------|------|
| 唯一读写入口 | 所有模块通过 `db_helper.py` 访问数据库 |
| CRUD 封装 | 19 个查询 + 7 个批量查询 + 13 个写入函数 |
| 数据完整性 | 参数化查询防注入、逻辑外键约束 |
| 并发安全 | WAL 模式：读写不互斥，写写串行 |

---

## 2. 技术方案深度分析

### 2.1 为什么 SQLite？

| 维度 | 评估 |
|------|------|
| 部署复杂度 | 零配置，单文件 `stock.db` |
| 性能 | 本地查询 <1ms，7 只股票万条数据完全够用 |
| 并发 | WAL 模式支持读并发，单用户写串行无瓶颈 |
| 备份 | 复制一个文件即完成全量备份 |

### 2.2 连接管理策略

```python
def get_db():
    db = sqlite3.connect(os.path.join(ROOT, "data", "stock.db"), timeout=10)
    db.row_factory = sqlite3.Row  # 字典式访问
    db.execute("PRAGMA journal_mode=WAL")
    return db

# 每次操作独立获取连接，操作后及时关闭
# 不在函数间共享连接对象
```

### 2.3 表设计原则

- **分析层**（9 表）：watchlist, kline_daily, kline_monthly, daily_predictions, prediction_hourly, prediction_signals, learning_params, accuracy_stats, seasonal
- **行情层**（2 表）：quotes, news
- **交易层**（6 表）：positions, closed_positions, trades, dividends, expert_reports, stocks
- **模拟交易层**（6 表）：paper_account, paper_positions, paper_trades, paper_daily_snapshot, paper_suggestions, **intraday_quotes**
- **回测层**（1 表）：backtest_runs
- **形态层**（1 表）：pattern_rules

---

## 3. 功能介绍和实现方式

### 3.1 查询函数（22个）

| 函数 | 输入 | 输出 | 行 |
|------|------|------|-----|
| `get_stock_search(keyword)` | 关键词 | 全A股模糊搜索结果×15 | `:20` |
| `get_watchlist()` | — | 自选股列表 | `:27` |
| `get_watchlist_codes()` | — | 仅代码列表 | `:31` |
| `get_kline_daily(code)` | 6位代码 | 日K线 O/H/L/C 数组 | `:48` |
| `get_quotes()` | — | 全部行情报价字典 | `:64` |
| `get_quotes_batch(db, codes)` | 代码列表 | 批量行情 | `:70` |
| `get_daily_predictions_batch(db, codes, date)` | 代码+日期 | 批量预测 | `:84` |
| `get_positions()` | — | 持仓+已平仓+交易完整数据 | `:105` |
| `get_daily_predictions(code)` | 6位代码 | 含小时+信号关联 | `:129` |
| `get_learning_params(code)` | 6位代码 | MWU权重+偏置+季节因子 | `:151` |
| `get_accuracy_stats(code)` | 6位代码 | last_20/last_60准确率 | `:164` |
| `get_news(filter_type)` | "all"/"major"/代码 | 新闻过滤 | `:176` |
| `get_quotes_by_date(date_str)` | 日期字符串 | 历史日期行情字典 | `:54` |
| `get_intraday_quotes(code, date)` | 代码+日期 | 分钟分时数据（支持日K线降级） | `:1725` |
| `get_intraday_dates_for_code(code, limit)` | 代码+上限 | 有分钟或K线数据的日期列表 | `:1770` |
| `get_expert_reports()` | — | 专家报告JSON | `:195` |
| `get_seasonal(code)` | 6位代码 | 12个月因子 | `:201` |
| `get_config()` | — | 从config.json读取 | `:209` |
| `get_current_positions()` | — | 当前持仓含费用 | `:227` |
| `get_closed_positions()` | — | 已清仓含费用 | `:273` |
| `get_trades(code?)` | 可选代码 | 含实时费用计算 | `:306` |
| `get_dividends(code?)` | 可选代码 | 含每股分红计算 | `:665` |

### 3.2 批量查询函数（7个）

`get_all_kline_daily` `get_all_kline_monthly` `get_all_predictions` `get_all_seasonal` `get_all_accuracy_stats` `get_all_monthly_changes` `get_all_learning_params`

### 3.3 写入函数（13个）

`add_watchlist` `remove_watchlist` `upsert_kline_daily` `upsert_kline_monthly` `upsert_quotes` `upsert_news` `upsert_seasonal` `insert_daily_prediction` `clear_today_predictions` `upsert_learning_params` `upsert_accuracy_stats` `upsert_positions` `insert_daily_predictions_batch`

### 3.4 数据完整性

```python
# 参数化查询（全部使用 ? 占位符）
db.execute("SELECT * FROM kline_daily WHERE code=? ORDER BY date", [code])

# 写入全量替换（先删后插）
db.execute("DELETE FROM kline_daily WHERE code=?", [code])
db.executemany("INSERT INTO kline_daily (...)", bars)

# JSON字段序列化
json.dumps(lp['signal_weights'])  # 写入
json.loads(row['signal_weights']) # 读取
```

---

## 4. 用户操作流程

数据库层对用户透明，无需用户操作。数据写入通过以下路径触发：

```
用户添加自选股    → add_watchlist()
定时sync_all.py  → upsert_kline_daily/insert_daily_prediction/...
上传对账单       → upsert_positions()
运行回测         → upsert_learning_params()
纸面交易执行     → INSERT paper_* 表
```

---

## 5. 依赖关系

| 方向 | 模块 | 方式 |
|------|------|------|
| 依赖库 | sqlite3, json, os | Python 标准库 |
| 被依赖 | server_v2.py | `from db_helper import ...` |
| 被依赖 | sync_all.py | 多函数导入 |
| 被依赖 | fetch_news.py | `get_watchlist`, `get_db` |
| 被依赖 | paper_trading.py | 纸面交易 CRUD |
| 被依赖 | backtest_engine.py | K线/学习参数读写 |
