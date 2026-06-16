# 附录 A — 数据库 Schema

> **关联规范**: [02-database-layer.md](02-database-layer.md)
> **数据库**: `data/stock.db` (SQLite WAL) | **表数**: 27+

---

## 1. 核心表

### stocks — A股全量列表

```sql
CREATE TABLE IF NOT EXISTS stocks (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    market TEXT DEFAULT 'sh',
    py TEXT DEFAULT '',
    industry TEXT DEFAULT ''
);
```

### watchlist — 自选股

```sql
CREATE TABLE IF NOT EXISTS watchlist (
    code TEXT PRIMARY KEY,
    name TEXT DEFAULT '',
    market TEXT DEFAULT 'sh'
);
```

### quotes — 实时行情

```sql
CREATE TABLE IF NOT EXISTS quotes (
    code TEXT PRIMARY KEY,
    price REAL DEFAULT 0,
    change REAL DEFAULT 0,
    change_pct REAL DEFAULT 0,
    open REAL DEFAULT 0,
    high REAL DEFAULT 0,
    low REAL DEFAULT 0,
    volume REAL DEFAULT 0,
    amount REAL DEFAULT 0,
    pe REAL DEFAULT 0,
    pb REAL DEFAULT 0,
    dy REAL DEFAULT 0
);
```

### kline_daily — 日K线

```sql
CREATE TABLE IF NOT EXISTS kline_daily (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL,
    date TEXT NOT NULL,
    open REAL DEFAULT 0,
    high REAL DEFAULT 0,
    low REAL DEFAULT 0,
    close REAL DEFAULT 0,
    volume REAL DEFAULT 0,
    amount REAL DEFAULT 0,
    change_pct REAL DEFAULT 0,
    UNIQUE(code, date)
);
```

### kline_monthly — 月K线

```sql
CREATE TABLE IF NOT EXISTS kline_monthly (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL,
    date TEXT NOT NULL,
    open REAL DEFAULT 0,
    high REAL DEFAULT 0,
    low REAL DEFAULT 0,
    close REAL DEFAULT 0,
    volume REAL DEFAULT 0,
    amount REAL DEFAULT 0,
    change_pct REAL DEFAULT 0,
    UNIQUE(code, date)
);
```

---

## 2. 交易表

### positions — 当前持仓

```sql
CREATE TABLE IF NOT EXISTS positions (
    code TEXT PRIMARY KEY,
    name TEXT DEFAULT '',
    qty INTEGER DEFAULT 0,
    avg_cost REAL DEFAULT 0,
    total_cost REAL DEFAULT 0,
    total_commission REAL DEFAULT 0,
    total_stamp_tax REAL DEFAULT 0,
    total_other_fees REAL DEFAULT 0
);
```

### closed_positions — 已清仓持仓

```sql
CREATE TABLE IF NOT EXISTS closed_positions (
    code TEXT PRIMARY KEY,
    name TEXT DEFAULT '',
    realized_pnl REAL DEFAULT 0,
    dividends_total REAL DEFAULT 0,
    total_commission REAL DEFAULT 0,
    total_stamp_tax REAL DEFAULT 0,
    total_other_fees REAL DEFAULT 0
);
```

### trades — 交易流水

```sql
CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT DEFAULT '',
    time TEXT DEFAULT '',
    code TEXT DEFAULT '',
    name TEXT DEFAULT '',
    type TEXT DEFAULT '',
    qty INTEGER DEFAULT 0,
    price REAL DEFAULT 0,
    commission REAL DEFAULT 0,
    stamp_tax REAL DEFAULT 0,
    transfer_fee REAL DEFAULT 0,
    settlement REAL DEFAULT 0
);
```

### dividends — 分红记录

```sql
CREATE TABLE IF NOT EXISTS dividends (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT DEFAULT '',
    date TEXT DEFAULT '',
    per_share REAL DEFAULT 0,
    amount REAL DEFAULT 0,
    price REAL DEFAULT 0
);
```

---

## 3. 预测与学习表

### daily_predictions — 日预测

```sql
CREATE TABLE IF NOT EXISTS daily_predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT DEFAULT '',
    date TEXT DEFAULT '',
    direction TEXT DEFAULT '',
    pred_price REAL DEFAULT 0,
    confidence REAL DEFAULT 0,
    lower_bound REAL DEFAULT 0,
    upper_bound REAL DEFAULT 0,
    suggestion TEXT DEFAULT ''
);
```

### prediction_hourly — 分时预测

```sql
CREATE TABLE IF NOT EXISTS prediction_hourly (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT DEFAULT '',
    date TEXT DEFAULT '',
    hour INTEGER DEFAULT 0,
    prices TEXT DEFAULT '[]'
);
```

### prediction_signals — 技术信号

```sql
CREATE TABLE IF NOT EXISTS prediction_signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT DEFAULT '',
    date TEXT DEFAULT '',
    signal_name TEXT DEFAULT '',
    value REAL DEFAULT 0,
    signal_type TEXT DEFAULT ''
);
```

### accuracy_stats — 准确率统计

```sql
CREATE TABLE IF NOT EXISTS accuracy_stats (
    code TEXT PRIMARY KEY,
    total_predictions INTEGER DEFAULT 0,
    direction_hits INTEGER DEFAULT 0,
    direction_rate REAL DEFAULT 0,
    range_hits INTEGER DEFAULT 0,
    range_rate REAL DEFAULT 0
);
```

### learning_params — 学习参数

```sql
CREATE TABLE IF NOT EXISTS learning_params (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT DEFAULT '',
    signal_name TEXT DEFAULT '',
    param_name TEXT DEFAULT '',
    param_value REAL DEFAULT 0
);
```

### seasonal — 季节性数据

```sql
CREATE TABLE IF NOT EXISTS seasonal (
    code TEXT DEFAULT '',
    month INTEGER DEFAULT 0,
    avg_change REAL DEFAULT 0,
    win_rate REAL DEFAULT 0,
    sample_count INTEGER DEFAULT 0
);
```

---

## 4. 信息表

### news — 新闻

```sql
CREATE TABLE IF NOT EXISTS news (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT DEFAULT '',
    title TEXT DEFAULT '',
    summary TEXT DEFAULT '',
    source TEXT DEFAULT '',
    sentiment TEXT DEFAULT 'neutral',
    date TEXT DEFAULT '',
    url TEXT DEFAULT '',
    is_major INTEGER DEFAULT 0,
    news_id TEXT DEFAULT '',
    content_status TEXT DEFAULT ''
);
```

### expert_reports — 专家报告

```sql
CREATE TABLE IF NOT EXISTS expert_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT DEFAULT '',
    date TEXT DEFAULT '',
    summary TEXT DEFAULT '',
    decision TEXT DEFAULT '',
    confidence REAL DEFAULT 0,
    risk_level INTEGER DEFAULT 3,
    data TEXT DEFAULT '{}',
    created_at TEXT DEFAULT ''
);
```

---

## 5. 形态表

### pattern_rules — 形态规则

```sql
CREATE TABLE IF NOT EXISTS pattern_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT DEFAULT '',
    description TEXT DEFAULT '',
    buy_signal TEXT DEFAULT '',
    sell_signal TEXT DEFAULT '',
    priority INTEGER DEFAULT 0
);
```

---

## 6. 公司关系表

### company_relations — 公司关系

```sql
CREATE TABLE IF NOT EXISTS company_relations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_code TEXT DEFAULT '',
    target_code TEXT DEFAULT '',
    relation_type TEXT DEFAULT '',
    weight REAL DEFAULT 0,
    source_name TEXT DEFAULT '',
    target_name TEXT DEFAULT ''
);
```

### company_business — 公司业务

```sql
CREATE TABLE IF NOT EXISTS company_business (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT DEFAULT '',
    business_type TEXT DEFAULT '',
    description TEXT DEFAULT ''
);
```

### ml_models — ML模型存储

```sql
CREATE TABLE IF NOT EXISTS ml_models (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT DEFAULT '',
    model_type TEXT DEFAULT '',
    model_data BLOB DEFAULT NULL,
    updated_at TEXT DEFAULT ''
);
```

---

## 7. 回测表

### backtest_runs — 回测运行记录

```sql
CREATE TABLE IF NOT EXISTS backtest_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    status TEXT DEFAULT 'pending',
    progress INTEGER DEFAULT 0,
    train_window INTEGER DEFAULT 252,
    test_window INTEGER DEFAULT 21,
    codes TEXT DEFAULT '',
    result TEXT DEFAULT '{}',
    started_at TEXT DEFAULT '',
    finished_at TEXT DEFAULT ''
);
```

---

## 8. 纸面交易表

### paper_account — 虚拟账户

```sql
CREATE TABLE IF NOT EXISTS paper_account (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    balance REAL DEFAULT 100000,
    initial_capital REAL DEFAULT 100000,
    market_value REAL DEFAULT 0,
    total_pnl REAL DEFAULT 0,
    total_commission REAL DEFAULT 0,
    total_trades INTEGER DEFAULT 0,
    created_at TEXT DEFAULT '',
    last_sync TEXT DEFAULT ''
);
```

### paper_positions — 虚拟持仓

```sql
CREATE TABLE IF NOT EXISTS paper_positions (
    code TEXT PRIMARY KEY,
    name TEXT DEFAULT '',
    qty INTEGER DEFAULT 0,
    avg_cost REAL DEFAULT 0,
    current_price REAL DEFAULT 0
);
```

### paper_trades — 纸面交易记录

```sql
CREATE TABLE IF NOT EXISTS paper_trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT DEFAULT '',
    date TEXT DEFAULT '',
    action TEXT DEFAULT '',
    price REAL DEFAULT 0,
    qty INTEGER DEFAULT 0,
    before_qty INTEGER DEFAULT 0,
    commission REAL DEFAULT 0,
    slippage REAL DEFAULT 0,
    pnl REAL DEFAULT 0
);
```

### paper_suggestions — 交易建议

```sql
CREATE TABLE IF NOT EXISTS paper_suggestions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT DEFAULT '',
    date TEXT DEFAULT '',
    direction TEXT DEFAULT '',
    price REAL DEFAULT 0,
    confidence REAL DEFAULT 0,
    reason TEXT DEFAULT ''
);
```

### paper_suggestions_history — 建议历史

```sql
CREATE TABLE IF NOT EXISTS paper_suggestions_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT DEFAULT '',
    date TEXT DEFAULT '',
    direction TEXT DEFAULT '',
    price REAL DEFAULT 0,
    confidence REAL DEFAULT 0,
    reason TEXT DEFAULT '',
    created_at TEXT DEFAULT ''
);
```

### paper_daily_snapshot — 日净值快照

```sql
CREATE TABLE IF NOT EXISTS paper_daily_snapshot (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT DEFAULT '',
    net_value REAL DEFAULT 0,
    cash REAL DEFAULT 0,
    market_value REAL DEFAULT 0
);
```

### intraday_quotes — 日内分时行情

```sql
CREATE TABLE IF NOT EXISTS intraday_quotes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT DEFAULT '',
    time TEXT DEFAULT '',
    price REAL DEFAULT 0,
    volume INTEGER DEFAULT 0
);
```
