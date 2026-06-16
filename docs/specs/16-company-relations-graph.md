# 16 — 公司关系图谱

> **页面文件**: `pages/CompanyGraph.vue` (574行) | **路由**: `/company-graph`
> **Store**: `stores/data.js` (useDataStore) + `stores/industry.js` (useIndustryStore)
> **组件**: `IndustryGroupTabs.vue` | **依赖**: @antv/g6（关系图谱库）
> **API**: GET /api/v2/company-relations, /api/v2/graph-data, /api/v2/relation-types

---

## 1. 业务需求说明书

### 1.1 业务背景

投资者需要了解股票之间的关联关系，包括供应链上下游、股权结构、高管任职、竞争对手等，以便在投资决策中考虑产业链联动效应。

### 1.2 核心目标

| 目标 | 说明 |
|------|------|
| 关系可视化 | 使用 @antv/g6 力导向图展示公司间关系 |
| 关系类型 | 供应链/股权投资/高管任职/竞争关系 |
| 交互探索 | 拖拽、缩放、点击节点查看详情 |
| 行业切换 | IndustryGroupTabs 选择股票 |

---

## 2. 页面布局

```
┌──────────────────────────────────────────────────────────┐
│ IndustryGroupTabs: [银行] [保险] [证券]                  │
│ [兴业银行] [招商银行] [工商银行]                         │
├──────────────────────────────────────────────────────────┤
│ ┌─ 关系图谱 (@antv/g6) ─────────────────────────────────┐ │
│ │                                                      │ │
│ │      [招商银行] ──── 股权投资 ──── [兴业银行]        │ │
│ │         │                    │                        │ │
│ │       高管                  供应链                     │ │
│ │         │                    │                        │ │
│ │    [原中国银监会]     [恒生电子]                      │ │
│ │                           │                           │ │
│ │                         竞争                          │ │
│ │                           │                           │ │
│ │                       [用友网络]                      │ │
│ └──────────────────────────────────────────────────────┘ │
├──────────────────────────────────────────────────────────┤
│ ┌─ 关系类型图例 ───────────────────────────────────────┐ │
│ │  🔴 股权投资  🟢 供应链  🔵 高管  🟡 竞争          │ │
│ └──────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────┘
```

---

## 3. 业务逻辑

### 3.1 数据源

关系数据通过 `fetch_company_relations.py` 从 NeoData API 获取：

```json
// graph-data API 返回格式
{
  "nodes": [
    {"id": "601166", "label": "兴业银行", "type": "stock"},
    {"id": "600036", "label": "招商银行", "type": "stock"},
    {"id": "恒生电子", "label": "恒生电子", "type": "company"}
  ],
  "edges": [
    {"source": "601166", "target": "恒生电子", "type": "供应链", "weight": 0.8},
    {"source": "601166", "target": "600036", "type": "竞争", "weight": 0.6}
  ]
}
```

### 3.2 关系类型

| 类型 | 颜色 | 说明 |
|------|------|------|
| 股权投资 | 🔴 #dc2626 | 交叉持股、母公司子公司 |
| 供应链 | 🟢 #16a34a | 供应商、客户关系 |
| 高管 | 🔵 #2563eb | 共同高管、董事会关联 |
| 竞争 | 🟡 #d97706 | 同行业竞争关系 |

### 3.3 @antv/g6 配置

```javascript
// 力导向图布局 (force)
const graph = new G6.Graph({
    container: 'graph-container',
    width: containerWidth,
    height: containerHeight,
    layout: {
        type: 'force',
        preventOverlap: true,
        nodeStrength: -200,
        edgeStrength: 0.1,
    },
    defaultNode: {
        type: 'circle',
        size: 40,
        labelCfg: { style: { fontSize: 12 } },
    },
    defaultEdge: {
        type: 'line',
        style: { endArrow: true, lineWidth: 2 },
    },
    modes: {
        default: ['drag-canvas', 'zoom-canvas', 'click-select'],
    },
})
```

---

## 4. 交互流程

```
挂载 → IndustryGroupTabs 选择股票
  → GET /api/v2/graph-data?code=XXX
  → 获取节点和边数据
  → @antv/g6 初始化渲染力导向图
  → 交互: 拖拽/缩放/点击节点高亮关联边
  → 图例展示关系类型颜色
```

---

## 5. 数据依赖

| API | 用途 |
|-----|------|
| GET /api/v2/company-relations | 原始关系数据 |
| GET /api/v2/graph-data | 图谱节点和边 |
| GET /api/v2/relation-types | 关系类型列表 |
