# 04 — 自学习引擎

> **核心文件**: `scripts/signals.py` (21.6KB) / `scripts/optimize_predict.py` (37.4KB)
> **算法**: MWU + EG + Beta-Binomial 三算法融合
> **信号数列**: 10 大技术信号 | **模型**: RandomForest + Ridge 混合回归

---

## 1. 业务需求说明书

### 1.1 业务背景

单纯的统计预测（如线性回归）无法适应当前 A 股市场的快速变化特征。系统需要一个自适应的信号权重调整机制，根据历史准确率动态调整各信号的影响力，同时叠加 ML 模型来提升预测精度。

### 1.2 核心目标

| 目标 | 说明 |
|------|------|
| 信号自适应调整 | 10个技术信号权重随历史表现动态优化 |
| ML模型融合 | RandomForest方向 + Ridge区间 = 混合预测 |
| 30+特征工程 | 价格/量/技术指标/季节/情绪多维度 |
| 在线学习 | 每次同步后增量更新参数，无需全量重训 |

---

## 2. 10大技术信号

| # | 信号 | 参数 | 说明 |
|---|------|------|------|
| 1 | MACD | 12/26/9 | 指数移动平均交叉，快线与慢线关系 |
| 2 | RSI | 14 | 相对强弱指数，超买(>70)/超卖(<30) |
| 3 | 布林带 | 20/2 | 突破上轨看跌、突破下轨看涨 |
| 4 | KDJ | 9/3/3 | 随机指标，K/D/J三线交叉 |
| 5 | 季节动量 | 12月 | 过去12个月的收益率动量 |
| 6 | ATR | 14 | 平均真实波幅，衡量波动性 |
| 7 | 资金流向 | 14 | 基于量价关系的资金流向 |
| 8 | ADX | 14 | 平均趋向指数，衡量趋势强度 |
| 9 | OBV | - | 能量潮，量价配合分析 |
| 10 | 波动率 | 20 | 20日历史波动率 |

### 信号输出格式
```json
{
  "signal_name": "MACD",
  "value": 0.85,           // 信号强度 -1 到 1
  "signal_type": "bullish"  // bullish/bearish/neutral
}
```

---

## 3. 算法详解

### 3.1 MWU (Multiplicative Weights Update)

核心思想：根据历史表现动态调整信号权重。

```python
def mwu_update(weights, payoffs, eta=0.1):
    """
    weights: 当前各信号权重（和为1）
    payoffs: 各信号在上一轮的收益（命中=1，未命中=0）
    eta: 学习率，默认0.1
    """
    new_weights = [w * (1 + eta * p) for w, p in zip(weights, payoffs)]
    # 归一化
    total = sum(new_weights)
    return [w / total for w in new_weights]
```

### 3.2 EG (Exponential Gradient)

针对稀疏信号场景的变体。

```python
def eg_update(weights, payoffs, eta=0.1):
    """指数梯度更新，适合权重差异大的场景"""
    new_weights = [w * math.exp(eta * p / max(1e-8, sum(weights)))
                   for w, p in zip(weights, payoffs)]
    total = sum(new_weights)
    return [w / total for w in new_weights]
```

### 3.3 Beta-Binomial 置信度

基于贝叶斯统计的信号置信度评估。

```python
alpha = hits + 1    # 命中次数 + 先验
beta = total - hits + 1  # 未命中次数 + 先验
confidence = alpha / (alpha + beta)
# 样本量越小，置信度越接近先验（0.5）
# 样本量越大，置信度越接近实际命中率
```

---

## 4. ML预测模型

### 4.1 特征工程（30+ 特征）

| 类别 | 特征数 | 示例 |
|------|--------|------|
| 价格特征 | 6 | 收盘价、开盘价、最高价、最低价、前复权价 |
| 量特征 | 4 | 成交量、成交额、换手率、量比 |
| 技术指标 | 10 | MACD/RSI/布林带/KDJ/ATR/ADX/OBV等 |
| 统计特征 | 5 | 移动平均(5/10/20/60)、标准差 |
| 时间特征 | 3 | 星期几、月份、季度 |
| 外部特征 | 3 | 行业涨跌幅、大盘涨跌幅、新闻情感 |

### 4.2 混合模型架构

```python
# 1. RandomForest 方向分类
rf_model = RandomForestClassifier(n_estimators=200, max_depth=10)
direction = rf_model.predict(features)  # bullish/bearish/neutral

# 2. Ridge 回归区间预测
ridge = Ridge(alpha=1.0, fit_intercept=True)
pred_price = ridge.predict(features)
lower_bound = pred_price - 1.96 * std_error
upper_bound = pred_price + 1.96 * std_error

# 3. 置信度 = 多个模型的投票一致性
confidence = max(direction_probs) * (1 - pred_volatility)
```

---

## 5. 存储结构

### learning_params 表

| 字段 | 类型 | 说明 |
|------|------|------|
| code | TEXT | 股票代码 |
| signal_name | TEXT | 信号名称 |
| param_name | TEXT | 参数名（weight/alpha/beta） |
| param_value | REAL | 参数值 |

### accuracy_stats 表

| 字段 | 类型 | 说明 |
|------|------|------|
| code | TEXT | 股票代码 |
| total_predictions | INTEGER | 总预测次数 |
| direction_hits | INTEGER | 方向命中次数 |
| direction_rate | REAL | 方向命中率 |
| range_hits | INTEGER | 区间命中次数 |
| range_rate | REAL | 区间命中率 |

---

## 6. 学习流程

```
同步触发 → Step 5
  │
  ├─ 1. 加载历史 signal payoffs（命中/未命中）
  ├─ 2. MWU更新 → 调整信号权重
  ├─ 3. EG更新 → 偏置校正
  ├─ 4. Beta-Binomial → 重新计算置信度
  ├─ 5. 保存学习参数到 SQLite
  └─ 6. 更新准确率统计到 SQLite
```

---

## 7. 数据流向

```
signals.py → 10个技术信号 → 特征向量 (30+维)
       ↓
optimize_predict.py → RF分类器 + Ridge回归
       ↓
   预测结果 (direction + price + bounds + confidence)
       ↓
   daily_predictions 表 / prediction_signals 表
```
