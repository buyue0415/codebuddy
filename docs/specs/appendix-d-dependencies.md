# 附录D: 依赖关系图与数据流

---

## ASCII 架构图

```
                    ┌──────────────────────┐
                    │  Vue 3 SPA (Vite)    │
                    │  + bank-stock-       │
                    │    system.html (兼容) │
                    └──────────┬───────────┘
                               │ fetch API (Vite proxy → :8766)
                    ┌──────────▼───────────┐
                    │   server_v2.py       │
                    │   (FastAPI+Uvicorn)  │
                    │      :8766           │
                    │  server.py 保留 :8765 │
                    └──┬──────┬──────┬─────┘
                       │      │      │
          ┌────────────▼──┐ ┌─▼──────▼──┐ ┌────────────▼──┐
          │  db_helper.py │ │ subprocess│ │  import_       │
          │  (SQLite CRUD) │ │  调用     │ │  expert_report │
          └───────┬───────┘ └─────┬─────┘ └───────────────┘
                  │               │
       ┌──────────▼───────────┐   │
       │    data/stock.db     │   │
       │    (17 tables)       │   │
       └──────────────────────┘   │
                                  │
       ┌──────────────────────────┼──────────────────────┐
       │                          │                      │
  ┌────▼──────┐  ┌────────▼───┐  ┌▼───────────┐  ┌──────▼────────┐
  │ sync_all  │  │ fetch_news │  │daily_update│  │ update_from   │
  │   .py     │  │   .py      │  │   .py      │  │ _statement.py │
  └────┬──────┘  └─────┬──────┘  └────────────┘  └───────────────┘
       │               │
       │     ┌─────────▼─────────┐
       │     │  westock-data     │
       │     │  (Node.js 插件)   │
       │     │  NeoData 金融数据  │
       │     └───────────────────┘
       │
  ┌────▼──────┐
  │ scheduler │  ← 外部定时器触发
  │   .py     │
  └───────────┘
```

---

## 关键数据流

### 1. 行情 + 预测流
```
NeoData → westock-data (Node.js)
        → sync_all.py [Step 3: 并行K线获取]
        → calc_signals() [7项技术指标]
        → gen_pred() [次日预测生成]
        → SQLite (kline_daily, daily_predictions, prediction_hourly, prediction_signals, learning_params)
        → server_v2.py GET /api/v2/*
        → 前端渲染
```

### 2. 持仓数据流
```
广发对账单.xlsx
    → update_from_statement.py [Excel解析 + 持仓计算]
    → broker_statement.json
    → system_data.json
    → SQLite (positions, closed_positions, trades, dividends)
    → server_v2.py GET /api/v2/positions/*
    → 前端渲染
```

### 3. 新闻流
```
NeoData → westock-data (Node.js)
        → fetch_news.py [Markdown解析 + 情感分析]
        → SQLite (news)
        → server_v2.py GET /api/v2/news
        → 前端渲染
```

### 4. 专家报告流
```
WorkBuddy 多Agent (trading-analysis skill)
    → 生成 JSON 报告
    → POST /api/v2/expert/import
    → import_expert_report.py [Schema验证 + 写入]
    → SQLite (expert_reports)
    → GET /api/v2/expert
    → 前端渲染 (五维雷达图、多空柱状图等)
```

---

## 依赖矩阵

| | server | db_helper | sync_all | fetch_news | daily_update | scheduler | update_stmt | import_expert | reinject | build_stock_db | audit |
|---|--------|-----------|----------|------------|-------------|-----------|-------------|---------------|----------|----------------|-------|
| **server** | — | 导入调用 | 子进程 | 子进程 | — | — | 子进程 | 导入调用 | 子进程 | — | 子进程 |
| **db_helper** | | — | | | | | | | | | |
| **sync_all** | | 导入调用 | — | 导入函数 | | | | | | | |
| **fetch_news** | | get_watchlist | | — | | | | | | | |
| **daily_update** | | | | | — | | | | | | |
| **scheduler** | | | 子进程 | 子进程 | 子进程 | — | 子进程 | | 子进程 | | |
| **update_stmt** | | | | | | | — | | | | |
| **import_expert** | | get_db | | | | | | — | | | |
| **reinject** | | sqlite3 | | | | | | | — | | |
| **build_stock_db** | | | | | | | | | | — | |
| **audit** | | | | | | | | | | | — |

> 空白单元格 = 无直接依赖关系。

---

## 外部依赖

| 依赖 | 类型 | 使用模块 |
|------|------|---------|
| Python 3.12+ | 运行时 | 全部 |
| Node.js 22+ | 运行时 | sync_all, fetch_news |
| westock-data (NeoData) | 数据源 | sync_all, fetch_news |
| pandas / openpyxl | Python 库 | parse_statement, build_stock_db |
| 广发对账单 Excel | 数据文件 | update_from_statement |
