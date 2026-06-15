# 16 — 纸面交易

> **前端页面**: `deliverables/v2/src/pages/PaperTrading.vue` (16KB)
> **路由**: `/paper` | **菜单**: 模拟交易 → 纸面交易
> **核心脚本**: `scripts/paper_trading.py` (19KB)

---

## 1. 业务需求说明书

### 1.1 业务背景

用户希望在真实投入资金之前，先验证预测系统的交易效果。纸面交易用虚拟资金（¥100,000）模拟真实交易，每日基于预测数据的 direction/confidence/entry_zone 自动执行买卖，帮助评估策略表现。

### 1.2 核心目标

| 目标 | 说明 |
|------|------|
| 虚拟账户 | ¥100,000 初始资金，独立于真实账户 |
| 自动交易 | sync_all 完成后自动执行买卖 |
| 凯利仓位 | 基于置信度动态计算仓位（上限30%） |
| 数据同源 | 必须与前端预测页使用完全相同的数据 |

---

## 2. 技术方案深度分析

### 2.1 数据一致性约束（🔴 强制）

纸面交易必须与前端智能预测使用完全相同的数据源：

| 数据项 | 来源 | 字段 |
|--------|------|------|
| 预测方向 | `daily_predictions.direction` | gen_multi_day_pred() 输出 |
| 置信度 | `daily_predictions.confidence` | 前端10天预测同一值 |
| 入场价 | `daily_predictions.entry_zone` | 前端展示的建议入场价 |

### 2.2 凯利仓位公式

```python
kelly_fraction = max(0, min(0.3, confidence × 2 - 1 + 0.05))
suggested_amount = total_asset × kelly_fraction
suggested_qty = int(suggested_amount / price / 100) × 100  # 整手
```

### 2.3 自动执行逻辑

```
每日对每只自选股:

if direction == 'bullish' and confidence > 0.5:
    凯利计算仓位 → 自动买入
elif direction == 'bearish' and has_position:
    自动卖出全部持仓
else:
    hold/watch（不操作）

同一天多次运行 → 检测 executed=1 已存在的建议 → 跳过 → 不重复交易
```

### 2.4 数据模型（4张表）

```
paper_account (1行)          paper_positions (N行)
├── cash                     ├── code, qty, avg_cost
├── initial_capital          ├── last_price, market_value
└── updated_at               └── unrealized_pnl

paper_trades (N行)           paper_daily_snapshot (N行)
├── date, code, direction    ├── date, total_asset
├── qty, price, commission   ├── cash, position_value
├── settlement               ├── daily_pnl
└── source, suggestion_id    └── cumulative_return
```

---

## 3. 功能介绍和实现方式

### 3.1 API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v2/paper/account` | 虚拟账户状态 |
| GET | `/api/v2/paper/positions` | 虚拟持仓列表 |
| GET | `/api/v2/paper/trades` | 交易记录（分页） |
| GET | `/api/v2/paper/suggestions` | 每日建议（自动生成+执行） |
| GET | `/api/v2/paper/intraday/{code}` | 盘中分时数据（支持日K线降级） |
| POST | `/api/v2/paper/reset` | 重置账户 |
| GET | `/api/v2/paper/performance` | 表现指标 |

### 3.2 执行触发方式

```
方式A（自动）: scheduler.py sync → sync_all → task_paper_trading()
方式B（API）:  GET /api/v2/paper/suggestions（首次访问自动生成+执行）
```

### 3.3 前端实现

```vue
<!-- PaperTrading.vue 核心结构 -->
<template>
  <!-- 账户概览 -->
  <AccountCard>
    <div>初始资金: ¥100,000</div>
    <div>总资产: ¥{{ totalAsset }}</div>
    <div>现金: ¥{{ cash }}</div>
    <div>累计收益: {{ returnPct }}%</div>
    <Button @click="resetAccount">🔄 重置账户</Button>
  </AccountCard>

  <!-- 今日交易结果 -->
  <section>
    <h3>今日交易（自动执行）</h3>
    <TradeCard v-for="sug in suggestions" :key="sug.code"
               :class="sug.action === 'buy' ? 'buy' : 'sell'">
      <div>✅ 买入 {{ sug.name }} {{ sug.qty }}股 @ ¥{{ sug.price }}</div>
      <div>预测: {{ sug.direction }} | 置信: {{ sug.confidence }}%</div>
    </TradeCard>
  </section>

  <!-- 虚拟持仓 -->
  <DataTable :data="positions" headerClass="paper-header">
    <Column field="code" header="代码" />
    <Column field="qty" header="持仓" />
    <Column field="avg_cost" header="成本" />
    <Column field="last_price" header="现价" />
    <Column field="market_value" header="市值" />
    <Column field="unrealized_pnl" header="浮盈亏" />
  </DataTable>
</template>
```

---

## 4. 用户操作流程

### 4.1 首次使用（需要初始化）

```
用户: 导航栏 "模拟交易" → "纸面交易"
  → 提示: "虚拟账户未初始化"
  → 点击 [初始化账户]
  → POST /api/v2/paper/reset
  → 初始资金 ¥100,000 到位
```

### 4.2 查看今日交易

```
用户: 每日早上打开纸面交易页面

页面显示:
┌───────────────────────────────────────────┐
│  💼 纸面交易              [🔄 重置账户]   │
│                                           │
│  虚拟账户                                  │
│  总资产: ¥108,500  |  现金: ¥82,745       │
│  累计收益: +8.5%                          │
│                                           │
│  今日交易（自动执行）                       │
│  ┌─ ✅ 买入 兴业银行 300股 @17.05 ────┐   │
│  │ 预测 bullish, 置信 65%, 仓位 12%    │   │
│  └────────────────────────────────────┘   │
│  ┌─ ✅ 卖出 招商银行 500股 @39.10 ────┐   │
│  │ 预测 bearish, 置信 58%             │   │
│  │ 实现盈亏: +¥450 (+2.3%)            │   │
│  └────────────────────────────────────┘   │
│                                           │
│  虚拟持仓（橙色表头区分真实持仓）            │
│  ┌──────┬────┬──────┬──────┬────┬──────┐ │
│  │601166│300 │17.05 │17.85 │5211│ +240 │ │
│  └──────┴────┴──────┴──────┴────┴──────┘ │
└───────────────────────────────────────────┘
```

### 4.3 重置账户

```
用户: 点击 [🔄 重置账户] → 确认弹窗
  → POST /api/v2/paper/reset
  → 现金恢复 ¥100,000
  → 清空虚拟持仓（保留历史交易记录）
```
