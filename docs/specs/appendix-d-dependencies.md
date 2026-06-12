# 附录 D: 模块依赖关系图

> **版本**: v4.0 | **更新日期**: 2026-06-06

---

## 系统架构

```
┌─────────────────────────────────────────────────────────┐
│              Vue 3 SPA (deliverables/v2/dist/)           │
│  index.html + assets/* + chart.*.js                      │
└──────────────┬──────────────────────────────────────────┘
               │ fetch /api/v2/*
               ▼
┌──────────────────────────────────────────────────────────┐
│           server_v2.py (FastAPI :8766)                    │
│                                                          │
│  GET  / → V2 dist/index.html                             │
│  GET  /assets/{path} → V2 dist assets                    │
│  GET  /api/v2/* → JSONResponse                            │
│  POST /api/v2/* → JSONResponse                            │
│  GET  /data/{path}, /scripts/{path} → 静态文件            │
│                                                          │
│  ┌── subprocess.run() ──────────────────────────────┐   │
│  │  sync_all.py  fetch_news.py  update_statement.py │   │
│  │  backtest_engine.py  paper_trading.py             │   │
│  └───────────────────────────────────────────────────┘   │
└──────────────┬───────────────────────────────────────────┘
               │ from db_helper import ...
               ▼
┌──────────────────────────────────────────────────────────┐
│              SQLite: data/stock.db (WAL)                  │
│                                                          │
│  分析层: watchlist, kline_daily/monthly,                  │
│          daily_predictions, prediction_hourly/signals,    │
│          learning_params, accuracy_stats, seasonal        │
│                                                          │
│  行情层: quotes, news                                    │
│                                                          │
│  交易层: stocks, positions, closed_positions,            │
│          trades, dividends, expert_reports                │
│                                                          │
│  V0.9: paper_account, paper_positions, paper_trades,     │
│         paper_daily_snapshot, paper_suggestions,          │
│         pattern_rules, backtest_runs                      │
└──────────────────────────────────────────────────────────┘
```

---

## 关键数据流

### 预测流
```
NeoData API → sync_all.py (8步流程)
  → kline_daily/daily_predictions/learning_params (SQLite)
  → GET /api/v2/predictions/daily → Vue 前端
```

### 交易流
```
广发对账单.xlsx → update_from_statement.py
  → positions/trades/dividends (SQLite)
  → GET /api/v2/positions → Vue 前端
```

### 新闻流
```
NeoData API → fetch_news.py
  → news (SQLite)
  → GET /api/v2/news → Vue 前端
```

### 回测+纸面交易流
```
backtest_engine.py → learning_params.backtest_weights
sync_all.py Step5 → 冷启动读取 → MWU在线微调
sync_all.py Step6 → daily_predictions
paper_trading.py → paper_suggestions → 自动执行
  → paper_* 表 → GET /api/v2/paper/* → Vue 前端
```

---

## 模块依赖矩阵

| 模块 | 核心文件 | 依赖 | 被依赖 |
|------|---------|------|--------|
| API服务 | server_v2.py | db_helper, subprocess脚本 | Vue前端 |
| 数据库 | db_helper.py | sqlite3 | 全部模块 |
| 同步引擎 | sync_all.py | db_helper, signals, fetch_news | scheduler, server_v2 |
| 信号引擎 | signals.py | numpy(可选) | sync_all, backtest_engine |
| 新闻抓取 | fetch_news.py | db_helper, Node.js | sync_all, server_v2 |
| 对账单解析 | update_from_statement.py | db_helper, pandas | server_v2 |
| 回测引擎 | backtest_engine.py | db_helper, signals | server_v2 |
| 纸面交易 | paper_trading.py | db_helper, markets | scheduler, server_v2 |
| 定时调度 | scheduler.py | subprocess各脚本 | Windows任务计划程序 |

---

## 外部依赖

| 依赖 | 版本 | 用途 |
|------|------|------|
| Python | 3.12+ | 后端环境 |
| FastAPI + Uvicorn | — | Web框架 |
| Node.js | 22+ | westock-data CLI |
| westock-data | — | NeoData 金融数据 |
| pandas/openpyxl | — | 对账单Excel解析 |
| Vue 3 + Vite | 5.x | 前端框架 |
| Chart.js | — | K线图表渲染 |
