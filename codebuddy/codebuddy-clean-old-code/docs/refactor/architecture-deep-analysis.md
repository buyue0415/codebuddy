# 系统架构深度分析报告

> **系统**: 股票投资管理系统 | **版本**: V0.7 | **分析日期**: 2026-06-03 | **分析方法**: 静态代码审查 + 依赖图分析 + 数据流追踪

---

## 1. 核心组件清单

### 1.1 组件全景

```
┌──────────────────────────────────────────────────────────────────┐
│                        前端 SPA 层                                │
│  bank-stock-system.html → js/{core,kline,intelligence,news,      │
│  triggers,expert,management,nav}.js + css/app.css                │
│  通过 fetch() 调用 REST API (localhost:8765)                      │
└───────────────────────────┬──────────────────────────────────────┘
                            │ HTTP (fetch API / EventSource)
┌───────────────────────────▼──────────────────────────────────────┐
│                      API 服务层 (server.py)                        │
│  ThreadedHTTPServer :8765   42 个端点   路由分发   并发控制        │
│  subprocess.run() → 子进程脚本协调                                │
└───┬──────────┬──────────┬──────────┬──────────┬──────────────────┘
    │          │          │          │          │
    ▼          ▼          ▼          ▼          ▼
┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────────────────┐
│sync_all│ │fetch_  │ │update_ │ │optimize│ │reinject_from_db    │
│.py     │ │news.py │ │from_   │ │_predict│ │.py (数据注入)       │
│(同步   │ │(新闻   │ │statement│ │.py     │ │                    │
│ 引擎)  │ │ 抓取)  │ │.py(对账│ │(ML预测)│ │                    │
│        │ │        │ │  单)   │ │        │ │                    │
└───┬────┘ └───┬────┘ └───┬────┘ └───┬────┘ └─────────┬──────────┘
    │          │          │          │                 │
    └──────────┴──────────┴──────────┴─────────────────┘
                         │
              ┌──────────▼──────────┐
              │   db_helper.py      │
              │   (数据库访问层)      │
              │   18 Query + 7 Batch │
              │   + 12 Write        │
              └──────────┬──────────┘
                         │
              ┌──────────▼──────────┐
              │   SQLite (stock.db) │
              │   17 张表 / WAL模式  │
              └─────────────────────┘
```

### 1.2 组件详细清单

| 层级 | 组件 | 文件 | 行数 | 状态 | 职责 |
|------|------|------|------|------|------|
| **前端** | SPA入口 | `deliverables/bank-stock-system.html` | ~500 | Active | 页面结构+导航 |
| | 核心逻辑 | `deliverables/js/core.js` | ~400 | Active | 初始化+数据绑定 |
| | K线图表 | `deliverables/js/kline.js` | ~1100 | Active | K线+Candlestick |
| | 智能预测 | `deliverables/js/intelligence.js` | ~600 | Active | 预测数据展示 |
| | 新闻模块 | `deliverables/js/news.js` | ~400 | Active | 新闻列表+内容 |
| | 触发器 | `deliverables/js/triggers.js` | ~250 | Active | 数据刷新触发 |
| | 专家分析 | `deliverables/js/expert.js` | ~220 | Active | 专家报告展示 |
| | 管理设置 | `deliverables/js/management.js` | ~160 | Active | 自选股管理 |
| | 导航 | `deliverables/js/nav.js` | ~90 | Active | Tab切换 |
| | 样式 | `deliverables/css/app.css` | ~700 | Active | 全局样式 |
| **API** | 服务器 | `server.py` | ~1500 | Active | HTTP路由+子进程协调 |
| **同步** | 同步引擎 | `scripts/sync_all.py` | ~1100 | Active | 8步全量同步 |
| | 新闻抓取 | `scripts/fetch_news.py` | ~280 | Active | NeoData→Markdown→SQLite |
| | 分红抓取 | `scripts/fetch_dividends.py` | ~200 | Active | 东方财富API |
| | 行情刷新 | `scripts/refresh_quotes.py` | ~250 | Active | 实时行情+TTM股息率 |
| **数据** | 数据库层 | `scripts/db_helper.py` | ~1100 | Active | SQLite CRUD |
| | 对账单解析 | `scripts/update_from_statement.py` | ~520 | Active | Excel解析 |
| **预测** | ML优化 | `scripts/optimize_predict.py` | ~1000 | Active | V3.0混合集成 |
| | 自学习 | `sync_all.py`内函数 | ~300 | Active | MWU+EG+Beta-Binomial |
| **报告** | 兼容层 | `scripts/report_compatibility.py` | ~1300 | Active | v1/v2/v3适配 |
| | 导入器 | `scripts/import_expert_report.py` | ~300 | Active | 验证+导入 |
| **运维** | 调度器 | `scripts/scheduler.py` | ~120 | Active | 定时任务 |
| | 数据注入 | `scripts/reinject_from_db.py` | ~280 | Active | SQLite→HTML注入 |
| | 系统审计 | `scripts/audit_system.py` | ~90 | Active | 6维度巡检 |
| | 迁移工具 | `scripts/migrate_to_sqlite.py` | ~300 | 一次性 | JSON→SQLite |
| **测试** | 10个模块 | `tests/` | ~1200 | Active | 单元+集成 |

---

## 2. 模块依赖关系图

```mermaid
graph TD
    subgraph Frontend["前端 SPA"]
        HTML["bank-stock-system.html"]
        CORE["js/core.js"]
        KLINE["js/kline.js"]
        INTEL["js/intelligence.js"]
        NEWS_JS["js/news.js"]
        TRIGGERS["js/triggers.js"]
        EXPERT_JS["js/expert.js"]
    end

    subgraph API["API 服务层"]
        SERVER["server.py (ThreadedHTTPServer)"]
    end

    subgraph Sync["数据同步管道"]
        SYNC["sync_all.py (8步同步)"]
        FETCH_NEWS["fetch_news.py"]
        FETCH_DIV["fetch_dividends.py"]
        REFRESH["refresh_quotes.py"]
    end

    subgraph DataProcessing["数据处理"]
        DB["db_helper.py (18Q+12W)"]
        STMT["update_from_statement.py"]
        REINJECT["reinject_from_db.py"]
    end

    subgraph Prediction["预测引擎"]
        OPTIMIZE["optimize_predict.py (ML)"]
        SELF_LEARN["sync_all 内自学习函数"]
    end

    subgraph Expert["专家报告"]
        COMPAT["report_compatibility.py"]
        IMPORT["import_expert_report.py"]
    end

    subgraph Ops["运维工具"]
        SCHEDULER["scheduler.py"]
        AUDIT["audit_system.py"]
        MIGRATE["migrate_to_sqlite.py"]
    end

    subgraph External["外部依赖"]
        NEODATA["NeoData (westock-data)"]
        XLSX["广发对账单.xlsx"]
        EASTMONEY["东方财富API"]
    end

    HTML -->|fetch()| SERVER
    SERVER -->|import| DB
    SERVER -->|subprocess| SYNC
    SERVER -->|subprocess| FETCH_NEWS
    SERVER -->|subprocess| STMT
    SERVER -->|subprocess| AUDIT
    SERVER -->|subprocess| REINJECT
    SERVER -->|import| IMPORT

    SYNC -->|import| DB
    SYNC -->|import| FETCH_NEWS
    SYNC -->|subprocess Node.js| NEODATA
    SYNC -->|import| REFRESH
    SYNC -->|import| FETCH_DIV

    FETCH_NEWS -->|subprocess Node.js| NEODATA
    FETCH_DIV -->|HTTP request| EASTMONEY

    STMT -->|读取| XLSX
    STMT -->|import| DB
    REINJECT -->|直接连接| DB

    OPTIMIZE -->|读取| DB
    SELF_LEARN -->|内嵌于| SYNC

    IMPORT -->|import| COMPAT
    IMPORT -->|import| DB

    SCHEDULER -->|subprocess| SYNC
    SCHEDULER -->|subprocess| STMT
```

### 依赖强度矩阵

| 被依赖 → | server | db_helper | sync_all | fetch_news | update_stmt | optimize | compat | scheduler | reinject |
|----------|--------|-----------|----------|------------|-------------|----------|--------|-----------|----------|
| **server.py** | - | 🔴强 | 🔴强 | 🟡中 | 🟡中 | - | - | - | 🟡中 |
| **db_helper.py** | - | - | - | - | - | - | - | - | - |
| **sync_all.py** | - | 🔴强 | - | 🟡中 | - | - | - | - | - |
| **fetch_news.py** | - | 🟡中 | - | - | - | - | - | - | - |
| **update_stmt** | - | 🔴强 | - | - | - | - | - | - | - |
| **optimize** | - | 🔴强 | - | - | - | - | - | - | - |
| **compat.py** | - | - | - | - | - | - | - | - | - |
| **scheduler.py** | - | - | 🔴强 | - | 🟡中 | - | - | - | - |
| **reinject.py** | - | 🟢直接SQL | - | - | - | - | - | - | - |

---

## 3. 关键数据流路径

### 3.1 行情+预测数据流（最核心）
```
NeoData API (westock-data Node.js)
  → sync_all.py Step 3: ThreadPoolExecutor(max_workers=4) 并行获取K线
  → db_helper.upsert_kline_daily() → kline_daily 表
  → sync_all.py Step 4: 预测回填 (验证历史预测)
  → sync_all.py Step 5: 准确率重算 → accuracy_stats 表
  → sync_all.py Step 6: calc_signals() → gen_pred() → insert_daily_prediction()
     → daily_predictions + prediction_hourly + prediction_signals 表
  → sync_all.py Step 7: 季节性+月K线 → seasonal + kline_monthly 表
  → server.py GET /api/v2/init → db_helper.get_all_*() → JSON响应
  → 前端 js/core.js → 绑定到 DOM
```

### 3.2 对账单解析数据流
```
用户上传 广发对账单.xlsx
  → server.py POST /api/upload/statement (multipart/form-data 手动解析)
  → 保存文件 + .bak备份
  → subprocess: update_from_statement.py
     → openpyxl(或纯Python) 解析Excel
     → 列名映射(中英文兼容)
     → 持仓计算: buy/sell/dividend聚合
     → db_helper.upsert_positions() → positions_* 4张表
     → db_helper.upsert_quotes() → quotes 表
  → subprocess: reinject_from_db.py
     → SQLite查询 → JSON重组 → 正则替换HTML中DATA块
```

### 3.3 新闻数据流
```
NeoData API (Node.js)
  → fetch_news.py fetch_news_node()
  → Markdown解析 → _parse_news_table()
  → 情感分析 (14正向+14负向关键词)
  → 重大性判断 (major/non-major)
  → 去重 (content_hash)
  → db_helper.upsert_news() → news 表
  → server.py GET /api/v2/news?filter=all|major|{code} → JSON
```

### 3.4 专家报告导入数据流
```
WorkBuddy 多Agent → POST /api/v2/expert/import (JSON)
  → server.py → import_expert_report.py
  → 格式验证 (v1/v2/v3检测)
  → report_compatibility.py: 归一化到 UnifiedExpertReport
  → 字段模糊映射 (中英文/命名变体)
  → db_helper 写入 expert_reports 表
  → GET /api/v2/expert → JSON响应
```

### 3.5 ML增强预测数据流 (V0.7新增)
```
optimize_predict.py
  → 从 kline_daily 读取K线数据
  → 30+特征工程 (OHLCV衍生+技术指标)
  → RandomForest 元学习器训练
  → Isotonic 校准
  → 超参调优 (GridSearch)
  → 生成增强预测 → 写入 daily_predictions
```

---

## 4. 瓶颈与风险分析

### 4.1 已识别瓶颈（按严重度排序）

| # | 瓶颈 | 严重度 | 影响范围 | 根因 | 建议 |
|---|------|--------|---------|------|------|
| 1 | **Python版本不一致** | 🔴高 | 全局 | server.py用3.14.3，scheduler用3.13.12 | 统一到单一Python版本 |
| 2 | **数据注入依赖正则匹配** | 🔴高 | 前端数据 | reinject使用正则匹配JS变量名，前端重构即失效 | 改为API注入或模板注入 |
| 3 | **行情无实时源** | 🔴高 | 行情准确性 | PE/PB/股息率硬编码为0 | 接入东方财富/新浪实时API |
| 4 | **sync_all模块级执行** | 🟡中 | 测试 | import sync_all即触发执行，迫使测试复制代码 | 用`if __name__`保护 |
| 5 | **JSON/SQLite双写不一致** | 🟡中 | 数据完整性 | DELETE自选股时双写，JSON侧可能遗漏 | 统一到SQLite单写 |
| 6 | **全局同步锁** | 🟡中 | 并发 | 单Lock阻止所有同步任务 | 按任务类型分层锁 |
| 7 | **月K线无增量更新** | 🟡中 | 季节性计算 | 仅首次生成，后续不追加 | 改为`INSERT OR REPLACE`逐月 |
| 8 | **新闻无自动清理** | 🟢低 | 存储膨胀 | 无过期清理，仅daily_update有30天过滤 | 添加定期清理机制 |
| 9 | **db_helper异常传播** | 🟢低 | 错误处理 | 查询函数不捕获异常，上游需自行处理 | 增加统一异常装饰器 |
| 10 | **子进程超时配置硬编码** | 🟢低 | 可维护性 | server.py中每个脚本超时硬编码 | 提取到config.json |

### 4.2 性能瓶颈

| 瓶颈 | 典型耗时 | 峰值 | 限制因素 |
|------|---------|------|---------|
| NeoData K线拉取 | 5-15s/股票 | - | Node.js子进程启动+网络 |
| 全量同步(3股) | 30-60s | - | 串行步骤 + 并行K线(4) |
| API响应 | <100ms | - | SQLite本地查询 |
| optimize_predict训练 | 10-30s | - | ML模型训练(RandomForest) |
| 前端初始加载 | 300-500KB | - | /api/v2/init全量数据 |

### 4.3 安全风险

| 风险 | 说明 | 建议 |
|------|------|------|
| 路径遍历 | server.py静态文件服务无路径净化 | 添加路径规范化 |
| SQL注入 | db_helper用参数化查询(✅安全) | 保持现状 |
| 文件上传 | 对账单上传无大小限制 | 添加大小上限(如50MB) |
| CORS | `Access-Control-Allow-Origin: *` | 本地应用可接受 |

---

## 5. 数据库Schema分析

### 5.1 17张表关系

```
stocks ──────────────────────────────────────────────┐
  │ (code FK)                                         │
  ├── watchlist (自选股，sort_order)                   │
  ├── kline_daily (日K线，200条/股)                    │
  ├── kline_monthly (月K线，合成)                      │
  ├── quotes (行情快照)                                │
  ├── daily_predictions ──┬── prediction_hourly        │
  │                       └── prediction_signals       │
  ├── learning_params (信号权重/偏置)                  │
  ├── accuracy_stats (last_20/last_60)                 │
  ├── seasonal (12月因子)                              │
  ├── news (新闻，content_hash去重)                    │
  ├── positions_current (当前持仓)                     │
  ├── positions_closed (已清仓)                        │
  ├── trades (交易记录)                                │
  └── dividends (分红记录)                             │

expert_reports ─────────────────────── (独立，按日期)  │
prediction_monthly_changes ─────────── (月涨跌幅)      │
```

### 5.2 外键约束（仅代码层面）
- `kline_daily.code ⊆ watchlist.code` → DELETE时级联
- `daily_predictions.code ⊆ watchlist.code` → DELETE时级联
- SQLite Schema仅 `prediction_hourly→daily_predictions` 和 `prediction_signals→daily_predictions` 有外键

---

## 6. API层分析

### 6.1 端点分类统计

| 类别 | 数量 | 路径前缀 |
|------|------|---------|
| 初始化 | 1 | `/api/v2/init` |
| 自选股 | 6 | `/api/v2/watchlist`, `/api/watchlist/*` |
| 行情 | 2 | `/api/v2/quotes` |
| 持仓/交易/分红 | 7 | `/api/v2/positions`, `/api/v2/trades`, `/api/v2/dividends` |
| K线 | 4 | `/api/v2/kline/daily`, `/api/v2/kline/monthly` |
| 预测 | 2 | `/api/v2/predictions/daily` |
| 新闻 | 1 | `/api/v2/news` |
| 专家报告 | 3 | `/api/v2/expert`, `/api/expert/import` |
| 学习/准确率 | 2 | `/api/v2/learning`, `/api/v2/accuracy` |
| 季节性 | 2 | `/api/v2/seasonal` |
| 配置 | 1 | `/api/v2/config` |
| 搜索 | 1 | `/api/search/stocks` |
| 触发器 | 4 | `/api/trigger/*` |
| 上传 | 1 | `/api/upload/statement` |
| 审计/工具 | 3 | `/api/audit`, `/api/system-data`, `/dbview` |
| **总计** | **40** | |

### 6.2 HTTP状态码分布

| 状态码 | 场景 | 端点 |
|--------|------|------|
| 200 | 成功 | 所有 |
| 400 | 参数缺失/无效 | 自选股增删 |
| 403 | 文件访问禁止 | 静态文件(.py) |
| 404 | 资源不存在 | 未知端点 |
| 409 | 重复添加 | 自选股增删 |
| 429 | 并发冲突 | 同步触发器 |
| 500 | 服务端异常 | 所有端点 |

---

## 7. 测试覆盖分析

### 7.1 现有覆盖

| 模块 | 测试文件 | 测试数 | 覆盖类型 | 关键缺口 |
|------|---------|--------|---------|---------|
| DB查询 | test_db_helper.py | 25 | 形状+字段+类型 | 写入函数(0个) |
| 同步引擎 | test_sync_engine.py | 34 | EMA+信号+预测+LP | 自学习更新函数 |
| 新闻 | test_news_fetcher.py | 29 | 代码提取+情感+重大性+解析 | 网络层 |
| 对账单 | test_statement_parser.py | 17 | 买/卖/分红/费用/边界 | 文件解析 |
| API | test_api_server.py | 6 | 响应格式+路由约定 | HTTP状态码测试 |
| DB层 | test_database_layer.py | ❓ | Schema+完整性 | 待确认 |

### 7.2 缺失覆盖

| 优先级 | 模块 | 缺失内容 |
|--------|------|---------|
| P0 | optimize_predict.py | 完全无测试 (1000+行代码) |
| P0 | db_helper写入 | 12个写入函数无测试 |
| P0 | 跨表数据完整性 | 无事务一致性测试 |
| P1 | report_compatibility.py | 完全无测试 (1300+行代码) |
| P1 | API错误状态码 | 429/409/500 无覆盖 |
| P1 | server.py路由 | 无路由匹配测试 |
| P2 | refresh_quotes.py | 无测试 |
| P2 | fetch_dividends.py | 无测试 |
| P2 | scheduler.py | 无测试 |

---

## 8. 架构优势与缺陷

### 8.1 架构优势

1. **清晰的分层设计**: 前端→API→数据管道→数据库，职责分明
2. **SQLite WAL模式**: 支持并发读，适合单用户场景
3. **db_helper封装**: 数据访问统一入口，业务层无直接SQL
4. **模块化specs文档**: 19个子文档分工明确，便于维护
5. **参数化查询**: 防止SQL注入
6. **并行K线拉取**: ThreadPoolExecutor节省网络等待
7. **MWU自学习**: 科学严谨的在线学习算法

### 8.2 架构缺陷

1. **sync_all.py模块级执行**: import即执行，严重影响可测试性
2. **Python版本硬编码**: server.py路径写死用户名和Python版本
3. **正则依赖的HTML注入**: reinject_from_db.py脆弱地依赖前端代码格式
4. **JSON遗留包袱**: system_data.json仍被维护，与SQLite双写
5. **缺乏统一配置管理**: 超时/路径分散在server.py各处
6. **无日志系统**: 仅有print()，无结构化日志
7. **无请求验证层**: API输入验证分散在各端点函数中

---

## 9. 改进建议（优先级排序）

### 短期（本次）
1. ✅ 创建 rules 规范文档（代码风格+架构约束+业务规则）
2. ✅ 新增 optimize_predict 测试
3. ✅ 新增 report_compatibility 测试
4. ✅ 补充 API 错误处理测试

### 中期
1. 将 sync_all.py 模块级执行改为 `if __name__ == '__main__'` 保护
2. 移除 Python版本和用户路径硬编码
3. 废弃 JSON 双写，统一 SQLite
4. 接入实时行情API

### 长期
1. 引入结构化日志系统
2. 提取统一配置层
3. 添加请求验证中间件
4. 实现新闻自动清理

---

> **分析结论**: 系统在 V0.7 阶段架构基本合理，分层清晰。主要风险集中在 Python版本不一致、HTML注入脆弱性、行情数据缺失三个方面。建议优先修复高严重度问题，同时补齐测试覆盖。
