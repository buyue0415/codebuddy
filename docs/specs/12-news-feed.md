# 12 — 新闻动态

> **前端页面**: `deliverables/v2/src/pages/News.vue` (21KB)
> **路由**: `/news` | **菜单**: 股票信息收集 → 新闻动态

---

## 1. 业务需求说明书

### 1.1 业务背景

用户需要及时获取自选股相关的最新财经新闻，了解市场动态。系统从 NeoData（东方财富）自动抓取新闻，并进行情感分析和重大性判断，帮助用户快速识别利好/利空信息。

### 1.2 核心目标

| 目标 | 说明 |
|------|------|
| 自动新闻抓取 | 遍历自选股从东方财富API获取最新新闻 |
| 情感分析 | 自动标注 positive/negative/neutral |
| 重大性判断 | 检测重大/重磅/政策/监管等关键词 |
| 多维度筛选 | 全部新闻/重大新闻/单股票筛选 |

---

## 2. 技术方案深度分析

### 2.1 情感分析规则

基于标题+摘要关键词匹配：

| 类型 | 关键词 |
|------|--------|
| 正向 | 上涨/净流入/买入/利好/增持/盈利/分红/看好/增长/突破/新高 |
| 负向 | 下跌/净流出/卖出/利空/减持/亏损/风险/看跌/下滑/承压/跌破 |
| 判定 | pos_count > neg_count → positive，否则 negative → neutral |

### 2.2 重大新闻判断

标题+摘要包含以下关键词标记为重大：
`重大/重磅/政策/利率/降准/加息/监管/央行/国务院`

### 2.3 数据流

```
POST /api/trigger/news
  → subprocess.run(fetch_news.py)
  → 遍历 watchlist → Node.js subprocess → NeoData API
  → 解析 Markdown 表格 → 情感分析 → 去重
  → upsert_news() 写入 SQLite

GET /api/v2/news
  → get_news(filter_type) → News.vue 渲染
```

---

## 3. 功能介绍和实现方式

### 3.1 API 端点

| 方法 | 路径 | 参数 | 说明 |
|------|------|------|------|
| GET | `/api/v2/news` | — | 获取全部新闻 |
| POST | `/api/trigger/news` | — | 手动触发新闻抓取 |

### 3.2 后端实现

```python
# fetch_news.py 核心函数

def fetch_news_node(market_code, limit=20):
    """Node.js 子进程 → NeoData 新闻 API"""
    # node scripts/index.js news sh601166 --limit 20
    # 解码: gbk优先 → utf-8 fallback

def _parse_news_table(text):
    """解析 Markdown 表格:
    | time | id | ... | symbol | title | ... | source | ... | summary |
    """

def _detect_sentiment(title, summary):
    """关键词匹配 → positive/negative/neutral"""

def _is_major(title, summary):
    """检查是否含重大新闻关键词"""
```

### 3.3 数据库存储

**news 表**:
```
id, date, code, title, summary, source, sentiment, major
```

### 3.4 前端实现

```vue
<!-- News.vue 核心结构 -->
<template>
  <!-- 筛选栏 -->
  <TabBar>
    <Tab label="全部新闻" filter="all" />
    <Tab label="重大新闻" filter="major" />
  </TabBar>
  <Dropdown v-model="filterCode" />

  <!-- 新闻列表 -->
  <NewsList :items="news">
    <NewsCard v-for="item in news">
      <Badge :type="item.sentiment" />
      <Badge v-if="item.major" type="major" text="重大" />
      <h4>{{ item.title }}</h4>
      <p>{{ item.summary }}</p>
      <span>{{ item.source }} · {{ item.date }}</span>
    </NewsCard>
  </NewsList>
</template>
```

---

## 4. 用户操作流程

### 4.1 查看新闻

```
用户: 导航栏 "股票信息收集" → "新闻动态"

页面显示:
┌──────────────────────────────────────────┐
│  新闻动态    [全部新闻] [重大新闻]        │
│              [全部股票 ▼]                │
│                                          │
│  ┌─ 🟢 增持评级 ─────────────────────┐  │
│  │ 🔴 重大                          │  │
│  │ 兴业银行获多家机构增持评级...      │  │
│  │ 证券之星 · 06-05                  │  │
│  └───────────────────────────────────┘  │
│  ┌─ 🔴 资金净流出 ───────────────────┐  │
│  │ 招商银行主力资金净流出3.2亿...      │  │
│  │ 东方财富 · 06-05                  │  │
│  └───────────────────────────────────┘  │
└──────────────────────────────────────────┘

数据来源: GET /api/v2/news
```

### 4.2 筛选重大新闻

```
用户: 点击 [重大新闻] 标签
  → 仅显示 major=1 的新闻
  → 关键字: 政策/利率/监管/央行等
```

### 4.3 按股票筛选

```
用户: 下拉选择 "601166 兴业银行"
  → 仅显示该股票的新闻
  → GET /api/v2/news (后端按 code 过滤)
```
