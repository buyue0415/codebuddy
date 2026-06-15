# 07 — 交易记录

> **前端页面**: `deliverables/v2/src/pages/Trades.vue` (4KB)
> **路由**: `/trades` | **菜单**: 个人交易数据 → 交易记录

---

## 1. 业务需求说明书

### 1.1 业务背景

用户需要查看从广发证券对账单中解析出的全部历史交易记录，包括买入、卖出、股息入账等操作，支持按股票代码筛选和时间排序。

### 1.2 核心目标

| 目标 | 说明 |
|------|------|
| 完整交易列表 | 展示日期/时间/代码/名称/类型/数量/价格/费用 |
| 股票筛选 | 按代码过滤特定股票的交易记录 |
| 费用明细 | 每笔交易的佣金/印花税/过户费 |

---

## 2. 技术方案深度分析

### 2.1 数据流

```
广发对账单 Excel
  → update_from_statement.py（pandas 解析）
  → trades 表写入（含佣金/印花税/过户费/发生金额）
  → GET /api/v2/trades?code={code}
  → Trades.vue 渲染
```

### 2.2 数据表结构

**trades 表**:
```
date, time, code, name, type, qty, price, commission, stamp_tax, settlement
```

**交易类型**:
- `证券买入`：qty 为正，settlement 为负（支出）
- `证券卖出`：qty 为负，settlement 为正（收入）
- `股息入账`：amount 为正

---

## 3. 功能介绍和实现方式

### 3.1 API 端点

| 方法 | 路径 | 参数 | 说明 |
|------|------|------|------|
| GET | `/api/v2/trades` | `?code=` | 全部交易/筛选股票 |
| GET | `/api/v2/trades/{code}` | — | 单只股票交易记录 |

### 3.2 后端实现

```python
# db_helper.py:306
def get_trades(code=None):
    db = get_db()
    if code:
        rows = db.execute(
            "SELECT * FROM trades WHERE code=? ORDER BY date DESC, time DESC",
            [code]
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT * FROM trades ORDER BY date DESC, time DESC"
        ).fetchall()
    db.close()
    # 含实时费用计算 _calc_fees()
    return [dict(r) for r in rows]
```

### 3.3 前端实现

```vue
<!-- Trades.vue -->
<template>
  <DataTable :data="trades" :filters="{ code }">
    <Column field="date" header="日期" sortable />
    <Column field="time" header="时间" />
    <Column field="code" header="代码" />
    <Column field="name" header="名称" />
    <Column field="type" header="类型" />
    <Column field="qty" header="数量" />
    <Column field="price" header="价格" :format="fmtMoney" />
    <Column field="commission" header="佣金" />
    <Column field="stamp_tax" header="印花税" />
    <Column field="settlement" header="发生金额" :class="pnlClass" />
  </DataTable>
</template>
```

---

## 4. 用户操作流程

### 4.1 查看全部交易记录

```
用户: 导航栏 "个人交易数据" → "交易记录"

页面显示:
┌──────────────────────────────────────────────────────┐
│  交易记录                              [代码筛选 ▼]  │
│  ┌────────┬──────┬────┬──────┬──┬────┬─────┬──────┐ │
│  │日期    │ 时间  │代码│名称  │类│数量│价格 │费用  │ │
│  │05-20   │09:35 │1601│兴业  │买│500 │17.30│¥7.50 │ │
│  │05-18   │14:20 │6000│招行  │卖│200 │38.5 │¥15.2 │ │
│  │05-15   │—     │6011│兴业  │息│—   │—    │¥936  │ │
│  └────────┴──────┴────┴──────┴──┴────┴─────┴──────┘ │
└──────────────────────────────────────────────────────┘

数据来源: GET /api/v2/trades
```

### 4.2 筛选特定股票

```
用户: 点击代码筛选下拉 → 选择 "601166 兴业银行"
  → 前端: GET /api/v2/trades/601166
  → 表格仅显示兴业银行的交易记录
```

### 4.3 更新交易数据

```
用户: 管理设置 → 上传新对账单
  → 自动解析 → trades 表追加新记录
  → 返回交易记录 → 显示最新数据
```
