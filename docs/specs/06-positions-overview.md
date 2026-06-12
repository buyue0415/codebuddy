# 06 — 持仓总览

> **前端页面**: `deliverables/v2/src/pages/Overview.vue` (11KB)
> **路由**: `/overview` | **菜单**: 个人交易数据 → 持仓总览

---

## 1. 业务需求说明书

### 1.1 业务背景

用户需要一目了然地了解当前持仓状态：持有哪些股票、成本价、当前市值、浮盈亏、历史分红收益，以及已清仓股票的实现盈亏。

### 1.2 核心目标

| 目标 | 说明 |
|------|------|
| 当前持仓总览 | 展示每只持仓股票的代码/名称/数量/成本/现价/盈亏 |
| 已清仓汇总 | 历史清仓股票的实现盈亏统计 |
| 分红收益 | 累计分红金额展示 |
| 关键指标 | 总资产、总盈亏、收益率一览 |

---

## 2. 技术方案深度分析

### 2.1 数据流

```
GET /api/v2/positions/current  → positions 表（当前持仓）
GET /api/v2/positions/closed   → closed_positions 表（已清仓）
GET /api/v2/quotes             → quotes 表（实时行情）
GET /api/v2/dividends          → dividends 表（分红记录）

client.js → loadAllData() → 并行请求 → Pinia store → Overview.vue computed
```

### 2.2 浮盈亏计算

```javascript
// 前端实时计算
unrealized_pnl = (current_price - avg_cost) × qty
unrealized_pnl_pct = (current_price / avg_cost - 1) × 100

// 后端 db_helper.py 提供费用汇总
get_current_positions() → {total_commission, total_stamp_tax, total_other_fees}
```

### 2.3 数据源

| 数据项 | 后端来源 | 表 |
|--------|---------|-----|
| 当前持仓 | `get_current_positions()` | positions |
| 已清仓汇总 | `get_closed_positions()` | closed_positions |
| 交易记录 | `get_trades()` | trades |
| 行情报价 | `get_quotes()` | quotes |
| 分红记录 | `get_dividends()` | dividends |

---

## 3. 功能介绍和实现方式

### 3.1 API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v2/positions` | 完整持仓数据（当前+已清仓） |
| GET | `/api/v2/positions/current` | 仅当前持仓 |
| GET | `/api/v2/positions/closed` | 仅已清仓 |

### 3.2 前端实现

```vue
<!-- Overview.vue 核心结构 -->
<template>
  <!-- 总览卡片 -->
  <div class="summary-cards">
    <Card title="总资产" :value="totalAsset" />
    <Card title="总盈亏" :value="totalPnl" :class="pnlClass" />
    <Card title="收益率" :value="totalReturnPct" />
  </div>

  <!-- 当前持仓表 -->
  <DataTable :data="currentPositions">
    <Column field="code" header="代码" />
    <Column field="name" header="名称" />
    <Column field="qty" header="持仓量" />
    <Column field="avg_cost" header="成本价" />
    <Column field="price" header="现价" />
    <Column field="market_value" header="市值" />
    <Column field="unrealized_pnl" header="浮盈亏" />
  </DataTable>

  <!-- 已清仓汇总 -->
  <DataTable :data="closedPositions"> ... </DataTable>
</template>
```

### 3.3 数据刷新

- 首次加载：`loadAllData()` 并行请求 15 个 API
- 手动刷新：切换至此页面时自动重新请求
- 上传对账单后：持仓数据自动更新

---

## 4. 用户操作流程

### 4.1 查看持仓总览

```
用户: 打开系统 → 默认进入 "持仓总览"

页面数据:
┌─────────────────────────────────────────┐
│  总资产: ¥108,500    总盈亏: +¥8,500    │
│  持仓市值: ¥85,000   现金: ¥23,500      │
│  收益率: +8.5%                          │
├─────────────────────────────────────────┤
│  当前持仓                               │
│  ┌──────┬────┬────┬──────┬───────┬────┐│
│  │601166│兴业│1000│17.35 │17.85  │+500││
│  │600036│招行│ 500│38.20 │39.10  │+450││
│  └──────┴────┴────┴──────┴───────┴────┘│
├─────────────────────────────────────────┤
│  已清仓汇总                             │
│  ┌──────┬────┬──────┬─────────┐        │
│  │600050│联通│+¥1,200│+3.2%   │        │
│  └──────┴────┴──────┴─────────┘        │
└─────────────────────────────────────────┘
```

### 4.2 更新持仓数据

```
用户: 管理设置 → 上传广发对账单
  → 自动解析 Excel → 写入 positions/trades/dividends 表
  → 返回持仓总览 → 自动刷新显示最新数据
```
