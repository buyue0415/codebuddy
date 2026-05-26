# 股票投资管理系统 — 模块化功能规范

> **系统版本**: V0.6 | **文档版本**: v2.0 | **生成日期**: 2026-05-26 | **定位**: 本地银行股投资管理单页应用

---

## 系统概述

### 架构模式
单页应用 (SPA) + RESTful API + SQLite 数据库，纯本地运行。

### 技术栈
| 层 | 技术 |
|----|------|
| 前端 | 单页 HTML + Chart.js + fetch API |
| 后端 | Python 3.13+ `http.server` (ThreadedHTTPServer) |
| 数据库 | SQLite 3 (WAL模式, 17张表) |
| 外部数据 | NeoData (westock-data Node.js 插件), 广发证券对账单 Excel |
| 运行环境 | Windows, Python 3.13+, Node.js 22+ |

### 数据规模
- 自选股: 3-10 只（银行股为主）
- 日K线: 每只 200 条
- 预测记录: 每只每日 1 条
- 新闻: 每只每日最多 20 条

### 启动方式
```bash
# 终端启动
python server.py

# 或双击
start_server.bat

# 浏览器访问
http://localhost:8765
```

---

## 文档导航

### 核心模块

| 序号 | 文档 | 对应模块 | 核心文件 |
|------|------|---------|---------|
| 01 | [Web API 服务层](./01-api-server.md) | 模块1 | `server.py` |
| 02 | [数据库访问层](./02-database-layer.md) | 模块2 | `scripts/db_helper.py` |
| 03 | [全模块同步引擎](./03-sync-engine.md) | 模块3 | `scripts/sync_all.py` |
| 04 | [自学习与预测算法](./04-self-learning.md) | 模块8/9/10 | `sync_all.py` 内函数 + `daily_update.py` |
| 05 | [每日更新模块](./05-daily-update.md) | 模块4 (⚠️ 部分废弃) | `scripts/daily_update.py` |
| 06 | [定时任务调度](./06-scheduler.md) | 模块5 | `scripts/scheduler.py` |

### 数据管道

| 序号 | 文档 | 对应模块 | 核心文件 |
|------|------|---------|---------|
| 07 | [新闻抓取](./07-news-fetcher.md) | 模块6 | `scripts/fetch_news.py` |
| 08 | [股票数据库构建](./08-stock-database.md) | 模块11 | `scripts/build_stock_db.py` |
| 09 | [券商对账单解析](./09-statement-parser.md) | 模块12 | `scripts/parse_statement.py` / `update_from_statement.py` |
| 10 | [专家报告导入](./10-expert-report.md) | 模块13 | `scripts/import_expert_report.py` |
| 11 | [数据注入](./11-data-injection.md) | 模块14 | `scripts/reinject_from_db.py` |

### 运维与附录

| 序号 | 文档 | 说明 |
|------|------|------|
| 12 | [数据迁移与系统审计](./12-migration-and-audit.md) | 模块15/16 |
| A | [数据库Schema](./appendix-a-schema.md) | 17张表完整定义 |
| B | [API端点清单](./appendix-b-api.md) | 42个端点详细说明 |
| C | [系统配置项](./appendix-c-config.md) | 配置文件和运行时常量 |
| D | [依赖关系图与数据流](./appendix-d-dependencies.md) | ASCII架构图 + 依赖矩阵 |
| E | [术语表](./appendix-e-glossary.md) | 25个统一术语定义 |
| F | [已知问题与性能基线](./appendix-f-known-issues.md) | 已知风险 + 性能指标 + 废弃模块 |

---

## 关键数据流

```
1. 行情+预测: NeoData → sync_all.py → SQLite → API → 前端
2. 持仓数据:   广发对账单.xlsx → update_from_statement.py → SQLite/JSON → API → 前端
3. 新闻数据:   NeoData → fetch_news.py → SQLite → API → 前端
4. 专家报告:   WorkBuddy多Agent → POST /api/v2/expert/import → SQLite → API → 前端
```

---

## 文档约定

- **代码引用**: 使用 `文件名:行号` 格式，如 `server.py:8765`
- **API路径**: 以 `/` 开头，如 `/api/v2/init`
- **数据库表**: 用 **粗体** 标记，如 **kline_daily**
- **配置项**: 用反引号标记，如 `fee_rates.transfer_fee_per_1000`
- **版本标记**: ⚠️ 表示已废弃或存在已知问题

---

> **维护说明**: 系统代码变更时需同步更新对应子文档。各模块文档的"关联文件"字段指向实际代码文件。
