# 19 — 行业股票选择器组件

> **组件文件**: `components/IndustryGroupTabs.vue` + `components/StockSelector.vue`
> **Store**: `stores/industry.js` (useIndustryStore)
> **API**: GET /api/v2/industries
> **用途**: 可复用的行业分类 + 股票筛选组件，用于5个分析页面

---

## 1. 业务需求说明书

### 1.1 业务背景

多个分析页面（智能预测、专家分析、新闻动态、K线走势、公司关系图谱）需要按行业分类切换股票的功能。需要一个可复用组件统一实现。

### 1.2 核心目标

| 目标 | 说明 |
|------|------|
| 行业分组 | 将自选股按行业分类展示 |
| 二级Tab切换 | 行业标签 → 股票标签，两层级 |
| 数据共享 | 通过 useIndustryStore 共享行业数据 |
| 回退处理 | 无行业信息的股票归为"未分类" |
| 搜索过滤 | 支持按行业/股票名称/代码实时搜索 |

---

## 2. IndustryGroupTabs 组件

### 2.1 Props

| Prop | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| stocks | Array | [] | 股票列表 `[{code, name}]` |
| activeCode | String | '' | 当前选中的股票代码 |
| excludeCodes | Array | [] | 排除的股票代码列表 |

### 2.2 Events

| Event | 参数 | 说明 |
|-------|------|------|
| switch | (code: String) | 切换股票时触发 |

### 2.3 行业分组逻辑

```javascript
// 1. 从 industryStore.flatStocks 建立 code→industry 映射
// 2. 根据 props.stocks 按行业分组
// 3. "未分类"排在最后
// 4. 切换行业时自动更新 activeIndustry
// 5. 外部 activeCode 变化时自动同步到对应行业
```

### 2.4 渲染结构

```
┌─ 行业一级标签 ──────────────────────────────────────┐
│ [银行(3)] [保险(1)] [证券(1)]                        │
├─ 股票二级标签 ──────────────────────────────────────┤
│ [兴业银行] [招商银行] [工商银行]                      │
└──────────────────────────────────────────────────────┘
```

---

## 3. StockSelector 组件

### 3.1 Props

| Prop | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| mode | String | 'watchlist-add' | 模式: watchlist-add / select |
| modelValue | Object | null | v-model 绑定（select模式） |
| watchlistOnly | Boolean | false | 是否仅显示自选股 |

### 3.2 Events

| Event | 参数 | 说明 |
|-------|------|------|
| update:modelValue | stock | select模式选中事件 |
| add-to-watchlist | stock | 添加到自选股事件 |

### 3.3 功能

- 搜索框：实时过滤行业/股票名称/代码
- 行业标签：按行业分组展示
- 股票列表：显示名称/代码/市场
- 添加按钮：mode=watchlist-add时显示"＋添加"
- 本地状态：已添加的自选股显示"✓ 已添加"
- 消息提示：操作成功/失败3秒自动消失

---

## 4. useIndustryStore

### 4.1 State

| 字段 | 类型 | 说明 |
|------|------|------|
| industries | Array | 行业分组列表 `[{industry, stocks, stock_count}]` |
| loading | Boolean | 加载状态 |
| error | String | 错误信息 |
| loadedAt | Number | 加载时间戳 |

### 4.2 Computed

| 字段 | 类型 | 说明 |
|------|------|------|
| industryNames | Array | 行业名称列表 |
| flatStocks | Array | 展平股票列表（含industry字段） |
| totalStocks | Number | 总股票数 |

### 4.3 Actions

| 方法 | 说明 |
|------|------|
| fetchIndustries() | 加载行业数据 |
| refreshIndustries() | 强制刷新行业数据 |
| markWatchlistStocks(codes, inWatchlist) | 本地乐观更新自选股标记 |

---

## 5. 数据依赖

| API | 用途 |
|-----|------|
| GET /api/v2/industries | 行业+股票列表 |

---

## 6. 使用示例

```vue
<!-- 在分析页面中使用 IndustryGroupTabs -->
<template>
  <IndustryGroupTabs
    :stocks="watchlist"
    :activeCode="currentCode"
    :excludeCodes="['601398']"
    @switch="onSwitchStock"
  />
</template>

<!-- 在管理页面中使用 StockSelector -->
<template>
  <StockSelector
    mode="watchlist-add"
    @add-to-watchlist="onAdd"
  />
</template>
```
