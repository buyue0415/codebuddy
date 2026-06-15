# 架构约束 (Architecture Constraints)

> **版本**: v2.0 | **级别**: 🔴 MUST | **更新日期**: 2026-06-04
> **适用**: 本项目所有代码、模块、脚本、配置文件

---

## 0. 文档定位

本文档是本项目的**最高级别架构规范**。所有功能开发、模块扩展、代码实现**必须**以本文档为唯一依据。违反本文档约束的实现视为不合格代码，必须在 Code Review 阶段拒绝合并。

**关联文档**（同级别 MUST 规范）：
| 文档 | 职责 |
|------|------|
| [业务逻辑规则](./business-logic-rules.md) | 数据一致性、预测算法、交易计算等业务强制规则 |
| [代码风格规范](./code-style.md) | 命名、格式、文档、错误处理等编码强制规则 |

**Architecture Decision Records**：关键技术决策记录在 `docs/specs/` 的对应模块 spec 中，新增决策必须在此文档中标注引用。

---

## 1. 系统技术架构（现状 V0.8）

### 1.1 整体架构

```
┌──────────────────────────────────────────────────────────┐
│                  表现层 (Presentation)                     │
│  deliverables/v2/  (Vue 3 SPA, Vite dev :5173)           │
│  deliverables/     (旧版 SPA, 保留兼容, 不继续开发)        │
│  仅通过 HTTP REST API 与后端通信                           │
├────────────────────────┬─────────────────────────────────┤
│  CORS + Proxy          │  Vite proxy: /api → :8766        │
├────────────────────────▼─────────────────────────────────┤
│                  服务层 (Service / API)                    │
│  server_v2.py  (FastAPI, 端口 8766, 主方案)               │
│  server.py     (http.server, 端口 8765, 保留兼容)         │
│  职责: 路由分发、请求验证、响应格式化、子进程触发            │
├────────────────────────┬─────────────────────────────────┤
│  import / subprocess    │                                  │
├────────────────────────▼─────────────────────────────────┤
│                业务层 (Business Logic)                     │
│  scripts/sync_all.py        全模块同步引擎 (8步)           │
│  scripts/optimize_predict.py ML增强预测 (RandomForest)      │
│  scripts/fetch_news.py      新闻抓取                       │
│  scripts/fetch_dividends.py 分红数据获取                   │
│  scripts/update_from_statement.py 对账单解析              │
│  scripts/scheduler.py       CLI任务编排                   │
│  scripts/backtest_engine.py 回测引擎 [待开发]              │
│  scripts/paper_trading.py   纸面交易 [待开发]              │
│  职责: 数据处理、算法计算、业务编排、外部数据获取            │
├────────────────────────┬─────────────────────────────────┤
│  import only            │                                  │
├────────────────────────▼─────────────────────────────────┤
│                数据层 (Data Access)                        │
│  scripts/db_helper.py   SQLite 唯一读写入口               │
│  职责: 封装所有 CRUD、管理连接生命周期、提供参数化查询       │
├────────────────────────┬─────────────────────────────────┤
│  sqlite3.connect()      │                                  │
├────────────────────────▼─────────────────────────────────┤
│                持久层 (Persistence)                        │
│  data/stock.db           SQLite WAL 模式 (22张表)          │
│  职责: 结构化数据持久存储                                   │
└──────────────────────────────────────────────────────────┘
```

### 1.2 技术栈明细

| 层 | 技术 | 版本 | 端口/文件 |
|----|------|------|----------|
| **前端 V2** | Vue 3 + Pinia + Vue Router | ^3.4 | `deliverables/v2/` |
| **前端 V2 构建** | Vite | ^5.2 | dev :5173 |
| **前端 V2 图表** | Chart.js + chartjs-plugin-zoom | CDN | `v2/` 中引入 |
| **前端旧版** | 原生 HTML + Chart.js | — | `deliverables/bank-stock-system.html` |
| **后端 V2** | Python 3.12+ FastAPI + Uvicorn | — | `server_v2.py` :8766 |
| **后端旧版** | Python http.server | — | `server.py` :8765 |
| **数据库** | SQLite 3 | WAL | `data/stock.db` |
| **外部数据** | NeoData (westock-data Node.js) | 22.12 | Node子进程调用 |
| **外部数据** | 广发证券对账单 Excel | — | 文件上传解析 |
| **数值计算** | numpy | — | `sync_all.py`, `backtest_engine.py` |

### 1.3 前端路由表（Vue Router）

| 路由 | 页面组件 | 导航分组 | 功能 |
|------|---------|---------|------|
| `/overview` | Overview.vue | 个人交易数据 | 持仓总览 |
| `/trades` | Trades.vue | 个人交易数据 | 交易记录 |
| `/fees` | Fees.vue | 个人交易数据 | 手续费分析 |
| `/manage` | Management.vue | 个人交易数据 | 管理设置 |
| `/intelligence` | Intelligence.vue | 股票分析预测 | 智能预测 |
| `/expert` | Expert.vue | 股票分析预测 | 专家分析 |
| `/news` | News.vue | 股票信息收集 | 新闻动态 |
| `/kline` | Kline.vue | 股票信息收集 | K线走势 |
| `/backtest` | BacktestPage.vue | 模拟交易 [待开发] | 回测分析 |
| `/paper` | PaperTrading.vue | 模拟交易 [待开发] | 纸面交易 |
| `/paper/history` | PaperHistory.vue | 模拟交易 [待开发] | 交易历史 |

---

## 2. 依赖方向规则（四层单向依赖）

### 2.1 依赖方向图

```
表现层 ──HTTP──▶ 服务层 ──import/subprocess──▶ 业务层 ──import──▶ 数据层 ──sqlite3──▶ 持久层
   │                │                │                │                │
   └── MUST NOT ────┼────────────────┼────────────────┼────────────────┤
                    └── MUST NOT ────┼────────────────┼────────────────┤
                                     └── MUST NOT ────┼────────────────┤
                                                       └── MUST NOT ────┘
```

### 2.2 强制性规则

| # | 规则 | 级别 | 示例违反 |
|----|------|------|---------|
| 1 | 上层可依赖下层，下层**不可** import 上层 | 🔴 MUST NOT | `db_helper.py` import `server_v2` |
| 2 | 前端**不可**直接访问 SQLite | 🔴 MUST NOT | `fetch('/data/stock.db')` |
| 3 | 业务层**不可**依赖 FastAPI 的 Request/Response | 🔴 MUST NOT | `sync_all.py` import `from fastapi import Request` |
| 4 | 数据层**不可**包含业务逻辑 | 🔴 MUST NOT | `db_helper.py` 中包含 `calc_signals()` |
| 5 | 服务层**不可**直接写原始 SQL | 🔴 MUST NOT | `server_v2.py` 中 `db.execute(...)` |
| 6 | 模块间**不可**循环导入 | 🔴 MUST NOT | A import B, B import A |
| 7 | 模块级代码**不可**产生副作用 | 🔴 MUST NOT | import 模块时自动执行数据同步 |

### 2.3 跨层合法通信方式

| 方向 | 合法方式 | 非法方式 |
|------|---------|---------|
| 表现层 → 服务层 | `fetch(API_BASE + '/api/v2/...')` | 直接文件读取、直接 db 连接 |
| 服务层 → 业务层 | `import` 或 `subprocess.run()` | 拷贝业务代码到服务层 |
| 服务层 → 数据层 | `import from db_helper` | `sqlite3.connect()` 直接写 |
| 业务层 → 数据层 | `import from db_helper` | 绕过 db_helper 直接 SQLite |
| 业务层 → 外部服务 | `subprocess.run()` (Node.js脚本) | 在业务层 import HTTP 客户端 |

---

## 3. 目录结构约束

### 3.1 标准目录树

```
project-root/
├── .rules/                         # 🔴 架构规范目录 (MUST 遵守)
│   ├── README.md                   # 规则体系导航
│   ├── architecture-constraints.md # 本文档
│   ├── business-logic-rules.md     # 业务逻辑规则
│   └── code-style.md               # 代码风格规范
│
├── docs/                           # 文档目录
│   └── specs/                      # 模块规范文档 (1份/模块)
│       ├── README.md               # 文档导航 + 系统概述
│       ├── 01-api-server.md        # 服务层规范
│       ├── 02-database-layer.md    # 数据层规范
│       ├── 03-sync-engine.md       # 同步引擎规范
│       ├── 04-self-learning.md     # 自学习算法规范
│       ├── 06-scheduler.md         # 调度器规范
│       ├── 13-ml-prediction-optimization.md
│       ├── 14-backtest-paper-trading.md  # 回测+纸面交易规范
│       └── appendix-*.md           # 附录 (Schema/API/配置/术语/已知问题)
│
├── scripts/                        # 🔴 业务层脚本 (MUST 可独立运行)
│   ├── db_helper.py                # 数据层唯一入口
│   ├── sync_all.py                 # 全模块同步引擎
│   ├── optimize_predict.py         # ML增强预测
│   ├── fetch_news.py               # 新闻抓取
│   ├── fetch_dividends.py          # 分红获取
│   ├── update_from_statement.py    # 对账单解析
│   ├── refresh_quotes.py           # 行情刷新
│   ├── build_stock_db.py           # 股票数据库构建
│   ├── import_expert_report.py     # 专家报告导入
│   ├── scheduler.py                # CLI任务编排
│   ├── audit_system.py             # 系统审计
│   ├── reinject_from_db.py         # 数据注入
│   ├── backtest_engine.py          # 回测引擎 [待开发]
│   └── paper_trading.py            # 纸面交易 [待开发]
│
├── server_v2.py                    # 🔴 主API服务器 (FastAPI, :8766)
├── server.py                       # 旧版服务器 (保留兼容, 不继续开发)
│
├── deliverables/                   # 前端交付物
│   ├── v2/                         # 🔴 Vue 3 前端 (主力开发)
│   │   ├── src/
│   │   │   ├── api/                # API 调用模块 (按功能域分文件)
│   │   │   ├── stores/             # Pinia 状态管理 (按功能域分文件)
│   │   │   ├── pages/              # Vue 页面组件 (每个路由一个)
│   │   │   ├── router.js           # Vue Router 配置
│   │   │   ├── App.vue             # 根组件 + 导航栏
│   │   │   └── main.js             # 入口
│   │   ├── vite.config.js          # Vite 配置 (proxy /api → :8766)
│   │   └── package.json            # 依赖声明
│   ├── bank-stock-system.html      # 旧版 SPA (保留兼容, 不继续开发)
│   ├── css/
│   │   └── app.css                 # 旧版样式
│   └── js/                         # 旧版脚本
│
├── data/                           # 数据目录
│   ├── stock.db                    # 🔴 SQLite 主数据库
│   └── config.json                 # 运行配置
│
├── tests/                          # 🔴 测试目录
│   ├── run_all.py                  # 测试运行器
│   └── test_*.py                   # 测试文件 (test_<module>.py)
│
└── 广发易淘金PC版-普通对账单结果查询.xlsx  # 对账单 (固定文件名)
```

### 3.2 文件命名强制规则

| 类型 | 规则 | 示例 |
|------|------|------|
| Python 脚本 | `snake_case.py` | `backtest_engine.py` |
| Vue 页面组件 | `PascalCase.vue` | `PaperTrading.vue` |
| Pinia Store | `kebab-case.js` (文件名) | `paper.js` |
| API 模块 | `kebab-case.js` (文件名) | `paper.js` |
| 测试文件 | `test_<module>.py` | `test_backtest_engine.py` |
| Spec 文档 | `NN-module-name.md` | `14-backtest-paper-trading.md` |
| Rule 文档 | `kebab-case.md` | `architecture-constraints.md` |

---

## 4. 模块交互规则

### 4.1 server_v2.py 约束

**MUST**:
- 所有 API 端点返回统一格式 `{success, data/error}`
- 通过 `from db_helper import ...` 读取数据
- 通过 `subprocess.run([PYTHON, script_path])` 触发业务脚本
- 新增端点全部在 `/api/v2/` 路径下
- 继承现有 `api_response()` 辅助函数构建响应

**MUST NOT**:
- 直接 `sqlite3.connect()` 写 SQL
- 在端点处理函数中执行复杂业务计算（>20行）
- 修改数据库 Schema（应在 db_helper 或迁移脚本中）
- 硬编码超时、路径、端口

**子进程调用标准模式**：
```python
def run_script(script_name: str, timeout: int = 60) -> tuple[bool, str]:
    """所有后端脚本调用必须通过此函数"""
    script_path = os.path.join(ROOT, "scripts", script_name)
    result = subprocess.run(
        [PYTHON, script_path], cwd=ROOT,
        capture_output=True, text=True, timeout=timeout
    )
    return result.returncode == 0, result.stdout.strip()
```

### 4.2 db_helper.py 约束

**MUST**:
- 作为 SQLite 唯一读写入口，所有数据库操作通过此文件
- 每个函数独立获取连接（`get_db()`），用完即关
- 使用参数化查询（`?` 占位符），禁止字符串拼接 SQL
- 新增表通过 `CREATE TABLE IF NOT EXISTS`
- 新增函数命名: `get_<entity>()` 查询, `insert_<entity>()` 写入, `upsert_<entity>()` 更新或插入

**MUST NOT**:
- import 其他业务模块
- 处理 HTTP 相关内容
- 包含业务计算逻辑

### 4.3 业务脚本约束

**MUST**:
- 每脚本单一职责，文件名反映功能
- 支持 `python script.py --arg1 val1` 格式 CLI 调用
- 通过 `if __name__ == '__main__': main()` 控制入口，导入不触发执行
- 输出日志使用 `sys.stderr` 写入，ANSI 颜色风格与 sync_all.py 一致
- 通过 `from db_helper import ...` 操作数据库

### 4.4 前端模块约束

**MUST**:
- Vue 页面组件在 `src/pages/`，一页一文件
- API 调用模块在 `src/api/`，按功能域分文件（不在页面组件中直接 fetch）
- Pinia Store 在 `src/stores/`，按功能域分文件
- 新增路由在 `src/router.js`，使用 `meta.group` 关联导航分组
- 新增导航菜单在 `App.vue` 的 `nav-group` 中

**Vue 前端 API 调用模式**：
```javascript
// src/api/paper.js
const API_BASE = ''
export async function fetchPaperAccount() {
  const res = await fetch(`${API_BASE}/api/v2/paper/account`)
  return await res.json()
}
```

---

## 5. 数据流强制规范

### 5.1 写入路径（唯一入口原则）

| 数据类型 | 唯一写入模块 | 唯一写入函数 |
|---------|-------------|-------------|
| 日K线 | sync_all.py | `db_helper.upsert_kline_daily()` |
| 月K线 | sync_all.py | `db_helper.upsert_kline_monthly()` |
| 预测数据 | sync_all.py | `db_helper.insert_daily_prediction()` |
| 新闻 | fetch_news.py | `db_helper.upsert_news()` |
| 持仓/交易 | update_from_statement.py | `db_helper` 对应函数 |
| 学习参数 | sync_all.py | `db_helper.upsert_learning_params()` |
| 准确率 | sync_all.py | `db_helper.upsert_accuracy_stats()` |
| 行情 | sync_all.py / refresh_quotes.py | `db_helper.upsert_quotes()` |
| **分钟分时数据** | **collect_intraday.py** | **`db_helper.insert_intraday_quotes()`** |
| **日K线降级分时数据** | **db_helper._get_kline_intraday_fallback()** | **查询时实时生成** |
| 虚拟账户 | paper_trading.py [待开发] | `db_helper` 对应函数 |
| 虚拟交易 | paper_trading.py [待开发] | `db_helper.insert_paper_trade()` |
| 回测结果 | backtest_engine.py [待开发] | `db_helper.insert_backtest_run()` |

**强制规则**：每种数据类型有且仅有一个写入模块。任一新功能需写入已有类型数据时，必须通过该类型指定的写入模块。

### 5.2 数据同步推荐频率

| 数据 | 频率 | 触发方式 |
|------|------|---------|
| 日K线 + 预测 + 学习 | 每日 15:35 | Windows 任务计划 → scheduler.py |
| 新闻 | 每日 09:00 | 独立触发 |
| 行情 | 按需 | Web API `/api/v2/quotes/refresh` |
| 回测引擎 | 每周/每月 | Web API `/api/v2/backtest/run` |
| 纸面交易建议 | 每日(预测后) | sync_all.py 回调 或 页面加载时 |

---

## 6. 外部依赖管理

| 依赖 | 调用方 | 调用方式 | 超时 | 失败处理 |
|------|--------|---------|------|---------|
| NeoData (K线/行情) | sync_all.py, refresh_quotes.py | Node.js 子进程 | 60s | 跳过该股票，继续 |
| NeoData (新闻) | fetch_news.py | Node.js 子进程 | 60s | 跳过该股票，继续 |
| 广发对账单 Excel | update_from_statement.py | openpyxl 解析 | 60s | 备份原文件，不覆盖已有数据 |
| 东方财富分红 API | fetch_dividends.py | HTTP (requests) | 30s | 不阻塞主流程 |
| 前端 Vite dev | — | proxy /api → :8766 | — | — |

---

## 7. 数据库规范

### 7.1 基本规则

- **MUST**: 使用 WAL 模式，每次连接执行 `PRAGMA journal_mode=WAL`
- **MUST**: 每个操作独立 `get_db()`，用完即 `close()`，不跨函数共享连接
- **SHOULD**: 复杂 JSON 数据（signal_weights, regime_weights 等）存储在 TEXT 列，序列化为 JSON 字符串
- **MUST**: 新增外键关联时同时添加索引

### 7.2 表命名

- 核心业务表: `snake_case`，描述数据实体
- 纸面交易表: `paper_` 前缀，如 `paper_account`, `paper_trades`
- 回测相关表: `backtest_` 前缀，如 `backtest_runs`

---

## 8. 版本兼容与迁移

### 8.1 当前活跃组件

| 组件 | 状态 | 说明 |
|------|------|------|
| `server_v2.py` (FastAPI, :8766) | 🔴 **主力** | 所有新API在这里开发 |
| `server.py` (http.server, :8765) | 🟡 保留兼容 | 不继续开发，不删除 |
| `deliverables/v2/` (Vue 3) | 🔴 **主力** | 所有新页面在这里开发 |
| `deliverables/bank-stock-system.html` | 🟡 保留兼容 | 不继续开发 |
| `scripts/sync_all.py` | 🔴 **主力** | 预测引擎核心 |

### 8.2 废弃/不继续开发清单

| 组件 | 状态 | 替代 |
|------|------|------|
| `scripts/daily_update.py` | ⚠️ 部分废弃 | sync_all.py Step 5 |
| JSON 遗留文件 (`system_data.json` 等) | ⚠️ 逐步废弃 | SQLite |

---

## 9. 强制校验机制

### 9.1 开发前校验（MUST 执行）

开发任何新功能前，必须：
1. ✅ 确认目标功能属于哪个架构层（表现/服务/业务/数据）
2. ✅ 确认新增文件放入正确的目录
3. ✅ 确认依赖方向合法（上层→下层，不能反向）
4. ✅ 确认数据写入路径符合"唯一入口原则"

### 9.2 Code Review 校验清单

| 检查项 | 通过标准 |
|--------|---------|
| 依赖方向 | 无循环导入，无下层依赖上层 |
| 数据库访问 | 仅通过 db_helper，无直接 SQLite 连接 |
| API 格式 | `{success, data/error}` 格式正确 |
| 模块职责 | 每文件单一职责，无越界代码 |
| 配置硬编码 | 路径/端口/超时不硬编码 |
| 文件命名 | 符合 3.2 节的命名规则 |
| Vue 组件位置 | pages/ 在正确目录，API 调用在 api/ |
| 测试覆盖 | 新功能有对应 test_*.py |

### 9.3 违规修正规则

- 任何 Code Review 发现的架构违规，**必须**在合并前修正
- 违规记录在 `docs/specs/appendix-f-known-issues.md` 中，标记为待修复
- 严重违规（如直接 SQLite 访问绕过 db_helper）需立即修正

---

## 10. 新模块集成规范（回测引擎 + 纸面交易）

以下规范适用于本次开发及未来所有新模块：

### 10.1 新增 Python 脚本

```python
"""<模块名称> - <一句话描述>

Usage:
    python scripts/<module>.py [--arg1 ARG1]

Architecture layer: 业务层 (Business Logic)
Data access: 仅通过 db_helper.py
Called by: server_v2.py (subprocess) / CLI
"""

def main():
    # 1. 参数解析
    # 2. 数据读取 (via db_helper)
    # 3. 核心逻辑
    # 4. 结果写入 (via db_helper)

if __name__ == '__main__':
    main()
```

### 10.2 新增 API 端点（server_v2.py）

```python
@app.get("/api/v2/<domain>/<resource>")
def api_<domain>_<resource>():
    """<简要描述>"""
    try:
        data = get_<resource>()  # via db_helper
        return api_response(data=data)
    except Exception as e:
        return api_response(success=False, error=str(e), status_code=500)
```

### 10.3 新增 Vue 页面

```
文件位置: deliverables/v2/src/pages/<PageName>.vue
路由: router.js 新增路由配置
导航: App.vue 新增 nav-group/nav-sub
API: 页面通过 src/api/<domain>.js 调用后端
Store: 共享状态通过 src/stores/<domain>.js 管理
```

### 10.4 新增数据库表

```sql
-- 在 db_helper.py init_backtest_tables() 中执行
CREATE TABLE IF NOT EXISTS <table_name> (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ...
);
CREATE INDEX IF NOT EXISTS idx_<table>_<col> ON <table_name>(<column>);
```

---

## 11. 更新历史

| 日期 | 版本 | 变更 |
|------|------|------|
| 2026-06-04 | v2.0 | 全面重写：补充 Vue 3 前端架构、修正端口号(8766)、新增回测+纸面交易模块规范、增加强制校验机制、补充目录结构约束 |
| 2026-06-03 | v1.0 | 初始版本：四层架构、模块边界、数据流规则 |
