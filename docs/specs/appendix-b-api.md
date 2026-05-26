# 附录B: API 端点清单

> **基路径**: `http://localhost:8765` | **统一响应**: `{success: bool, data?, error?, message?, output?, count?, trace?}`

---

## 响应格式规范

| HTTP Code | 场景 | 响应体 |
|-----------|------|--------|
| 200 | 成功 | `{success: true, data: ...}` |
| 400 | 参数缺失/无效 | `{success: false, error: "..."}` |
| 404 | 资源不存在 | `{success: false, error: "..."}` |
| 409 | 重复添加 | `{success: false, error: "股票 XXX 已存在"}` |
| 429 | 并发冲突 | `{success: false, error: "刷新已在运行中"}` |
| 500 | 服务端异常 | `{success: false, error: "...", trace: "..."}` |

---

## 完整端点列表

### 初始化

| 端点 | 方法 | 参数 | 返回值 |
|------|------|------|--------|
| `/api/v2/init` | GET | — | 全量数据: `{watchlist, quotes, positions {current, closed, all_trades}, kline_daily, daily_predictions, news, expert_reports, kline, seasonal, learning_params, accuracy_stats}` |

### 自选股 (Watchlist)

| 端点 | 方法 | 参数 | 返回值 |
|------|------|------|--------|
| `/api/v2/watchlist` | GET | — | `{data: [{code, name, market}], count}` |
| `/api/v2/watchlist` | POST | `{code, name, market}` | `{message, watchlist, output}` |
| `/api/v2/watchlist/{code}` | DELETE | path: code | `{message}` |
| `/api/watchlist` | GET | — | `{data: [{code, name, market}]}` (JSON文件版) |
| `/api/watchlist/add` | POST | `{code, name, market}` | `{message, watchlist, output}` (旧版) |
| `/api/watchlist/remove` | POST | `{code}` | `{message, watchlist}` (旧版) |

### 行情 (Quotes)

| 端点 | 方法 | 参数 | 返回值 |
|------|------|------|--------|
| `/api/v2/quotes` | GET | — | `{data: {code: {price, change, open, high, low, pe, pb, dy}}}` |
| `/api/v2/quotes/{code}` | GET | path: code | `{data: {price, ...}}` |

### 持仓 (Positions)

| 端点 | 方法 | 参数 | 返回值 |
|------|------|------|--------|
| `/api/v2/positions` | GET | — | `{data: {current_positions, closed_positions, all_trades}}` |
| `/api/v2/positions/current` | GET | — | `{data: {code: {qty, avg_cost, trades, dividends, ...}}, count}` |
| `/api/v2/positions/closed` | GET | — | `{data: {code: {realized_pnl, ...}}, count}` |
| `/api/v2/trades` | GET | `?code=` (可选) | `{data: [{date, time, code, name, type, qty, price, ...}], count}` |
| `/api/v2/trades/{code}` | GET | path: code | 同上，按股票过滤 |
| `/api/v2/dividends` | GET | `?code=` (可选) | `{data: [{date, code, amount, price, per_share}], count}` |
| `/api/v2/dividends/{code}` | GET | path: code | 同上 |

### K线 (K-line)

| 端点 | 方法 | 参数 | 返回值 |
|------|------|------|--------|
| `/api/v2/kline/daily` | GET | `?codes=` (逗号分隔) | `{data: {code: [[date,open,close,high,low]]}}` |
| `/api/v2/kline/daily/{code}` | GET | path: code | `{data: [[date,open,close,high,low]]}` |
| `/api/v2/kline/monthly` | GET | `?codes=` (逗号分隔) | `{data: {code: [[date,open,high,low,close,volume,change_pct]]}}` |
| `/api/v2/kline/monthly/{code}` | GET | path: code | `{data: [[...]]}` |

### 预测 (Predictions)

| 端点 | 方法 | 参数 | 返回值 |
|------|------|------|--------|
| `/api/v2/predictions/daily` | GET | — | `{data: [{date, code, prev_close, next_day{direction, confidence, high, low, advice, entry_zone}, hourly[], signals{}, actual{}}], count}` |
| `/api/v2/predictions/daily/{code}` | GET | path: code | 同上，按股票过滤 |

### 新闻 (News)

| 端点 | 方法 | 参数 | 返回值 |
|------|------|------|--------|
| `/api/v2/news` | GET | `?filter=all` / `major` / `{code}` | `{data: [{date, code, title, summary, source, sentiment, major}]}` |

### 专家报告 (Expert Reports)

| 端点 | 方法 | 参数 | 返回值 |
|------|------|------|--------|
| `/api/v2/expert` | GET | — | `{data: [{date, stocks: {...}}]}` |
| `/api/v2/expert/import` | POST | JSON 报告体 | `{success, message, warnings}` |

### 学习与准确率 (Learning & Accuracy)

| 端点 | 方法 | 参数 | 返回值 |
|------|------|------|--------|
| `/api/v2/learning` | GET | `?code=` (可选) | `{data: {code: {signal_weights, hourly_bias, seasonal_adj, confidence_beta, learning_rate, mw_beta, update_count}}}` |
| `/api/v2/accuracy` | GET | `?code=` (可选) | `{data: {code: {last_20/last_60: {direction{correct,total,rate}, range{...}, hourly{...}}}}}` |

### 季节性 (Seasonal)

| 端点 | 方法 | 参数 | 返回值 |
|------|------|------|--------|
| `/api/v2/seasonal` | GET | — | `{data: {code: [factor×12]}}` |
| `/api/v2/seasonal/{code}` | GET | path: code | `{data: [factor×12]}` |

### 系统配置 (Config)

| 端点 | 方法 | 参数 | 返回值 |
|------|------|------|--------|
| `/api/v2/config` | GET | — | `{data: {account, broker, server_port, fee_rates, price_strategy, advice_templates, disclaimer}}` |

### 搜索 (Search)

| 端点 | 方法 | 参数 | 返回值 |
|------|------|------|--------|
| `/api/search/stocks` | GET | `?q=` 关键词 | `{data: [{code, name, market, py, score}]}` (最多15条) |

### 触发器 (Triggers)

| 端点 | 方法 | 参数 | 返回值 |
|------|------|------|--------|
| `/api/trigger/news` | POST | — | `{success, output, message}` |
| `/api/trigger/predict` | POST | — | `{success, message, output, data?}` |
| `/api/trigger/update_statement` | POST | — | `{success, output, message}` |
| `/api/trigger/expert` | POST | `{code, name}` | `{success, message}` (返回提示，不执行) |

### 上传 (Upload)

| 端点 | 方法 | 参数 | 返回值 |
|------|------|------|--------|
| `/api/upload/statement` | POST | `multipart/form-data` (xlsx) | `{success, message, output}` |

### 审计与工具 (Audit & Tools)

| 端点 | 方法 | 参数 | 返回值 |
|------|------|------|--------|
| `/api/audit` | GET | — | `{success, output}` |
| `/api/system-data` | GET | — | `{success, data: {...}}` (遗留JSON) |
| `/dbview` | GET | `?t=` 表名 | HTML 数据库浏览器 |
