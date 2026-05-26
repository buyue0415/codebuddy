# 模块4: 自学习与预测算法

> **核心文件**: `sync_all.py` 内函数 + `daily_update.py` Step5 | **涉及函数**: `calc_signals()`, `gen_pred()`, 自学习更新逻辑

---

## 1. 功能概述

本模块涵盖三个紧密关联的子功能：
1. **技术指标计算** (`calc_signals()`): 基于日K线计算 7 项技术信号
2. **预测生成** (`gen_pred()`): 综合信号和自学习参数生成次日预测
3. **自学习引擎** (在线更新逻辑): 基于预测-实际对比优化参数

---

## 2. 技术指标计算 (`calc_signals()`)

### 2.1 输入

```
kdata: list[list[str, float, float, float, float]]
       [    [date,   open,  close, high,   low], ...]
seasonal_factor: float  # 来自 _calc_seasonal_from_db() 的当月因子
```

**前置条件**: kdata 至少 14 条。

### 2.2 7项技术指标

| 指标 | 计算周期 | 公式/方法 | 方向判断 |
|------|---------|----------|---------|
| **MACD** | EMA12/EMA26/Signal=EMA9 | 真EMA（非SMA），含 Signal线交叉检测 | MACD > Signal → bullish, 否则 bearish |
| **RSI** | 14日 | `RSI = 100 - 100/(1 + avg_gain/avg_loss)` | RSI > 55 → bullish, < 45 → bearish, 否则 neutral |
| **Bollinger** | 20日, 2σ | `upper = MA + 2σ, lower = MA - 2σ` | 价格 > 上轨×0.98 → bearish, < 下轨×1.02 → bullish, 否则 neutral |
| **KDJ** | 9日 | `RSV → K → D → J = 3K-2D` | J > 80 → bearish, J < 20 → bullish, 否则 neutral |
| **Seasonal** | 12月历史 | 从 kline_monthly.change_pct 按月聚合 | factor > 1 → bullish, 否则 bearish |
| **ATR** | 14日 True Range | `TR = max(H-L, |H-C_prev|, |L-C_prev|)` | 中性，仅提供数值 |
| **Money Flow** | 3日+10日涨跌幅 | 多周期动量背离 | 3日>1%且10日>0 → bullish, 3日<-1%且10日<0 → bearish; 否则看3日>(2.5%)/(−2.5%) |

### 2.3 EMA公式
使用真正的指数移动平均（非SMA）：
$$EMA(t) = Price_t \times \frac{2}{n+1} + EMA(t-1) \times (1 - \frac{2}{n+1})$$
初始值使用前 n 个价格的 SMA。

### 2.4 季节因子计算 (`_calc_seasonal_from_db()`)
从 **kline_monthly** 表的 `change_pct` 字段按月聚合，计算各月平均涨跌幅，缩放至 0.8~1.2：
$$scaled = 1.0 + avg\\_monthly\\_change \times 3 / 100$$
限制范围: `max(0.80, min(1.20, scaled))`

### 2.5 输出

```json
{
  "close": 17.37,
  "atr": 0.325,
  "signals": {
    "macd":    {"value": "+0.15%", "direction": "bullish", "diff": 0.026, "signal": 0.018, "raw": 0.15},
    "rsi":     {"value": 48.3, "direction": "neutral", "raw": 48.3},
    "bollinger": {"direction": "neutral", "value": "0.3σ", "raw": 0.3, "upper": 18.1, "lower": 16.5},
    "kdj":     {"value": "K55 D52 J61", "raw": 61, "direction": "neutral"},
    "seasonal": {"direction": "bullish", "factor": 1.05},
    "atr":     {"value": 0.325, "pct": 1.87, "direction": "neutral", "raw": 0.325},
    "money_flow": {"direction": "bullish", "value": "+1.5%", "raw": 1.5}
  }
}
```

---

## 3. 预测生成 (`gen_pred()`)

### 3.1 输入
```
code: str          # 6位股票代码
info: dict         # calc_signals() 的输出
lp: dict           # 学习参数 (new_lp() 或 get_learning_params())
```

### 3.2 日内方向判断
$$\text{weighted\\_score} = \sum_{s \in SIGNALS} w_s[\text{next\\_day}] \times dir(s) + sa[\text{month}] \times 2$$

其中 $dir(s) = 1$ (bullish), $-1$ (bearish), $0$ (neutral)

$$\text{direction} = \begin{cases} bullish & ws > 0.5 \\ bearish & ws < -0.5 \\ neutral & \text{otherwise} \end{cases}$$

### 3.3 置信度计算
$$\text{confidence} = \max(0.4, 0.6 \times \text{consensus} + 0.4 \times \beta\\_conf)$$

- `consensus`: 非中性信号中与预测方向一致的比例
- `β_conf`: Beta-Binomial 历史命中率 $= \frac{\alpha}{\alpha + \beta}$

### 3.4 价格区间
- 日振幅: $ATR \times 2.5$
- 预测高点: $close + ATR \times 2.5 \times 0.6$
- 预测低点: $close - ATR \times 2.5 \times 0.4$

### 3.5 分时预测（4个时段）

| 时段 | 权重 | 备注 |
|------|------|------|
| 09:30-10:30 | 0.35 | 开盘消化隔夜信息 |
| 10:30-11:30 | 0.20 | 横盘整理 |
| 13:00-14:00 | 0.20 | 午后资金活跃 |
| 14:00-15:00 | 0.25 | 尾盘主力动作 |

每个时段独立计算加权分数，结合学习偏置 `bias[block] × 2` 调整。

### 3.6 操作建议
| 方向 | 建议 |
|------|------|
| bullish | "低吸为主" |
| bearish | "逢高减仓" |
| neutral | "观望为主" |

### 3.7 输出

```json
{
  "date": "2026-05-26",
  "code": "601166",
  "prev_close": 17.37,
  "next_day": {
    "direction": "bullish",
    "confidence": 0.65,
    "high": 17.85,
    "low": 17.05,
    "advice": "低吸为主",
    "entry_zone": 17.05
  },
  "hourly": [
    {"block": "09:30-10:30", "pred_open": 17.37, "pred_high": 17.65, "pred_low": 17.20, "pred_close": 17.45, "direction": "bullish", "strength": 3, "note": "开盘消化隔夜信息"},
    ...
  ],
  "signals": { /* calc_signals 输出 */ },
  "actual": {
    "open": null, "high": null, "low": null, "close": null,
    "next_day_direction_hit": null,
    "daily_range_hit": null,
    "hourly_hits": [null, null, null, null]
  }
}
```

---

## 4. 自学习引擎

> 核心代码位于 `daily_update.py` Step5。V0.6 中 `sync_all.py` 仅初始化参数（使用 `new_lp()`），不执行在线更新。

### 4.1 学习参数初始化 (`new_lp()`)

```json
{
  "signal_weights": { "<signal>": { "<block>": 1.0 } },  // 7×5 矩阵
  "hourly_bias": { "<block>": 0.0 },                        // 5个偏置
  "seasonal_adj": { "1"~"12": 0.0 },                        // 12个月调整
  "confidence_beta": {
    "bullish":  {"alpha": 1, "beta": 1},
    "bearish":  {"alpha": 1, "beta": 1},
    "neutral":  {"alpha": 1, "beta": 1}
  },
  "learning_rate": 0.01,
  "mw_beta": 0.7,
  "update_count": 0
}
```

### 4.2 MWU (Multiplicative Weights Update) 信号权重更新

对于每个技术信号 $s$ 和每个时段 $p$（含 next_day）：
$$\text{new\\_weight} = \text{old\\_weight} \times \begin{cases} e^{1.0} & \text{if correct} \\ e^{-1.0} & \text{if wrong} \end{cases}$$

衰减平滑：
$$\text{weight} = \text{weight} \times 0.7 + 1.0 \times 0.3$$

跨 5 个时段归一化到 sum=5。

### 4.3 EG (Exponentiated Gradient) 偏置更新

$$\eta = 0.01 \times 0.995^n$$
$$\text{new\\_bias} = \text{old\\_bias} + \eta \times \text{error}$$
$$\text{bias} = \text{clamp}(\text{new\\_bias}, -0.05, 0.05)$$

其中 $n$ = `update_count`，error = 1 (正确) / -1 (错误)。

### 4.4 Beta-Binomial 置信度更新

- 预测正确: $\alpha_{\text{direction}} \mathrel{+}= 1$
- 预测错误: $\beta_{\text{direction}} \mathrel{+}= 1$

### 4.5 季节因子 EMA 更新

$$\text{new\\_factor}_m = 0.2 \times \text{daily\\_ret} + 0.8 \times \text{old\\_factor}_m$$

### 4.6 更新条件

| 条件 | 行为 |
|------|------|
| `dir_hit IS NOT NULL` | 执行全部更新 |
| 预测方向为 neutral | 跳过 Beta-Binomial 更新 |
| 无 learning_params | 跳过自学习 |
| 偏置裁剪 | 确保不发散（±0.05 裁剪） |

---

## 5. 依赖关系

| 方向 | 模块 | 说明 |
|------|------|------|
| **依赖库** | `math`, `datetime` | Python标准库 |
| **被调用** | [同步引擎](./03-sync-engine.md) | `calc_signals()` + `gen_pred()` |
| **被调用** | [每日更新](./05-daily-update.md) | 自学习更新逻辑 |

---

## 6. 异常处理机制

| 场景 | 处理 |
|------|------|
| K线数据不足 14 条 | `calc_signals()` 返回 None，调用方跳过 |
| RSI 分母为零 | `rs = 100 if losses == 0` |
| 预测方向为 neutral | Beta-Binomial 跳过更新 |
| 偏置越界 | clamp 到 ±0.05 |
