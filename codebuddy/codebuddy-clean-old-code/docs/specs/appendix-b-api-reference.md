# 附录 B: API 端点参考

> **基路径**: `http://localhost:8766` | **响应格式**: `{ success: true, data: {...} }`
> **自动文档**: `http://localhost:8766/docs`（Swagger UI）

---

## 响应格式

| HTTP Code | 场景 | 响应体 |
|-----------|------|--------|
| 200 | 成功 | `{ success: true, data: {...} }` |
| 200 | 业务异常 | `{ success: false, error: "...", message: "..." }` |
| 400 | 参数错误 | `{ success: false, error: "...", diagnostics: {...} }` |
| 404 | 资源不存在 | FastAPI 默认 |
| 429 | 并发冲突 | `{ success: false, error: "刷新已在运行中" }` |
| 503 | 前端缺失 | 纯文本 |

---

## 完整端点清单

### 前端静态资源
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | V2 前端 index.html |
| GET | `/index.html` | 同上 |
| GET | `/assets/{path}` | JS/CSS bundles |
| GET | `/chart.umd.min.js` | Chart.js |
| GET | `/chartjs-chart-financial.min.js` | 金融图表库 |

### 初始化
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v2/init` | 完整初始化数据（15 API 聚合） |
| GET | `/api/system-data` | 系统数据快照（旧版兼容） |

### 系统
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v2/config` | 系统配置 |
| GET | `/api/v2/snapshot` | 运行时快照 |
| GET | `/api/search/stocks?keyword=` | A股搜索 |
| GET | `/api/audit` | 系统审计 |
| GET | `/api/v2/statement/status` | 对账单导入状态 |
| GET | `/dbview?t=表名` | 数据库查看器（调试） |

### 自选股
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v2/watchlist` | 列表 |
| POST | `/api/v2/watchlist` | 添加 |
| DELETE | `/api/v2/watchlist/{code}` | 删除 |

### 行情
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v2/quotes` | 批量行情 |
| GET | `/api/v2/quotes/{code}` | 单股票行情 |
| POST | `/api/v2/quotes/refresh` | 刷新行情 |

### 持仓与交易
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v2/positions` | 完整持仓 |
| GET | `/api/v2/positions/current` | 当前持仓 |
| GET | `/api/v2/positions/closed` | 已清仓 |
| GET | `/api/v2/trades` | 交易记录 (?code=) |
| GET | `/api/v2/trades/{code}` | 单股票交易 |
| GET | `/api/v2/dividends` | 分红记录 |
| GET | `/api/v2/dividends/{code}` | 单股票分红 |
| GET | `/api/v2/dividend-yield-series` | 股息率时间序列 |

### K线
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v2/kline/daily` | 批量日K |
| GET | `/api/v2/kline/daily/{code}` | 单股票日K |
| GET | `/api/v2/kline/monthly` | 批量月K |
| GET | `/api/v2/kline/monthly/{code}` | 单股票月K |

### 预测
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v2/predictions/daily` | 批量预测 |
| GET | `/api/v2/predictions/daily/{code}` | 单股票预测 |

### 新闻
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v2/news` | 全部新闻 |

### 专家报告
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v2/expert` | 报告列表 |
| POST | `/api/v2/expert/import` | 导入报告 |
| POST | `/api/expert/import` | 旧版兼容 |

### 学习与准确率
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v2/learning` | 学习参数 |
| GET | `/api/v2/accuracy` | 批量准确率 |
| GET | `/api/v2/accuracy/{code}` | 单股票准确率 |

### 季节性
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v2/seasonal` | 批量季节因子 |
| GET | `/api/v2/seasonal/{code}` | 单股票季节因子 |

### 触发器
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/trigger/news` | 抓取新闻 |
| POST | `/api/trigger/predict` | 全量同步 |
| POST | `/api/trigger/update_statement` | 重解析对账单 |
| POST | `/api/trigger/expert` | 导入专家报告 |

### 上传
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/upload/statement` | 上传对账单 Excel |

### 回测（V0.9）
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v2/backtest/run` | 启动回测 |
| GET | `/api/v2/backtest/status` | 状态查询 |
| POST | `/api/v2/backtest/stop` | 停止回测 |
| GET | `/api/v2/backtest/results/{run_id}` | 结果查询 |
| GET | `/api/v2/backtest/history` | 历史记录 |

### 纸面交易
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v2/paper/account` | 虚拟账户状态 |
| GET | `/api/v2/paper/positions` | 虚拟持仓列表 |
| GET | `/api/v2/paper/trades` | 交易记录（分页） |
| GET | `/api/v2/paper/suggestions` | 每日建议 |
| GET | `/api/v2/paper/intraday/{code}?date=` | **分时数据**（支持日K线降级，超5日自动降级为4个O/H/L/C点） |
| POST | `/api/v2/paper/reset` | 重置账户 |
| GET | `/api/v2/paper/performance` | 表现指标 |
| GET | `/api/v2/paper/snapshots` | 每日快照 |（V0.9）
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v2/paper/account` | 账户状态 |
| GET | `/api/v2/paper/positions` | 持仓 |
| GET | `/api/v2/paper/trades` | 交易记录 |
| GET | `/api/v2/paper/suggestions` | 每日建议 |
| GET | `/api/v2/paper/intraday/{code}` | 盘中数据 |
| POST | `/api/v2/paper/reset` | 重置账户 |
| GET | `/api/v2/paper/performance` | 表现指标 |

### 形态规则（V0.9）
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v2/pattern-rules` | 所有规则 |
| GET | `/api/v2/pattern-rules/{rule_id}` | 单条规则 |
| POST | `/api/v2/pattern-rules` | 新增规则 |
| PUT | `/api/v2/pattern-rules/{rule_id}` | 更新规则 |
| DELETE | `/api/v2/pattern-rules/{rule_id}` | 删除规则 |
| POST | `/api/v2/pattern-rules/init` | 初始化33条标准规则 |
| GET | `/api/v2/pattern-scan/{code}` | 扫描形态 |

### 静态文件
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/data/{path}` | data/ 目录文件 |
| GET | `/scripts/{path}` | scripts/ 非.py文件 |

---

## 统计

| 维度 | 数量 |
|------|------|
| GET | ~52 |
| POST | ~15 |
| DELETE | 3 |
| PUT | 2 |
| **合计** | **~72 个端点** |
