# 模块11: 数据注入模块

> **核心文件**: `scripts/reinject_from_db.py` (V0.6 推荐), `scripts/reinject_data.py` (V0.5 遗留)
> **触发**: 对账单更新后自动链式调用

---

## 1. 功能概述

将 SQLite 数据库中的全部数据读取为 JSON 对象，通过正则替换写入 HTML 文件的 `const DATA = {...};` 块中，使前端单页应用可以离线读取所有数据。

> ⚠️ **已知风险**: 使用正则替换 JS 变量，依赖 HTML 文件中存在精确的 `const DATA = {...};` 声明格式。若前端代码重构时改变了该声明方式，注入将静默失败。

---

## 2. 核心业务逻辑

### 2.1 数据映射（`reinject_from_db.py`）

从 `stock.db` 的 17 张表读取所有数据，重组为与前端期望一致的数据结构：

```python
data = {
    "account", "broker", "generated",
    "watchlist":       [...],        # 来自 watchlist 表
    "quotes":          {code: {...}}, # 来自 quotes 表
    "kline_daily":     {code: [...]}, # 来自 kline_daily 表
    "kline":           {code: [...]}, # monthly, 来自 kline_monthly 表
    "seasonal":        {code: [...]}, # 来自 seasonal 表
    "all_trades":      [...],         # 来自 trades 表
    "current_positions": {code: {...}}, # 来自 positions 表 + dividends + trades
    "closed_positions": {code: {...}},  # 来自 closed_positions + trades
    "dividends_<code>": [...],          # 每股票独立key
    "monthly_changes_<code>": [...],    # 每股票独立key
    "daily_predictions": [...],         # 来自 daily_predictions + hourly + signals
    "learning_params":  {code: {...}},  # 来自 learning_params 表
    "accuracy_stats":   {code: {...}},  # 来自 accuracy_stats 表
    "news":            [...],           # 来自 news 表
    "expert_reports":  [...]            # 来自 expert_reports 表
}
```

### 2.2 HTML 注入

```python
# 正则匹配并替换
html = re.sub(
    r'(let|const|var)( DATA = )\{.*?\};\n',
    r'\1\2' + json.dumps(data, ensure_ascii=False, separators=(',', ':')) + ';\n',
    html,
    flags=re.DOTALL
)
```

### 2.3 验证

注入后重新解析 DATA 块确认数据完整性：
```python
m = re.search(r'(let|const|var) DATA = ({.*?});\s*', html, re.DOTALL)
if m:
    vdata = json.loads(m.group(2))
    print(f"HTML re-injected: {len(vdata.keys())} top-level keys")
else:
    print("ERROR: DATA block not found in HTML!")
```

### 2.4 费用计算

交易记录中的 `transfer_fee`、`regulatory_fee`、`handling_fee` 为实时计算：
- 过户费: `max(1.0, round(qty/1000 * 1.0, 2))`
- 规费: `round(qty * price * 0.00002, 2)`
- 经手费: `round(qty * price * 0.0000487, 2)`

> 注意: 此处使用硬编码费率，与 [数据库访问层](./02-database-layer.md) 的 `_calc_fees()` 从 `config.json` 读取不同。

---

## 3. 依赖关系

| 方向 | 模块 |
|------|------|
| **依赖库** | `sqlite3`, `json`, `re`, `os` |
| **输入** | `data/stock.db` (SQLite) |
| **输入** | `deliverables/bank-stock-system.html` |
| **输出** | 修改后的 `deliverables/bank-stock-system.html` |
| **被调用** | [Web API 层](./01-api-server.md) — 对账单上传后链式调用 |

---

## 4. 异常处理机制

| 场景 | 处理 |
|------|------|
| DATA 块未找到 | 打印 `ERROR: DATA block not found in HTML!` |
| JSON 序列化 | `ensure_ascii=False` 确保中文正常显示 |
| HTML 编码 | 以 UTF-8 读写 |
