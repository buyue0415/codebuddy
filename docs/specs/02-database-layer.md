# 02 — 数据库与存储方案

> **核心文件**: `scripts/db_helper.py` (~100KB) | **数据库**: `data/stock.db`
> **库**: sqlite3 (Python 标准库) | **模式**: WAL (Write-Ahead Log) | **表数**: 27+
> **无 ORM** | **遗留文件**: `data/system_data.json` / `broker_statement.json` (过渡中)

---

## 1. 业务需求说明书

### 1.1 业务背景

系统所有业务数据（行情、K线、预测、持仓、交易、新闻、公司关系、纸面交易、回测等）需要统一持久化存储。选型要求轻量、零配置、本地运行、支持并发读。

### 1.2 核心目标

| 目标 | 说明 |
|------|------|
| 唯一读写入口 | 所有模块通过 `db_helper.py` 访问数据库 |
| CRUD 封装 | 30+ 查询函数 + 12+ 写入函数 |
| 数据完整性 | 参数化查询防注入、UNIQUE 索引防重复、事务原子性 |
| 并发安全 | WAL 模式：读写不互斥，写写串行 |
| Schema 演进 | 在线迁移：PRAGMA table_info → ALTER TABLE ADD COLUMN |

---

## 2. 数据库设计原则

### 2.1 选型分析

| 维度 | SQLite | MySQL | PostgreSQL |
|------|--------|-------|------------|
| 部署 | 零配置 | 需安装服务 | 需安装服务 |
| 备份 | 复制单文件 | mysqldump | pg_dump |
| 并发 | WAL支持读并行 | 行级锁 | MVCC |
| 适用场景 | 单用户本地 | 多用户服务器 | 复杂分析 |

### 2.2 连接管理

```python
def get_db():
    db = sqlite3.connect(DB_PATH, timeout=10)
    db.row_factory = sqlite3.Row  # 字典式访问
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=5000")
    # 每条操作独立获取连接，操作后及时关闭
    return db
```

### 2.3 表分类

| 层级 | 表 | 用途 |
|------|-----|------|
| 基础 | stocks, watchlist | A股全量列表、自选股 |
| 行情 | quotes | 实时行情快照 |
| K线 | kline_daily, kline_monthly | 日K和月K |
| 交易 | positions, closed_positions, trades, dividends | 券商交易数据 |
| 预测 | daily_predictions, prediction_hourly, prediction_signals | ML预测 |
| 学习 | learning_params, accuracy_stats, seasonal | 自学习参数 |
| 新闻 | news | 股票新闻 |
| 专家 | expert_reports | AI专家报告 |
| 形态 | pattern_rules | K线形态规则 |
| 关系 | company_relations, company_business | 公司关系图谱 |
| 回测 | backtest_runs | 回测运行记录 |
| 纸面交易 | paper_account, paper_positions, paper_trades, paper_daily_snapshot, paper_suggestions, paper_suggestions_history, intraday_quotes | 模拟交易 |
| ML | ml_models | 存储ML模型 |

---

## 3. 表结构详解

### stocks — A股全量列表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| code | TEXT | PK | 6位股票代码 |
| name | TEXT | NOT NULL | 股票名称 |
| market | TEXT | | sh / sz |
| py | TEXT | | 拼音首字母 |

数据来源：`a_stocks.json`（4596只A股）。

### watchlist — 自选股

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| code | TEXT | PK | 6位代码 |
| name | TEXT | | 股票名称 |
| market | TEXT | | sh / sz |

### kline_daily — 日K线

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| code | TEXT | NOT NULL | 股票代码 |
| date | TEXT | NOT NULL | YYYY-MM-DD |
| open | REAL | | 开盘价（前复权） |
| high | REAL | | 最高价 |
| low | REAL | | 最低价 |
| close | REAL | | 收盘价 |
| volume | REAL | | 成交量（股） |
| amount | REAL | | 成交额（元） |
| change_pct | REAL | | 涨跌幅% |

UNIQUE(code, date)。数据通过 ThreadPoolExecutor 4并发从 Westock/NeoData 采集。

### kline_monthly — 月K线

同 kline_daily 结构，以月线聚合。

### quotes — 实时行情

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| code | TEXT | PK | 股票代码 |
| price | REAL | | 当前价格 |
| change | REAL | | 涨跌额 |
| change_pct | REAL | | 涨跌幅% |
| open | REAL | | 开盘价 |
| high | REAL | | 最高价 |
| low | REAL | | 最低价 |
| volume | REAL | | 成交量 |
| amount | REAL | | 成交额 |
| pe | REAL | | 市盈率 |
| pb | REAL | | 市净率 |
| dy | REAL | | 股息率% |

注：PE/PB/DY 在部分数据源中可能为 0（无实时源）。

### positions — 当前持仓

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| code | TEXT | PK | 股票代码 |
| name | TEXT | | 股票名称 |
| qty | INTEGER | | 持仓股数 |
| avg_cost | REAL | | 平均成本价 |
| total_cost | REAL | | 总成本 |
| total_commission | REAL | | 总佣金 |
| total_stamp_tax | REAL | | 总印花税 |
| total_other_fees | REAL | | 其他费用 |

### closed_positions — 已清仓持仓

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| code | TEXT | PK | 股票代码 |
| name | TEXT | | 股票名称 |
| realized_pnl | REAL | | 已实现盈亏 |
| dividends_total | REAL | | 分红合计 |
| total_commission | REAL | | 总佣金 |
| total_stamp_tax | REAL | | 总印花税 |
| total_other_fees | REAL | | 其他费用 |

### trades — 交易流水

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK AUTO | |
| date | TEXT | | 日期 YYYY-MM-DD |
| time | TEXT | | 时间 HH:MM:SS |
| code | TEXT | | 股票代码 |
| name | TEXT | | 股票名称 |
| type | TEXT | | buy / sell / dividend |
| qty | INTEGER | | 数量 |
| price | REAL | | 价格 |
| commission | REAL | | 佣金 |
| stamp_tax | REAL | | 印花税 |
| transfer_fee | REAL | | 过户费 |
| settlement | REAL | | 清算金额 |

### daily_predictions — 日预测

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| code | TEXT | | 股票代码 |
| date | TEXT | | 预测日期 |
| direction | TEXT | | bullish / bearish / neutral |
| pred_price | REAL | | 预测收盘价 |
| confidence | REAL | | 置信度 0-1 |
| lower_bound | REAL | | 预测下限 |
| upper_bound | REAL | | 预测上限 |
| suggestion | TEXT | | 操作建议 |

### news — 新闻

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK AUTO | |
| code | TEXT | | 股票代码 |
| title | TEXT | | 标题 |
| summary | TEXT | | 摘要 |
| source | TEXT | | 来源 |
| sentiment | TEXT | | bullish / bearish / neutral |
| date | TEXT | | 日期 |
| url | TEXT | | 原文链接 |
| is_major | INTEGER | | 是否重大事件 |

### expert_reports — 专家报告

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK AUTO | |
| code | TEXT | | 股票代码 |
| date | TEXT | | 报告日期 |
| summary | TEXT | | 摘要 |
| decision | TEXT | | buy / hold / sell |
| confidence | REAL | | 信心值 0-100 |
| risk_level | INTEGER | | 风险等级 1-5 |
| data | TEXT | | 完整 JSON 数据 |

### pattern_rules — 形态规则

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK AUTO | |
| name | TEXT | | 规则名称 |
| description | TEXT | | 规则描述 |
| buy_signal | TEXT | | 买入信号条件 |
| sell_signal | TEXT | | 卖出信号条件 |
| priority | INTEGER | | 优先级 |

### backtest_runs — 回测记录

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK AUTO | |
| status | TEXT | | running / completed / cancelled |
| progress | INTEGER | | 进度 0-100 |
| train_window | INTEGER | | 训练窗口天数 |
| test_window | INTEGER | | 测试窗口天数 |
| codes | TEXT | | 回测股票列表 |
| started_at | TEXT | | 开始时间 |
| finished_at | TEXT | | 完成时间 |

### paper_trading 系列表

**paper_account**: id, balance, initial_capital, market_value, total_pnl, total_commission, total_trades, created_at, last_sync
**paper_positions**: code, name, qty, avg_cost, current_price
**paper_trades**: id, code, date, action, price, qty, before_qty, commission, slippage, pnl
**paper_suggestions**: id, code, date, direction, price, confidence, reason
**paper_suggestions_history**: 同 suggestions 带时间戳归档

---

## 4. 数据访问层

### 4.1 查询函数

| 函数 | 返回 | 底层 SQL |
|------|------|----------|
| get_watchlist() | list| SELECT FROM watchlist |
| get_quotes() | dict{code: data} | SELECT FROM quotes |
| get_all_kline_daily() | dict{code: list} | SELECT FROM kline_daily |
| get_kline_daily(code) | list | WHERE code=? ORDER BY date |
| get_kline_monthly(code) | list | WHERE code=? ORDER BY date |
| get_positions() | dict| SELECT FROM positions |
| get_closed_positions() | dict| SELECT FROM closed_positions |
| get_all_trades() | list | SELECT FROM trades ORDER BY date, time |
| get_dividends() | list | SELECT FROM dividends |
| get_predictions(code) | list | SELECT FROM daily_predictions |
| get_prediction_signals(code, date) | list | WHERE code=? AND date=? |
| get_accuracy(code) | dict | SELECT FROM accuracy_stats |
| get_news() | list | SELECT FROM news ORDER BY date DESC |
| get_expert_reports() | list | SELECT FROM expert_reports ORDER BY date |
| get_pattern_rules() | list | SELECT FROM pattern_rules ORDER BY priority |
| get_seasonal(code) | list | SELECT FROM seasonal |
| get_company_relations(code) | list | JOIN company_relations AND stocks |
| get_graph_data() | list | 完整图谱节点+边 |
| get_industries() | list | SELECT FROM stocks GROUP BY industry |
| get_industry_stocks(industry) | list | SELECT FROM stocks WHERE industry=? |
| get_paper_account() | dict | SELECT FROM paper_account |
| get_paper_positions() | dict | SELECT FROM paper_positions |

### 4.2 写入函数

| 函数 | 用途 |
|------|------|
| save_watchlist(code, name, market) | 添加自选股 |
| remove_watchlist(code) | 删除自选股 |
| save_kline_daily(code, bars) | 批量写入日K线 |
| save_kline_monthly(code, bars) | 批量写入月K线 |
| save_quotes(quotes_dict) | 更新行情快照 |
| save_predictions(code, predictions) | 批量写入预测 |
| save_accuracy(code, stats) | 更新准确率 |
| save_news(news_list) | 批量写入新闻 |
| save_expert_report(report) | 保存专家报告 |
| save_pattern_rule(rule) | 创建形态规则 |
| update_pattern_rule(id, rule) | 更新形态规则 |
| delete_pattern_rule(id) | 删除形态规则 |
| save_paper_trade(trade) | 记录纸面交易 |
| update_paper_account(balance, mv) | 更新账户 |
| save_paper_suggestion(suggestion) | 保存交易建议 |
| save_company_relation(relation) | 保存公司关系 |
| save_backtest_run(params) | 创建回测记录 |
| update_backtest_status(id, status) | 更新回测状态 |

---

## 5. 遗留数据处理

旧版使用 JSON 文件存储数据，当前版本以 SQLite 为主：

| 遗留文件 | 状态 | 说明 |
|----------|------|------|
| `data/system_data.json` | 仅读取 | 旧版全量系统数据，仍在读取 |
| `data/broker_statement.json` | 读+写 | 券商对账单缓存，同时同步写入 SQLite |
| `data/a_stocks.json` | 仅读取 | A股列表来源 |
| `data/config.json` | 读+写 | 系统配置 |

---

## 6. 数据流图

```
对账单上传 → update_from_statement.py → SQLite (positions/trades/dividends)
                                          ↕
sync_all.py → fetch_news.py              → SQLite (news)
            → 并行K线采集                → SQLite (kline_daily/monthly)
            → 预测回填                   → SQLite (daily_predictions)
            → 重算准确率                 → SQLite (accuracy_stats)
            → 自学习                     → SQLite (learning_params)
            → 生成10日预测               → SQLite (daily_predictions)
            → 季节性因子                 → SQLite (seasonal)
行情刷新 → subprocess quotes_refresh    → SQLite (quotes)

前端请求 → db_helper 查询 → SQLite → JSON response
```
