# 14 — K线走势

> **页面文件**: `pages/Kline.vue` (820+行) | **路由**: `/kline`
> **Store**: `stores/data.js` (useDataStore) + `stores/industry.js` (useIndustryStore)
> **组件**: `IndustryGroupTabs.vue`
> **依赖**: Chart.js + chartjs-chart-financial（金融图表插件）

---

## 1. 业务需求说明书

### 1.1 业务背景

K线图是股票技术分析的基础工具，投资者需要查看日K和月K级别的价格走势、月度涨跌幅统计以及季节性规律。

### 1.2 核心目标

| 目标 | 说明 |
|------|------|
| 日K线图 | 使用 chartjs-chart-financial 绘制标准 OHLC 蜡烛图 |
| 月K线图 | 月度涨跌幅柱状图 + 日期范围筛选 + 缩放/平移滑块 |
| 季节性规律 | 按股票独立计算各月平均涨跌幅的柱状图 |
| 形态扫描 | 识别 K线形态并在图表上标注 |
| 行业切换 | IndustryGroupTabs 按行业和股票切换 |

---

## 2. 页面布局

```
┌──────────────────────────────────────────────────────────┐
│ IndustryGroupTabs: [银行] [保险] [证券]                  │
│ [兴业银行] [招商银行] [工商银行]                          │
├──────────────────────────────────────────────────────────┤
│ ┌─ 日K走势图 (Card 1) ─────────────────────────────────┐ │
│ │  Candlestick 蜡烛图 + SMA20/SMA60 + 分红标记 + 形态  │ │
│ │  ← 缩放/平移滑块 →                                  │ │
│ │  ┌─ 股息率(TTM推算) ──────────────────────────────┐  │ │
│ │  └─────────────────────────────────────────────────┘  │ │
│ └──────────────────────────────────────────────────────┘ │
│ ┌─ 月度涨跌幅 (Card 2) ───────────────────────────────┐ │
│ │  [开始日期] 至 [结束日期]  12个月 | 涨 8个 | 跌 4个 │ │
│ │  ████████████████ 柱状图（红涨绿跌）                │ │
│ │  ← 缩放/平移滑块 →                                │ │
│ └──────────────────────────────────────────────────────┘ │
│ ┌─ 季节性规律 (Card 3) ───────────────────────────────┐ │
│ │  1月 2月 3月 ... 12月 各月平均涨跌幅                │ │
│ └──────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────┘
```

---

## 3. 业务逻辑

### 3.1 日K线数据格式

```javascript
// 日K线数据: data.allKlineDaily[code]
// 从后端 API /api/v2/kline/daily 获取, store 自动注入
// 数组元素: [date_string, open, close, high, low]
// 前端转换为 candleData: { x: index, o, h, l, c }

// 移动平均线
const sma20 = calcSMA(closes, 20)
const sma60 = calcSMA(closes, 60)
```

### 3.2 月度涨跌幅柱状图

#### 数据来源

```javascript
const mcRaw = data.allKlineMonthly[code] || []
// 数组元素: [YYYY-MM-DD, open, high, low, close, volume, change_pct]
```

#### 涨跌幅计算

为避免后端 `change_pct` 字段缺失或为 0，前端从收盘价自行计算：

```javascript
// 相邻月份收盘价比较: (本月收盘 - 上月收盘) / 上月收盘 × 100
const mc = mcRaw.map((b, i) => {
  const prev = i > 0 ? mcRaw[i - 1] : null
  const prevClose = prev ? prev[4] : b[4]
  const cp = prevClose ? +((b[4] - prevClose) / prevClose * 100).toFixed(2) : 0
  return [b[0], cp]
})
```

#### 月份排序

数据从后端返回时按日期降序（最新在前），前端反转后按时间正序渲染图表。

#### 统计数据

```javascript
// 基于用户选择的日期范围 (mcStart ~ mcEnd) 计算:
// total:    总月数
// upCount:  上涨月份数   upAvg:   上涨月份平均涨幅
// downCount:下跌月份数   downAvg: 下跌月份平均跌幅
// maxUp:    最大月涨幅   maxDown: 最大月跌幅
// avg:      所有月份平均涨跌幅
```

#### 颜色规则

| 条件 | 颜色 | 说明 |
|------|------|------|
| 月涨幅 > 0 | `#dc2626` 红色 | 上涨（柱状图 + 统计数字） |
| 月涨幅 < 0 | `#16a34a` 绿色 | 下跌 |
| 月涨幅 = 0 | `#6b7280` 灰色 | 持平 |

#### 交互

- 日期筛选: 两个 `<input type="date">` 控制统计范围
- 缩放: Ctrl+滚轮缩放宽高
- 平移: 滚轮左右平移
- 滑块: 底部滑块支持拖动选择可见区间（默认显示最近60个月）
- 悬停: 显示当月涨跌幅详情 tooltip

### 3.3 季节性规律

```javascript
// 数据: data.seasonal[code]
// 格式: 长度为12的数组，各元素为对应月份的历史平均涨跌幅
// 例: [0.8, -2.5, 1.2, 0.5, -1.0, 2.3, ...]
// 索引0 = 1月, 索引11 = 12月
```

#### 计算方式

季节性因子按股票在 `scheduler.py` Step 3 中独立计算：

```python
# 从 kline_monthly 表读取该股票所有月度 change_pct
# 按日历月份 (1-12) 分组求算数平均
# 无月度数据的股票使用 DEFAULT_SEASONAL 回退
```

#### 前端渲染

```javascript
// Chart.js bar 控制器
labels: ['1月', '2月', ..., '12月']
data: sea  // 长度为12的数值数组
color: 正值→红色(#dc2626)  负值→绿色(#16a34a)
```

### 3.4 形态扫描

```javascript
// 切换股票时自动请求
GET /api/v2/pattern-scan/{code}

// 返回:
{ bullish: [{ name, idx, strength }], bearish: [{ name, idx, strength }] }

// 在 K线图底部 strip 区域用彩色圆点标注形态位置
// 黄色 = 看涨形态  紫色 = 看跌形态
// tooltip 中同步显示形态名称和强度
```

### 3.5 数据刷新监听

K线页面通过 watcher 自动感知数据更新，避免用户手动刷新：

```javascript
// 监视 store 中月度数据的引用变化
watch(() => data.allKlineMonthly[activeCode.value], (newData, oldData) => {
  if (activeCode.value && newData !== oldData) nextTick(renderAll)
})
```

触发场景：
- 用户点击"全量刷新"按钮
- 在管理页面添加/删除自选股后
- 数据同步完成后自动重渲染所有图表

---

## 4. 交互流程

```
挂载 → 加载watchlist
  → 设置 activeCode = 第一只股票
  → renderAll():
      1. 获取日K线 → 蜡烛图 + SMA + 分红标记
      2. 异步请求形态扫描
      3. 获取月K线 → 月度柱状图 + 统计
      4. 获取季节性 → 月均涨跌幅柱状图
      5. 异步请求股息率序列 → 子图
  → 切换股票 → 重新 renderAll()
  → store 数据更新 → 自动 renderAll()
```

---

## 5. 数据依赖

| API | 用途 | 数据来源 |
|-----|------|----------|
| GET /api/v2/kline/daily | 日K线 | useDataStore.allKlineDaily |
| GET /api/v2/kline/monthly | 月K线 | useDataStore.allKlineMonthly |
| GET /api/v2/seasonal | 季节性因子 | useDataStore.seasonal |
| GET /api/v2/pattern-scan/{code} | 形态扫描 | 独立API调用 |
| GET /api/v2/dividend-yield-series | 股息率序列 | 独立API调用 |

---

## 6. K线颜色规则

| 条件 | 颜色 | 说明 |
|------|------|------|
| close > open | `#ef4444` 红色 | 上涨阳线 (蜡烛图) |
| close < open | `#16a34a` 绿色 | 下跌阴线 (蜡烛图) |
| 月度涨 > 0 | `#dc2626` 红色 | 月度上涨 (柱状图) |
| 月度涨 < 0 | `#16a34a` 绿色 | 月度下跌 (柱状图) |
| 季节性 > 0 | `#dc2626` 红色 | 历史月均上涨 |
| 季节性 < 0 | `#16a34a` 绿色 | 历史月均下跌 |
