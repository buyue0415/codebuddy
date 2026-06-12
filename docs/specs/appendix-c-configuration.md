# 附录 C: 系统配置说明

> **配置文件**: `data/config.json`, `server_v2.py` 常量, `signals.py` 常量

---

## config.json

| 配置项 | 值 | 说明 |
|--------|-----|------|
| `account` | `"51312640"` | 广发证券账户号 |
| `broker` | `"广发证券"` | 券商名称 |
| `server_port` | `8765` | 旧版端口（保留在配置文件，实际使用 8766） |
| `fee_rates.transfer_fee_per_1000` | `1.0` | 过户费(元/千股) |
| `fee_rates.regulatory_fee_rate` | `0.00002` | 规费率 |
| `fee_rates.handling_fee_rate` | `0.0000487` | 经手费率 |
| `price_strategy.buy_multiplier` | `0.95` | 买入折扣系数 |
| `price_strategy.sell_multiplier` | `1.10` | 卖出溢价系数 |
| `disclaimer` | 风险提示 | 免责声明文本 |

---

## server_v2.py 运行时常量

| 常量 | 值 | 说明 |
|------|-----|------|
| `PORT` | `8766` | HTTP 服务端口 |
| `PYTHON` | `...Python312\python.exe` | Python 解释器路径 |
| `NODE` | `...node\22.12.0\node.exe` | Node.js 运行环境 |

---

## signals.py 常量

| 常量 | 值 |
|------|-----|
| `SIGNALS` | `['macd','rsi','bollinger','kdj','seasonal','atr','money_flow','adx_trend','obv_divergence','vol_convergence']` |
| `BLOCKS` | `['09:30-10:30', '10:30-11:30', '13:00-14:00', '14:00-15:00', 'next_day']` |

---

## K线获取参数

| 参数 | 值 | 说明 |
|------|-----|------|
| `period` | `day` | 日K线 |
| `limit` | `2000` | 获取条数 |
| `fq` | `qfq` | 前复权 |
