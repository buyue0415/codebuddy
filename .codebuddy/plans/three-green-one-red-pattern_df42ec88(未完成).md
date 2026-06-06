---
name: three-green-one-red-pattern
overview: 在日K线图中集成"三绿一红"蜡烛图形态识别，作为新信号参与预测投票，并在K线图上用箭头/标记可视化提示买入位置。
todos:
  - id: backend-signal
    content: 在 scripts/signals.py 中新增 three_green_one_red 信号：注册到 SIGNALS 列表，实现形态检测逻辑并集成到 calc_signals 返回结构
    status: pending
  - id: frontend-scan
    content: 在 Kline.vue 的 renderAll 中实现前端形态扫描，生成 patternPoints 数组
    status: pending
  - id: frontend-chart
    content: 在 buildKlineChart 的 datasets 中追加三绿一红 scatter 标记数据集
    status: pending
    dependencies:
      - frontend-scan
  - id: frontend-zoom
    content: 在 applyZoom 中追加 pattern 标记的切片与重索引逻辑，确保缩放平移时标记正确显示
    status: pending
    dependencies:
      - frontend-scan
---

## 产品概述

在现有A股投资管理系统中建立一套**数据库驱动的日K线量化形态规则引擎**，支持33条标准化K线形态规则的存储、编辑、自动检测和可视化标注。用户可通过管理页面手动增删改规则，后端从数据库读取规则并实时扫描日K线数据，在前端图表中可视化标记所有匹配的位置。

## 核心功能

- **规则管理**：管理页面支持CRUD（增删改查）全部K线形态规则，字段含名称/方向/分类/强度/O-H-L-C量化条件/是否启用
- **形态检测**：后端读取数据库中的已启用规则，在calc_signals中扫描日K线数据，输出匹配方向信号
- **预测集成**：形态信号自动参与系统加权投票，影响买卖决策
- **K线图标注**：日K走势图上以不同颜色/图标标记所有匹配形态的位置（看涨=金色三角向上，看跌=紫色三角向下）
- **自适应渲染**：标记支持图表缩放和平移

## 技术方案

### 总览

```
pattern_rules 表 (DB)
    ↓ 读取
[规则引擎: scripts/pattern_engine.py]  →  扫描kdata → 匹配结果
    ↓                                    ↓               ↓
calc_signals() 参与投票            Kline.vue 可视化      API 查询端
```

### 1. 数据库表结构

在 `data/stock.db` 中新增 `pattern_rules` 表：

```sql
CREATE TABLE IF NOT EXISTS pattern_rules (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_id     TEXT    NOT NULL UNIQUE,     -- 如 'C3-05', 'C2-01'
    name        TEXT    NOT NULL,            -- '三绿一红'
    name_en     TEXT    DEFAULT '',          -- 'Three Green One Red'
    category    TEXT    NOT NULL,            -- 'single'/'double'/'triple'/'multi'/'special'
    direction   TEXT    NOT NULL,            -- 'bullish'/'bearish'/'neutral'
    strength    INTEGER NOT NULL DEFAULT 3, -- 1~10
    span_days   INTEGER NOT NULL,           -- K线跨度天数
    conditions  TEXT    NOT NULL,            -- JSON: 量化触发条件
    enabled     INTEGER NOT NULL DEFAULT 1, -- 1启用 0禁用
    memo        TEXT    DEFAULT '',          -- 备注
    created_at  TEXT    DEFAULT (datetime('now','localtime')),
    updated_at  TEXT    DEFAULT (datetime('now','localtime'))
);
```

### 2. conditions 字段 JSON 结构

每个规则的量化条件统一用JSON存储，格式如下：

```
{
    "candles": [
        {
            "idx": 0,
            "label": "K1（最新）",
            "rules": [
                {"field": "close", "op": ">", "value": "close_1", "ref": "previous"},
                {"field": "body_ratio", "op": ">=", "value": 0.6}
            ]
        },
        {
            "idx": 1,
            "label": "K2",
            "rules": [
                {"field": "close", "op": "<", "value": "open", "ref": "self"},
                {"field": "body_ratio", "op": ">=", "value": 0.5}
            ]
        }
    ],
    "cross_candle": [
        {"idx": 0, "field": "low", "op": ">", "from_idx": 1, "from_field": "high", "ref": "cross"}
    ],
    "strength_extra": {
        "gap_required": false,
        "volume_confirmation": false
    }
}
```

**支持的条件操作符**：

| op | 含义 | 示例 |
| --- | --- | --- |
| `>` `>=` `<` `<=` | 数值比较 | `close > close_1` |
| `==` | 相等（含容差） | body_type == 'yang' |
| `body_ratio` | 实体/总范围比 | body_ratio >= 0.6 |
| `upper_shadow` / `lower_shadow` | 上/下影线长度 | lower_shadow >= body * 2 |
| `engulf` | 吞没判断 | engulf(K0实体, K1实体) |
| `midpoint` | 实体中心 | close > midpoint(K1) |


### 3. 新增文件：`scripts/pattern_engine.py`

独立模块，负责：

- 从DB读取所有已启用的规则
- 对给定的日K线数据扫描所有规则
- 返回匹配结果列表

```python
def scan_patterns(kdata: list) -> dict:
    """
    扫描日K线数据，检测所有已启用的形态规则。
    
    kdata: newest-first K线列表
           [(date, open, close, high, low, volume), ...]
    
    return: {
        'patterns': [
            {'rule_id': 'C3-05', 'name': '三绿一红',
             'direction': 'bullish', 'strength': 3, 'trigger_idx': 3},
            ...
        ],
        'aggregate': {
            'bullish_count': 1, 'bearish_count': 0,
            'max_bullish_strength': 3, 'max_bearish_strength': 0
        }
    }
    """
```

### 4. 修改 `scripts/signals.py`

- 在 `SIGNALS` 列表中新增 `'pattern_signals'` 别名
- 在 `calc_signals()` 中调用 `scan_patterns()`，将匹配结果聚合为单个信号方向

```python
# 在 calc_signals() 末尾:
pattern_result = scan_patterns(kdata)
pat_dir = 'bullish' if pattern_result['aggregate']['bullish_count'] > pattern_result['aggregate']['bearish_count'] else 'bearish' if ...  else 'neutral'

signals['pattern_signals'] = {
    'direction': pat_dir,
    'value': f"{pat_result['aggregate']['bullish_count']}买{pat_result['aggregate']['bearish_count']}卖",
    'raw': pat_result['aggregate']['max_bullish_strength'] - pat_result['aggregate']['max_bearish_strength'],
    'details': pattern_result['patterns']  # 前端标记用
}
```

### 5. API 端点

新增端点（在 `server_v2.py`）：

| 端点 | 方法 | 功能 |
| --- | --- | --- |
| `/api/v2/pattern-rules` | GET | 获取全部规则列表（含分页） |
| `/api/v2/pattern-rules/{id}` | GET | 获取单条规则详情 |
| `/api/v2/pattern-rules` | POST | 新增规则 |
| `/api/v2/pattern-rules/{id}` | PUT | 修改规则 |
| `/api/v2/pattern-rules/{id}` | DELETE | 删除规则 |
| `/api/v2/pattern-scan/{code}` | GET | 对指定股票扫描所有规则，返回匹配结果 |


### 6. 前端新页面：`PatternRules.vue`

管理页面（在侧边栏新增"形态规则"入口）：

- 展示所有规则的表格（id/名称/方向/分类/强度/启用状态）
- 按分类/方向筛选
- 编辑弹窗：修改条件JSON、名称、启用状态等
- 支持批量启用/禁用

### 7. 修改 `Kline.vue`

从 `data.predictions` 中的 `pattern_signals.details`（或调用 `/api/v2/pattern-scan/{code}`）获取该股票全部历史形态匹配结果，分组后渲染多个scatter数据集：

- 看涨形态：金色向上三角
- 看跌形态：紫色向下三角
- 鼠标悬停tooltip显示形态名称和强度

### 8. 初始化数据

在 `scripts/init_rules.py` 中将完整33条形态规则写入DB（首次运行、自动迁移）。

## 数据库初始化

首次部署时运行：

```python
# scripts/init_pattern_rules.py
from db_helper import get_connection
from pattern_engine import RULE_CATALOG  # 全量规则定义

def init_rules():
    conn = get_connection()
    for rule in RULE_CATALOG:
        conn.execute("INSERT OR IGNORE INTO pattern_rules ...", rule)
    conn.commit()
```

## 目录变更

```
scripts/
├── pattern_engine.py       # [NEW] 形态检测引擎，读取DB规则+扫描K线
├── init_pattern_rules.py   # [NEW] 初始化写入33条规则到DB
└── signals.py              # [MODIFY] 新增 pattern_signals 信号，集成引擎

deliverables/v2/src/pages/
├── PatternRules.vue         # [NEW] 形态规则管理页面
└── Kline.vue               # [MODIFY] 渲染所有历史形态标注点

server_v2.py                # [MODIFY] 新增 pattern-rules REST API
server.py                   # [MODIFY] 同步新增同路径处理
```

## TODOs

| ID | 任务 | 说明 | 依赖 |
| --- | --- | --- | --- |
| `db-rules-table` | 创建 pattern_rules 表及初始化脚本 | 建表SQL + init_pattern_rules.py 全量规则写入 | - |
| `pattern-engine` | 实现 pattern_engine.py 形态扫描引擎 | 解析conditions JSON，匹配K线数据 | `db-rules-table` |
| `backend-signal` | 集成到 signals.py | 在calc_signals中调用引擎，注册模式信号 | `pattern-engine` |
| `api-crud` | 新增 pattern-rules REST API | 增删改查端点 + pattern-scan 扫描接口 | `db-rules-table` |
| `frontend-mgmt` | 创建 PatternRules.vue 管理页面 | 规则表格 + 编辑弹窗 + 筛选 | `api-crud` |
| `frontend-chart` | 修改 Kline.vue 渲染形态标记 | 读取pattern-scan结果，渲染多色标记 | api-crud |
