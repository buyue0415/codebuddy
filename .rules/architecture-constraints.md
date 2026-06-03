# 架构约束 (Architecture Constraints)

> **版本**: v1.0 | **级别**: 🔴 MUST | **更新日期**: 2026-06-03

---

## 1. 分层架构原则

### 1.1 四层架构

```
┌────────────────────────────────────┐
│  表现层 (Presentation)             │
│  deliverables/*.html, js/*.js      │
│  仅通过 HTTP API 与后端通信         │
└──────────────┬─────────────────────┘
               │ HTTP (fetch API)
┌──────────────▼─────────────────────┐
│  服务层 (Service / API)            │
│  server.py                         │
│  路由分发、请求验证、响应格式化      │
└──────────────┬─────────────────────┘
               │ import / subprocess
┌──────────────▼─────────────────────┐
│  业务层 (Business Logic)           │
│  sync_all.py, fetch_news.py,       │
│  optimize_predict.py, ...          │
│  数据处理、算法计算、业务编排        │
└──────────────┬─────────────────────┘
               │ import
┌──────────────▼─────────────────────┐
│  数据层 (Data Access)              │
│  db_helper.py                      │
│  SQLite 唯一读写入口               │
└────────────────────────────────────┘
```

### 1.2 依赖方向规则

| 规则 | 说明 |
|------|------|
| **MUST** | 上层可依赖下层，下层不可依赖上层 |
| **MUST NOT** | 数据层不可 import 业务层 |
| **MUST NOT** | 业务层不可 import 服务层 |
| **MUST NOT** | 前端不可直接访问 SQLite |
| **SHOULD NOT** | 跨层直接调用（如 服务层直接 SQL） |

### 1.3 跨层通信方式

| 方向 | 方式 | 示例 |
|------|------|------|
| 前端 → 服务层 | HTTP fetch API | `fetch('/api/v2/init')` |
| 服务层 → 业务层 | `import` 或 `subprocess.run()` | `from db_helper import get_watchlist` |
| 业务层 → 数据层 | `import` | `from db_helper import upsert_kline_daily` |
| 数据层 → 数据库 | `sqlite3.connect()` | `db.execute(...)` |

---

## 2. 模块边界规则

### 2.1 server.py 职责边界

**MUST**:
- 处理 HTTP 请求路由和响应
- 解析请求参数
- 调用 `db_helper` 查询函数
- 通过 `subprocess.run()` 触发后台脚本

**MUST NOT**:
- 直接写 SQL 查询（应通过 db_helper）
- 执行复杂业务计算（应在业务层）
- 修改数据库 Schema

### 2.2 db_helper.py 职责边界

**MUST**:
- 作为 SQLite 唯一读写入口
- 封装所有 CRUD 操作
- 管理连接生命周期
- 提供参数化查询

**MUST NOT**:
- 包含业务逻辑（如计算预测、信号）
- 调用其他业务模块
- 处理 HTTP 相关内容

### 2.3 sync_all.py 职责边界

**MUST**:
- 编排全量同步流程（8步）
- 通过 db_helper 读写数据
- 通过 subprocess 调用 NeoData

**MUST NOT**:
- 绕过 db_helper 直接操作 SQLite
- 处理 HTTP 请求
- 修改前端代码

### 2.4 脚本模块独立性

**MUST**:
- 每个脚本模块可用 `if __name__ == '__main__'` 独立运行
- 导入模块不应触发副作用（如执行数据同步）

**MUST NOT**:
- 模块级代码执行副作用操作（如 `sync_all.py` 当前的模块级执行）
- 模块间循环导入

---

## 3. 数据流规则

### 3.1 数据写入路径

| 数据类型 | 唯一写入入口 | 写入方式 |
|---------|-------------|---------|
| K线数据 | `db_helper.upsert_kline_daily()` | sync_all.py |
| 预测数据 | `db_helper.insert_daily_prediction()` | sync_all.py |
| 新闻数据 | `db_helper.upsert_news()` | fetch_news.py |
| 持仓数据 | `db_helper.upsert_positions()` | update_from_statement.py |
| 学习参数 | `db_helper.upsert_learning_params()` | sync_all.py / daily_update.py |
| 准确率 | `db_helper.upsert_accuracy_stats()` | sync_all.py |
| 季节性 | `db_helper.upsert_seasonal()` | sync_all.py |
| 行情 | `db_helper.upsert_quotes()` | sync_all.py / refresh_quotes.py |

### 3.2 数据读取路径

**MUST**: 所有前端数据读取通过 API 端点
**MUST**: API 端点通过 `db_helper` 查询函数获取数据
**MUST NOT**: 前端直接读取文件或数据库

---

## 4. 外部依赖规则

### 4.1 NeoData (westock-data)

- 仅 `sync_all.py` 和 `fetch_news.py` 可调用
- 通过 Node.js 子进程调用，不直接 import
- 添加重试机制（建议最多3次）

### 4.2 东方财富 API

- 仅 `fetch_dividends.py` 可调用
- HTTP 请求需设置合理超时（30s）
- 失败不阻塞主流程

### 4.3 券商对账单 Excel

- 仅 `update_from_statement.py` 解析
- 上传前创建 .bak 备份
- 解析失败不影响已有数据

---

## 5. 配置管理规则

### 5.1 配置文件
- **MUST**: 所有可配置项集中在 `data/config.json`
- **MUST NOT**: 硬编码路径、超时、常量在业务代码中
- **SHOULD**: 新增配置项添加默认值

### 5.2 当前硬编码项（待修复）
- `server.py` 中的 Python 路径 → 移至环境变量
- `server.py` 中的脚本超时 → 移至 `config.json`
- `sync_all.py` 中的 max_workers=4 → 移至 `config.json`

---

## 6. 并发与线程安全

### 6.1 同步锁规则
- **MUST**: 使用 `threading.Lock` 保护共享状态
- **SHOULD**: 按任务类型分层锁（避免全局锁阻塞不相关任务）
- **MUST**: 锁操作包裹在最小范围内

### 6.2 数据库并发
- SQLite WAL 模式：读并发，写串行
- **MUST**: 每个操作独立获取连接，用完即关
- **MUST NOT**: 跨函数共享连接对象

---

## 7. 版本兼容规则

### 7.1 API 版本
- 当前活跃版本: `/api/v2/`
- 旧版本 `/api/watchlist/*` 保留兼容
- **SHOULD**: 新增端点在 `/api/v2/` 路径下

### 7.2 数据格式兼容
- 专家报告支持 v1/v2/v3 格式自动识别
- 对账单 Excel 支持中英文列名兼容
- JSON 遗留文件逐步废弃，不新增依赖

### 7.3 Python 版本
- **MUST**: 统一使用同一 Python 版本（当前不统一: 3.13.12 / 3.14.3）
- **SHOULD**: 目标版本: Python 3.13+
