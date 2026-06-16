# 07 — 交易记录

> **页面文件**: `pages/Trades.vue` (3.86 KB) | **路由**: `/trades`
> **Store**: `stores/data.js` (useDataStore)
> **依赖**: Chart.js | **数据源**: GET /api/v2/trades

---

## 1. 业务需求说明书

### 1.1 业务背景

需要查看从券商对账单解析出的全部历史交易流水，便于核对交易记录和税费明细。

### 1.2 核心目标

| 目标 | 说明 |
|------|------|
| 完整交易流水 | 展示全部买入、卖出、分红记录 |
| 关键字段展示 | 日期/时间/股票/类型/数量/价格/费用 |
| 月度趋势图 | Chart.js 柱状图按月统计买入/卖出/分红量 |

---

## 2. 页面布局

```
┌─ 交易流水 ───────────────────────────────────────────┐
│ 日期       │ 时间  │ 股票 │ 类型 │数量│价格│佣金│印花税│清算│
│ 2026-06-15 │09:30 │兴业  │买入 │5000│18.2│ 5.00│0    │-...│
│ 2026-06-10 │10:15 │招商  │卖出 │1000│36.5│ 3.00│36.5 │+...│
│ 2026-05-20 │--    │兴业  │分红 │--  │--  │--   │--   │+940│
└────────────────────────────────────────────────────────┘

┌─ 月度交易时间线 ──────────────────────────────────────┐
│  ████████  买入                                        │
│  ████      卖出                                        │
│  ██        分红                                        │
│  1月 2月 3月 4月 5月 6月                               │
└────────────────────────────────────────────────────────┘
```

---

## 3. 业务逻辑

### 3.1 交易流水表格

| 字段 | 数据来源 | 格式 |
|------|----------|------|
| 日期 | trades[].date | YYYY-MM-DD |
| 时间 | trades[].time | HH:MM:SS |
| 股票 | trades[].name | 中文名称 |
| 类型 | trades[].type | 买入(buy)/卖出(sell)/分红(dividend) |
| 数量 | trades[].qty | 整数，带千分位 |
| 价格 | trades[].price | 保留2位小数 |
| 佣金 | trades[].commission | 保留2位小数 |
| 印花税 | trades[].stamp_tax | 保留2位小数 |
| 清算金额 | trades[].settlement | 买入为负/卖出为正/分红为正 |

### 3.2 月度交易时间线

```javascript
// 使用 Chart.js 绘制堆叠柱状图
// 按月分组：买入总量(蓝色bar)、卖出总量(红色bar)、分红总量(绿色bar)
// X轴: 月份 (YYYY-MM)
// Y轴: 交易金额（元）

// 数据聚合逻辑
const monthlyData = {}
allTrades.forEach(t => {
    const month = t.date.slice(0, 7)
    if (!monthlyData[month]) monthlyData[month] = { buy: 0, sell: 0, div: 0 }
    if (t.type === 'buy') monthlyData[month].buy += t.settlement * -1  // 买入为正显示
    if (t.type === 'sell') monthlyData[month].sell += t.settlement
    if (t.type === 'dividend') monthlyData[month].div += t.settlement
})
```

---

## 4. 交互流程

```
路由 /trades → 组件挂载
  → useDataStore 提供 allTrades 数据
  → 渲染交易流水表格
  → Chart.js onMounted 绘制月度柱状图
  → 无刷新按钮（数据随全局刷新更新）
```

---

## 5. 数据依赖

| 数据 | 来源 | 用途 |
|------|------|------|
| allTrades | GET /api/v2/trades | 表格渲染 + 图表数据 |
