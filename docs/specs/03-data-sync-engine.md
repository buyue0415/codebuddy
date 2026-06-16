# 03 — 数据同步引擎

> **核心文件**: `scripts/scheduler.py` (替代旧版 `sync_all.py`) | **执行方式**: subprocess `scheduler.py sync`
> **触发条件**: POST /api/trigger/predict | **全量超时**: 240s (server_v2.py 硬编码)
> **并发**: ThreadPoolExecutor max_workers=4 | **数据源**: Westock → NeoData → 东方财富 → 新浪 → 腾讯

---

## 1. 业务需求说明书

### 1.1 业务背景

系统依赖多源数据服务采集股票行情、K线、新闻、分红等信息。需要一个统一的同步引擎，按既定步骤顺序执行数据采集和计算任务，保证数据时效性和完整性。

### 1.2 核心目标

| 目标 | 说明 |
|------|------|
| 全量同步 | 4步流水线覆盖所有数据维度 |
| 多源回退 | 主源失效时自动降级到备用源 |
| 增量更新 | 只获取缺失或过期数据 |
| 并发采集 | 多只股票 K线并行获取 |
| 结果持久化 | 所有采集数据直接写入 SQLite |

---

## 2. 4步同步流水线

实际实现位于 `scripts/scheduler.py` 的 `sync_all()` 函数：

```
Step 1   → 并行获取K线 (ThreadPoolExecutor 4)            约30-60s
Step 2   → 生成多日预测 (calc_signals + gen_pred)         约30s
Step 3   → 月K线聚合 + 季节性因子 + 行情快照             约20s
Step 4   → 轻量脚本 (行情刷新 + 新闻 + 分红)             约120s
```

### Step 1: 并行获取K线

```python
# 通过 subprocess 调用 scripts/index.js 从 Westock 获取
# 每只股票获取 2000 根日K线数据
# 格式: [date, open, close, high, low]
# 直接写入 kline_daily 表
with ThreadPoolExecutor(max_workers=4) as pool:
    for fut in as_completed({pool.submit(sync_one, s): s for s in watchlist}):
        code, bars = fut.result()
        kline_results[code] = bars
```

数据源：Westock 本地版（通过 index.js 脚本）。

### Step 2: 生成10日预测

```python
# 1. calc_signals: 基于日K线计算10个技术信号 (MACD/RSI/布林带等)
# 2. gen_multi_day_pred: RandomForest + Ridge 混合模型
# 3. 输出: direction, pred_price, confidence, lower_bound, upper_bound
# 4. 写入 daily_predictions 表，更新 learning_params 和 accuracy_stats
```

详见 [04-self-learning-engine.md]

### Step 3: 月K线 + 季节性因子 + 行情快照

#### 3.1 月K线聚合

对 **新增股票**（`kline_monthly` 表无该股票记录），从 `kline_results` 中的日K线按月聚合：

```python
# 按月分组日K线
for bar in daily:
    m = bar[0][:7]  # "YYYY-MM-DD" → "YYYY-MM"
    monthly[m] = {
        'open': bar[1],           # 月首日开盘
        'high': max(highs),       # 月最高价
        'low': min(lows),         # 月最低价
        'close': 最后一日收盘,     # 月末收盘
    }

# 计算每月涨跌幅 change_pct
# 相邻月份收盘价比较:
for i, (m, v) in enumerate(sorted_months):
    prev_close = 上个月收盘 (首月使用自身收盘)
    change_pct = (本月收盘 - prev_close) / prev_close * 100
```

**历史问题修复**: 旧版 `change_pct` 硬编码为 `0.0`，导致所有月度涨跌幅显示为持平。
修复方案：`scheduler.py:146-151` 从日K线收盘价逐月推算涨跌幅。

#### 3.2 季节性因子

从 `kline_monthly` 表中按股票独立计算各月平均涨跌幅：

```python
# 对 watchlist 中每只股票独立计算
rows = SELECT date, change_pct FROM kline_monthly WHERE code=?
mg = {1:[], 2:[], ..., 12:[]}
for r in rows:
    month = int(r['date'][5:7])   # 提取日历月份
    mg[month].append(r['change_pct'])

seasonal = []
for m in 1..12:
    vals = mg[m]
    seasonal[m] = avg(vals) if vals else 0.0
```

**历史问题修复**: 旧版所有股票使用同一个 `DEFAULT_SEASONAL` 硬编码数组。
修复方案：`scheduler.py:152-167` 从各股票的实际历史月度数据计算季节性因子。

#### 3.3 行情快照

将最新的日K线数据写入 `quotes` 表，供其他页面实时展示。

### Step 4: 轻量脚本

通过 subprocess 串行执行以下辅助脚本：

| 脚本 | 超时 | 用途 |
|------|------|------|
| `refresh_quotes.py` | 120s | 刷新实时行情 |
| `fetch_news.py` | 120s | 采集股票新闻 |
| `fetch_dividends.py` | 120s | 采集分红数据 |

---

## 3. 多源回退策略

```python
fetchers = [
    WestockFetcher(),    # 本地量化数据服务，最快
    NeoDataFetcher(),    # NeoData API 金融数据
    EastMoneyFetcher(),  # 东方财富 (akshare)
    SinaFetcher(),       # 新浪财经
    TencentFetcher(),    # 腾讯证券
]

for fetcher in fetchers:
    try:
        data = fetcher.fetch(code)
        if data and len(data) > 0:
            return data
    except Exception:
        continue  # 自动降级到下一源
```

---

## 4. 命令行模式

```bash
# 全量同步 (sync + news)
python scheduler.py all

# 仅数据同步 (Steps 1-3)
python scheduler.py sync

# 仅新闻采集
python scheduler.py news

# 仅日内数据采集
python scheduler.py intraday
```

---

## 5. 日志输出

同步过程输出到 stdout：

```
[scheduler] Sync all: 15 stocks
[scheduler] Fetching K-line (limit=2000)...
  兴业银行(601166): 1250 bars
  招商银行(600036): 1250 bars
  ...
[scheduler] Generating 10-day predictions...
  兴业银行(601166): 10 days (...)
  ...
[scheduler] Sync all done. 15 stocks.
```

完整日志通过 API 返回给前端（`POST /api/trigger/predict` 的 `output` 字段）。

---

## 6. 安全与限制

| 限制 | 值 | 说明 |
|------|-----|------|
| 全量同步最长时间 | 240s | 超过则 subprocess 超时中断 |
| 并发采集数 | 4 | ThreadPoolExecutor 上限 |
| 交易日检查 | 工作日 | 非交易日报跳过，注释可覆盖 |
| K线采集数量 | 2000根 | --limit 参数传至 Westock |
| 预测天数 | 10日 | gen_multi_day_pred 固定参数 |

---

## 7. 触发方式

| 方式 | 说明 |
|------|------|
| API触发 | POST /api/trigger/predict → subprocess scheduler.py sync |
| 前端全量刷新 | App.vue 右上角"全量刷新"按钮 |
| 添加股票自动触发 | Management.vue addStock() 步骤4 |
| 定时触发 | Windows 任务计划程序每日开盘前执行 |
