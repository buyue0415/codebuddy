# 04 — 自学习与预测引擎

> **核心文件**: `scripts/signals.py` (22KB) | **信号数**: 10 | **时段数**: 5
> **导入方**: `sync_all.py`, `backtest_engine.py`

---

## 1. 业务需求说明书

### 1.1 业务背景

系统基于历史K线数据生成次日涨跌预测。预测引擎需要：
- 从K线计算多项技术指标
- 综合信号产生方向/置信度/价格区间预测
- 根据实际结果自动调整各信号权重（自学习）

### 1.2 核心目标

| 目标 | 说明 |
|------|------|
| 10 信号技术分析 | 覆盖趋势/动量/波动/成交量多维度 |
| 加权投票预测 | 信号方向 × 自学习权重 → 综合判断 |
| MWU 在线学习 | 做对的信号加强，做错的信号减弱 |
| 10 天滚动预测 | Day1 全信号 → Day2-10 动量投影 |

---

## 2. 技术方案深度分析

### 2.1 10 项技术信号

| # | 信号 | 类型 | 方向判断 | 计算周期 |
|----|------|------|---------|---------|
| 1 | **MACD** | 趋势 | MACD>Signal→bullish | EMA12/EMA26/Signal9 |
| 2 | **RSI** | 动量 | >55 bullish, <45 bearish | 14日 |
| 3 | **Bollinger** | 波动 | 价>上轨 bearish, <下轨 bullish | 20日 2σ |
| 4 | **KDJ** | 超买超卖 | J>80 bearish, J<20 bullish | 9日 RSV |
| 5 | **Seasonal** | 季节性 | factor>1 bullish | 12月历史聚合 |
| 6 | **ATR** | 波动性 | 中性 | 14日 True Range |
| 7 | **Money Flow** | 资金流 | 3日>1% bullish, <-1% bearish | 3日+10日动量 |
| 8 | **ADX_Trend** | 趋势强度 | DI+>DI- bullish | 14日 ADX |
| 9 | **OBV_Divergence** | 量价背离 | OBV新高 bullish | On-Balance Volume |
| 10 | **Vol_Convergence** | 波动收敛 | 波动收窄→突破方向 | 布林带宽收敛 |

### 2.2 MWU 在线学习算法

```
对于每个信号 s 的每个时段 p（含 next_day）:
  if dir_hit == 1:  w[s][p] = w[s][p] × e^(+0.5)   # 正确：权重 × 1.649
  if dir_hit == 0:  w[s][p] = w[s][p] × e^(-0.5)   # 错误：权重 × 0.607

自适应衰减:
  β = 0.5 + 0.3 × clamp(0.3, stock_accuracy, 0.8)
  w[s][p] = w[s][p] × β + 1.0 × (1 - β)

归一化:
  w[s][p] = w[s][p] / sum(w[s,:]) × 5.0  # 每信号5时段和为5
```

### 2.3 EG 偏置更新

```
η = 0.005 × 0.995^n
bias[p] = clamp(bias[p] + η × error, -0.05, 0.05)
```

### 2.4 三组件协同

```
MWU 权重更新 → "哪些信号更值得信赖?"
EG 偏置更新  → "时段级的系统偏差修正"
Beta-Binomial → "历史统计的可靠性评估"
```

---

## 3. 功能介绍和实现方式

### 3.1 信号计算 `calc_signals()`

```python
# 输入: kdata（日K线列表）+ seasonal_factor
# 输出: {close, atr, signals: {macd, rsi, bollinger, kdj, seasonal,
#         atr, money_flow, adx_trend, obv_divergence, vol_convergence}}
# 前置条件: kdata ≥ 14条
```

### 3.2 预测生成 `gen_multi_day_pred()`

```
输入: code, kdata, info(信号输出), lp(学习参数), num_days=10

Day 1（当日全信号预测）:
  加权分数 = Σ w[s][next_day] × dir(s) + seasonal_adj × 2
  方向判断: ws>0.5→bullish, ws<-0.5→bearish
  置信度  = max(0.4, 0.6×consensus + 0.4×β_conf)
  价格区间 = close ± ATR × 2.5

Day 2-10（动量投影）:
  基于 Day1 方向 + 衰减置信度
  confidence_Dn = confidence_D1 × 0.85^(n-1)
```

### 3.3 5 个预测时段（分时）

| 时段 | 权重 | 说明 |
|------|------|------|
| 09:30-10:30 | 0.35 | 开盘消化隔夜信息 |
| 10:30-11:30 | 0.20 | 横盘整理 |
| 13:00-14:00 | 0.20 | 午后资金活跃 |
| 14:00-15:00 | 0.25 | 尾盘主力动作 |
| next_day | — | 次日终盘方向（核心输出） |

### 3.4 学习参数初始化 `new_lp()`

```json
{
  "signal_weights": { "macd": {"next_day": 1.0, "09:30-10:30": 1.0, ...}, ... },
  "hourly_bias": { "09:30-10:30": 0.0, ... },
  "seasonal_adj": { "1"~"12": 0.0 },
  "confidence_beta": { "bullish": {"alpha":1,"beta":1}, ... },
  "learning_rate": 0.01, "mw_beta": 0.7, "update_count": 0
}
```

---

## 4. 用户操作流程

### 4.1 首次添加自选股

```
用户: 管理设置 → 添加自选股 "601166"
  → sync_all.py 执行
  → Step 5: update_count==0, 尝试读取回测冷启动权重
  → Step 6: 生成第一条预测
  → 前端 "智能预测" 页显示：预测 bullish, 置信度 55%
```

### 4.2 每日自学习

```
每日收盘后:
  → sync_all.py Step 3: 回填昨日预测（dir_hit 更新）
  → Step 5: MWU 更新权重 → EG 更新偏置 → Beta-Binomial 更新置信度
  → 预测准确率逐步提升（从 ~50% → ~60%）
```

### 4.3 查看预测详情

```
用户: 智能预测 → 选择股票 "兴业银行"
  → 看到10天滚动预测（Day 1 置信度最高，Day 10 衰减）
  → 查看10信号详情：MACD bullish (+0.15%), RSI 55.2 neutral, ...
  → 分时预测：4个时段的独立方向预测
```
