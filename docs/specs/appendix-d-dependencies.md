# 附录 D: 依赖关系图与数据流

> **版本**: v2.0 | **更新日期**: 2026-06-06

---

## 系统架构图

```
┌────────────────────────────────────────────────────────────────┐
│                        Vue 3 SPA (Vite Build)                   │
│  deliverables/v2/dist/                                         │
│  ├── index.html                   ← 入口         [GET /]       │
│  ├── assets/index-*.js            ← JS 构建产物  [GET /assets/] │
│  ├── assets/index-*.css           ← CSS 构建产物 [GET /assets/] │
│  ├── chart.umd.min.js             ← Chart.js     [GET /chart.*] │
│  └── chartjs-chart-financial.min.js ← 金融图表    [GET /chart.*] │
└──────────────┬─────────────────────────────────────────────────┘
               │ /api/v2/*
               ▼
┌───────────────────────────────────────────────────────────────┐
│                server_v2.py (FastAPI :8766)                    │
│                                                               │
│  GET  / → HTMLResponse (V2 dist/index.html)                   │
│  GET  /assets/{path} → V2 dist assets                         │
│  GET  /api/v2/* → JSONResponse (业务数据)                      │
│  POST /api/v2/* → JSONResponse (创建/触发/上传)                │
│  GET  /data/{path} → 静态文件服务                               │
│  GET  /scripts/{path} → 静态文件服务                            │
├───────────────────────────────────────────────────────────────┤
│  subprocess.run() ─────────────────────────────────────────┐  │
└──────────────────────────────────────────────────────────────┘
         │                          │
         ▼                          ▼
┌──────────────────┐   ┌──────────────────────────┐
│  SQLite CRUD     │   │  脚本层 subprocess        │
│  db_helper.py    │   │                          │
│                  │   │  sync_all.py              │
│  18 查询函数     │   │  fetch_news.py            │
│  12 写入函数     │   │  update_from_statement.py │
│  7 批量查询函数  │   │  import_expert_report.py  │
│  2 辅助函数      │   │  backtest_engine.py       │
│                  │   │  paper_trading.py         │
│                  │   │  audit_system.py          │
└───────┬──────────┘   └────────────┬──────────────┘
        │                           │
        ▼                           ▼
┌────────────────────────────────────────────────────────────┐
│                      SQLite: data/stock.db                   │
│                                                              │
│  分析层：watchlist, kline_daily, kline_monthly,              │
│          daily_predictions, seasonal, learning_params,        │
│          accuracy_stats, quotes, news, expert_reports         │
│                                                              │
│  交易层：positions, closed_positions, trades, dividends,     │
│          statement_dividends, config                          │
│                                                              │
│  V0.9: paper_account, paper_positions, paper_trades,         │
│         paper_daily_snapshot, paper_suggestions,              │
│         pattern_rules, backtest_runs, backtest_results        │
└──────────────────────────────────────────────────────────────┘
```

---

## 关键数据流

### 1. 行情 + 预测流

```
NeoData (外部API)
  │ 定时触发 sync_all.py（或手动 POST /api/trigger/predict）
  │
  ├── Step 1: 读取 watchlist（SQLite）
  ├── Step 2: 新闻抓取（fetch_news.py，最多4并发）
  ├── Step 3: 并行日K线获取（ThreadPoolExecutor, max_workers=4）
  │              → Node.js 子进程调用 westock-data
  ├── Step 4: 预测回填（验证历史预测）
  ├── Step 5: 准确率重算（last_20 / last_60）
  ├── Step 6: 生成当日预测（信号计算 → MWU → 持久化）
  └── Step 7: 季节性 + 月K线 + 行情报价刷新
       │
       ▼
  SQLite（quotes / kline_daily / daily_predictions / ...）
       │
       ▼
  GET /api/v2/* → Vue 前端渲染
```

### 2. 持仓数据流

```
广发证券对账单.xlsx
  │ POST /api/upload/statement
  │
  ├── 魔数检测（PK\x03\x04 ZIP 格式验证）
  ├── 文件保存 + 自动备份（bak_{timestamp} / upload_bak）
  └── update_from_statement.py（pandas 解析 Excel）
       │
       ▼
  SQLite（positions / closed_positions / trades / dividends）
       │
       ▼
  GET /api/v2/positions → Vue 前端渲染
```

### 3. 新闻流

```
NeoData (外部API)
  │ POST /api/trigger/news
  │
  ├── fetch_news.py（东方财富 API）
  │   ├── 按市场分市（SH / SZ）
  │   └── 限制：每只股票最多 5 条最新 + 3 条热点
  │
  ▼
SQLite（news 表）
  │
  ▼
GET /api/v2/news → Vue 前端渲染
```

### 4. 专家报告流

```
WorkBuddy 多 Agent 系统
  │ POST /api/v2/expert/import
  │
  ├── import_expert_report.py
  │   ├── 解析 JSON 报告（支持 v1/v2/v3 格式）
  │   └── 更新 expert_reports 表
  │
  ▼
SQLite（expert_reports 表）
  │
  ▼
GET /api/v2/expert → Vue 前端渲染
```

### 5. 回测与纸面交易流（V0.9）

```
回测：POST /api/v2/backtest/run
  │
  ├── backtest_engine.py
  │   ├── Walk-forward 网格搜索（252天训练 + 21天测试）
  │   ├── 两阶段权重搜索（Phase 1: 80次 → Phase 2: 512次）
  │   └── 写入 learning_params（冷启动权重）
  │
  ▼
纸面交易：paper_trading.py（每日自动执行）
  │
  ├── 读取 learning_params + daily_predictions
  ├── 凯利公式仓位计算
  ├── 自动执行模拟交易
  └── 写入 paper_* 表
       │
       ▼
  GET /api/v2/paper/* → Vue 前端渲染
```

---

## 模块依赖矩阵

| 模块 | 核心文件 | 被依赖方 | 依赖方 |
|------|---------|---------|--------|
| **API 服务** | `server_v2.py` | 前端 Vue 3 | db_helper, sync_all, fetch_news, update_from_statement, import_expert_report, backtest_engine, paper_trading, audit_system |
| **数据库层** | `scripts/db_helper.py` | 所有模块 | sqlite3 |
| **同步引擎** | `scripts/sync_all.py` | API (trigger/predict) | db_helper, fetch_news, signals, refresh_quotes |
| **信号计算** | `scripts/signals.py` | sync_all, backtest_engine | db_helper, report_compatibility |
| **新闻抓取** | `scripts/fetch_news.py` | sync_all, API | db_helper |
| **对账单解析** | `scripts/update_from_statement.py` | API (upload/trigger) | parse_statement, db_helper |
| **专家报告** | `scripts/import_expert_report.py` | API | db_helper, report_compatibility |
| **回测引擎** | `scripts/backtest_engine.py` | API | db_helper, signals |
| **纸面交易** | `scripts/paper_trading.py` | API | db_helper, signals |
| **股票数据库** | `scripts/build_stock_db.py` | 手动运行 | — |
| **系统审计** | `scripts/audit_system.py` | API | db_helper |

---

## 外部依赖

| 依赖 | 版本 | 用途 |
|------|------|------|
| Python | 3.12+ | 后端运行环境 |
| Node.js | 22+ | westock-data CLI 调用（K线数据获取） |
| FastAPI | — | Python Web 框架 |
| Uvicorn | — | ASGI 服务器 |
| pandas / openpyxl | — | 对账单 Excel 解析 |
| westock-data | — | NeoData 金融数据 CLI |
| Vue 3 | — | 前端框架 |
| Vite | 5.x | 前端构建工具 |
| Chart.js | — | K线图表渲染 |
