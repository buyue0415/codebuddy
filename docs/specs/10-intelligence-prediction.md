# 10 — 智能预测

> **前端页面**: `deliverables/v2/src/pages/Intelligence.vue` (18KB)
> **路由**: `/intelligence` | **菜单**: 股票分析预测 → 智能预测

---

## 1. 业务需求说明书

### 1.1 业务背景

用户需要基于技术分析信号获取次日涨跌预测，辅助买卖决策。系统需展示10天滚动预测、10项技术信号详情、分时走势预测和历史预测准确率。

### 1.2 核心目标

| 目标 | 说明 |
|------|------|
| 10天滚动预测 | 未来10个交易日的方向/置信度/价格区间 |
| 10信号详情 | 每项技术指标的当前值和方向 |
| 分时预测 | 4个时段的独立方向预测 |
| 历史验证 | 已回填预测的命中率展示 |
| 手动刷新 | [🔄 刷新] 按钮触发全量同步 |

---

## 2. 技术方案深度分析

### 2.1 预测生成（10天滚动）

```python
# signals.py: gen_multi_day_pred()
# 输入: code, kdata, info(10信号), lp(学习参数), num_days=10

Day 1（全信号预测）:
  # 10信号加权投票
  ws = Σ w[s]['next_day'] × dir_sign(s) + seasonal_adj[month] × 2
  direction = bullish if ws>0.5 else bearish if ws<-0.5 else neutral
  confidence = max(0.4, 0.6 × consensus + 0.4 × β_conf)

Day 2-10（动量投影）:
  direction = Day1的方向（动量延续假设）
  confidence_n = confidence_1 × 0.85^(n-1)  # 指数衰减
```

### 2.2 置信度衰减

```
Day 1:  confidence = 0.65 (全信号计算)
Day 2:  confidence = 0.65 × 0.85 = 0.55
Day 3:  confidence = 0.55 × 0.85 = 0.47
...
Day 10: confidence = 0.65 × 0.85^9 ≈ 0.15
```

### 2.3 数据流

```
sync_all.py Step 6
  → calc_signals() + gen_multi_day_pred()
  → daily_predictions 表（每条含 direction/confidence/high/low/entry_zone）
  → GET /api/v2/predictions/daily/{code}
  → Intelligence.vue 渲染
```

---

## 3. 功能介绍和实现方式

### 3.1 API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v2/predictions/daily` | 批量获取全部自选股预测 |
| GET | `/api/v2/predictions/daily/{code}` | 单只股票预测（含历史验证） |
| GET | `/api/v2/accuracy` | 批量准确率统计 |
| GET | `/api/v2/accuracy/{code}` | 单只股票准确率 |
| POST | `/api/trigger/predict` | 触发全量同步刷新 |

### 3.2 前端实现

```vue
<!-- Intelligence.vue 核心结构 -->
<template>
  <!-- 股票选择 -->
  <Dropdown v-model="selectedCode" :options="watchlist" />

  <!-- 当前预测卡片 -->
  <PredictionCard>
    <div>当前: ¥{{ close }}</div>
    <div>预测: {{ directionLabel }} ↑/↓/→</div>
    <div>置信度: {{ confidence }}%</div>
    <div>区间: {{ low }} ~ {{ high }}</div>
    <div>建议: {{ advice }}</div>
  </PredictionCard>

  <!-- 10天走势预测 -->
  <D10PredictionChart :data="futurePreds" />

  <!-- 10信号详情 -->
  <SignalsDetail :signals="signals" />

  <!-- 分时预测 -->
  <HourlyPrediction :hourly="hourly" />

  <!-- 刷新按钮 -->
  <Button @click="refresh">🔄 刷新</Button>
</template>
```

### 3.3 数据存储

```sql
-- daily_predictions 表核心字段
direction     TEXT    -- bullish/bearish/neutral
confidence    REAL    -- 0.4-1.0
high          REAL    -- 预测最高价
low           REAL    -- 预测最低价
entry_zone    REAL    -- 建议入场价位
advice        TEXT    -- 操作建议文本
-- 回填字段
actual_close  REAL    -- 实际收盘
dir_hit       INTEGER -- 方向命中(1/0/NULL)
range_hit     INTEGER -- 区间命中(1/0/NULL)
```

---

## 4. 用户操作流程

### 4.1 查看预测

```
用户: 导航栏 "股票分析预测" → "智能预测"

页面显示:
┌──────────────────────────────────────────┐
│  智能预测              [兴业银行 ▼]      │
│                                          │
│  当前 ¥17.37  预测 bullish ↑  置信 65%  │
│  区间 ¥17.05 ~ ¥17.85  建议: 低吸为主   │
│                                          │
│  10天走势预测                            │
│  [06-05] [06-06] [06-09] [06-10] ...     │
│   🟢↑     🟢↑     🟡→     🟡→           │
│  17.35   17.42   17.38   17.40           │
│   65%     62%     48%     45%            │
│                                          │
│  10信号详情                              │
│  MACD +0.15% ↑ | RSI 55.2 → | ...        │
│                                          │
│  [🔄 刷新]                               │
└──────────────────────────────────────────┘
```

### 4.2 手动刷新预测

```
用户: 点击 [🔄 刷新]
  → 按钮禁用，显示 "刷新中..."
  → POST /api/trigger/predict
  → 约 30-120 秒后完成
  → 预测数据自动更新
  → 按钮恢复可用
```

### 4.3 切换股票查看

```
用户: 股票下拉菜单选择 "招商银行"
  → GET /api/v2/predictions/daily/600036
  → 图表和信号详情全部切换为新股票数据
```
