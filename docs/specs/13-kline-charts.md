# 13 — K线走势

> **前端页面**: `deliverables/v2/src/pages/Kline.vue` (39KB)
> **路由**: `/kline` | **菜单**: 股票信息收集 → K线走势

---

## 1. 业务需求说明书

### 1.1 业务背景

用户需要查看自选股的日K线和月K线图表，通过可视化分析历史价格走势，识别趋势、支撑位和阻力位。系统支持形态识别标注。

### 1.2 核心目标

| 目标 | 说明 |
|------|------|
| 日K线图表 | OHLC 蜡烛图，含成交量柱状图 |
| 月K线图表 | 按月聚合的 OHLC 走势 |
| 形态识别 | 自动标注头肩顶/双底等K线形态 |
| 技术指标叠加 | MA均线/Bollinger带等叠加显示 |

---

## 2. 技术方案深度分析

### 2.1 图表渲染

```javascript
// Kline.vue 使用 Chart.js + chartjs-chart-financial
// 蜡烛图: open/high/low/close 四值
// 成交量: 下方柱状图（涨红跌绿）
// 均线: MA5/MA10/MA20/MA60 叠加线
```

### 2.2 K线数据来源

| 周期 | 表 | 获取函数 | 数据量 |
|------|-----|---------|--------|
| 日K | kline_daily | `get_kline_daily(code)` | 2000条 |
| 月K | kline_monthly | `get_all_kline_monthly(codes)` | ~100条 |

### 2.3 月K线生成

```python
# sync_all.py Step 7
# 从日K线合成月OHLC:
#   open  = 当月第一条日K的 open
#   close = 当月最后一条日K的 close
#   high  = max(当月所有日K的 high)
#   low   = min(当月所有日K的 low)
#   change_pct = (当月close - 上月close) / 上月close
# 写入 kline_monthly 表
```

---

## 3. 功能介绍和实现方式

### 3.1 API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v2/kline/daily` | 批量日K线 |
| GET | `/api/v2/kline/daily/{code}` | 单股票日K线 |
| GET | `/api/v2/kline/monthly` | 批量月K线 |
| GET | `/api/v2/kline/monthly/{code}` | 单股票月K线 |
| GET | `/api/v2/pattern-scan/{code}` | 扫描K线形态 |

### 3.2 前端实现

```vue
<!-- Kline.vue 核心结构 -->
<template>
  <!-- 股票选择 + 周期切换 -->
  <Dropdown v-model="selectedCode" />
  <TabBar>
    <Tab label="日K" period="daily" />
    <Tab label="月K" period="monthly" />
  </TabBar>

  <!-- K线图表（Chart.js） -->
  <div class="chart-container">
    <canvas ref="chartCanvas" />
  </div>

  <!-- 形态标注 -->
  <PatternAnnotations :patterns="detectedPatterns" />

  <!-- 指标切换 -->
  <CheckboxGroup>
    <Checkbox label="MA5" v-model="showMA5" />
    <Checkbox label="MA10" v-model="showMA10" />
    <Checkbox label="MA20" v-model="showMA20" />
    <Checkbox label="MA60" v-model="showMA60" />
    <Checkbox label="Bollinger" v-model="showBollinger" />
  </CheckboxGroup>
</template>
```

### 3.3 动画效果

股票切换时使用 canvas 动画平滑过渡，避免突兀的画面跳跃。

---

## 4. 用户操作流程

### 4.1 查看日K线

```
用户: 导航栏 "股票信息收集" → "K线走势"

页面显示:
┌──────────────────────────────────────────────┐
│  K线走势    [兴业银行 ▼]  [日K] [月K]        │
│                                              │
│  ┌──────────────────────────────────────┐    │
│  │  📈 蜡烛图 (Chart.js)                │    │
│  │  ██████░░░░░██░░░░████░░░░           │    │
│  │  ─ MA5 ─ MA10 ─ MA20 ─ MA60         │    │
│  │                                      │    │
│  │  📊 成交量                           │    │
│  │  ▓▓▓▓░░▓▓▓▓░░░░▓▓░░░░               │    │
│  └──────────────────────────────────────┘    │
│                                              │
│  ☑ MA5  ☑ MA10  ☐ MA20  ☐ MA60  ☐ Boll    │
│  🔍 形态: 头肩底 (06-03), 双底 (05-15)      │
└──────────────────────────────────────────────┘
```

### 4.2 切换时间周期

```
用户: 点击 [月K] 标签
  → GET /api/v2/kline/monthly/601166
  → 图表切换为月K线数据
  → 显示多年月度走势
```

### 4.3 查看形态识别

```
用户: 日K图表中 hover 形态标注
  → 弹窗: "头肩底形态 · 2026-06-03"
  → "左肩 ¥16.80 | 头部 ¥16.20 | 右肩 ¥16.90"
  → "突破颈线 ¥17.30 → 理论目标 ¥18.40"

后端: GET /api/v2/pattern-scan/601166
  → pattern_engine.py 扫描识别
```
