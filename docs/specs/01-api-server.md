# 模块 1: Web API 服务层

> **核心文件**: `server_v2.py` | **端口**: 8766
> **文档类型**: 技术规格说明 | **版本**: v2.0 | **更新日期**: 2026-06-06

---

## 1. 功能概述

V2 系统的统一 API 入口，基于 FastAPI + Uvicorn 构建，提供 RESTful 接口和静态前端资源服务。

| 特性 | 说明 |
|------|------|
| 框架 | FastAPI + Uvicorn |
| 端口 | 127.0.0.1:8766 |
| 自动文档 | http://localhost:8766/docs (Swagger UI) |
| 前端托管 | 构建后的 Vue 3 SPA（`deliverables/v2/dist/`） |

---

## 2. 核心业务逻辑

### 2.1 服务器初始化

```python
app = FastAPI(title="股票投资管理系统 V2")
app.add_middleware(CORSMiddleware, allow_origins=["*"], ...)
# 绑定 127.0.0.1:8766，Uvicorn 自动启动
```

启动时自动：
- 初始化纸面交易表（`paper_account`, `paper_positions` 等）
- 初始化形态规则表（`pattern_rules`）
- 清理过期回测记录

### 2.2 请求路由

| 类型 | 端点 | 功能 |
|------|------|------|
| 首页 | `GET /` | 返回 V2 前端构建产物 `deliverables/v2/dist/index.html` |
| 前端静态资源 | `GET /assets/{path}` | 提供 V2 前端 JS/CSS 构建产物 |
| 图表库 | `GET /chart.umd.min.js` | Chart.js 图表库（来自 V2 dist） |
| 图表库 | `GET /chartjs-chart-financial.min.js` | 金融图表库（来自 V2 dist） |
| 核心 API | `GET/POST /api/v2/...` | 40+ 个 RESTful API 端点 |
| 数据文件 | `GET /data/{path}` | 数据目录静态文件服务（JSON 配置文件等） |
| 脚本文件 | `GET /scripts/{path}` | 脚本目录静态文件服务（日志等） |

**路由总览**：约 60 个 GET + 10 个 POST + 1 个 DELETE + 2 个 PUT

### 2.3 脚本编排

通过 `subprocess.run()` 异步调用 `scripts/` 目录下的业务脚本：

| 端点 | 脚本 | 超时 |
|------|------|------|
| `POST /api/trigger/predict` | `sync_all.py` | 180s |
| `POST /api/trigger/news` | `fetch_news.py` | 60s |
| `POST /api/trigger/update_statement` | `update_from_statement.py` | 60s |
| `POST /api/trigger/expert` | `import_expert_report.py` | 60s |
| `POST /api/v2/backtest/run` | `backtest_engine.py` | 300s |
| `POST /api/upload/statement` | `update_from_statement.py` | 60s |

### 2.4 并发控制

- `threading.Lock` + `_refresh_in_progress` 全局标志
- 长耗时操作（sync_all / backtest）并行执行时返回 HTTP 429
- 缓存机制：`_init_cache` (TTL 5s) 避免重复读取

### 2.5 对账单上传处理

```
POST /api/upload/statement
  ├── Layer 1: 文件大小检查（>100 字节）
  ├── Layer 2: 魔数检测（PK\x03\x04 ZIP 格式）
  ├── Layer 3: 保存 + 自动备份（.bak_{timestamp} + .upload_bak）
  └── Layer 4: 解析 update_from_statement.py → SQLite
      返回：{ success: true, message: "对账单已更新，刷新页面查看" }
```

---

## 3. 输入输出参数定义

### 3.1 统一响应格式

```json
// 成功
{ "success": true, "data": {...} }

// 失败
{ "success": false, "error": "...", "message": "..." }
```

### 3.2 核心 API 端点

| 分类 | 端点 | 方法 |
|------|------|------|
| 初始化 | `/api/v2/init` | GET |
| 自选股 | `/api/v2/watchlist` | GET / POST |
| 自选股删除 | `/api/v2/watchlist/{code}` | DELETE |
| 行情 | `/api/v2/quotes` / `{code}` | GET |
| 持仓 | `/api/v2/positions` / `current` / `closed` | GET |
| 交易 | `/api/v2/trades` | GET |
| 分红 | `/api/v2/dividends` | GET |
| K线 | `/api/v2/kline/daily` / `monthly` | GET |
| 预测 | `/api/v2/predictions/daily` | GET |
| 新闻 | `/api/v2/news` | GET |
| 专家报告 | `/api/v2/expert` | GET / POST |
| 学习参数 | `/api/v2/learning` | GET |
| 准确率 | `/api/v2/accuracy` | GET |
| 季节性 | `/api/v2/seasonal` | GET |
| 配置 | `/api/v2/config` | GET |
| 快照 | `/api/v2/snapshot` | GET |
| 搜索 | `/api/search/stocks` | GET |
| 审计 | `/api/audit` | GET |
| 回测 | `/api/v2/backtest/run` / `status` / `results/{id}` / `history` | GET/POST |
| 纸面交易 | `/api/v2/paper/account` / `positions` / `trades` / `suggestions` / `performance` | GET |
| 形态规则 | `/api/v2/pattern-rules` | GET/POST/PUT/DELETE |

> 完整端点清单见 [附录 B — API 端点清单](appendix-b-api.md)

---

## 4. 依赖关系

### 4.1 导入依赖

```python
from scripts.db_helper import (get_stock_search, get_watchlist, ...)
```

### 4.2 子进程调用

通过 `run_script()` 调用：`sync_all.py`、`fetch_news.py`、`update_from_statement.py`、`import_expert_report.py`、`backtest_engine.py`、`paper_trading.py`、`audit_system.py`

### 4.3 被依赖关系

- 前端 Vue 3 SPA 通过 `/api/v2/...` 获取所有数据
- V2 前端构建产物位于 `deliverables/v2/dist/`（含 `index.html` + `assets/` + 图表库）

---

## 5. 异常处理机制

| 场景 | HTTP Code | 响应体 |
|------|-----------|--------|
| 正常返回 | 200 | `{ success: true, data: {...} }` |
| 参数错误 / 业务异常 | 200 | `{ success: false, error: "...", message: "..." }` |
| 资源不存在 | 404 | FastAPI 默认 404 |
| 上传文件格式错误 | 400 | `{ success: false, error: "...", diagnostics: {...} }` |
| 脚本超时 / 子进程失败 | 200 | `{ success: false, error: "...", output: "..." }` |
| 并发刷新冲突 | 429 | `{ success: false, error: "刷新已在运行中" }` |
| 500 内部错误 | 500 | `{ success: false, error: traceback }` |
| 静态文件缺失 | 503 | HTML 提示 "前端构建文件缺失" |
