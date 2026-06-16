# 附录 B — API 参考

> **关联规范**: [01-system-architecture.md](01-system-architecture.md)
> **基础路径**: `http://127.0.0.1:8766` | **响应格式**: JSON `{"success": bool, "data": ..., "error": "..."}`

---

## 1. 响应格式

```json
// 成功
{ "success": true, "data": { ... }, "timestamp": "2026-06-16 17:10:00" }

// 失败
{ "success": false, "error": "错误描述" }

// 任务进行中
{ "success": false, "error": "sync already in progress", "progress": 50 }
```

---

## 2. 全局参数

| 参数 | 位置 | 说明 |
|------|------|------|
| code | Path/Query | 6位股票代码 |
| date | Query | YYYY-MM-DD格式日期 |

---

## 3. API端点完整列表

### 3.1 初始化/系统（4个）

| # | 方法 | 路径 | 说明 |
|---|------|------|------|
| 1 | GET | /api/v2/init | 全量初始化数据（15+数据集） |
| 2 | GET | /api/system-data | 遗留系统数据 |
| 3 | GET | /api/audit | 审计日志 |
| 4 | GET | /api/v2/snapshot | 系统快照 |

### 3.2 配置（1个）

| # | 方法 | 路径 | 说明 |
|---|------|------|------|
| 5 | GET | /api/v2/config | 系统配置（费率/价格策略/模板） |

### 3.3 自选股（3个）

| # | 方法 | 路径 | 说明 |
|---|------|------|------|
| 6 | GET | /api/v2/watchlist | 获取自选股列表 `[{code, name, market}]` |
| 7 | POST | /api/v2/watchlist | 添加自选股 `{code, name, market}` |
| 8 | DELETE | /api/v2/watchlist/{code} | 删除自选股 |

### 3.4 行情（2个）

| # | 方法 | 路径 | 说明 |
|---|------|------|------|
| 9 | GET | /api/v2/quotes | 行情快照 `{code: {price, pe, pb, dy, ...}}` |
| 10 | POST | /api/v2/quotes/refresh | 刷新行情（触发数据源采集） |

### 3.5 K线（4个）

| # | 方法 | 路径 | 说明 |
|---|------|------|------|
| 11 | GET | /api/v2/kline/daily | 全部日K线 `{code: [[date,o,h,l,c,v,a,cp], ...]}` |
| 12 | GET | /api/v2/kline/daily/{code} | 单只日K线 |
| 13 | GET | /api/v2/kline/monthly | 全部月K线 |
| 14 | GET | /api/v2/kline/monthly/{code} | 单只月K线 |

### 3.6 持仓/交易（5个）

| # | 方法 | 路径 | 说明 |
|---|------|------|------|
| 15 | GET | /api/v2/positions | 全部持仓（当前+已清仓） |
| 16 | GET | /api/v2/positions/current | 当前持仓 |
| 17 | GET | /api/v2/positions/closed | 已清仓持仓 |
| 18 | GET | /api/v2/trades | 交易流水 |
| 19 | GET | /api/v2/dividends | 分红记录 |

### 3.7 预测（4个）

| # | 方法 | 路径 | 说明 |
|---|------|------|------|
| 20 | GET | /api/v2/predictions/daily | 日预测数据 |
| 21 | GET | /api/v2/learning | 学习参数（含prediction_signals） |
| 22 | GET | /api/v2/accuracy | 准确率统计 |
| 23 | GET | /api/v2/seasonal | 季节性数据 |

### 3.8 新闻（1个）

| # | 方法 | 路径 | 说明 |
|---|------|------|------|
| 24 | GET | /api/v2/news | 新闻列表 |

### 3.9 专家报告（2个）

| # | 方法 | 路径 | 说明 |
|---|------|------|------|
| 25 | GET | /api/v2/expert | 专家报告列表 |
| 26 | POST | /api/v2/expert/import | 导入专家报告（multipart） |

### 3.10 形态规则（5个）

| # | 方法 | 路径 | 说明 |
|---|------|------|------|
| 27 | GET | /api/v2/pattern-rules | 规则列表 |
| 28 | POST | /api/v2/pattern-rules | 创建规则 |
| 29 | PUT | /api/v2/pattern-rules/{id} | 更新规则 |
| 30 | DELETE | /api/v2/pattern-rules/{id} | 删除规则 |
| 31 | GET | /api/v2/pattern-rules/scan | K线形态扫描 |

### 3.11 公司关系（3个）

| # | 方法 | 路径 | 说明 |
|---|------|------|------|
| 32 | GET | /api/v2/company-relations | 公司关系列表 |
| 33 | GET | /api/v2/graph-data | 图谱渲染数据（nodes+edges） |
| 34 | GET | /api/v2/relation-types | 关系类型列表 |

### 3.12 行业股票（2个）

| # | 方法 | 路径 | 说明 |
|---|------|------|------|
| 35 | GET | /api/v2/industries | 行业列表（含股票） |
| 36 | GET | /api/v2/industries-stocks | 行业股票列表 |

### 3.13 触发器（2个）

| # | 方法 | 路径 | 说明 |
|---|------|------|------|
| 37 | POST | /api/trigger/predict | 全量同步+预测（subprocess） |
| 38 | POST | /api/trigger/news | 新闻采集（subprocess） |

### 3.14 上传/搜索（2个）

| # | 方法 | 路径 | 说明 |
|---|------|------|------|
| 39 | POST | /api/upload/statement | 上传对账单（multipart） |
| 40 | GET | /api/search/stocks | 股票搜索 ?q=xxx |

### 3.15 回测（5个）

| # | 方法 | 路径 | 说明 |
|---|------|------|------|
| 41 | POST | /api/v2/backtest/run | 启动回测 |
| 42 | GET | /api/v2/backtest/status | 回测状态 |
| 43 | POST | /api/v2/backtest/stop | 停止回测 |
| 44 | GET | /api/v2/backtest/results/{run_id} | 回测结果 |
| 45 | GET | /api/v2/backtest/history | 回测历史 |

### 3.16 纸面交易（13个）

| # | 方法 | 路径 | 说明 |
|---|------|------|------|
| 46 | GET | /api/v2/paper/account | 账户信息 |
| 47 | GET | /api/v2/paper/positions | 持仓列表 |
| 48 | GET | /api/v2/paper/suggestions | 交易建议 |
| 49 | GET | /api/v2/paper/trades | 交易记录 |
| 50 | GET | /api/v2/paper/performance | 表现统计 |
| 51 | POST | /api/v2/paper/execute | 执行交易 |
| 52 | POST | /api/v2/paper/generate | 生成建议 |
| 53 | POST | /api/v2/paper/reset | 重置账户 |
| 54 | GET | /api/v2/paper/auto-status | 自动执行状态 |
| 55 | GET | /api/v2/paper/suggestions-history | 建议历史 |
| 56 | GET | /api/v2/paper/verify | 数据验证 |
| 57 | POST | /api/v2/paper/intraday/collect | 日内数据采集 |
| 58 | GET | /api/v2/paper/intraday/{code} | 日内分时数据 |

### 3.17 NeoData（2个）

| # | 方法 | 路径 | 说明 |
|---|------|------|------|
| 59 | GET | /api/v2/neodata/info | NeoData账户信息 |
| 60 | GET | /api/v2/neodata/quota | NeoData额度信息 |
