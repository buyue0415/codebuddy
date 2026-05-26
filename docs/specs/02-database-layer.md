# 模块2: 数据库访问层

> **核心文件**: `scripts/db_helper.py` | **数据库**: `data/stock.db` | **表数**: 17

---

## 1. 功能概述

SQLite 数据库的唯一读写入口，封装所有数据表的 CRUD 操作。提供单条/批量查询函数供 API 服务层和同步脚本使用，实现数据层与业务层的解耦。

---

## 2. 核心业务逻辑

### 2.1 连接管理
- 使用 `sqlite3.connect(data/stock.db)` 建立连接
- `row_factory = sqlite3.Row` 使查询结果支持字典式访问
- 每次操作独立获取连接，操作后及时关闭（不跨函数共享连接对象）
- ROOT 路径基于脚本文件位置上溯两级计算

### 2.2 查询函数（18个）

| 函数 | 输入 | 输出 | 说明 |
|------|------|------|------|
| `get_stock_search(keyword)` | 搜索关键词 | `[{code, name, market, py}]` ×15 | A股模糊搜索，含拼音匹配 |
| `get_watchlist()` | — | `[{code, name, market}]` | 按 sort_order 排序 |
| `get_watchlist_codes()` | — | `["601166",...]` | 仅代码列表 |
| `get_kline_daily(code)` | 6位代码 | `[[date, open, close, high, low]]` | 单股票日K线 |
| `get_kline_monthly(code)` | 6位代码 | `[[date,open,high,low,close,volume,change_pct]]` | 仅含月度首日(day=01) |
| `get_quotes()` | — | `{code: {price, change, open, high, low, pe, pb, dy}}` | 全部行情报价 |
| `get_positions()` | — | `{current_positions, closed_positions, all_trades}` | 持仓含分红聚合 |
| `get_daily_predictions(code)` | 6位代码 | `[{date, code, prev_close, next_day, hourly, signals, actual}]` | 含小时+信号关联 |
| `get_learning_params(code)` | 6位代码 | `{signal_weights, hourly_bias, seasonal_adj, confidence_beta, learning_rate, mw_beta, update_count}` | 单股票学习参数 |
| `get_accuracy_stats(code)` | 6位代码 | `{period: {direction, range, hourly}}` | 单股票准确率 |
| `get_news(filter_type)` | `"all"` / `"major"` / `"<code>"` | `[{date, code, title, summary, source, sentiment, major}]` | 新闻过滤查询 |
| `get_expert_reports()` | — | `[{date, stocks: {...}}]` | 专家报告，JSON反序列化 |
| `get_seasonal(code)` | 6位代码 | `[factor×12]` | 12个月季节因子 |
| `get_config()` | — | `{account, broker, server_port, fee_rates, ...}` | 从 `data/config.json` 读取 |
| `get_current_positions()` | — | `{code: {..., trades, total_commission, ...}}` | 含交易费用汇总 |
| `get_closed_positions()` | — | `{code: {..., realized_pnl, trades, ...}}` | 含费用汇总 |
| `get_trades(code?)` | 6位代码 (可选) | `[{date, time, code, name, type, qty, price, ..., fees}]` | 含实时费用计算 |
| `get_dividends(code?)` | 6位代码 (可选) | `[{date, code, amount, price, per_share}]` | 含每股分红计算 |

### 2.3 批量查询函数（7个）

| 函数 | 默认范围 | 说明 |
|------|---------|------|
| `get_all_kline_daily(codes?)` | 全部watchlist | 批量日K线 |
| `get_all_kline_monthly(codes?)` | 全部watchlist | 批量月K线 |
| `get_all_predictions(codes?)` | 全部watchlist | 批量预测（含小时/信号） |
| `get_all_seasonal(codes?)` | 全部watchlist | 批量季节因子 |
| `get_all_accuracy_stats(codes?)` | 全部watchlist | 批量准确率统计 |
| `get_all_monthly_changes(codes?)` | 全部watchlist | 批量月度涨跌幅 |
| `get_all_learning_params(codes?)` | 全部watchlist | 批量学习参数 |

### 2.4 写入函数（12个）

```
add_watchlist(code, name, market)        → 追加到watchlist表 + 标记stocks.watchlist=1
remove_watchlist(code)                   → 从watchlist表删除 + 标记stocks.watchlist=0
upsert_kline_daily(code, bars)           → 先删后插，全量替换
upsert_kline_monthly(code, bars)         → 先删后插，全量替换
upsert_quotes(quotes_dict)              → INSERT OR REPLACE 逐条
upsert_news(news_list, today?)          → 当日数据先删后插
upsert_seasonal(code, factors)          → INSERT OR REPLACE
insert_daily_prediction(code, date, ...) → 插入主表 + hourly + signals 关联表
clear_today_predictions(date)           → 级联删除三表（signals→hourly→predictions）
upsert_learning_params(code, lp)        → INSERT OR REPLACE，JSON字段序列化
upsert_accuracy_stats(code, period, stats) → INSERT OR REPLACE
upsert_positions(current, closed, trades) → 全量清空重建4张表
```

### 2.5 辅助函数

| 函数 | 说明 |
|------|------|
| `_calc_fees(qty, price, config?)` | 根据配置费率计算过户费、规费、经手费 |
| `_shares_before_date(code, date)` | 计算指定日期前的持仓股数（用于每股分红计算） |

---

## 3. 数据完整性约束

> 以下约束在代码中通过逻辑保证，SQLite Schema 层面未全部实现外键约束。

| 约束 | 实现位置 |
|------|---------|
| `kline_daily.code ⊆ watchlist.code` | DELETE级联: `server.py:541-548` |
| `daily_predictions.code ⊆ watchlist.code` | 同上 |
| `quotes.code ⊆ watchlist.code` | 同上 |
| `prediction_hourly.pred_id → daily_predictions.id` | Schema外键: `migrate_to_sqlite.py:40` |
| `prediction_signals.pred_id → daily_predictions.id` | Schema外键: `migrate_to_sqlite.py:43` |

---

## 4. 依赖关系

| 方向 | 模块 | 方式 |
|------|------|------|
| **依赖库** | `sqlite3`, `json`, `os` | Python标准库 |
| **被依赖** | [Web API层](./01-api-server.md) | `from db_helper import ...` |
| **被依赖** | [同步引擎](./03-sync-engine.md) | 多函数导入 |
| **被依赖** | [新闻抓取](./07-news-fetcher.md) | `get_watchlist`, `get_db` |
| **被依赖** | [数据注入](./11-data-injection.md) | 直接使用 `sqlite3` 连接 |
| **被依赖** | [数据迁移](./12-migration-and-audit.md) | 直接使用 `sqlite3` 连接 |

---

## 5. 异常处理机制

- **查询函数**: 不封装 try/except，异常向上传播由调用方处理
- **写入函数**: 使用参数化查询 `?` 占位符防止 SQL 注入
- **字典访问**: get() 系列返回空/默认值而非抛异常（如 `lp.get('signal_weights', {})`）
- **连接管理**: 在函数内部打开和关闭，异常时连接自动回收
- **JSON字段**: 写入时 `json.dumps()` 序列化，读取时 `json.loads()` 反序列化
