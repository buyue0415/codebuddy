# 附录 B: API 端点清单

> **基路径**: `http://localhost:8766`
> **响应格式**: 统一 `{ success: true, data: {...} }` / `{ success: false, error: "...", message: "..." }`
> **版本**: v2.0 | **更新日期**: 2026-06-06

---

## 响应格式规范

| HTTP Code | 场景 | 响应体 |
|-----------|------|--------|
| 200 | 成功 | `{ success: true, data: {...} }` |
| 200 | 业务异常 | `{ success: false, error: "...", message: "..." }` |
| 400 | 参数错误/格式错误 | `{ success: false, error: "...", diagnostics: {...} }` |
| 404 | 资源不存在 | FastAPI 默认 404 |
| 409 | 资源冲突 | `{ success: false, error: "..." }` |
| 429 | 并发请求 | `{ success: false, error: "刷新已在运行中" }` |
| 500 | 内部错误 | `{ success: false, error: traceback }` |
| 503 | 前端文件缺失 | 纯文本 "前端构建文件缺失" |

---

## 完整端点列表

### 1. 首页与前端静态资源

| 方法 | 路径 | 参数 | 说明 |
|------|------|------|------|
| GET | `/` | — | 返回 V2 前端构建产物 `index.html` |
| GET | `/index.html` | — | 同上 |
| GET | `/assets/{path}` | path: JS/CSS 资源路径 | V2 前端构建产物静态资源 |
| GET | `/chart.umd.min.js` | — | Chart.js 图表库 |
| GET | `/chartjs-chart-financial.min.js` | — | 金融图表库 |

### 2. 初始化

| 方法 | 路径 | 参数 | 说明 |
|------|------|------|------|
| GET | `/api/v2/init` | — | 返回完整初始化数据（配置+自选股+行情+持仓+K线+预测+新闻+专家报告+准确率+学习参数） |

### 3. 系统

| 方法 | 路径 | 参数 | 说明 |
|------|------|------|------|
| GET | `/api/system-data` | — | 返回系统数据快照（历史遗留） |
| GET | `/api/audit` | — | 运行审计脚本，返回系统状态报告 |
| GET | `/api/v2/config` | — | 返回系统配置（账户/券商/费率/免责声明） |
| GET | `/api/v2/snapshot` | — | 返回完整运行时快照 |
| GET | `/api/search/stocks` | `?keyword=` | 搜索 A 股股票代码/名称 |
| GET | `/dbview` | `?t=表名` | SQLite 数据库查看器（调试用） |

### 4. 自选股 (Watchlist)

| 方法 | 路径 | 参数 | 说明 |
|------|------|------|------|
| GET | `/api/v2/watchlist` | — | 获取自选股列表 |
| POST | `/api/v2/watchlist` | `{ code, name, market }` | 添加自选股（含自动行情刷新） |
| DELETE | `/api/v2/watchlist/{code}` | — | 删除自选股（清理分析层数据，保留交易层） |

### 5. 行情 (Quotes)

| 方法 | 路径 | 参数 | 说明 |
|------|------|------|------|
| GET | `/api/v2/quotes` | — | 批量获取自选股实时行情 |
| GET | `/api/v2/quotes/{code}` | — | 获取单只股票行情 |
| POST | `/api/v2/quotes/refresh` | — | 手动刷新所有自选股行情 |

### 6. 持仓与交易 (Positions & Trades)

| 方法 | 路径 | 参数 | 说明 |
|------|------|------|------|
| GET | `/api/v2/positions` | — | 获取全部持仓（当前+已平仓） |
| GET | `/api/v2/positions/current` | — | 仅当前持仓 |
| GET | `/api/v2/positions/closed` | — | 仅已平仓持仓 |
| GET | `/api/v2/trades` | `?code=` | 获取交易记录（可筛选股票代码） |
| GET | `/api/v2/trades/{code}` | — | 获取单只股票交易记录 |
| GET | `/api/v2/dividends` | — | 获取分红记录 |
| GET | `/api/v2/dividends/{code}` | — | 获取单只股票分红记录 |
| GET | `/api/v2/dividend-yield-series` | — | 获取股息率时间序列 |

### 7. K 线 (Kline)

| 方法 | 路径 | 参数 | 说明 |
|------|------|------|------|
| GET | `/api/v2/kline/daily` | — | 批量获取自选股日K线 |
| GET | `/api/v2/kline/daily/{code}` | — | 获取单只股票日K线 |
| GET | `/api/v2/kline/monthly` | — | 批量获取自选股月K线 |
| GET | `/api/v2/kline/monthly/{code}` | — | 获取单只股票月K线 |

### 8. 预测 (Predictions)

| 方法 | 路径 | 参数 | 说明 |
|------|------|------|------|
| GET | `/api/v2/predictions/daily` | — | 批量获取自选股每日预测 |
| GET | `/api/v2/predictions/daily/{code}` | — | 获取单只股票每日预测 |

### 9. 新闻 (News)

| 方法 | 路径 | 参数 | 说明 |
|------|------|------|------|
| GET | `/api/v2/news` | — | 获取自选股新闻列表 |

### 10. 专家报告 (Expert Reports)

| 方法 | 路径 | 参数 | 说明 |
|------|------|------|------|
| GET | `/api/v2/expert` | — | 获取专家分析报告列表 |
| POST | `/api/v2/expert/import` | `{ company, title, content, analysis }` | 导入新的专家报告 |
| POST | `/api/expert/import` | — | 旧版兼容接口（同 `/api/v2/expert/import`） |

### 11. 学习与准确率 (Learning & Accuracy)

| 方法 | 路径 | 参数 | 说明 |
|------|------|------|------|
| GET | `/api/v2/learning` | — | 获取学习参数（MWU 权重 + Beta 衰减） |
| GET | `/api/v2/accuracy` | — | 批量获取自选股准确率统计 |
| GET | `/api/v2/accuracy/{code}` | — | 获取单只股票准确率统计 |

### 12. 季节性 (Seasonal)

| 方法 | 路径 | 参数 | 说明 |
|------|------|------|------|
| GET | `/api/v2/seasonal` | — | 批量获取自选股季节性数据 |
| GET | `/api/v2/seasonal/{code}` | — | 获取单只股票季节性数据 |

### 13. 触发器 (Triggers)

| 方法 | 路径 | 参数 | 说明 |
|------|------|------|------|
| POST | `/api/trigger/news` | — | 手动触发现新闻抓取 |
| POST | `/api/trigger/predict` | — | 手动触发全量同步（sync_all.py） |
| POST | `/api/trigger/update_statement` | — | 手动触发对账单重新解析 |
| POST | `/api/trigger/expert` | — | 手动触发专家报告导入 |

### 14. 上传 (Upload)

| 方法 | 路径 | 参数 | 说明 |
|------|------|------|------|
| POST | `/api/upload/statement` | `file: UploadFile` | 上传广发证券对账单 Excel（自动解析+写入DB） |

### 15. 回测 (Backtest) — V0.9

| 方法 | 路径 | 参数 | 说明 |
|------|------|------|------|
| POST | `/api/v2/backtest/run` | `{ codes, start_date, end_date }` | 启动回测任务 |
| GET | `/api/v2/backtest/status` | — | 查询回测任务状态 |
| POST | `/api/v2/backtest/stop` | — | 停止运行中的回测任务 |
| GET | `/api/v2/backtest/results/{run_id}` | — | 获取指定回测结果 |
| GET | `/api/v2/backtest/history` | — | 获取历史回测记录 |

### 16. 纸面交易 (Paper Trading) — V0.9

| 方法 | 路径 | 参数 | 说明 |
|------|------|------|------|
| GET | `/api/v2/paper/account` | — | 获取纸面交易账户信息 |
| GET | `/api/v2/paper/positions` | — | 获取纸面交易持仓 |
| GET | `/api/v2/paper/trades` | — | 获取纸面交易记录 |
| GET | `/api/v2/paper/suggestions` | — | 获取每日交易建议 |
| GET | `/api/v2/paper/intraday/{code}` | — | 获取盘中数据 |
| POST | `/api/v2/paper/reset` | — | 重置纸面交易账户 |
| GET | `/api/v2/paper/performance` | — | 获取纸面交易表现指标 |

### 17. 形态规则 (Pattern Rules) — V0.9

| 方法 | 路径 | 参数 | 说明 |
|------|------|------|------|
| GET | `/api/v2/pattern-rules` | — | 获取所有K线形态规则 |
| GET | `/api/v2/pattern-rules/{rule_id}` | — | 获取单条形态规则 |
| POST | `/api/v2/pattern-rules` | `{ name, description, type, code }` | 新增形态规则 |
| PUT | `/api/v2/pattern-rules/{rule_id}` | — | 更新形态规则 |
| DELETE | `/api/v2/pattern-rules/{rule_id}` | — | 删除形态规则 |
| POST | `/api/v2/pattern-rules/init` | — | 初始化33条标准形态规则 |
| GET | `/api/v2/pattern-scan/{code}` | — | 扫描指定股票的K线形态 |

### 18. 数据文件服务

| 方法 | 路径 | 参数 | 说明 |
|------|------|------|------|
| GET | `/data/{path}` | — | 提供 `data/` 目录下的静态文件服务 |
| GET | `/scripts/{path}` | — | 提供 `scripts/` 目录下的非 .py 静态文件 |

---

## 统计

| 维度 | 数量 |
|------|------|
| GET 端点 | ~45 |
| POST 端点 | ~13 |
| DELETE 端点 | 2 |
| PUT 端点 | 1 |
| **合计** | **~61 个端点** |
