# 股票投资管理系统 — 模块化功能规范

> **系统版本**: V0.8 | **文档版本**: v2.3 | **更新日期**: 2026-06-04 | **定位**: 本地银行股投资管理单页应用

---

## 系统概述

### 架构模式
单页应用 (SPA) + RESTful API + SQLite 数据库，纯本地运行。

### 技术栈
| 层 | 技术 |
|----|------|
| 前端 (V2) | Vue 3 + Pinia + Vue Router + Chart.js (Vite) |
| 前端 (旧版) | 单页 HTML + Chart.js + fetch API (保留兼容) |
| 后端 | Python 3.12+ `FastAPI` + Uvicorn (原 `http.server` 保留兼容) |
| 数据库 | SQLite 3 (WAL模式, 17张表) |
| 外部数据 | NeoData (westock-data Node.js 插件), 广发证券对账单 Excel |
| 运行环境 | Windows, Python 3.13+, Node.js 22+ |

### 数据规模
- 自选股: 3-10 只（银行股为主）
- 日K线: 每只 200~2000 条（默认拉取上限 2000 条，当前最多 2000 条/覆盖约8年）
- 预测记录: 每只每日 1 条
- 新闻: 每只每日最多 20 条

### 启动方式
```bash
# FastAPI 版 (推荐)
python server_v2.py           # 后端 :8766 + Swagger UI
start_v2_fastapi.bat          # 一键启动 FastAPI + Vite 前端

# 原版保留
python server.py              # http.server :8765
start_server.bat              # 原版启动脚本

# 浏览器访问
http://localhost:5173         # Vite 开发前端
http://localhost:8766/docs    # FastAPI Swagger 文档
```

---

## 文档导航

### 核心模块

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

### 预测增强 (V0.7 新增)

| 序号 | 文档 | 对应模块 | 核心文件 |
|------|------|---------|---------|
| 13 | [ML增强预测优化](./13-ml-prediction-optimization.md) | 模块17 | `scripts/optimize_predict.py` |

### 新功能规划 (V0.9)

| 序号 | 文档 | 类型 | 说明 |
|------|------|------|------|
| 14 | [回测引擎与纸面交易 — 业务需求说明书](./14-business-requirements.md) | 业务需求 | 核心目标、用户场景、功能清单、验收标准 |
| 14F | [用户操作流程](./14-user-flow.md) | 操作流程 | 三阶段流程：首次回测 → 每日自动 → 日常查看，含异常处理 |
| 14T | [回测引擎与纸面交易 — 技术设计方案](./14-backtest-paper-trading.md) | 技术设计 | MWU原理、回测算法、纸面交易数据模型、API设计、数据库设计 |
| 14A | [技术方案深度分析](./14-analysis.md) | 审查报告 | 架构/性能/安全/可扩展/可维护五维度审查，10项问题优先级

### 运维与附录

| 序号 | 文档 | 说明 |
|------|------|------|
| 12 | [数据迁移与系统审计](./12-migration-and-audit.md) | 模块15/16 |
| A | [数据库Schema](./appendix-a-schema.md) | 17张表完整定义 |
| B | [API端点清单](./appendix-b-api.md) | 40个端点详细说明 |
| C | [系统配置项](./appendix-c-config.md) | 配置文件和运行时常量 |
| D | [依赖关系图与数据流](./appendix-d-dependencies.md) | ASCII架构图 + 依赖矩阵 |
| E | [术语表](./appendix-e-glossary.md) | 25个统一术语定义 |
| F | [已知问题与性能基线](./appendix-f-known-issues.md) | 已知风险 + 性能指标 + 废弃模块 |

---

## 关键数据流

```
1. 行情+预测: NeoData → sync_all.py (8步) → SQLite → API → 前端
2. ML增强预测:  K线数据 → optimize_predict.py (30+特征+RandomForest+Isotonic校准) → SQLite
3. 持仓数据:   广发对账单.xlsx → update_from_statement.py → SQLite/JSON → API → 前端
4. 新闻数据:   NeoData → fetch_news.py → SQLite → API → 前端
5. 专家报告:   WorkBuddy多Agent → POST /api/v2/expert/import → SQLite → API → 前端
6. 分红数据:   东方财富API → fetch_dividends.py → SQLite
7. V0.9 回测:  K线数据 → backtest_engine.py (Walk-forward+网格搜索) → learning_params
8. V0.9 纸面:  每日预测 → paper_trading.py (凯利仓位+建议) → API → 前端
```

---

## 文档约定

- **代码引用**: 使用 `文件名:行号` 格式，如 `server_v2.py:8766`
- **API路径**: 以 `/` 开头，如 `/api/v2/init`
- **数据库表**: 用 **粗体** 标记，如 **kline_daily**
- **配置项**: 用反引号标记，如 `fee_rates.transfer_fee_per_1000`
- **版本标记**: ⚠️ 表示已废弃或存在已知问题

---

> **维护说明**: 系统代码变更时需同步更新对应子文档。各模块文档的"关联文件"字段指向实际代码文件。

## 更新历史

| 日期 | 版本 | 变更 |
|------|------|------|
| 2026-06-04 | v2.3 | V0.8 升级：后端从 http.server 迁移至 FastAPI (server_v2.py)，原版 server.py 保留兼容 |
| 2026-06-04 | v2.2 | 前端 Vue 3 迁移完成：8页面全部迁移，新增 rules 规范体系，测试扩至100+ |
| 2026-06-03 | v2.1 | V0.7更新：新增13-ml-prediction-optimization spec；README版本号更新；新增6条数据流 |
| 2026-05-26 | v2.0 | 从单文件拆分重构为 19 个子文档 |
