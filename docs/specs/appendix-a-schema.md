# 附录A: 数据库 Schema

> **数据库**: `data/stock.db` | **模式**: WAL | **外键**: ON

---

## 表清单（17 张）

### 1. stocks — A 股全量列表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| code | TEXT | PRIMARY KEY | 6 位股票代码 |
| name | TEXT | NOT NULL | 股票名称 |
| market | TEXT | | `sh` / `sz` |
| py | TEXT | | 拼音首字母 |
| watchlist | INTEGER | DEFAULT 0 | 是否在自选股中 |

**索引**: `idx_stocks_py`, `idx_stocks_name`

---

### 2. watchlist — 自选股

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| code | TEXT | PRIMARY KEY | 6 位股票代码 |
| name | TEXT | | |
| market | TEXT | | |
| sort_order | INTEGER | | 排序序号 |

---

### 3. kline_daily — 日K线

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | |
| code | TEXT | NOT NULL | 6 位股票代码 |
| date | TEXT | NOT NULL | `YYYY-MM-DD` |
| open | REAL | | 开盘价 |
| close | REAL | | 收盘价 |
| high | REAL | | 最高价 |
| low | REAL | | 最低价 |

**索引**: `idx_kd_code_date (code, date)`

---

### 4. kline_monthly — 月K线

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | |
| code | TEXT | NOT NULL | |
| date | TEXT | NOT NULL | `YYYY-MM-01` |
| open | REAL | | |
| high | REAL | | |
| low | REAL | | |
| close | REAL | | |
| volume | REAL | | 成交量（日条数） |
| change_pct | REAL | | 月度涨跌幅 % |

**索引**: `idx_km_code_date (code, date)`

---

### 5. quotes — 行情报价

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| code | TEXT | PRIMARY KEY | |
| price | REAL | | 最新价 |
| change | REAL | | 涨跌幅 % |
| open | REAL | | 今日开盘 |
| high | REAL | | 今日最高 |
| low | REAL | | 今日最低 |
| pe | REAL | | 市盈率 |
| pb | REAL | | 市净率 |
| dy | REAL | | 股息率 % |

---

### 6. daily_predictions — 每日预测

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | |
| code | TEXT | NOT NULL | |
| date | TEXT | NOT NULL | |
| prev_close | REAL | | 前收盘价 |
| direction | TEXT | | bullish/bearish/neutral |
| confidence | REAL | | 置信度 0-1 |
| high | REAL | | 预测最高价 |
| low | REAL | | 预测最低价 |
| advice | TEXT | | 操作建议 |
| entry_zone | REAL | | 建议入场价位 |
| actual_open | REAL | | 实际开盘 (回填) |
| actual_high | REAL | | 实际最高 (回填) |
| actual_low | REAL | | 实际最低 (回填) |
| actual_close | REAL | | 实际收盘 (回填) |
| dir_hit | INTEGER | | 方向命中 1/0/NULL |
| range_hit | INTEGER | | 区间命中 1/0/NULL |

**索引**: `idx_dp_code_date (code, date)`

---

### 7. prediction_hourly — 分时预测

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | |
| pred_id | INTEGER | NOT NULL FK → daily_predictions.id | |
| block | TEXT | | 时段标识 |
| pred_open | REAL | | 预测开盘 |
| pred_high | REAL | | 预测最高 |
| pred_low | REAL | | 预测最低 |
| pred_close | REAL | | 预测收盘 |
| direction | TEXT | | |
| strength | INTEGER | | 强度 1-5 |
| note | TEXT | | 备注 |
| hit | INTEGER | | 命中 1/0/NULL |

**索引**: `idx_ph_pred (pred_id)`

---

### 8. prediction_signals — 技术信号快照

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | |
| pred_id | INTEGER | NOT NULL FK → daily_predictions.id | |
| name | TEXT | | 信号名称 |
| value | TEXT | | 信号显示值 |
| direction | TEXT | | |
| raw_value | REAL | | 信号原始值 |
| extra | TEXT | | 额外信息 |

---

### 9. learning_params — 学习参数

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| code | TEXT | PRIMARY KEY | |
| signal_weights | TEXT | JSON | 7×5 权重矩阵 |
| hourly_bias | TEXT | JSON | 5 个时段偏置 |
| seasonal_adj | TEXT | JSON | 12 个月调整因子 |
| confidence_beta | TEXT | JSON | Alpha/Beta 计数 |
| learning_rate | REAL | | 学习率 |
| mw_beta | REAL | | MWU 衰减参数 |
| update_count | INTEGER | | 累计更新次数 |

---

### 10. accuracy_stats — 准确率统计

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| code | TEXT | PRIMARY KEY (code, period) | |
| period | TEXT | PRIMARY KEY | last_20 / last_60 |
| dir_correct | INTEGER | | 方向正确次数 |
| dir_total | INTEGER | | 方向总次数 |
| dir_rate | REAL | | 方向命中率 % |
| range_correct | INTEGER | | 区间正确次数 |
| range_total | INTEGER | | 区间总次数 |
| range_rate | REAL | | 区间命中率 % |
| hourly_stats | TEXT | JSON | 分时统计 |

---

### 11. trades — 交易记录

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | |
| date | TEXT | | `YYYY-MM-DD` |
| time | TEXT | | `HH:MM:SS` |
| code | TEXT | | |
| name | TEXT | | |
| type | TEXT | | 证券买入/卖出/股息入账 |
| qty | INTEGER | | 数量（买入为正） |
| price | REAL | | 成交价 |
| commission | REAL | | 佣金 |
| stamp_tax | REAL | | 印花税 |
| settlement | REAL | | 发生金额 |

**索引**: `idx_trades_code (code)`, `idx_trades_date (date)`

---

### 12. positions — 当前持仓

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| code | TEXT | PRIMARY KEY | |
| name | TEXT | | |
| qty | INTEGER | | 持仓数量 |
| total_cost | REAL | | 总投入成本 |
| avg_cost | REAL | | 平均成本价 |
| realized_pnl | REAL | | 已实现盈亏 |

---

### 13. closed_positions — 已清仓

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| code | TEXT | PRIMARY KEY | |
| name | TEXT | | |
| realized_pnl | REAL | | 实现盈亏 |
| dividends_total | REAL | | 分红合计 |
| total_commission | REAL | | 佣金合计 |
| total_stamp_tax | REAL | | 印花税合计 |
| total_other_fees | REAL | | 其他费用合计 |

---

### 14. dividends — 分红记录

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | |
| code | TEXT | | |
| date | TEXT | | |
| amount | REAL | | 分红金额 |
| price | REAL | | 登记日股价 |

**索引**: `idx_div_code (code)`

---

### 15. news — 新闻

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | |
| date | TEXT | | |
| code | TEXT | | |
| title | TEXT | | |
| summary | TEXT | | |
| source | TEXT | | 来源 |
| sentiment | TEXT | | positive/negative/neutral |
| major | INTEGER | DEFAULT 0 | 是否重大新闻 |

**索引**: `idx_news_date (date)`

---

### 16. expert_reports — 专家报告

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | |
| date | TEXT | | |
| report_data | TEXT | JSON | 完整报告 JSON |

---

### 17. seasonal — 季节因子

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| code | TEXT | PRIMARY KEY | |
| factors | TEXT | JSON | `[factor1, factor2, ..., factor12]` |
