# 附录 A: 数据库 Schema

> **数据库**: `data/stock.db` | **模式**: WAL | **表数**: 24

---

## 分析层（9 表）

### 1. stocks — A股全量列表
| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| code | TEXT | PK | 6位股票代码 |
| name | TEXT | NOT NULL | 股票名称 |
| market | TEXT | | sh/sz |
| py | TEXT | | 拼音首字母 |
| watchlist | INTEGER | DEFAULT 0 | 是否自选 |

### 2. watchlist — 自选股
| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| code | TEXT | PK | 6位代码 |
| name | TEXT | | |
| market | TEXT | | |
| sort_order | INTEGER | | 排序序号 |

### 3. kline_daily — 日K线
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK AUTO | |
| code | TEXT NOT NULL | |
| date | TEXT NOT NULL | YYYY-MM-DD |
| open/close/high/low | REAL | 前复权价格 |
| **索引** | `idx_kd_code_date (code, date)` | |

### 4. kline_monthly — 月K线
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK AUTO | |
| code | TEXT NOT NULL | |
| date | TEXT NOT NULL | YYYY-MM-01 |
| open/high/low/close | REAL | |
| volume | REAL | 成交量（日条数） |
| change_pct | REAL | 月度涨跌幅% |

### 5. daily_predictions — 每日预测
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK AUTO | |
| code | TEXT NOT NULL | |
| date | TEXT NOT NULL | |
| prev_close | REAL | 前收盘价 |
| direction | TEXT | bullish/bearish/neutral |
| confidence | REAL | 置信度 0-1 |
| high/low | REAL | 预测区间 |
| advice | TEXT | 操作建议 |
| entry_zone | REAL | 建议入场价 |
| actual_open/high/low/close | REAL | 回填字段 |
| dir_hit | INTEGER | 方向命中 1/0/NULL |
| range_hit | INTEGER | 区间命中 1/0/NULL |

### 6. prediction_hourly — 分时预测
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK AUTO | |
| pred_id | INTEGER FK→daily_predictions.id | |
| block | TEXT | 时段标识 |
| pred_open/high/low/close | REAL | |
| direction | TEXT | |
| strength | INTEGER | 1-5 |
| note | TEXT | |
| hit | INTEGER | 1/0/NULL |

### 7. prediction_signals — 技术信号快照
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK AUTO | |
| pred_id | INTEGER FK→daily_predictions.id | |
| name | TEXT | 信号名（macd/rsi/...） |
| value | TEXT | 显示值 |
| direction | TEXT | |
| raw_value | REAL | |
| extra | TEXT | |

### 8. learning_params — 学习参数
| 字段 | 类型 | 说明 |
|------|------|------|
| code | TEXT PK | |
| signal_weights | TEXT (JSON) | 10×5 权重矩阵 |
| hourly_bias | TEXT (JSON) | 5时段偏置 |
| seasonal_adj | TEXT (JSON) | 12月调整 |
| confidence_beta | TEXT (JSON) | Alpha/Beta计数 |
| learning_rate | REAL | |
| mw_beta | REAL | MWU衰减参数 |
| update_count | INTEGER | |
| backtest_weights | TEXT (JSON) | **V0.9新增**: 回测冷启动权重 |
| regime_weights | TEXT (JSON) | **V0.9新增**: 市场状态权重 |
| backtest_timestamp | TEXT | **V0.9新增**: 回测时间戳 |

### 9. accuracy_stats — 准确率统计
| 字段 | 类型 |
|------|------|
| code | TEXT PK (code, period) |
| period | TEXT PK |
| dir_correct / dir_total / dir_rate | INTEGER/REAL |
| range_correct / range_total / range_rate | INTEGER/REAL |
| hourly_stats | TEXT (JSON) |

---

## 行情层（2 表）

### 10. quotes — 行情报价
| 字段 | 类型 |
|------|------|
| code | TEXT PK |
| price/change/open/high/low | REAL |
| pe/pb/dy | REAL |

### 11. news — 新闻
| 字段 | 类型 |
|------|------|
| id | INTEGER PK AUTO |
| date/code/title/summary/source | TEXT |
| sentiment | TEXT (positive/negative/neutral) |
| major | INTEGER DEFAULT 0 |

---

## 交易层（6 表）

### 12-15: positions / closed_positions / trades / dividends
（标准交易数据结构，含佣金/印花税/过户费字段）

### 16. expert_reports — 专家报告
| 字段 | 类型 |
|------|------|
| id | INTEGER PK AUTO |
| date | TEXT |
| report_data | TEXT (JSON) |

---

## 模拟交易层（6 表）

### 17-22: paper_account / paper_positions / paper_trades / paper_daily_snapshot / paper_suggestions / intraday_quotes

| 表 | 关键字段 |
|------|---------|
| paper_account | cash, initial_capital, created_at, updated_at |
| paper_positions | code, qty, avg_cost, last_price, market_value, unrealized_pnl |
| paper_trades | date, code, direction(buy/sell), qty, price, commission, stamp_tax, settlement, source |
| paper_daily_snapshot | date, total_asset, cash, position_value, daily_pnl, cumulative_return |
| paper_suggestions | date, code, action, qty, price, confidence, reason, executed |
| **intraday_quotes** | code, timestamp(UNIQUE), price, change_pct, volume, **is_kline_fallback** |

**intraday_quotes 字段详情**：

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK AUTO | |
| code | TEXT | NOT NULL, FK→stocks | 6位股票代码 |
| timestamp | TEXT | NOT NULL, UNIQUE(code,ts) | 时间戳 'YYYY-MM-DD HH:MM:SS' |
| price | REAL | NOT NULL | 当前成交价 |
| change_pct | REAL | DEFAULT 0 | 涨跌幅% |
| volume | INTEGER | DEFAULT 0 | 成交量 |

**数据来源说明**：
- **实时采集**（242点/日）：`collect_intraday.py once` 调用 `westock-data minute`，数据源仅保留最近约5个交易日
- **日K线降级**（4点/日）：`db_helper._get_kline_intraday_fallback()` 从 `kline_daily` 生成 O/H/L/C 四点，
  标记 `is_kline_fallback: true`，对 API 层透明

---

## 形态层（1 表）

### 22. pattern_rules — 形态规则
| 字段 | 类型 |
|------|------|
| id | INTEGER PK AUTO |
| name | TEXT |
| description | TEXT |
| type | TEXT (reversal/continuation) |
| code | TEXT (Python检测代码) |

---

## 回测层（1 表）

### 23. backtest_runs — 回测记录
| 字段 | 类型 |
|------|------|
| id | INTEGER PK AUTO |
| started_at / finished_at | TEXT |
| status | TEXT (running/done/error) |
| train_window / test_window / total_stocks | INTEGER |
| summary_json / error_msg | TEXT |
