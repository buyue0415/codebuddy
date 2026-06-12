# 17 — 交易历史

> **前端页面**: `deliverables/v2/src/pages/PaperHistory.vue` (8KB)
> **路由**: `/paper/history` | **菜单**: 模拟交易 → 交易历史

---

## 1. 业务需求说明书

### 1.1 业务背景

用户需要追踪纸面交易的长期表现：资金曲线走势、交易胜率、盈亏比、与买入持有基准的对比。交易历史页提供完整的可视化分析和统计摘要。

### 1.2 核心目标

| 目标 | 说明 |
|------|------|
| 资金曲线图 | 纸面账户 vs 买入持有基准双线对比 |
| 统计摘要 | 总交易次数/胜率/盈亏比/最大单笔盈亏 |
| 交易明细 | 全部交易记录，支持筛选/排序 |
| 时间范围 | 30天/90天/180天可切换 |

---

## 2. 技术方案深度分析

### 2.1 表现指标计算

```python
# paper_trading.py: calculate_performance()

# 夏普比率
daily_returns = [snap[i].total_asset / snap[i-1].total_asset - 1 ...]
sharpe = mean(daily_returns) / std(daily_returns) × √252

# 最大回撤
for each snapshot:
    peak = max(peak, total_asset)
    max_dd = max(max_dd, (peak - total_asset) / peak)

# 胜率
wins = count(r > 0 for r in daily_returns)
win_rate = wins / total
```

### 2.2 资金曲线数据来源

```
paper_daily_snapshot 表
  → 每日一条: {date, total_asset, cash, position_value, daily_pnl}
  → 前端 Chart.js 渲染折线图
```

### 2.3 买入持有基准

```python
# 基准 = 等权买入所有当前持仓股票
# 起始值 = initial_capital
# 每日值 = initial_capital × (1 + avg_return_of_positions)
```

---

## 3. 功能介绍和实现方式

### 3.1 API 端点

| 方法 | 路径 | 参数 | 说明 |
|------|------|------|------|
| GET | `/api/v2/paper/trades` | `?code=&limit=&offset=` | 交易记录分页 |
| GET | `/api/v2/paper/performance` | `?days=90` | 表现指标+资金曲线 |

### 3.2 前端实现

```vue
<!-- PaperHistory.vue 核心结构 -->
<template>
  <!-- 资金曲线 -->
  <section>
    <h3>资金曲线</h3>
    <TabBar>
      <Tab label="30天" :days="30" />
      <Tab label="90天" :days="90" />
      <Tab label="180天" :days="180" />
    </TabBar>
    <LineChart :data="equityCurve">
      <Dataset label="纸面账户" color="blue" :data="accountValues" />
      <Dataset label="买入持有" color="gray" :data="benchmarkValues" dashed />
    </LineChart>
  </section>

  <!-- 统计摘要 -->
  <SummaryCards>
    <Card title="总交易" :value="totalTrades" />
    <Card title="胜率" :value="winRate" suffix="%" />
    <Card title="盈亏比" :value="profitFactor" />
    <Card title="最大单笔盈利" :value="maxWin" />
    <Card title="最大单笔亏损" :value="maxLoss" />
  </SummaryCards>

  <!-- 交易明细 -->
  <DataTable :data="trades" :filters="{ code }" sortable>
    <Column field="date" header="日期" />
    <Column field="code" header="代码" />
    <Column field="direction" header="买/卖" />
    <Column field="qty" header="数量" />
    <Column field="price" header="价格" />
    <Column field="pnl" header="盈亏" :class="pnlClass" />
  </DataTable>
</template>
```

---

## 4. 用户操作流程

### 4.1 查看资金曲线

```
用户: 导航栏 "模拟交易" → "交易历史"

页面显示:
┌───────────────────────────────────────────────┐
│  📜 交易历史                                   │
│                                               │
│  资金曲线    [30天] [90天] [180天]              │
│  ┌────────────────────────────────────────┐   │
│  │  ¥110,000                               │   │
│  │  ¥105,000    ████████░░░░░░  ← 纸面账户 │   │
│  │  ¥100,000 ████░░░░░░░░░░░░  ← 买入持有  │   │
│  │   ¥95,000                               │   │
│  │          06-01  06-03  06-05            │   │
│  └────────────────────────────────────────┘   │
│                                               │
│  统计摘要                                     │
│  总交易: 45次 | 胜率: 58.3% | 盈亏比: 1.32    │
│                                               │
│  交易记录                         [全部 ▼]    │
│  ┌─────────┬──────┬──┬────┬──────┬──────┐    │
│  │日期     │ 代码 │方│数量│价格  │盈亏  │    │
│  │06-05    │601166│买│ 300│17.05 │ —    │    │
│  │06-04    │002594│卖│ 200│268.5 │+1240 │    │
│  └─────────┴──────┴──┴────┴──────┴──────┘    │
└───────────────────────────────────────────────┘
```

### 4.2 切换时间范围

```
用户: 点击 [180天] 标签
  → GET /api/v2/paper/performance?days=180
  → 图表数据更新为更长周期
  → 统计摘要相应变化
```

### 4.3 筛选交易记录

```
用户: 下拉筛选 "601166 兴业银行"
  → GET /api/v2/paper/trades?code=601166
  → 仅显示该股票的交易记录
```
