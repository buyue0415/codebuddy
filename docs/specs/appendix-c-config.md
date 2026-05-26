# 附录C: 系统配置项

> **配置文件**: `data/config.json`, `server.py` 常量, `sync_all.py` 常量

---

## config.json

| 配置项 | 值 | 说明 |
|--------|-----|------|
| `account` | `"51312640"` | 广发证券账户号 |
| `broker` | `"广发证券"` | 券商名称 |
| `server_port` | `8765` | HTTP 服务端口 |
| `fee_rates.transfer_fee_per_1000` | `1.0` | 过户费 (元/千股) |
| `fee_rates.regulatory_fee_rate` | `0.00002` | 规费率 |
| `fee_rates.handling_fee_rate` | `0.0000487` | 经手费率 |
| `price_strategy.buy_multiplier` | `0.95` | 买入折扣系数 |
| `price_strategy.sell_multiplier` | `1.10` | 卖出溢价系数 |
| `advice_templates.bearish_seasonal` | `"短期看跌 + 当前月季节性偏弱 → 等待下月加仓窗口"` | 看跌建议模板 |
| `advice_templates.bullish` | `"短期看涨 → 耐心持有，选择最佳月份高位兑现"` | 看涨建议模板 |
| `advice_templates.neutral` | `"信号中性 → 股息率{dividend_yield}%提供安全垫，持有收息为主"` | 中性建议模板 |
| `disclaimer` | 风险提示文本 | 免责声明 |

---

## 运行时常量 (server.py)

| 常量 | 值 | 说明 |
|------|-----|------|
| `PORT` | `8765` | HTTP 服务端口 |
| `ROOT` | 自动计算 | 项目根目录 |
| `PYTHON` | `C:\Users\28312\.workbuddy\binaries\python\versions\3.14.3\python.exe` | Python 解释器路径 |
| `NODE` | `C:\Users\28312\.workbuddy\binaries\node\versions\22.12.0\node.exe` | Node.js 运行时路径 |

---

## 运行时常量 (sync_all.py)

| 常量 | 值 | 说明 |
|------|-----|------|
| `NODE` | `C:\Users\28312\.workbuddy\binaries\node\versions\22.12.0\node.exe` | Node.js 路径 |
| `WESTOCK` | `C:\Users\28312\.workbuddy\plugins\...\westock-data` | westock-data 插件目录 |
| `SCRIPT` | `scripts/index.js` | 相对 WESTOCK 的 CLI 入口 |
| `TODAY` | `datetime.now().strftime("%Y-%m-%d")` | 程序运行当日 |
| `SIGNALS` | `['macd','rsi','bollinger','kdj','seasonal','atr','money_flow']` | 7 项信号名称 |
| `BLOCKS` | `['09:30-10:30','10:30-11:30','13:00-14:00','14:00-15:00','next_day']` | 5 个预测时段 |

---

## 运行时常量 (scheduler.py)

| 常量 | 值 | 说明 |
|------|-----|------|
| `PYTHON` | `...\python\versions\3.13.12\python.exe` | Python 路径 (与 server.py 版本不同) |

> ⚠️ **版本不一致**: `scheduler.py` 使用 Python 3.13.12，`server.py` 使用 3.14.3。需统一。

---

## K线获取参数

| 参数 | 值 | 说明 |
|------|-----|------|
| `period` | `day` | 日K线 |
| `limit` | `200` | 获取条数 |
| `fq` | `qfq` | 前复权 |
