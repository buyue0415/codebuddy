# 15 — 回测分析

> **前端页面**: `deliverables/v2/src/pages/BacktestPage.vue` (16KB)
> **路由**: `/backtest` | **菜单**: 模拟交易 → 回测分析
> **核心脚本**: `scripts/backtest_engine.py` (17KB)

---

## 1. 业务需求说明书

### 1.1 业务背景

MWU 在线学习算法对新股票存在"冷启动"问题——从 weight=1.0 开始需要10-20天才调优。回测引擎通过历史数据 Walk-forward 优化，为每只股票生成最优初始权重，消除冷启动等待期。

### 1.2 核心目标

| 目标 | 说明 |
|------|------|
| 冷启动权重 | 新股票直接用回测最优权重代替 1.0 |
| 市场状态自适应 | 趋势/震荡/高波动3套独立权重矩阵 |
| 性能量化 | 夏普比率/最大回撤/胜率/年化收益 |
| 异步执行 | 不阻塞 API 主线程 |

---

## 2. 技术方案深度分析

### 2.1 Walk-Forward 滚动窗口

```
训练窗口(252天)         测试窗口(21天)
[====================]  [=======]
                       ↓ 前滚 21 天
        [====================]  [=======]
```

### 2.2 两阶段权重搜索

替代全量网格搜索（8^10≈1亿组合），采用高效两阶段方案：

```
Phase 1: 单信号独立评估（80次/股）
  10 信号 × 8 候选权重 → 筛选 top 3 最有价值信号

Phase 2: top 3 组合搜索（512次/股）
  3 信号 × 8^3 = 512 次

总计: 592次/股, 6股 ≈ 3,552次（约30-60秒）
```

### 2.3 市场状态检测

```python
def detect_market_regime(kdata):
    adx = calc_adx(kdata)           # ADX 趋势强度
    volatility = std(returns) / mean(returns)

    if adx > 25 and volatility < 0.02:  return "trending"
    elif adx < 20 and volatility < 0.015: return "ranging"
    else:                                 return "volatile"
```

### 2.4 冷启动集成

```python
# sync_all.py Step 5:
lp = get_learning_params(code) or new_lp()

if lp.get('backtest_weights') and lp['update_count'] == 0:
    lp['signal_weights'] = json.loads(lp['backtest_weights'])
    # 新股票跳过冷启动，直接使用历史最优权重

if lp.get('regime_weights'):
    regime = detect_market_regime(kdata)
    lp['signal_weights'] = blend(
        lp['signal_weights'],
        lp['regime_weights'][regime],
        ratio=0.3  # 30%倾向当前市场状态
    )
```

---

## 3. 功能介绍和实现方式

### 3.1 API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v2/backtest/run` | 启动回测（异步subprocess） |
| GET | `/api/v2/backtest/status` | 查询运行状态 |
| POST | `/api/v2/backtest/stop` | 停止运行中回测 |
| GET | `/api/v2/backtest/results/{run_id}` | 获取回测结果 |
| GET | `/api/v2/backtest/history` | 历史回测记录 |

### 3.2 性能指标

| 指标 | 计算 | 用途 |
|------|------|------|
| 夏普比率 | (年化收益-无风险率)/年化波动 | 风险调整收益 |
| 最大回撤 | max(峰值-谷值)/峰值 | 最大亏损幅度 |
| 胜率 | 盈利交易/总交易 | 方向准确度 |
| Calmar比率 | 年化收益/最大回撤 | 回撤调整收益 |

### 3.3 前端实现

```vue
<!-- BacktestPage.vue 核心结构 -->
<template>
  <!-- 控制面板 -->
  <ControlPanel>
    <Button @click="runBacktest" :disabled="running">
      {{ running ? '● 运行中' : '▶ 运行回测' }}
    </Button>
    <Select v-model="trainWindow" :options="[126, 252, 504]" />
    <Select v-model="testWindow" :options="[21, 42, 63]" />
    <StatusBadge :status="status" />
  </ControlPanel>

  <!-- 指标卡片 -->
  <MetricsCards>
    <Card title="夏普比率" :value="sharpe" />
    <Card title="最大回撤" :value="maxDrawdown" />
    <Card title="胜率" :value="winRate" />
    <Card title="年化收益" :value="annualReturn" />
  </MetricsCards>

  <!-- 权重对比表 -->
  <DataTable :data="weightComparison">
    <Column field="code" header="股票" />
    <Column field="original_accuracy" header="原始MWU准确率" />
    <Column field="optimized_accuracy" header="回测优化后" />
    <Column field="improvement" header="改善幅度" />
    <Column field="sharpe" header="夏普" />
  </DataTable>

  <!-- 市场状态权重 -->
  <RegimeWeightsTable :data="regimeWeights" />
</template>
```

---

## 4. 用户操作流程

### 4.1 首次运行回测

```
用户: 导航栏 "模拟交易" → "回测分析"
  → 界面显示: "未运行过回测，点击开始"
  → 选择参数: 训练252天 / 测试21天
  → 点击 [▶ 运行回测]
  → POST /api/v2/backtest/run
  → 状态: ●运行中（轮询 GET status 每2秒）
  → 约 60-120 秒后完成
  → 显示:
    夏普 0.85 | 最大回撤 -12.5% | 胜率 58.3% | 年化 +15.7%
    601166: 原始55.2% → 优化62.1% (↑6.9%)
  → 权重自动写入 learning_params
  → 下次 sync_all.py 运行时 MWU 从优化权重冷启动
```

### 4.2 查看市场状态权重

```
用户: 回测完成后，查看 "市场状态权重矩阵"
  → 趋势市场: MACD权重1.52（趋势跟踪强信号）
  → 震荡市场: RSI权重1.45（超买超卖检测）
  → 高波动: ATR权重1.18（波动率管理）
```

### 4.3 历史记录

```
用户: 在回测页底部查看历史记录
  → GET /api/v2/backtest/history
  → 每次运行的回测时间和主要指标
  → 可点击查看某次完整结果
```
