---
name: three-green-one-red-pattern
overview: 建立数据库驱动的日K线量化形态规则引擎，支持33条标准化K线形态规则的增删改查、自动检测、图表标注，用户可通过管理页面手动编辑规则。
todos:
  - id: db-rules-table
    content: 创建 pattern_rules 表并实现 33 条规则的初始化写入脚本
    status: pending
  - id: pattern-engine
    content: 实现 pattern_engine.py 形态检测引擎：加载规则 + 解析 conditions JSON + 扫描K线匹配
    status: pending
    dependencies:
      - db-rules-table
  - id: backend-signal
    content: 在 signals.py 注册 pattern_signals 信号并集成引擎调用，参与预测投票
    status: pending
    dependencies:
      - pattern-engine
  - id: api-crud
    content: 在 server_v2.py 新增 pattern-rules CRUD API 和 pattern-scan 扫描接口
    status: pending
    dependencies:
      - db-rules-table
  - id: frontend-mgmt
    content: 创建 PatternRules.vue 管理页面，注册路由和导航，实现规则表格+编辑弹窗
    status: pending
    dependencies:
      - api-crud
  - id: frontend-chart
    content: 修改 Kline.vue 从 API 获取扫描结果，渲染多色形态标记并支持缩放
    status: pending
    dependencies:
      - api-crud
---

## 产品概述

在现有A股投资管理系统中建立一套**数据库驱动的日K线量化形态规则引擎**。引擎自动扫描33条标准化的K线形态规则（涵盖单K线、双K线、三K线、多K线、特殊结构五大类），在日K线上实时检测匹配的形态，结果参与系统预测投票，并在K线图上以可视化标记展示。所有规则存储在数据库内，用户可通过管理页面自行增、删、改、启用/禁用。

## 核心功能

- **规则库管理**：新增 `PatternRules.vue` 管理页面，以表格展示全部规则，支持按分类/方向/强度筛选，支持新增、编辑、删除规则
- **形态自动检测**：后端 `pattern_engine.py` 读取数据库中的已启用规则，对日K线数据进行多规则并行扫描，输出匹配结果
- **预测信号集成**：形态扫描结果聚合为一个 `pattern_signals` 信号，自动加入 `SIGNALS` 列表参与加权投票
- **K线图可视化标注**：在日K走势图上以金色向上三角(看涨)/紫色向下三角(看跌)标记历史形态出现位置，鼠标悬停显示形态名称和强度
- **初始化数据**：首次运行时自动将33条标准规则写入数据库

## Tech Stack Selection

- **后端语言**: Python 3.12 + FastAPI (复用现有 stack)
- **数据库**: SQLite (复用现有 `data/stock.db`)
- **前端框架**: Vue 3 + Pinia + Vue Router (复用现有)
- **图表库**: Chart.js (复用现有 Kline.vue 实现)
- **数据格式**: JSON (conditions 字段存储量化条件)
- **部署**: 本地部署，无外部依赖

## Implementation Approach

### 总体策略

采用**数据库驱动 + 后端计算 + 前端标注**三层架构：

1. **数据层**（pattern_rules 表）：存储规则的定义，包含名称/方向/分类/强度/OHLC量化条件(JSON)/启用状态等字段
2. **计算层**（pattern_engine.py + signals.py）：引擎从DB加载已启用规则，扫描日K线数据逐条匹配，结果聚合为单一信号参与投票
3. **展示层**（PatternRules.vue + Kline.vue）：管理页面CRUD规则，K线图读取扫描结果渲染标记

### 关键设计决策

1. **conditions 字段使用JSON格式**：每条规则的量化条件统一用JSON表达，支持 `candles`（逐根K线约束）、`cross_candle`（跨K线约束如吞没/跳空）、`strength_extra`（加强条件）。JSON可被前端编辑器和后端解析器双向理解。

2. **规则扫描引擎独立模块**：新建 `pattern_engine.py`，与现有 signals.py 解耦。signals.py 仅做薄层调用，不关心具体规则逻辑。未来如果规则数量增长到100+，不影响主信号计算性能。

3. **后端仅返回"当前"信号，前端扫描历史**：calc_signals() 只扫描最近N根K线判断当前是否有形态信号；Kline.vue 独立扫描全部历史数据做可视化标注。两者逻辑一致但职责分离。

4. **管理页面放在"管理设置"分组**：复用现有 `/manage` 路由附近的架构，在App.vue的 `navGroups` 中为 `rule` 分组添加入口。

### 性能注意事项

- pattern_engine 每次 calc_signals 调用时加载规则（DB查询，30条规则 < 1ms）
- 前端扫描历史形态时一次性完成（JavaScript 纯计算，1000条K线 * 33条规则 ≈ 33000次比较，< 50ms）
- 后续可考虑缓存规则列表到内存（LRU缓存，TTL=60s）

## Architecture Design

```mermaid
flowchart TB
    subgraph DataLayer[数据层 - SQLite]
        PR[pattern_rules 表<br/>id, rule_id, name, category<br/>direction, strength, span_days<br/>conditions JSON, enabled]
    end

    subgraph Backend[后端 - Python]
        PE[pattern_engine.py<br/>scan_patterns()]
        SI[signals.py<br/>calc_signals + gen_pred]
        API[server_v2.py<br/>REST API]
        DB_HELPER[db_helper.py<br/>get_db + CRUD helpers]
    end

    subgraph Frontend[前端 - Vue 3]
        ROUTER[router.js<br/>新增 /patterns 路由]
        NAV[App.vue<br/>导航栏新增入口]
        PM[PatternRules.vue<br/>规则管理表格+编辑弹窗]
        KL[Kline.vue<br/>形态标注+tooltip]
        DS[data.js Store<br/>patterns 数据]
    end

    PR -->|加载已启用规则| PE
    KLINE[(kline_daily 表)] -->|日K线数据| PE
    PE -->|匹配结果| SI
    SI -->|gen_pred| API
    API -->|GET /api/v2/pattern-rules| PR
    API -->|POST/PUT/DELETE| DB_HELPER
    DB_HELPER -->|写入| PR
    KL -->|GET /api/v2/pattern-scan/{code}| API
    API -->|扫描结果| KL
    PM -->|CRUD 操作| API
    DATA[data.predictions] -->|pattern_signals| KL
```

## Directory Structure

```
scripts/
├── pattern_engine.py       # [NEW] 形态检测引擎：加载DB规则 + 扫描K线输出匹配结果
├── init_pattern_rules.py   # [NEW] 初始化写入33条规则到数据库
├── db_helper.py            # [MODIFY] 新增 pattern_rules 表DDL + CRUD helper函数
└── signals.py              # [MODIFY] 注册 pattern_signals，集成引擎调用

server_v2.py                # [MODIFY] 新增 pattern-rules CRUD API + pattern-scan 扫描接口

deliverables/v2/src/
├── router.js               # [MODIFY] 新增 /patterns 路由
├── App.vue                 # [MODIFY] 导航栏新增"形态规则"入口
├── stores/data.js          # [MODIFY] 新增 patterns 数据引用
├── api/client.js           # [MODIFY] 在 loadAllData 中加载 pattern-rules
└── pages/
    ├── PatternRules.vue    # [NEW] 规则管理页面（表格+编辑弹窗+筛选）
    └── Kline.vue           # [MODIFY] 渲染形态标注点（多色标记+tooltip）
```

## Key Code Structures

### 数据库表结构

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

### conditions JSON 格式

```
{
    "candles": [
        {
            "idx": 0,
            "label": "K1（最新）",
            "rules": [
                {"field": "close", "op": ">", "ref": "open", "type": "self"},
                {"field": "body_ratio", "op": ">=", "value": 0.6, "type": "value"}
            ]
        }
    ],
    "cross_candle": [
        {"from_idx": 1, "from_field": "high", "op": "<", "to_idx": 0, "to_field": "low", "type": "cross"}
    ]
}
```

### 后端引擎接口

```python
def scan_patterns(kdata: list, rules: list = None) -> dict:
    """
    扫描K线数据匹配形态规则。
    
    Args:
        kdata: newest-first K线列表 [(date, open, close, high, low, volume), ...]
        rules: 规则列表，None则自动从DB加载已启用规则
    
    Returns:
        {'patterns': [{'rule_id': 'C3-05', 'name': '三绿一红', 'direction': 'bullish',
                       'strength': 3, 'trigger_idx': 3}, ...],
         'summary': {'bullish': {'count': 2, 'max_strength': 7},
                     'bearish': {'count': 1, 'max_strength': 6},
                     'neutral': {'count': 0, 'max_strength': 0}}}
    """
```

### signals.py 集成（添加在 calc_signals 返回结构中）

```python
# 在 calc_signals 的 signals dict 中新增:
'pattern_signals': {
    'direction': 'bullish',   # 由扫描结果汇总决定
    'value': f'{pat["summary"]["bullish"]["count"]}买{pat["summary"]["bearish"]["count"]}卖',
    'raw': pat["summary"]["bullish"]["max_strength"] - pat["summary"]["bearish"]["max_strength"],
    'details': pat["patterns"],  # 透传给前端做可视化
}
```

### 前端 patternPoints 数据结构（Kline.vue 内部）

```javascript
// 每个形态类型一组
const patternByType = {
  'C3-05': { label: '三绿一红', color: '#f59e0b', direction: 'bullish', points: [
    { x: 42, y: 18.56, date: '2026-01-15' },
    ...
  ]},
  'C2-01': { label: '看涨吞没', color: '#f59e0b', direction: 'bullish', points: [...]},
  ...
}
```

## Agent Extensions

### Skill

- **brainstorming**
- Purpose: 已用于前期需求澄清和规则体系设计，确定5大类33条规则的结构化方案
- Expected outcome: 形成完整规则目录和量化条件定义

- **subagent-driven-development**
- Purpose: 执行计划时的任务分批执行。本计划的6个任务相互独立且有明确数据依赖，适合使用子代理并行开发
- Expected outcome: 通过子代理隔离执行后端模块和前端模块，提高开发效率

### SubAgent

- **code-explorer**
- Purpose: 探索阶段已完成，用于定位 signals.py/SIGNALS 列表、Kline.vue 渲染逻辑、db_helper.py建表模式和服务器路由注册模式
- Expected outcome: 确认所有修改点的精确行号和代码模式

### MCP

- **GitHub**
- Purpose: 执行完成后，通过 GitHub 创建 PR 或推送代码到远端仓库以备份本次改动
- Expected outcome: 代码变更通过 git commit 和 push 存储到远程仓库