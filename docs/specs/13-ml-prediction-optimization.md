# 模块13: ML增强预测优化

> **核心文件**: `scripts/optimize_predict.py` | **版本**: V3.0 混合集成架构 | **触发**: 手动运行 | **依赖**: `db_helper.py`

---

## 1. 功能概述

基于历史K线数据，使用机器学习方法增强预测精度。采用 V3.0 混合集成架构：
- **特征工程**: 30+ 技术指标衍生特征
- **元学习器**: RandomForest 分类器
- **概率校准**: Isotonic Regression
- **超参优化**: GridSearch 交叉验证

与 `sync_all.py` 的规则投票预测互补，提供 ML 增强的第二意见。

---

## 2. 核心业务逻辑

### 2.1 特征工程（30+维）

基于日K线 OHLCV 数据衍生：

| 类别 | 特征 | 计算方式 |
|------|------|---------|
| **价格衍生** | 收益率 (1/3/5/10/20日) | `(close[-n] - close[0]) / close[0]` |
| | 波动率 (5/10/20日) | `std(returns, n)` |
| | 涨跌比 | `up_days / down_days` |
| **技术指标** | MACD (DIF/DEA/Histogram) | EMA12-EMA26 |
| | RSI (14日) | 标准RSI公式 |
| | KDJ (K/D/J值) | 随机指标 |
| | Bollinger (%B, Bandwidth) | (price-lower)/(upper-lower) |
| | ATR (14日) | True Range EMA |
| | OBV (On-Balance Volume) | 累积量价指标 |
| | ADX (14日) | 趋势强度指标 |
| **市场结构** | 支撑/阻力位 | 近期高低点 |
| | 均线排列 (MA5/10/20/60) | 多头/空头排列 |
| | 成交量异常 | Vol/MA(Vol)比例 |

### 2.2 训练数据准备

```python
def prepare_training_data(code):
    """从 kline_daily 构建训练集"""
    # 1. 读取日K线（200条）
    bars = get_kline_daily(code)
    
    # 2. 构建特征矩阵 X (每行=一个交易日)
    features = []
    for i in range(60, len(bars)):  # 需要前60天计算指标
        feat = extract_features(bars[:i+1])
        features.append(feat)
    
    # 3. 标签：次日涨跌 (1=涨, 0=跌)
    labels = [
        1 if bars[i+1][2] > bars[i+1][1] else 0
        for i in range(60, len(bars))
    ]
    
    return np.array(features), np.array(labels)
```

### 2.3 模型架构（V3.0 混合集成）

```
原始K线数据
    │
    ├── 规则投票 (sync_all.py)
    │   ├── calc_signals() → 7个技术信号
    │   └── gen_pred() → 加权投票预测
    │
    └── ML增强 (optimize_predict.py)
        ├── 特征工程 (30+维)
        ├── RandomForest (n_estimators=100-500)
        ├── Isotonic Calibration
        └── 概率输出 + 置信度
            │
            ▼
        加权融合 → 增强预测
```

### 2.4 概率校准

```python
from sklearn.calibration import CalibratedClassifierCV

# Isotonic校准确保预测概率与实际频率一致
calibrated = CalibratedClassifierCV(
    RandomForestClassifier(),
    method='isotonic',
    cv=5
)
```

### 2.5 超参优化

```python
param_grid = {
    'n_estimators': [100, 200, 500],
    'max_depth': [5, 10, 15, None],
    'min_samples_split': [2, 5, 10],
    'min_samples_leaf': [1, 2, 4]
}
grid_search = GridSearchCV(
    RandomForestClassifier(),
    param_grid,
    cv=5,
    scoring='accuracy'
)
```

---

## 3. 输入输出参数定义

### 3.1 输入

| 参数 | 类型 | 来源 | 说明 |
|------|------|------|------|
| `code` | `str` | 命令行参数/函数参数 | 6位股票代码 |
| K线数据 | `list[list]` | `get_kline_daily(code)` | 日K线OHLCV |
| 历史预测 | `list[dict]` | `get_daily_predictions(code)` | 用于验证 |

### 3.2 输出

```json
{
  "code": "601166",
  "date": "2026-06-03",
  "ml_prediction": {
    "direction": "bullish",
    "probability": 0.72,
    "calibrated_prob": 0.68,
    "confidence": "high"
  },
  "feature_importance": {
    "rsi_14": 0.15,
    "macd_histogram": 0.12,
    "volume_ratio": 0.10,
    "...": "..."
  },
  "model_info": {
    "algorithm": "RandomForest",
    "n_estimators": 200,
    "training_samples": 140,
    "cross_val_score": 0.62
  }
}
```

---

## 4. 与 sync_all.py 的集成

| 阶段 | 执行时机 | 职责 |
|------|---------|------|
| **sync_all.py** | 每次触发同步 | 规则投票预测 (7信号 + MWU自学习) |
| **optimize_predict.py** | 手动/定期执行 | ML模型训练 + 增强预测生成 |
| **融合** | 前端/API层 | 综合两个预测源的建议 |

当前 V0.7 中 `optimize_predict.py` 为独立执行，未来版本将集成到 `sync_all.py` Step 6 之后。

---

## 5. 依赖关系

| 方向 | 模块 | 方式 |
|------|------|------|
| **依赖库** | `numpy`, `sklearn.ensemble.RandomForestClassifier`, `sklearn.calibration.CalibratedClassifierCV`, `sklearn.model_selection.GridSearchCV` | |
| **导入调用** | [数据库访问层](./02-database-layer.md) | `get_kline_daily()`, `get_daily_predictions()` |
| **被调用** | 命令行直接执行 | `python optimize_predict.py` |

---

## 6. 异常处理机制

| 场景 | 处理 |
|------|------|
| 数据不足 (K线<60条) | 返回错误提示，不执行训练 |
| 模型训练失败 | try/except捕获，打印详细traceback |
| 特征计算异常 | 用NaN填充 + warn日志 |
| sklearn依赖缺失 | 导入时检测，给出安装提示 |
