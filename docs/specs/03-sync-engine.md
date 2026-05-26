# 模块3: 全模块同步引擎

> **核心文件**: `scripts/sync_all.py` | **超时**: 180s | **触发**: `POST /api/trigger/predict`

---

## 1. 功能概述

系统最核心的业务流程编排器，对自选股列表中的所有股票执行完整的数据刷新链路。包含 K 线获取、技术指标计算、预测生成、预测回填验证、准确率重算等全流程。

---

## 2. 核心业务逻辑

### 2.1 执行流程（8步）

```
Step 1: 从 SQLite 读取 watchlist
Step 2: 新闻抓取（调用 fetch_news.py 的 fetch_news_node + _parse_news_table，写入 news 表）
Step 3: 并行日K线获取（ThreadPoolExecutor, max_workers=min(len(watchlist), 4)）
Step 4: 预测回填——从K线数据验证历史预测，写入 actual_* 字段
Step 5: 准确率重算——基于回填后数据计算 last_20/last_60 准确率
Step 6: 生成当日预测（清旧→计算信号→生成预测→写 DB）
Step 7: 季节性+月K线补充（仅新股票生成月K线）+ 行情报价更新
Step 8: 写遗留 system_data.json（兼容旧版 API）
```

> **修复说明**: 原 SPECS v1.0 使用 Step 0/0.5/1/1.5/1.6/2/2.5/3 编号，v2.0 统一为连续编号 1-8。

### 2.2 并行日K线获取（Step 3）

- 使用 `concurrent.futures.ThreadPoolExecutor`，最多 4 并发
- 每个股票通过 Node.js 子进程调用 `westock-data` 插件获取日K线
- 命令: `node scripts/index.js kline {market_code} --period day --limit 200 --fq qfq`
- 编码处理: 先尝试 gbk 解码，fallback utf-8（Windows 兼容）
- 结果通过 `upsert_kline_daily()` 写入 **kline_daily** 表

```python
def sync_one_stock(stock: dict) -> tuple:
    """单股票K线获取+持久化，返回 (code, bars)"""
    kdata = fetch_kline(f'{mkt}{code}')     # subprocess → NeoData
    if kdata:
        bars = [[date, open, close, high, low] for ...]
        upsert_kline_daily(code, bars)       # 写入 SQLite
    return code, bars
```

### 2.3 预测回填（Step 4）

- 查找所有 `dir_hit IS NULL` 的历史预测
- 用同日期K线的 open/high/low/close 验证：
  - **方向命中**: 预测 bullish/bearish 与 `actual_close vs prev_close` 方向一致
  - **区间命中**: 实际 high ≤ 预测 high 且 实际 low ≥ 预测 low
- 更新 **daily_predictions** 表的 `actual_open/actual_high/actual_low/actual_close/dir_hit/range_hit`
- 跳过当日预测（不可验证）

### 2.4 准确率重算（Step 5）

对每只股票的已验证预测计算：

| 窗口 | 统计项 |
|------|--------|
| last_20 | dir_hit 命中率 / range_hit 命中率 |
| last_60 | dir_hit 命中率 / range_hit 命中率 |

写入 **accuracy_stats** 表。

### 2.5 预测生成（Step 6）

调用链: `calc_signals() → gen_pred() → insert_daily_prediction()`

详细算法参见 [自学习与预测算法](./04-self-learning.md)。

### 2.6 季节性+月K线补充（Step 7）

- **季节性**: 使用 12 个月默认因子值写入 **seasonal** 表
- **月K线**: 仅当 **kline_monthly** 表无数据时，从日K线合成月OHLC
- **行情**: 取最新日K线收盘价写入 **quotes** 表

---

## 3. 输入输出参数定义

| 项目 | 类型 | 来源/目标 |
|------|------|----------|
| **输入** | | |
| watchlist | `[{code, name, market}]` | 从 **watchlist** 表读取 |
| NeoData K-line | 管道分隔文本 | Node.js 子进程 stdout |
| **输出（SQLite 表）** | | |
| kline_daily | 每股票最多 200 条 | `upsert_kline_daily()` |
| daily_predictions | 每股票 1 条当日预测 | `insert_daily_prediction()` |
| prediction_hourly | 每条预测 4 条小时预测 | 关联写入 |
| prediction_signals | 每条预测 7 条技术信号 | 关联写入 |
| learning_params | 每股票 1 条参数记录 | `upsert_learning_params()` |
| accuracy_stats | 每股票 2 条 (last_20/last_60) | `upsert_accuracy_stats()` |
| seasonal | 每股票 12 个月因子 | `upsert_seasonal()` |
| kline_monthly | 新股票月K线合成 | `upsert_kline_monthly()` |
| quotes | 每日行情快照 | `upsert_quotes()` |
| news | 当日新闻 | `upsert_news()` |
| **输出（JSON文件）** | | |
| system_data.json | 遗留格式同步 | 兼容 `/api/system-data` |

---

## 4. 依赖关系

| 方向 | 模块 | 方式 |
|------|------|------|
| **依赖库** | `json`, `math`, `subprocess`, `os`, `sys`, `datetime`, `timedelta`, `ThreadPoolExecutor`, `defaultdict`, `concurrent.futures` | |
| **导入调用** | [数据库访问层](./02-database-layer.md) | 多函数导入 |
| **导入函数** | [新闻抓取](./07-news-fetcher.md) | `from fetch_news import fetch_news_node, _parse_news_table` |
| **外部依赖** | `westock-data` Node.js 插件, Node.js 运行时 | 子进程调用 |
| **内部函数** | `fetch_kline()`, `sync_one_stock()`, `_ema()`, `_calc_seasonal_from_db()`, `new_lp()`, `calc_signals()`, `gen_pred()` | 7个函数 |
| **被调用** | [Web API层](./01-api-server.md) | `POST /api/trigger/predict` → `run_script("sync_all.py")` |
| **被调用** | [定时任务调度](./06-scheduler.md) | `task_sync_all()` |

---

## 5. 异常处理机制

| 场景 | 处理策略 |
|------|---------|
| 新闻抓取失败 | try/except 捕获，打印日志并跳过，不阻塞主流程 |
| 单股票K线获取失败 | 返回空列表，打印 `"FAILED"`，不阻塞其他股票 |
| DB写入失败 | try/except 捕获，打印日志 |
| `clear_today_predictions` 失败 | try/except，不阻塞后续预测生成 |
| 单股票数据不足 | `calc_signals()` 返回 None，跳过该股票 |
| system_data.json 写入失败 | try/except 捕获，打印日志 |
