# 03 — 数据同步引擎

> **核心文件**: `scripts/sync_all.py` (30KB) | **超时**: 180s | **触发**: `POST /api/trigger/predict`

---

## 1. 业务需求说明书

### 1.1 业务背景

系统需要每日（或用户手动触发时）对自选股列表执行完整的数据刷新：获取最新K线、验证历史预测、重新计算准确率、生成新的预测。所有步骤需按序执行。

### 1.2 核心目标

| 目标 | 说明 |
|------|------|
| 全量数据同步 | 一站式刷新行情/K线/预测/新闻/季节性 |
| 预测闭环 | 回填验证 → 准确率重算 → 生成新预测 |
| 并行加速 | K线获取使用 ThreadPoolExecutor 并发 |
| 容错设计 | 单股票失败不阻塞其他股票 |

---

## 2. 技术方案深度分析

### 2.1 执行流程（8步）

```
Step 1: 新闻抓取（调用 fetch_news.py）
Step 1.5: 分红数据获取（东方财富公开API）
Step 2: 并行日K线获取（ThreadPoolExecutor, max_workers=4）
Step 3: 预测回填（验证 dir_hit IS NULL 的历史预测）
Step 4: 准确率重算（last_20 / last_60 统计）
Step 5: 自学习（Adaptive MWU + 回测冷启动 + 市场状态自适应）
Step 6: 生成10天预测（calc_signals → gen_multi_day_pred → 写DB）
Step 7: 季节性 + 月K线 + 行情刷新
```

### 2.2 并行K线获取（Step 2）

```python
# 使用 ThreadPoolExecutor，最多 4 并发
# 每股票通过 Node.js 子进程调用 westock-data
# 命令: node scripts/index.js kline {code} --period day --limit 2000 --fq qfq
# 编码: gbk 优先 → utf-8 fallback
```

### 2.3 数据同步参数

| 参数 | 值 | 说明 |
|------|-----|------|
| K线获取条数 | 2000 | 约8年日K数据 |
| 复权方式 | qfq（前复权） | 最新价不变，历史价按比例调整 |
| 并行并发数 | min(len(watchlist), 4) | 最多4只股票同时获取 |

---

## 3. 功能介绍和实现方式

### 3.1 预测回填（Step 3）

```python
# 查找所有 dir_hit IS NULL 的历史预测
# 用实际K线验证方向（涨跌一致）和区间（高低价覆盖）
# 更新 daily_predictions 的 actual_*/dir_hit/range_hit 字段
# 跳过当日预测（不可验证）
```

### 3.2 信号计算（Step 6）

调用链：
```
calc_signals(kdata, seasonal_factor)
  → 返回 {close, atr, signals: {MACD, RSI, Bollinger, KDJ, Seasonal, ATR, Money Flow, ADX_Trend, OBV_Divergence, Vol_Convergence}}
gen_multi_day_pred(code, kdata, info, lp, num_days=10)
  → 加权投票 → 方向判断 → 置信度计算 → 写入 DB
```

### 3.3 数据流

```
watchlist (SQLite)
  ↓ Step 2
NeoData API → kline_daily (SQLite)
  ↓ Step 3-4
回填验证 → accuracy_stats (SQLite)
  ↓ Step 5
自学习 → learning_params (SQLite)
  ↓ Step 6
信号计算 → daily_predictions + prediction_signals + prediction_hourly (SQLite)
  ↓ GET /api/v2/init
Vue 3 SPA（前端渲染）
```

---

## 4. 用户操作流程

### 4.1 手动刷新（Web触发）

```
用户: 导航栏 "股票分析预测" → "智能预测"
  → 点击 [🔄 刷新]
  → 前端: POST /api/trigger/predict
  → 后端: subprocess.run('sync_all.py', timeout=180)
  → 约 30-120 秒后完成
  → 前端自动刷新数据
```

### 4.2 定时触发（Windows任务计划程序）

```
Windows任务计划程序: 每日 15:35
  → python scheduler.py sync
  → 调用 sync_all.py 8步流程
  → 完成后自动执行 paper_trading.py
```

### 4.3 异常处理

| 场景 | 行为 |
|------|------|
| 单股票K线获取失败 | 打印 FAILED，继续其他股票 |
| 新闻抓取失败 | try/except 跳过，不阻塞主流程 |
| K线数据不足（<14条） | calc_signals() 返回 None，跳过该股 |
| DB写入失败 | try/except 捕获，打印日志 |
