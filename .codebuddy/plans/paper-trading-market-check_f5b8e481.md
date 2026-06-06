---
name: paper-trading-market-check
overview: 为纸面交易增加开市检查、行情有效性校验、分时数据采集（每1小时调 westock-data minute 获取全分钟级数据）、以及带日历控件的分时图前端（支持历史日期查询）。
todos:
  - id: create-market-utils
    content: 新建 scripts/market_utils.py，实现 is_market_open() 和 get_market_status() 函数
    status: completed
  - id: add-intraday-table
    content: 修改 scripts/db_helper.py，在 init_backtest_tables() 中新增 intraday_quotes 建表语句，新增 get_intraday_quotes() 和 insert_intraday_quotes() 函数
    status: completed
  - id: create-collect-script
    content: 新建 scripts/collect_intraday.py，实现每1小时调用 westock-data minute 采集全天分钟数据，INSERT OR REPLACE 写入 intraday_quotes
    status: completed
    dependencies:
      - create-market-utils
      - add-intraday-table
  - id: fix-paper-trading
    content: 修改 scripts/paper_trading.py：auto_execute() 加开市检查，generate_suggestions() 加价格有效性判断，交易执行前用 westock-data quote 获取实时价
    status: completed
    dependencies:
      - create-market-utils
  - id: fix-server-api
    content: 修改 server_v2.py：api_paper_suggestions() 增加开市检查+market_status+修复重复return；新增 GET /api/v2/paper/intraday/{code}?date= 分时数据接口
    status: completed
    dependencies:
      - create-market-utils
      - add-intraday-table
  - id: fix-scheduler
    content: 修改 scripts/scheduler.py，task_paper_trading() 增加兜底市场时间检查
    status: completed
    dependencies:
      - create-market-utils
  - id: update-frontend
    content: 修改 PaperTrading.vue + paper.js API + paper.js Store，增加市场状态横幅、日期选择器和 Chart.js 分时折线图
    status: completed
    dependencies:
      - fix-server-api
---

## 产品概述

完善纸面交易（模拟交易）功能，解决四个核心问题：非交易时段执行买卖不合理、行情价格过期或无效、缺少实时分时数据记录、分时图无法回顾历史日期。

## 核心功能

### 1. 开市时间检查

A股交易时段校验（周一至周五 9:30-11:30, 13:00-15:00），在纸面交易的三个入口层（定时任务、API调用、核心执行函数）全部增加检查，非交易时段拒绝执行买卖并记录日志。

### 2. 行情价格有效性检查

在生成交易建议时校验价格是否有效——当 quotes 表价格为空或回退到预测 entry_zone 时，不生成买入/卖出建议，改为 hold。同时，执行交易前通过 westock-data quote 获取实时价格，确保成交价是真实市价而非日K收盘价。

### 3. 实时行情采集与分时存储

新建 `collect_intraday.py` 脚本，开市期间每1小时调用 westock-data minute 获取自选股全天分钟级数据，存入新建的 `intraday_quotes` 表。使用 `INSERT OR REPLACE` 按 (code, timestamp) 唯一索引去重。对10只自选股每天约80次请求，不会触发限流。

### 4. 分时图可视化 + 日期选择器

前端 PaperTrading.vue 增加分时走势图区域，包含日期选择器。API 端点 `/api/v2/paper/intraday/{code}?date=YYYY-MM-DD`，date 为空时默认返回当日数据。用 Chart.js 折线图渲染选中日期的价格变化趋势，X轴为时间、Y轴为价格。

### 5. 市场状态提示

前端在市场关闭/非交易日时展示提示横幅，API 返回 market_status 字段告知当前状态。

## 技术栈

- **后端**：Python 3.12 + FastAPI（server_v2.py）
- **脚本**：Python（paper_trading.py, collect_intraday.py, scheduler.py, market_utils.py）
- **数据库**：SQLite（stock.db），新增 intraday_quotes 表
- **前端**：Vue 3.4 + Pinia 2.1 + Chart.js（全局 window.Chart，CDN 加载）
- **数据源**：westock-data Node.js 插件（minute 命令分时采集，quote 命令实时交易价）

## 实现方案

### 整体策略

新建 `market_utils.py` 为基础设施，在纸面交易全链路（scheduler → API → auto_execute → generate_suggestions）构建三层市场检查防护。同时新建 `intraday_quotes` 表和 `collect_intraday.py` 采集脚本，使用 westock-data minute 命令每1小时获取全天分钟数据。前端分时图带日期选择器，API 支持 `?date=` 参数筛选历史数据。

### 架构设计

```mermaid
flowchart TD
    subgraph 入口层
        A[scheduler.py 定时任务]
        B[server_v2.py API]
    end
    subgraph 市场检查层
        C[market_utils.py]
    end
    subgraph 执行层
        D[paper_trading.py auto_execute]
        E[generate_suggestions]
    end
    subgraph 数据层
        F[westock-data minute]
        G[(quotes 表)]
        H[(intraday_quotes 表)]
        I[collect_intraday.py]
        J[westock-data quote]
    end
    subgraph 展示层
        K[PaperTrading.vue 分时图+日期选择器]
        L[市场状态横幅]
    end
    A --> C
    B --> C
    C -->|开市| D
    C -->|闭市| L
    D --> C
    D --> E
    E --> G
    I -->|每小时一次| F
    I --> H
    D -->|交易瞬间| J
    H --> K
    B -->|market_status| L
    B <-->|?date=YYYY-MM-DD| K
```

### 数据流

1. **开市检查**：入口 → `is_market_open()` → 是则继续，否则记录日志并返回状态
2. **分时采集**：`collect_intraday.py` → 每3600秒循环 → `westock-data minute` 逐股获取 → 解析分钟OHLC → `INSERT OR REPLACE` 写入 intraday_quotes
3. **交易执行**：auto_execute → market check → generate_suggestions → 价格有效性检查 → `westock-data quote` 批量取实时价 → 执行交易
4. **分时图查询**：前端选择日期 → `GET /api/v2/paper/intraday/{code}?date=YYYY-MM-DD` → 查询 intraday_quotes → 时间序列 JSON → Chart.js 折线图

## 目录结构

```
project-root/
├── scripts/
│   ├── market_utils.py          # [NEW] 市场时间工具模块。is_market_open(dt=None) 判断是否在周一至周五 9:30-11:30/13:00-15:00；get_market_status(dt=None) 返回 'open'/'closed'/'non_trading_day'
│   ├── collect_intraday.py      # [NEW] 分时采集脚本。COLLECT_INTERVAL=3600秒，开市期间循环调用 westock-data minute 命令逐股获取全天分钟数据，解析后 INSERT OR REPLACE 写入 intraday_quotes。支持 --once 单次采集和持续运行模式。自动根据 is_market_open() 控制启停
│   ├── paper_trading.py         # [MODIFY] auto_execute() 143行前增加 is_market_open() 检查；generate_suggestions() 109行取价逻辑增加有效性判断（price<=0 或回退到 entry_zone 时改为 hold）；执行交易前通过 subprocess 调用 westock-data quote 获取实时价格
│   └── scheduler.py             # [MODIFY] task_paper_trading() 66-71行增加 is_market_open() 兜底检查，非交易时段跳过
├── server_v2.py                  # [MODIFY] api_paper_suggestions() 增加 is_market_open() 检查和 market_status 返回；修复1835-1836行重复return bug；新增 GET /api/v2/paper/intraday/{code}?date= 分时数据接口
├── scripts/db_helper.py          # [MODIFY] init_backtest_tables() 1434行前新增 intraday_quotes 建表语句（含 (code,timestamp) 唯一索引和 (code,date(timestamp)) 查询索引）；新增 get_intraday_quotes(code, date) 和 insert_intraday_quotes(rows) 函数
└── deliverables/v2/src/
    ├── api/paper.js              # [MODIFY] 新增 fetchIntraday(code, date) API 调用函数
    ├── stores/paper.js           # [MODIFY] 新增 intradayData ref([])、selectedDate ref('')、availableDates ref([])、loadIntraday(code, date) 方法
    └── pages/PaperTrading.vue    # [MODIFY] 增加市场状态横幅（marketStatus ref + 条件渲染，橙色"当前非交易时段"/灰色"今日非交易日"）；增加分时图卡片区域（日期选择器 input[type=date] + canvas + Chart.js 折线图渲染）
```

### 关键代码结构

**intraday_quotes 表**：

```sql
CREATE TABLE IF NOT EXISTS intraday_quotes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL,
    timestamp TEXT NOT NULL,          -- 'YYYY-MM-DD HH:MM:SS'
    price REAL NOT NULL,
    change_pct REAL DEFAULT 0,
    volume INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now','localtime')),
    FOREIGN KEY (code) REFERENCES stocks(code)
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_iq_code_ts ON intraday_quotes(code, timestamp);
CREATE INDEX IF NOT EXISTS idx_iq_code_date ON intraday_quotes(code, date(timestamp));
```

**market_utils.py 核心接口**：

```python
def is_market_open(dt=None) -> bool:
    """判断当前是否在A股交易时段：周一至周五 9:30-11:30 或 13:00-15:00"""
    
def get_market_status(dt=None) -> str:
    """返回 'open' | 'closed' | 'non_trading_day'"""
```

**collect_intraday.py 核心逻辑**：

```python
COLLECT_INTERVAL = 3600  # 1小时

def fetch_minute_data(market_code: str) -> list:
    """调用 westock-data minute 获取全天分钟数据，解析为 [{time, price}, ...]"""

def collect_once():
    """单次采集：遍历自选股 → 逐股调 minute → INSERT OR REPLACE 写入"""

def collect_loop():
    """持续采集：while True → is_market_open()? → collect_once() → sleep(3600)"""
```

**API 接口**：

- `GET /api/v2/paper/intraday/{code}?date=YYYY-MM-DD`：返回 `{ code, date, data: [{timestamp, price, change_pct, volume}, ...], count }`
- 现有 `/api/v2/paper/suggestions` 返回值新增 `market_status` 字段

**Store 新增状态**：

- `intradayData`：`ref([])` — 当前选中日期的分时数据
- `selectedDate`：`ref('')` — 当前选中的日期（默认当日）
- `availableDates`：`ref([])` — 有分时数据的日期列表
- `loadIntraday(code, date)`：异步加载函数

### 实现注意事项

- **Chart.js 复用**：使用 `window.Chart`（全局 CDN），与 Kline.vue/Fees.vue/PaperHistory.vue 等现有页面模式完全一致
- **日期选择器**：使用原生 `<input type="date">`，max 属性限制为当日，默认值 `new Date().toISOString().slice(0,10)`
- **minute 命令解析**：输出为管道分隔的文本行，每行 `时间|开盘|收盘|最高|最低|成交量`，提取时间和收盘价
- **性能**：intraday_quotes 每天每股票约240条（4小时×每分钟1条），保留90天约 90×10×240=21.6万条，SQLite 无压力
- **日志**：所有拦截和采集行为通过 `sys.stderr.write` 记录，与现有风格一致
- **向后兼容**：不修改 CLI 参数和现有返回值格式，仅增加字段和提前返回
- **幂等性**：auto_execute 的 `executed=1` 幂等检查保持不变
- **采集启停**：`collect_intraday.py` 使用 `is_market_open()` 自动控制采集启停，非开市时 sleep 60秒等待
- **限流安全**：每1小时采集一次，10只自选股每天约80次请求，远低于任何限流阈值

## 使用的扩展

### SubAgent

- **code-explorer**
- 用途：在实现过程中探索代码库，查找具体函数签名、导入路径和现有模式引用
- 预期结果：获取准确的 API 签名、import 语句和 Chart.js 使用模式，确保代码与现有项目一致

### Skill

- **verification-before-completion**
- 用途：完成所有修改后验证功能正确性，检查 Python 语法、Vue 模板语法和导入完整性
- 预期结果：确认所有文件无语法错误，前后端逻辑完整，互不冲突