# 模块1: Web API 服务层

> **核心文件**: `server_v2.py` (FastAPI) / `server.py` (原版保留) | **前端**: `deliverables/bank-stock-system.html`, `deliverables/v2/` (Vue 3) | **端口**: 8766 | **框架**: FastAPI + Uvicorn | **版本**: V0.8

---

## 1. 功能概述

基于 Python **FastAPI** 的异步 HTTP 服务器（V0.8 升级），为前端提供 RESTful API 接口。
V0.8 从原 `http.server` (ThreadedHTTPServer) 迁移至 FastAPI，所有 API 输入输出、业务逻辑、边界条件与原版完全一致。
原版 `server.py` (端口 8765) 保留兼容，两者可并行运行。

---

## 2. 核心业务逻辑

### 2.1 服务器初始化
- 绑定 `127.0.0.1:8766`
- 使用 **FastAPI** + **Uvicorn** (ASGI) 替代原 `ThreadingMixIn` + `HTTPServer`
- 异步请求处理，自动线程池支持同步阻塞操作 (如 `subprocess.run()`)
- 自动生成 Swagger UI 文档 (`/docs`)
- CORS 中间件声明式配置
- Python 运行时: 系统 Python 3.12+ (需 `fastapi`, `uvicorn`, `python-multipart`)

### 2.2 请求路由
V0.8 使用 FastAPI `@app.get()` / `@app.post()` / `@app.delete()` 装饰器替代原 `if/elif startswith()` 串行匹配。

| Method | 功能 |
|--------|------|
| **GET** | 数据查询 (46个端点)、静态文件服务 (`/deliverables/*`, `/data/*`)、DB查看器 (`/dbview`) |
| **POST** | 自选股增删 (`/api/v2/watchlist`, `/api/watchlist/add`)、触发器执行 (`/api/trigger/*`)、对账单上传 (`/api/upload/statement`)、专家报告导入 (`/api/v2/expert/import`) |
| **DELETE** | 自选股移除及级联数据清理 (`/api/v2/watchlist/{code}`) |
| **OPTIONS** | CORS 预检 (自动处理，无需手动定义) |

> ✅ **路由顺序**: FastAPI 自动按精确匹配 > 动态匹配优先级路由，消除原版 `startswith` 顺序敏感问题。`.py` 文件访问仍被拦截 (403)。

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
- Uvicorn 异步事件循环 + 线程池自动处理多请求并发

### 2.5 对账单上传处理
- 使用 FastAPI `UploadFile` 标准处理 multipart/form-data (替代手动解析)
- 魔数检测、格式诊断、备份逻辑与原版完全一致
- 提取文件保存到 `广发易淘金PC版-普通对账单结果查询.xlsx`，创建 `.bak` 备份
- 自动链式触发 `update_from_statement.py` → `reinject_from_db.py`

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
| **依赖库** | `fastapi`, `uvicorn`, `python-multipart`, `sqlite3`, `subprocess`, `threading`, `datetime`, `json` | PyPI + 标准库 |
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
