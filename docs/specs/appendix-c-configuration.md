# 附录 C — 系统配置

> **配置文件**: `data/config.json` (888B) | **API**: GET /api/v2/config

---

## 1. 配置文件结构

```json
{
  "account": "",
  "broker": "",
  "server_port": 8766,
  "fee_rates": {
    "transfer_fee_per_1000": 1.0,
    "regulatory_fee_rate": 0.00002,
    "handling_fee_rate": 0.0000487
  },
  "price_strategy": {
    "buy_multiplier": 0.95,
    "sell_multiplier": 1.10
  },
  "advice_templates": {
    "bearish_seasonal": "当前进入季节性弱势区间，建议控制仓位观望",
    "bullish": "技术信号积极，预测方向看涨，可考虑加仓",
    "neutral": "信号不明确，建议维持当前仓位等待确认"
  },
  "disclaimer": "免责声明：以上数据来源于广发证券对账单及NeoData金融数据服务，仅供参考，不构成投资建议。"
}
```

---

## 2. 字段说明

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| account | string | "" | 券商账户号（前端展示） |
| broker | string | "" | 券商名称（前端展示） |
| server_port | int | 8766 | API服务器端口 |
| fee_rates.transfer_fee_per_1000 | number | 1.0 | 过户费（每千股） |
| fee_rates.regulatory_fee_rate | number | 0.00002 | 证管费率0.002% |
| fee_rates.handling_fee_rate | number | 0.0000487 | 经手费率0.00487% |
| price_strategy.buy_multiplier | number | 0.95 | 加仓价 = 预测价 × 0.95 |
| price_strategy.sell_multiplier | number | 1.10 | 减仓价 = 预测价 × 1.10 |
| advice_templates | object | - | 操作建议模板 |
| disclaimer | string | - | 免责声明底部文案 |

---

## 3. 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| NODE_PATH | Westock离线数据路径 | - |
| WESTOCK_PATH | Westock可执行文件路径 | - |
| NEODATA_PATH | NeoData API路径 | - |
| API_PORT | 服务端口 | 8766 |

---

## 4. 运营配置（data/watchlist.json）

```json
["601166", "600036", "601398"]
```

自选股列表，初始包含：兴业银行、招商银行、工商银行。

---

## 5. 数据源配置（scripts/fetchers/）

回退链：WestockFetcher → NeoDataFetcher → EastMoneyFetcher → SinaFetcher → TencentFetcher

各获取器可通过环境变量独立开关。
