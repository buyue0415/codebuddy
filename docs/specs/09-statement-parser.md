# 模块9: 券商对账单解析模块

> **核心文件**: `scripts/parse_statement.py` (原始版), `scripts/update_from_statement.py` (生产版)
> **触发**: `POST /api/upload/statement` | **券商**: 广发证券

---

## 1. 功能概述

解析广发证券 "普通对账单结果查询" Excel 文件，提取交易记录，计算当前持仓、已清仓、分红数据和累计手续费，输出标准化的 `broker_statement.json` 并同步更新 `system_data.json`。

---

## 2. 核心业务逻辑

### 2.1 Excel 列映射

```
date, time, seq, account, code, name, type, qty, price,
commission, stamp_tax, transfer_fee, regulatory_fee, handling_fee,
other_fee, settlement, currency, order_id, accrued_interest
```

### 2.2 持仓计算规则

| 交易类型 | 计算逻辑 |
|---------|---------|
| **证券买入** | `qty += abs(qty)`, `total_cost += abs(qty) * price + commission + stamp_tax + 其他费用` |
| **证券卖出** | 按均价法核算成本: `avg_cost = total_cost / old_qty`, `realized_pnl = 卖出金额 - 费用 - avg_cost * sell_qty` |
| **股息入账** | 追加到 `dividends` 列表；**不调整成本基数** |
| **已清仓** | `qty == 0` 且非 IPO 申购代码 (736435) |

### 2.3 费用汇总

| 费用项 | 来源 |
|--------|------|
| `total_commission` | 佣金合计 |
| `total_stamp_tax` | 印花税合计 |
| `total_other_fees` | 过户费 + 规费 + 经手费 |

### 2.4 文件版本关系

| 文件 | 输入路径 | 特点 |
|------|---------|------|
| `parse_statement.py` | `C:\Users\28312\Desktop\...` | 原始版本，固定路径 |
| `update_from_statement.py` | 项目根目录 | 生产版本，自动备份 (.bak)，同步更新 system_data.json |

---

## 3. 输入输出参数定义

### 输入
```
广发易淘金PC版-普通对账单结果查询.xlsx  (项目根目录)
```

### 输出 (`broker_statement.json`)
```json
{
  "account": "51312640",
  "broker": "广发证券",
  "current_positions": {
    "<code>": {
      "code": "601166",
      "name": "兴业银行",
      "qty": 1000,
      "total_cost": 17350.00,
      "avg_cost": 17.350,
      "realized_pnl": 0.00,
      "dividends": [{"date": "2025-06-15", "amount": 936.00, "price": 17.37}],
      "total_commission": 15.50,
      "total_stamp_tax": 17.35,
      "total_other_fees": 3.80,
      "trades": [{...}]
    }
  },
  "closed_positions": {
    "<code>": {
      "code": "600036",
      "name": "招商银行",
      "realized_pnl": 520.00,
      "dividends_total": 300.00,
      "total_commission": 25.00,
      "total_stamp_tax": 30.00,
      "total_other_fees": 5.00,
      "trades": [{...}]
    }
  },
  "all_trades": [
    {"date": "2026-05-20", "time": "09:35:12", "code": "601166", "name": "兴业银行",
     "type": "证券买入", "qty": 500, "price": 17.30, "commission": 7.50,
     "stamp_tax": 0, "settlement": -8657.50}
  ]
}
```

---

## 4. 依赖关系

| 方向 | 模块 |
|------|------|
| **外部依赖** | `pandas`, `openpyxl`, `shutil` |
| **输入** | 广发对账单 Excel（手动下载） |
| **输出** | `data/broker_statement.json` |
| **同步更新** | `data/system_data.json`（update_from_statement.py 版本） |
| **被调用** | [Web API 层](./01-api-server.md) `POST /api/upload/statement` |

---

## 5. 异常处理机制

| 场景 | 处理 |
|------|------|
| 卖出时当前持仓为 0 | 跳过成本核算（先卖后买场景） |
| IPO 申购代码 736435 | 过滤 |
| 文件覆盖 | 操作前创建 `.bak` 备份 |
| 除权除息标记 XD | `name.replace('XD', '')` 清理名称 |
