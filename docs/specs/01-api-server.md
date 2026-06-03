# 模块1: Web API 服务层

> **核心文件**: `server.py` | **前端**: `deliverables/bank-stock-system.html`, `deliverables/js/*.js` | **端口**: 8765 | **基类**: `ThreadedHTTPServer` | **版本**: V0.7

---

## 1. 功能概述

基于 Python `http.server` 的多线程 HTTP 服务器，为前端单页应用提供 RESTful API 接口。承接前端所有数据请求，通过子进程调用后台脚本执行数据同步任务，并直接查询 SQLite 数据库返回结构化 JSON 数据。

---

## 2. 核心业务逻辑

### 2.1 服务器初始化
- 绑定 `127.0.0.1:8765`
- 使用 `ThreadedHTTPServer`（`ThreadingMixIn` + `HTTPServer`），支持多请求并发
- 守护线程模式 (`daemon_threads = True`)，主线程退出时自动回收
- Python运行时路径通过动态检测或环境变量获取（V0.7改进）

### 2.2 请求路由
根据 URL path 和 HTTP method 分发：

| Method | 功能 |
|--------|------|
| **GET** | 数据查询 (40个端点)、静态文件服务 (`/deliverables/*`, `/data/*`)、DB查看器 (`/dbview`) |
| **POST** | 自选股增删 (`/api/v2/watchlist`, `/api/watchlist/add`)、触发器执行 (`/api/trigger/*`)、对账单上传 (`/api/upload/statement`)、专家报告导入 (`/api/v2/expert/import`) |
| **DELETE** | 自选股移除及级联数据清理 (`/api/v2/watchlist/{code}`) |
| **OPTIONS** | CORS 预检，允许跨域请求 |

> ⚠️ **路由顺序敏感**: 精准匹配路径（如 `/api/v2/kline/daily`）必须在模糊匹配路径（如 `startswith("/api/v2/kline/daily")`）之前。静态文件路由有Python文件访问保护（403）。

### 2.3 脚本编排
通过 `subprocess.run()` 调用 Python 子进程执行后台脚本：

| 脚本 | 最大超时 | 触发端点 |
|------|---------|---------|
| `sync_all.py` | 180s | `POST /api/trigger/predict`, `POST /api/watchlist/add`, `POST /api/v2/watchlist` |
| `fetch_news.py` | 60s | `POST /api/trigger/news` |
| `update_from_statement.py` | 30s | `POST /api/trigger/update_statement`, `POST /api/upload/statement` |
| `reinject_data.py` | 10s | 链式调用（对账单上传后） |
| `audit_system.py` | 60s | `GET /api/audit` |

### 2.4 并发控制
- 使用 `threading.Lock` + `_refresh_in_progress` 标志防止同步任务重复执行
- 并发同步请求时返回 HTTP 429 (Too Many Requests)

### 2.5 对账单上传处理
- 手动解析 `multipart/form-data` 边界（未使用标准库解析器）
- 提取文件保存到 `广发易淘金PC版-普通对账单结果查询.xlsx`，创建 `.bak` 备份
- 自动链式触发 `update_from_statement.py` → `reinject_data.py`

---

## 3. 输入输出参数定义

### 3.1 统一响应格式

```json
// 成功
{ "success": true, "data": <any>, "count?": <number>, "message?": "<string>" }

// 失败
{ "success": false, "error": "<string>", "trace?": "<string>" }
```

### 3.2 API端点清单

完整端点列表、参数及返回值详见 [附录B: API端点清单](./appendix-b-api.md)。

核心端点速览：

| 类别 | 端点前缀 | 说明 |
|------|---------|------|
| 初始化 | `GET /api/v2/init` | 前端加载时获取全量数据 |
| 自选股 | `/api/v2/watchlist` + `/api/watchlist/*` | CRUD（含双向JSON/SQLite同步） |
| 行情 | `/api/v2/quotes` | 批量/单股票行情 |
| 持仓 | `/api/v2/positions/*` | 当前/已清仓/交易记录 |
| K线 | `/api/v2/kline/*` | 日K/月K（批量+单股票） |
| 预测 | `/api/v2/predictions/daily` | 每日预测列表 |
| 新闻 | `/api/v2/news` | 支持 all/major/{code} 过滤 |
| 专家报告 | `/api/v2/expert` + `/api/v2/expert/import` | 查看/导入 |
| 学习参数 | `/api/v2/learning` | 批量/单股票 |
| 准确率 | `/api/v2/accuracy` | 批量/单股票 |
| 季节性 | `/api/v2/seasonal` | 批量/单股票 |
| 配置 | `/api/v2/config` | 系统配置项 |
| 搜索 | `/api/search/stocks` | A股模糊搜索（含拼音） |
| 触发器 | `/api/trigger/*` | 手动触发同步任务 |
| 上传 | `/api/upload/statement` | 对账单文件上传 |
| 审计 | `/api/audit` | 系统健康检查 |
| 工具 | `/dbview` | SQLite数据库浏览器 |

---

## 4. 依赖关系

| 方向 | 模块/文件 | 说明 |
|------|----------|------|
| **依赖库** | `http.server`, `socketserver`, `urllib.parse`, `sqlite3`, `subprocess`, `threading`, `datetime`, `json` | Python标准库 |
| **导入调用** | [数据库访问层](./02-database-layer.md) | `from db_helper import ...` |
| **子进程调用** | [同步引擎](./03-sync-engine.md), [新闻抓取](./07-news-fetcher.md), [对账单解析](./09-statement-parser.md), [数据注入](./11-data-injection.md), [专家报告](./10-expert-report.md), [系统审计](./12-migration-and-audit.md) | 通过 `run_script()` |
| **被依赖** | `bank-stock-system.html` (前端) | 通过 `fetch()` 调用所有API |

---

## 5. 异常处理机制

| 场景 | HTTP Code | 响应 |
|------|-----------|------|
| 正常处理 | 200 | `{success: true, ...}` |
| 参数缺失/无效 | 400 | `{success: false, error: "..."}` |
| 资源不存在 | 404 | `{success: false, error: "Unknown endpoint: ..."}` |
| Python文件访问 | 403 | `{error: "Forbidden"}` |
| 重复添加 | 409 | `{success: false, error: "股票 XXX 已存在"}` |
| 并发冲突 | 429 | `{success: false, error: "刷新已在运行中，请稍候"}` |
| 服务端异常 | 500 | `{success: false, error: ..., trace: ...}` |
| 子进程超时 | 200 | `{success: false, error: "Script timed out after Ns"}` |
| DB不可用 | 500 | `{success: false, error: "DB not available"}` |

- 所有 API 端点均包裹 `try/except`
- 子进程输出截断：stdout 最多 3000 字符，stderr 最多 1000 字符
- CORS 头 `Access-Control-Allow-Origin: *` 全局透出
