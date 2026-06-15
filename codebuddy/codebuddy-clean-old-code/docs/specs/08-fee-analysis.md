# 08 — 手续费分析

> **前端页面**: `deliverables/v2/src/pages/Fees.vue` (7KB)
> **路由**: `/fees` | **菜单**: 个人交易数据 → 手续费分析

---

## 1. 业务需求说明书

### 1.1 业务背景

用户需要了解在广发证券账户上的交易费用明细，包括佣金、印花税、过户费、规费、经手费等各项费用的累计金额和占比，用于评估交易成本和优化交易策略。

### 1.2 核心目标

| 目标 | 说明 |
|------|------|
| 费用分类统计 | 佣金/印花税/其他费用（过户+规费+经手费） |
| 单股票费用明细 | 每只股票的交易费用详情 |
| 费率可视化 | 费用占比饼图或条形图展示 |

---

## 2. 技术方案深度分析

### 2.1 费用计算规则

```python
# db_helper.py: _calc_fees() 函数
# 基于 config.json 中的 fee_rates 计算

# 佣金: 最低5元（买卖均收）
commission = max(5, qty × price × 0.0003)

# 印花税: 仅卖出收取（0.1%）
stamp_tax = qty × price × 0.001 if sell else 0

# 过户费: 买卖均收（¥1.0/千股）
transfer_fee = qty / 1000 × 1.0

# 规费: 买卖均收（0.002%）
regulatory_fee = qty × price × 0.00002

# 经手费: 买卖均收（0.00487%）
handling_fee = qty × price × 0.0000487
```

### 2.2 数据流

```
广发对账单 Excel
  → update_from_statement.py 解析费用字段
  → positions/closed_positions 表（total_commission/stamp_tax/other_fees）
  → GET /api/v2/positions
  → Fees.vue 聚合计算 + 图表渲染
```

---

## 3. 功能介绍和实现方式

### 3.1 API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v2/positions/current` | 含当前持仓费用汇总 |
| GET | `/api/v2/positions/closed` | 含已清仓费用汇总 |

### 3.2 后端数据模型

```python
# positions 表字段（费用相关）
total_commission    # 累计佣金
total_stamp_tax     # 累计印花税
total_other_fees    # 过户费+规费+经手费
```

### 3.3 前端实现

```vue
<!-- Fees.vue 核心结构 -->
<template>
  <!-- 费用总览卡片 -->
  <div class="fee-summary">
    <Card title="总佣金" :value="totalCommission" />
    <Card title="总印花税" :value="totalStampTax" />
    <Card title="其他费用" :value="totalOtherFees" />
    <Card title="总费用" :value="totalFees" />
  </div>

  <!-- 费用占比图 -->
  <PieChart :data="feeBreakdown" />

  <!-- 单股票费用明细 -->
  <DataTable :data="perStockFees">
    <Column field="code" header="代码" />
    <Column field="commission" header="佣金" />
    <Column field="stamp_tax" header="印花税" />
    <Column field="other" header="其他费用" />
    <Column field="total" header="合计" />
  </DataTable>
</template>
```

---

## 4. 用户操作流程

### 4.1 查看手续费汇总

```
用户: 导航栏 "个人交易数据" → "手续费分析"

页面显示:
┌───────────────────────────────────────────┐
│  累计费用统计                              │
│  ┌────────┬────────┬────────┬──────────┐  │
│  │ 总佣金 │ 印花税 │ 其他   │ 合计     │  │
│  │¥156.50 │¥85.30  │¥38.20  │¥280.00   │  │
│  └────────┴────────┴────────┴──────────┘  │
│                                           │
│  费用占比                                 │
│  [饼图: 佣金56% | 印花税30% | 其他14%]    │
│                                           │
│  各股票费用                               │
│  ┌──────┬──────┬────┬──────┬──────┐      │
│  │601166│¥75.0 │¥42 │¥18.5 │¥135.5│      │
│  └──────┴──────┴────┴──────┴──────┘      │
└───────────────────────────────────────────┘

数据来源: GET /api/v2/positions (current + closed)
```

### 4.2 理解费用构成

```
用户: 查看各费用项占比
  → 佣金最高（买卖双向收取）
  → 印花税仅卖出时产生
  → 其他费用占比最小（过户费+规费+经手费）
  → 优化策略: 减少高频交易以降低佣金支出
```
