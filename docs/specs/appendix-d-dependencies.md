# 附录 D — 依赖关系

> **关联规范**: [01-system-architecture.md](01-system-architecture.md)

---

## 1. Python 运行时依赖

### 1.1 标准库（Python 3.10+）

| 模块 | 用途 |
|------|------|
| http.server | 旧版服务器（已废弃） |
| json | JSON序列化/反序列化 |
| sqlite3 | SQLite数据库操作 |
| subprocess | 子进程脚本编排（sync_all, fetch_news等） |
| threading | 并发控制（全局锁） |
| concurrent.futures | K线并行采集 |
| datetime / time | 时间和日期处理 |
| email / imaplib | 邮件对账单解析 |
| os / sys / pathlib | 文件和路径操作 |
| zipfile | ZIP对账单解压 |
| io | 文件流处理 |
| xml.parsers.expat | 对账单Excel XML解析 |
| hashlib | 文件校验 |
| csv | CSV导出 |
| logging | 日志记录 |
| re | 正则表达式 |

### 1.2 第三方库

| 包 | 用途 | 安装 |
|----|------|------|
| fastapi | API框架 | pip install fastapi |
| uvicorn | ASGI服务器 | pip install uvicorn |
| akshare | 东方财富数据源 | pip install akshare |
| pandas | 数据分析 | pip install pandas |
| numpy | 数值计算 | pip install numpy |
| scikit-learn | ML模型(RF/Ridge) | pip install scikit-learn |

### 1.3 可选依赖

| 包 | 用途 |
|----|------|
| openpyxl | Excel读写（对账单解析） |

---

## 2. Python 模块依赖

```
server_v2.py (FastAPI)
  ├── scripts/db_helper.py       [数据库访问层]
  ├── scripts/fetchers/__init__.py [数据源获取器]
  │     ├── WestockFetcher        [本地量化数据源]
  │     ├── NeoDataFetcher        [NeoData API]
  │     ├── EastMoneyFetcher      [东方财富, via akshare]
  │     ├── SinaFetcher           [新浪财经]
  │     └── TencentFetcher        [腾讯证券]
  │
  ├── subprocess → scripts/sync_all.py   [全量同步]
  │     └── import → scripts/fetch_news.py
  │     └── import → scripts/signals.py
  │     └── import → scripts/optimize_predict.py
  │
  ├── subprocess → scripts/fetch_news.py  [新闻采集]
  │     └── import → scripts/db_helper.py
  │
  └── subprocess → scripts/update_from_statement.py [对账单解析]
        └── import → scripts/db_helper.py
```

---

## 3. 页面路由依赖

| 页面 | 路由 | 组件 | Stores | API |
|------|------|------|--------|-----|
| Overview | /overview | - | useDataStore, useOverviewStore | 15个并行API |
| Trades | /trades | - | useDataStore | /trades |
| Fees | /fees | - | useDataStore | 遍历持仓 |
| Management | /manage | StockSelector | useDataStore, useIndustryStore | /watchlist |
| Intelligence | /intelligence | IndustryGroupTabs | useDataStore, useIndustryStore | /predictions, /learning, /accuracy |
| Expert | /expert | IndustryGroupTabs | useDataStore, useIndustryStore | /expert |
| News | /news | IndustryGroupTabs | useDataStore, useIndustryStore | /news |
| StockData | /stock-data | - | useDataStore, useIndustryStore | /quotes |
| Kline | /kline | IndustryGroupTabs | useDataStore, useIndustryStore | /kline/daily |
| PatternRules | /pattern-rules | - | useDataStore | /pattern-rules |
| CompanyGraph | /company-graph | IndustryGroupTabs | useDataStore, useIndustryStore | /graph-data |
| BacktestPage | /backtest | - | useDataStore | /backtest/* |
| PaperTrading | /paper | - | useDataStore | /paper/* |

---

## 4. Stores 依赖

```
useDataStore (data.js)
  → api/client.js (15个并行请求)
  → 共享: watchlist, quotes, positions, trades, news, kline, predictions, expertReports, accuracy, learning, seasonal, config

useOverviewStore (overview.js)
  → useDataStore (计算派生数据)

useIndustryStore (industry.js)
  → api/client.js (/api/v2/industries)
  → 共享: industries, flatStocks
```

---

## 5. 数据库表依赖

```
stock.db
  ├── 基础: stocks, watchlist
  ├── K线: kline_daily, kline_monthly
  ├── 行情: quotes
  ├── 交易: positions, closed_positions, trades, dividends
  ├── 预测: daily_predictions, prediction_hourly, prediction_signals
  ├── 学习: learning_params, accuracy_stats, seasonal
  ├── 新闻: news
  ├── 专家: expert_reports
  ├── 形态: pattern_rules
  ├── 关系: company_relations, company_business, ml_models
  ├── 回测: backtest_runs
  └── 纸面: paper_account, paper_positions, paper_trades, 
             paper_daily_snapshot, paper_suggestions,
             paper_suggestions_history, intraday_quotes
```
