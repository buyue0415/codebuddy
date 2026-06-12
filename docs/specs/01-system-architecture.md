# 01 — 系统架构与 API 服务层

> **核心文件**: `server_v2.py` | **端口**: 8766 | **框架**: FastAPI + Uvicorn
> **前端入口**: `deliverables/v2/dist/index.html`（Vue 3 + Vite 构建）

---

## 1. 业务需求说明书

### 1.1 业务背景

系统需要一个统一的 Web 服务入口，将所有后端能力（数据查询、脚本编排、文件上传）通过 RESTful API 暴露给前端 Vue 3 SPA，同时作为静态文件服务器托管前端构建产物。

### 1.2 核心目标

| 目标 | 说明 |
|------|------|
| 统一 API 网关 | 所有数据读写通过 FastAPI 路由分发，单一入口 |
| 静态前端托管 | 直接提供 Vite 构建的 Vue 3 SPA 静态文件 |
| 脚本编排 | 通过 subprocess 异步调用后台计算脚本 |
| 并发控制 | 全局锁防止重复触发的同步/回测任务 |

---

## 2. 技术方案深度分析

### 2.1 架构决策

**为什么选 FastAPI？**
- 原生 async 支持，SQLite 不走异步但未来可扩展
- 自动生成 Swagger UI（`/docs`）和 OpenAPI schema
- Pydantic 类型校验，减少运行时错误
- 比旧版 `http.server` 性能高 5-10 倍

**前端托管方案**：构建产物 `deliverables/v2/dist/` 直接由 FastAPI 提供（开发模式用 Vite dev server proxy，生产直接用构建产物）

### 2.2 性能分析

| 指标 | 典型值 | 说明 |
|------|--------|------|
| API 响应 (SQLite 查询) | <100ms | 纯内存操作，无网络 |
| 脚本编排启动 | 1-3s | subprocess + Python 解释器冷启动 |
| 首页加载 | ~500KB | 15 个 API 并行请求 |
| 并发限制 | 1（全局锁） | 单用户设计，同步/回测互斥 |

### 2.3 安全性

- 🔴 绑定 `127.0.0.1`，仅本地可访问
- 🟡 subprocess 使用 `list` 参数传递，不经过 shell
- 🟢 SQLite 参数化查询防注入
- 🟢 上传文件魔数检测（PK\x03\x04 ZIP 格式）

---

## 3. 功能介绍和实现方式

### 3.1 路由总览

```python
# server_v2.py 路由分 4 类

# ── 前端静态资源 ──
@app.get("/")                    # V2 dist/index.html
@app.get("/assets/{path}")       # JS/CSS bundles
@app.get("/chart.umd.min.js")    # Chart.js 图表库
@app.get("/chartjs-chart-financial.min.js")  # 金融图表库

# ── 核心 API (40+) ──
@app.get("/api/v2/init")         # 初始化数据（15 个 API 聚合）
@app.get("/api/v2/watchlist")    # 自选股
# ... 见附录B完整清单

# ── 触发器 (POST) ──
@app.post("/api/trigger/predict")    # → sync_all.py (180s)
@app.post("/api/trigger/news")       # → fetch_news.py (60s)
@app.post("/api/upload/statement")   # → update_from_statement.py (60s)

# ── 静态文件服务 ──
@app.get("/data/{path}")         # data/ 目录文件
@app.get("/scripts/{path}")      # scripts/ 目录非.py文件
```

### 3.2 脚本编排

通过 `run_script()` 函数调用：

```python
def run_script(name, timeout=60):
    """Call scripts/<name> via subprocess, return (success, output)"""
    script = os.path.join(ROOT, "scripts", name)
    r = subprocess.run([PYTHON, script], cwd=ROOT,
                       capture_output=True, text=True, timeout=timeout)
    return r.returncode == 0, (r.stdout + r.stderr)[-2000:]
```

### 3.3 并发控制

```python
_refresh_lock = threading.Lock()
_refresh_in_progress = False

# 同步/回测/上传等长耗时操作共用全局锁
# 重复请求返回 429
```

### 3.4 启动时初始化

```python
# server_v2.py 启动时自动：
# 1. 初始化纸面交易表
# 2. 初始化形态规则表（33条标准规则）
# 3. 清理过期回测记录
```

### 3.5 对账单上传处理链

```
POST /api/upload/statement
  ├── Layer 1: 文件大小检查（>100 字节）
  ├── Layer 2: 魔数检测（PK\x03\x04 ZIP 格式）
  ├── Layer 3: 保存 + 自动备份（.bak_{timestamp}）
  └── Layer 4: subprocess → update_from_statement.py → SQLite
```

---

## 4. 用户操作流程

### 4.1 启动系统

```
用户: 双击 start.bat 或运行 python server_v2.py
控制台输出:
  ✓ 纸面交易表初始化完成
  ✓ 形态规则表初始化完成
  Uvicorn running on http://127.0.0.1:8766

用户: 浏览器打开 http://localhost:8766
  → FastAPI 返回 deliverables/v2/dist/index.html
  → Vue SPA 加载，并行请求 15 个 API
  → 首页 "持仓总览" 渲染完成
```

### 4.2 手动刷新数据

```
用户: 导航栏 "股票分析预测" → "智能预测"
  → 点击 [🔄 刷新] 按钮
  → 前端: POST /api/trigger/predict
  → 后端: subprocess.run(sync_all.py, timeout=180s)
  → 前端轮询: 按钮显示 "刷新中..."（禁用状态）
  → 完成后: 自动重新加载数据，预测更新
```

---

## 5. 依赖关系

| 模块 | 关系 | 调用方式 |
|------|------|---------|
| `db_helper.py` | 导入调用 | `from db_helper import get_watchlist, ...` |
| `sync_all.py` | 子进程 | `subprocess.run([PYTHON, 'sync_all.py'])` |
| `fetch_news.py` | 子进程 | `subprocess.run([PYTHON, 'fetch_news.py'])` |
| `update_from_statement.py` | 子进程 | `subprocess.run([PYTHON, 'update_from_statement.py'])` |
| Vue 3 SPA | HTTP 客户端 | `fetch(/api/v2/...)` 通过 Vite proxy |
