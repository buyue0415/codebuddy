---
name: three-green-one-red-pattern
overview: 在日K走势图中集成独立的K线形态规则引擎：规则存储在数据库中，用户通过管理页面CRUD，后端扫描K线数据匹配规则，结果仅在日K线图上以多色标记展示，不参与预测投票系统。
todos:
  - id: db-rules-table
    content: 在 db_helper.py 中新增 init_pattern_rules_tables() 建表函数和 CRUD helper，创建 init_pattern_rules.py 写入33条标准规则
    status: completed
  - id: pattern-engine
    content: 创建 scripts/pattern_engine.py 实现形态检测引擎：从DB加载规则、解析conditions JSON、扫描K线数据匹配
    status: completed
    dependencies:
      - db-rules-table
  - id: api-crud
    content: 在 server_v2.py 新增 pattern-rules CRUD API 和 pattern-scan 扫描接口
    status: completed
    dependencies:
      - db-rules-table
      - pattern-engine
  - id: frontend-mgmt
    content: 创建 PatternRules.vue 管理页面（表格+编辑弹窗+筛选），注册路由和导航
    status: completed
    dependencies:
      - api-crud
  - id: frontend-chart
    content: 修改 Kline.vue 调用 pattern-scan 接口，渲染看涨/看跌形态标记并支持缩放
    status: completed
    dependencies:
      - api-crud
---

在现有A股投资管理系统的日K线走势图中，新增一套数据库驱动的K线形态规则引擎。系统支持33条标准化的K线形态规则（涵盖单K线、双K线、三K线、多K线、特殊结构五大类）的增删改查管理，并能在日K线图上以可视化标记展示历史形态出现位置。形态检测结果仅用于图表展示辅助，不参与预测投票。

## 技术栈

- 后端：Python 3 + FastAPI + SQLite（复用现有 server_v2.py + db_helper.py + data/stock.db）
- 前端：Vue 3 + Chart.js（复用现有 deliverables/v2/ 技术栈）
- 数据格式：JSON（conditions 字段存储量化条件）

## 实现方案

### 总体架构

```
[DB] pattern_rules 表 --> pattern_engine.py 加载规则 --> 扫描K线 --> 匹配结果
                                                              |
               Kline.vue <-- /api/v2/pattern-scan/{code} <---+
               PatternRules.vue <-> /api/v2/pattern-rules (CRUD) --> DB
```

采用**去耦合独立引擎**策略：pattern_engine.py 是纯计算模块，从DB加载规则后对日K线数据进行扫描匹配。它**不**被 signals.py 调用（用户明确要求），而是通过API暴露给前端。前端Kline.vue直接调用扫描接口获取结果并渲染标记。

### 关键技术决策

1. **conditions JSON 统一格式**：每条规则的量化条件使用标准JSON存储，支持三种约束类型：

- `candles`：逐根K线约束（如K1收盘>开盘、实体比例>=0.6）
- `cross_candle`：跨K线约束（如K2收盘 > K1开盘即吞没、跳空缺口）
- 支持操作符：`>` `>=` `<` `<=` `==`，字段包括：`open` `close` `high` `low` `body` `body_ratio` `upper_shadow` `lower_shadow` `midpoint`

2. **纯计算不耦合**：pattern_engine.py 不依赖 signals.py 的任何函数，也不修改 SIGNALS 列表。新增文件、新增API、新增前端页面，不改原有预测逻辑。

3. **前端直接API调用**：Kline.vue 复用已有的 `apiCall` 函数，在 `renderAll()` 末尾异步调用 `/api/v2/pattern-scan/{code}` 获取结果后渲染标记。

4. **管理页面独立路由**：新增路由 `/patterns`，放在 App.vue 的 "股票信息收集" 分组下（与K线走势同组）。

### 性能考虑

- 引擎每次扫描30条规则*1000根K线约33000次比较，纯Python计算<50ms
- 首次部署自动建表和写入规则，仅执行一次
- Kline.vue 调用扫描API是异步的，不影响主图表渲染

## 架构设计

```mermaid
flowchart TB
    subgraph Data[数据层 SQLite]
        PR[pattern_rules 表<br/>id, rule_id, name, category<br/>direction, strength, conditions JSON<br/>enabled, created_at, updated_at]
        KD[（复用）kline_daily 表]
    end

    subgraph Backend[后端 Python]
        PE[pattern_engine.py<br/>scan_patterns(kdata) -> 匹配结果]
        API[server_v2.py<br/>+ /api/v2/pattern-rules CRUD<br/>+ /api/v2/pattern-scan/{code}]
        DBH[db_helper.py<br/>新增 pattern_rules 建表 + CRUD helper]
    end

    subgraph Frontend[前端 Vue 3]
        RTR[router.js<br/>新增 /patterns 路由]
        NAV[App.vue<br/>「股票信息收集」分组下新增入口]
        PM[PatternRules.vue<br/>规则管理表格 + 编辑弹窗 + 筛选]
        KL[Kline.vue<br/>调用scan接口 + 渲染多色标记]
    end

    PE -->|从DB加载已启用规则| PR
    PE -->|扫描K线数据| KD
    API -->|调用引擎| PE
    PM -->|CRUD 操作| API
    API -->|读写| PR
    KL -->|GET pattern-scan| API
    KL -->|渲染标记| CHART[Chart.js candlestick + scatter datasets]
```

## 目录结构

```
scripts/
├── pattern_engine.py       # [NEW] 形态检测引擎：加载规则 + 解析conditions + 扫描K线匹配
├── init_pattern_rules.py   # [NEW] 初始化写入33条标准规则到数据库
└── db_helper.py            # [MODIFY] 新增 init_pattern_rules_tables() + CRUD helper 函数

server_v2.py                # [MODIFY] 新增 pattern-rules CRUD 路由 + pattern-scan 路由

deliverables/v2/src/
├── router.js               # [MODIFY] 新增 path: '/patterns', component: PatternRules
├── App.vue                 # [MODIFY] "股票信息收集" navGroup 下新增 { route: '/patterns', label: '形态规则' }
└── pages/
    ├── PatternRules.vue    # [NEW] 规则管理页面（表格 + 编辑弹窗 + 筛选）
    └── Kline.vue           # [MODIFY] 异步调用 pattern-scan + 渲染标记（看涨=金色三角/看跌=紫色三角）
```

## 关键代码结构

### 数据库表结构（新增到 db_helper.py）

```sql
CREATE TABLE IF NOT EXISTS pattern_rules (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_id     TEXT    NOT NULL UNIQUE,
    name        TEXT    NOT NULL,
    name_en     TEXT    DEFAULT '',
    category    TEXT    NOT NULL CHECK(category IN ('single','double','triple','multi','special')),
    direction   TEXT    NOT NULL CHECK(direction IN ('bullish','bearish','neutral')),
    strength    INTEGER NOT NULL DEFAULT 3,
    span_days   INTEGER NOT NULL,
    conditions  TEXT    NOT NULL,
    enabled     INTEGER NOT NULL DEFAULT 1,
    memo        TEXT    DEFAULT '',
    created_at  TEXT    DEFAULT (datetime('now','localtime')),
    updated_at  TEXT    DEFAULT (datetime('now','localtime'))
);
```

### conditions JSON 格式示例（C2-01 看涨吞没）

```
{
    "candles": [
        {
            "idx": 0,
            "label": "K1（最新）",
            "rules": [
                {"field": "close", "op": ">", "ref": "open", "type": "self"},
                {"field": "open", "op": "<", "ref": "close_1", "type": "prev"},
                {"field": "close", "op": ">", "ref": "open_1", "type": "prev"}
            ]
        },
        {
            "idx": 1,
            "label": "K2（前日）",
            "rules": [
                {"field": "close", "op": "<", "ref": "open", "type": "self"}
            ]
        }
    ]
}
```

### 引擎接口（scripts/pattern_engine.py）

```python
def scan_patterns(kdata: list, rules: list = None) -> dict:
    """
    扫描K线数据，检测所有已启用的形态规则。

    Args:
        kdata: newest-first K线列表
               [(date, open, close, high, low, volume), ...]
        rules: 规则列表，None则自动从DB加载已启用规则

    Returns:
        {'patterns': [
            {'rule_id': 'C3-05', 'name': '三绿一红', 'name_cn': '三绿一红',
             'direction': 'bullish', 'strength': 3, 'trigger_idx': 3},
         ],
         'summary': {
            'bullish': {'count': 1, 'max_strength': 3},
            'bearish': {'count': 0, 'max_strength': 0}
         }}
    """

def load_rules_from_db() -> list:
    """从 pattern_rules 表加载所有 enabled=1 的规则。"""

def match_single_rule(kdata: list, rule: dict) -> dict | None:
    """对单条规则扫描K线，返回匹配结果或None。"""

def _eval_condition(candle: tuple, condition: dict, candles_map: dict) -> bool:
    """递归评估单条条件。"""
```

### 前端 Kline.vue patternPoints 数据结构

```javascript
// 从 /api/v2/pattern-scan/{code} 返回结果转换
const scanResult = {
  bullish: [
    { rule_id: 'C3-05', name: '三绿一红', idx: 42, price: 18.56, date: '2026-01-15', strength: 3 }
  ],
  bearish: [
    { rule_id: 'C2-02', name: '看跌吞没', idx: 35, price: 19.20, date: '2026-01-08', strength: 6 }
  ]
}

// 转换为 Chart.js scatter 数据
// bullishPoints / bearishPoints 各为一个 scatter dataset
```

## Agent Extensions

### SubAgent

- **code-explorer**: 已在前期探索阶段用于定位 Kline.vue 渲染逻辑（line 95-441）、App.vue 导航结构（navGroups/four groups）、router.js 路由模式（lazy loading）、db_helper.py 建表范本（init_backtest_tables）。后续执行阶段若需要查找更多模式（如API注册位置、前端样式约定），可再次调用。

### MCP

- **GitHub**: 实现完成后，通过 GitHub 创建 commit 和 push 代码变更到远端仓库，备份本次形态规则引擎的全部改动。