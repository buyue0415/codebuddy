# 01 — 系统架构与 API 服务层

> **核心文件**: `server_v2.py` (~4200 行) | **端口**: 8766 | **框架**: FastAPI + Uvicorn
> **前端入口**: `deliverables/v2/dist/index.html`（Vue 3 + Vite 构建）
> **后端**: Python 3.10+ / FastAPI / 单进程 / 全局锁并发控制

---

## 1. 业务需求说明书

### 1.1 业务背景

系统需要一个统一的 Web 服务入口，将所有后端能力（数据查询、脚本编排、文件上传）通过 RESTful API 暴露给前端 Vue 3 SPA，同时作为静态文件服务器托管前端构建产物。

### 1.2 核心目标

| 目标 | 说明 |
|------|------|
| 统一 API 网关 | 所有数据读写通过 FastAPI 路由分发，单一入口 |
| 静态前端托管 | 直接提供 Vite 构建的 Vue 3 SPA 静态文件 |
| 脚本编排 | 通过 subprocess 异步调用后台计算脚本（sync_all.py 等） |
| 并发控制 | 全局锁防止重复触发的同步/回测/上传任务 |
| 数据采集回退 | Westock → NeoData → 东方财富 → 新浪 → 腾讯 多源回退 |

### 1.3 用户角色

单用户系统，运行在个人电脑本地。通过浏览器访问 `http://localhost:8766`。

---

## 2. 技术方案深度分析

### 2.1 架构决策

**为什么选 FastAPI？**
- 原生 async 支持，SQLite 查询走同步但无性能瓶颈
- 自动生成 Swagger UI（`/docs`）和 OpenAPI schema
- Pydantic 类型校验，减少运行时错误
- 比旧版 `http.server` 性能高 5-10 倍

**前端托管方案**：构建产物 `deliverables/v2/dist/` 直接由 FastAPI 提供静态文件服务。开发模式使用 Vite dev server，通过 proxy 转发 API 请求到后端 8766 端口。

**数据层**：SQLite WAL 模式，单文件 `data/stock.db`。无 ORM，通过 `db_helper.py` 封装所有数据库操作。

### 2.2 数据流架构

```
┌─────────────────────────────────────────────────────────┐
│                    浏览器  (Vue 3 SPA)                    │
│  App.vue ── nav-top / nav-sub-bar                        │
│  ├── Overview.vue     ├── Intelligence.vue    ├── News.vue│
│  ├── Trades.vue       ├── Expert.vue          ├── StockData.vue
│  ├── Fees.vue         └── ...                 ├── Kline.vue
│  ├── Management.vue                            ├── PatternRules.vue
│  └── (useDataStore / useIndustryStore / useOverviewStore) │
└──────────────────┬──────────────────────────────────────┘
                   │ HTTP fetch (Vite proxy → :8766)
                   ▼
┌──────────────────────────────────────────────────────────┐
│             FastAPI 服务层 (server_v2.py)                  │
│  ┌────────────────────────────────────────────────────┐  │
│  │  80+ REST 端点 (api/v2/*)                          │  │
│  │  并发控制: threading.Lock → 429                    │  │
│  └────────────────────────────────────────────────────┘  │
│          │ 导入调用            │ subprocess               │
│          ▼                     ▼                          │
│  ┌──────────────┐   ┌───────────────────┐                │
│  │  db_helper   │   │  sync_all.py      │                │
│  │  signals     │   │  fetch_news.py    │                │
│  │  fetchers/*  │   │  backtest_engine  │                │
│  │  pattern_eng │   │  paper_trading    │                │
│  └──────┬───────┘   │  optimize_predict │                │
│         │           └───────────────────┘                │
│         ▼                                                │
│  ┌────────────┐  ┌──────────┐  ┌───────────┐            │
│  │ stock.db   │  │ data/    │  │ scripts/  │            │
│  │ (SQLite)   │  │ *.json   │  │ fetchers/ │            │
│  └────────────┘  └──────────┘  └───────────┘            │
└──────────────────────────────────────────────────────────┘
```

### 2.3 性能分析

| 指标 | 典型值 | 说明 |
|------|--------|------|
| API 响应（SQLite 查询） | <50ms | 纯内存操作，无网络延迟 |
| 脚本编排启动 | 1-3s | subprocess + Python 解释器冷启动 |
| 全量同步（sync_all） | ~180s | 含新闻抓取、K线补全、ML预测训练 |
| 行情刷新 | ~5s | 分布式数据源回退 |
| 回测运行 | 10-60s | 取决于窗口大小和股票数量 |
| 首页加载 | ~500KB | 15 个 API 并行请求 |
| 并发限制 | 1（全局锁） | 单用户设计，长耗时任务互斥 |

### 2.4 启动初始化

启动时自动执行以下初始化操作：

```python
# 1. 纸面交易表初始化（确保表结构存在）
# 2. 纸面交易纸面策略表初始化
# 3. 形态规则表初始化（33条标准K线形态规则）
# 4. 清理过期回测记录
# 5. 初始化公司关系表结构
# 6. 检查 NeoData API token 状态
```

控制台输出示例：
```
✓ 纸面交易表初始化完成
✓ 形态规则表初始化完成（33条规则）
✓ 回测过期记录清理完成
Uvicorn running on http://127.0.0.1:8766
```

---

## 3. 功能介绍和实现方式

### 3.1 路由总览

```python
# ── 前端静态资源 ──────────────────────────────────
app.mount("/", StaticFiles(directory=DIST_DIR, html=True))

# ── 初始化 / 系统 ──────────────────────────────────
GET  /api/v2/init              # 全量初始化数据（15个接口聚合）
GET  /api/system-data          # 遗留系统数据（兼容旧版）
GET  /api/audit                # 审计日志
GET  /api/v2/snapshot          # 快照数据

# ── 自选股管理 ─────────────────────────────────────
GET    /api/v2/watchlist       # 获取自选股列表
POST   /api/v2/watchlist       # 添加自选股
DELETE /api/v2/watchlist/{code} # 删除自选股

# ── 行情 / K 线 ────────────────────────────────────
GET /api/v2/quotes             # 行情快照（含价格/涨跌/PE/PB/股息率）
POST /api/v2/quotes/refresh    # 刷新行情（触发数据源回退链）
GET /api/v2/kline/daily        # 日K线（全部自选股）
GET /api/v2/kline/daily/{code} # 日K线（单只股票）
GET /api/v2/kline/monthly      # 月K线（全部自选股）
GET /api/v2/kline/monthly/{code} # 月K线（单只股票）

# ── 持仓 / 交易 ────────────────────────────────────
GET /api/v2/positions          # 全部持仓（当前+已清仓）
GET /api/v2/positions/current  # 当前持仓
GET /api/v2/positions/closed   # 已清仓持仓
GET /api/v2/trades             # 交易流水
GET /api/v2/dividends          # 分红记录

# ── 预测 ────────────────────────────────────────────
GET /api/v2/predictions/daily  # 日预测数据
GET /api/v2/learning           # 学习参数
GET /api/v2/accuracy           # 准确率统计
GET /api/v2/seasonal           # 季节性数据

# ── 新闻 ────────────────────────────────────────────
GET /api/v2/news               # 新闻列表

# ── 专家报告 ────────────────────────────────────────
GET  /api/v2/expert            # 专家报告列表
POST /api/v2/expert/import     # 导入专家报告

# ── 形态规则 ────────────────────────────────────────
GET    /api/v2/pattern-rules   # 规则列表
POST   /api/v2/pattern-rules   # 创建规则
PUT    /api/v2/pattern-rules/{id} # 更新规则
DELETE /api/v2/pattern-rules/{id} # 删除规则
GET    /api/v2/pattern-rules/scan  # 扫描K线匹配形态

# ── 公司关系图谱 ────────────────────────────────────
GET /api/v2/company-relations  # 公司关系数据
GET /api/v2/graph-data         # 图谱渲染数据
GET /api/v2/relation-types     # 关系类型列表

# ── 行业股票 ────────────────────────────────────────
GET /api/v2/industries         # 行业列表
GET /api/v2/industries-stocks  # 行业股票列表

# ── 回测 ────────────────────────────────────────────
POST /api/v2/backtest/run      # 启动回测
GET  /api/v2/backtest/status   # 回测状态
POST /api/v2/backtest/stop     # 停止回测
GET  /api/v2/backtest/results/{run_id} # 回测结果
GET  /api/v2/backtest/history  # 回测历史

# ── 纸面交易 ────────────────────────────────────────
GET  /api/v2/paper/account     # 账户信息
GET  /api/v2/paper/positions   # 持仓
GET  /api/v2/paper/suggestions # 交易建议
POST /api/v2/paper/execute     # 执行交易
POST /api/v2/paper/generate    # 生成建议
POST /api/v2/paper/reset       # 重置账户
GET  /api/v2/paper/trades      # 交易记录
GET  /api/v2/paper/performance # 表现统计
GET  /api/v2/paper/auto-status # 自动执行状态
GET  /api/v2/paper/suggestions-history # 建议历史
GET  /api/v2/paper/verify      # 数据验证
POST /api/v2/paper/intraday/collect # 日内数据采集
GET  /api/v2/paper/intraday/{code}  # 日内分时数据

# ── 触发器 ──────────────────────────────────────────
POST /api/trigger/predict     # 触发全量同步+预测
POST /api/trigger/news        # 触发新闻采集

# ── 配置 / 工具 ────────────────────────────────────
GET  /api/v2/config           # 系统配置
POST /api/upload/statement    # 上传对账单
GET  /api/search/stocks       # 股票搜索
GET  /api/v2/neodata/info     # NeoData 账户信息
GET  /api/v2/neodata/quota    # NeoData 额度信息

# ── 静态文件服务 ────────────────────────────────────
/      → deliverables/v2/dist/index.html
/assets/{path} → 前端 JS/CSS 资源
/data/{path}   → data/ 目录文件
/scripts/{path} → scripts/ 目录非 .py 文件
```

### 3.2 脚本编排

通过 `run_script()` 函数调用：

```python
def run_script(name, timeout=60):
    """通过 subprocess 调用 scripts/<name>"""
    script = os.path.join(ROOT_DIR, "scripts", name)
    r = subprocess.run([PYTHON, script], cwd=ROOT_DIR,
                       capture_output=True, text=True, timeout=timeout)
    return r.returncode == 0, (r.stdout + r.stderr)[-2000:]
```

| 脚本 | 超时 | 触发源 |
|------|------|--------|
| `sync_all.py` | 300s | POST /api/trigger/predict |
| `fetch_news.py` | 120s | POST /api/trigger/news |
| `update_from_statement.py` | 120s | POST /api/upload/statement |

### 3.3 并发控制

```python
_refresh_lock = threading.Lock()
_refresh_in_progress = False

# 所有长耗时操作共享全局锁
# 正在运行时重复请求返回 {"success": false, "error": "sync already in progress", "progress": n}
```

被保护的端点：POST /api/trigger/predict, POST /api/trigger/news, POST /api/upload/statement

### 3.4 响应格式

```json
{
  "success": true/false,
  "data": { ... },        // 成功时返回的数据
  "error": "错误信息",     // 失败时的错误描述
  "progress": 50,         // 正在进行中的任务进度（百分比）
  "timestamp": "2026-06-16 17:10:00"  // 数据时间戳
}
```

---

## 4. 用户操作流程

### 4.1 启动系统

```
用户: 运行 python server_v2.py

控制台输出:
  ✓ 纸面交易表初始化完成
  ✓ 形态规则表初始化完成（33条规则）
  ✓ 回测过期记录清理完成
  Uvicorn running on http://127.0.0.1:8766

用户: 浏览器打开 http://localhost:8766
  → FastAPI 返回 index.html (SPA)
  → Vue 应用加载 → App.vue 渲染布局
  → 并行请求 15 个 API 完成数据初始化
  → 根据路由默认显示持仓总览页面
```

### 4.2 导航结构

```
┌─ 股票投资管理系统 V2 ────────────────────────────────┐
│ [个人交易数据] [股票分析预测] [股票信息收集] [模拟交易] │
│  ├ 持仓总览        ├ 智能预测        ├ 新闻动态        │
│  ├ 交易记录        ├ 专家分析        ├ 股票数据        │
│  ├ 手续费分析                        ├ K线走势         │
│  └ 管理设置                          ├ 形态规则        │
│                                      └ 公司关系图谱    │
│             [个人交易数据]  [股票分析预测]             │
│             [股票信息收集]  [模拟交易]   [刷新]        │
└──────────────────────────────────────────────────────┘
```

### 4.3 全量刷新流程

```
用户在任意页面点击工具栏 [🔄] 按钮
  → useDataStore.triggerFullRefresh()
  → POST /api/trigger/predict
  → 后端: subprocess.run(sync_all.py, timeout=300s)
  → sync_all.py 8步执行:
      Step 1: 抓取新闻 (fetch_news.py)
      Step 1.5: 抓取分红 (东方财富)
      Step 2: 并行获取K线 (ThreadPoolExecutor 4并发)
      Step 3: 回填预测验证
      Step 4: 重算准确率
      Step 5: 自学习更新
      Step 6: 生成10日预测
      Step 7: 季节性因子 + 月K线 + 行情快照
  → 完成后 fetchAll() 重新加载数据
  → 按钮状态恢复
```

### 4.4 对账单上传流程

```
用户在管理页面上传对账单 ZIP 文件
  → POST /api/upload/statement (multipart/form-data)
  → 后端检查: 文件大小 >100 字节, 魔数 PK\x03\x04
  → 保存 + 自动备份 (broker_statement.json.bak_{timestamp})
  → subprocess → update_from_statement.py
  → 解析后写入 SQLite (positions/trades/dividends)
  → 返回处理结果
  → 前端自动刷新数据
```

---

## 5. 依赖关系

### 5.1 后端 Python 模块

| 模块 | 关系 | 路径 |
|------|------|------|
| `db_helper` | import | `scripts/db_helper.py` |
| `fetchers` | import | `scripts/fetchers/__init__.py` |

### 5.2 subprocess 调用脚本

| 脚本 | 超时 | 用途 |
|------|------|------|
| `sync_all.py` | 300s | 全量数据同步 + 预测 |
| `fetch_news.py` | 120s | 新闻采集 |
| `update_from_statement.py` | 120s | 对账单解析 |

### 5.3 前端依赖

| 包 | 用途 |
|------|------|
| Vue 3 | SPA 框架 |
| Vue Router 4 | 前端路由 |
| Pinia | 状态管理 |
| Chart.js + chartjs-chart-financial | K线图和统计图 |
| @antv/g6 | 关系图谱可视化 |
| Vite | 构建工具 |

### 5.4 数据库表依赖

27+ 张表：详见 [02-database-layer.md](02-database-layer.md)

---

## 6. API 端点总览

| # | 方法 | 路径 | 组 | 说明 |
|---|------|------|-----|------|
| 1 | GET | /api/v2/init | 初始化 | 全量初始化数据 |
| 2 | GET | /api/system-data | 初始化 | 遗留系统数据 |
| 3 | GET | /api/audit | 初始化 | 审计日志 |
| 4 | GET | /api/v2/config | 配置 | 获取系统配置 |
| 5 | GET | /api/v2/watchlist | 自选股 | 获取自选股列表 |
| 6 | POST | /api/v2/watchlist | 自选股 | 添加自选股 |
| 7 | DELETE | /api/v2/watchlist/{code} | 自选股 | 删除自选股 |
| 8 | GET | /api/v2/quotes | 行情 | 行情快照 |
| 9 | POST | /api/v2/quotes/refresh | 行情 | 刷新行情 |
| 10 | GET | /api/v2/kline/daily | K线 | 全部日K线 |
| 11 | GET | /api/v2/kline/daily/{code} | K线 | 单只日K线 |
| 12 | GET | /api/v2/kline/monthly | K线 | 全部月K线 |
| 13 | GET | /api/v2/kline/monthly/{code} | K线 | 单只月K线 |
| 14 | GET | /api/v2/positions | 持仓 | 全部持仓 |
| 15 | GET | /api/v2/positions/current | 持仓 | 当前持仓 |
| 16 | GET | /api/v2/positions/closed | 持仓 | 已清仓持仓 |
| 17 | GET | /api/v2/trades | 交易 | 交易流水 |
| 18 | GET | /api/v2/dividends | 交易 | 分红记录 |
| 19 | GET | /api/v2/predictions/daily | 预测 | 日预测 |
| 20 | GET | /api/v2/learning | 预测 | 学习参数 |
| 21 | GET | /api/v2/accuracy | 预测 | 准确率统计 |
| 22 | GET | /api/v2/seasonal | 预测 | 季节性数据 |
| 23 | GET | /api/v2/news | 新闻 | 新闻列表 |
| 24 | GET | /api/v2/expert | 专家 | 专家报告列表 |
| 25 | POST | /api/v2/expert/import | 专家 | 导入专家报告 |
| 26 | GET | /api/v2/pattern-rules | 形态 | 规则列表 |
| 27 | POST | /api/v2/pattern-rules | 形态 | 创建规则 |
| 28 | PUT | /api/v2/pattern-rules/{id} | 形态 | 更新规则 |
| 29 | DELETE | /api/v2/pattern-rules/{id} | 形态 | 删除规则 |
| 30 | GET | /api/v2/pattern-rules/scan | 形态 | 扫描K线 |
| 31 | GET | /api/v2/company-relations | 关系 | 公司关系数据 |
| 32 | GET | /api/v2/graph-data | 关系 | 图谱渲染数据 |
| 33 | GET | /api/v2/relation-types | 关系 | 关系类型列表 |
| 34 | GET | /api/v2/industries | 行业 | 行业列表 |
| 35 | GET | /api/v2/industries-stocks | 行业 | 行业股票 |
| 36 | POST | /api/trigger/predict | 触发器 | 触发全量同步 |
| 37 | POST | /api/trigger/news | 触发器 | 触发新闻采集 |
| 38 | POST | /api/upload/statement | 上传 | 上传对账单 |
| 39 | GET | /api/search/stocks | 搜索 | 股票搜索 |
| 40 | POST | /api/v2/backtest/run | 回测 | 启动回测 |
| 41 | GET | /api/v2/backtest/status | 回测 | 回测状态 |
| 42 | POST | /api/v2/backtest/stop | 回测 | 停止回测 |
| 43 | GET | /api/v2/backtest/results/{run_id} | 回测 | 回测结果 |
| 44 | GET | /api/v2/backtest/history | 回测 | 回测历史 |
| 45 | GET | /api/v2/paper/account | 纸面交易 | 账户信息 |
| 46 | GET | /api/v2/paper/positions | 纸面交易 | 持仓 |
| 47 | GET | /api/v2/paper/suggestions | 纸面交易 | 交易建议 |
| 48 | GET | /api/v2/paper/trades | 纸面交易 | 交易记录 |
| 49 | GET | /api/v2/paper/performance | 纸面交易 | 表现统计 |
| 50 | POST | /api/v2/paper/execute | 纸面交易 | 执行交易 |
| 51 | POST | /api/v2/paper/generate | 纸面交易 | 生成建议 |
| 52 | POST | /api/v2/paper/reset | 纸面交易 | 重置账户 |
| 53 | GET | /api/v2/paper/auto-status | 纸面交易 | 自动执行状态 |
| 54 | GET | /api/v2/paper/suggestions-history | 纸面交易 | 建议历史 |
| 55 | GET | /api/v2/paper/verify | 纸面交易 | 数据验证 |
| 56 | POST | /api/v2/paper/intraday/collect | 纸面交易 | 日内数据采集 |
| 57 | GET | /api/v2/paper/intraday/{code} | 纸面交易 | 日内分时数据 |
| 58 | GET | /api/v2/neodata/info | NeoData | 账户信息 |
| 59 | GET | /api/v2/neodata/quota | NeoData | 额度信息 |
