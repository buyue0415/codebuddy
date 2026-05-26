# 模块7: 新闻抓取模块

> **核心文件**: `scripts/fetch_news.py` | **数据源**: NeoData (westock-data) | **触发**: `POST /api/trigger/news`

---

## 1. 功能概述

遍历自选股列表，通过 Node.js 子进程调用 NeoData 新闻服务获取每只股票的新闻，解析 Markdown 表格格式输出，进行情感分析和重大性判断，去重后写入 SQLite 数据库。

---

## 2. 核心业务逻辑

### 2.1 抓取流程

```
1. 从 SQLite 读取 watchlist
2. 对每只股票调用 fetch_news_node(market_code, limit=20)
   → Node 子进程: node scripts/index.js news {market_code} --limit 20
3. 解码输出（gbk优先，utf-8 fallback）
4. 解析 Markdown 表格 → _parse_news_table(text) → _parse_news_row(row)
5. 情感分析: _detect_sentiment(title, summary)
6. 重大性判断: _is_major(title, summary)
7. 去重写入: 基于 (title, date, code) 检查 DB 已有记录
```

### 2.2 情感分析规则

基于标题+摘要的关键词匹配：

| 类型 | 关键词 |
|------|--------|
| **正向** | 上涨 / 净流入 / 买入 / 利好 / 增持 / 盈利 / 分红 / 看好 / 增长 / 回升 / 突破 / 新高 / 受捧 / 资金净流入 |
| **负向** | 下跌 / 净流出 / 卖出 / 利空 / 减持 / 亏损 / 风险 / 看跌 / 下滑 / 承压 / 跌破 / 抛压 / 资金净流出 / 融资净卖出 |

判定: `pos_count > neg_count → positive`, `neg_count > pos_count → negative`, 否则 `neutral`

### 2.3 重大新闻判断

标题+摘要包含以下任意关键字则标记为重大：
`重大 / 重磅 / 政策 / 利率 / 降准 / 加息 / 监管 / 央行 / 国务院`

### 2.4 Markdown 解析

NeoData 输出格式为 Markdown 表格：

| time | id | ... | symbol | title | url | ... | source | ... | summary |
|------|----|-----|--------|-------|-----|-----|--------|-----|---------|
| 2026-05-26 09:00 | 12345 | | sh601166 | 新闻标题 | url | | 证券之星 | | 摘要 |

解析步骤:
1. 查找分隔行 `|---` 定位数据起始行
2. 按 `|` 分割，取第 1 列 (time)、第 4 列 (symbol)、第 5 列 (title)、第 10 列 (source)、第 14 列 (summary)
3. 从 symbol 中正则提取 6 位代码: `re.search(r'(\d{6})', symbol)`

---

## 3. 输入输出参数定义

| 函数 | 输入 | 输出 |
|------|------|------|
| `fetch_news_node(market_code, limit=20)` | `"sh601166"` | `[{date, code, title, summary, source, url, sentiment, major, news_id}]` |
| `_parse_news_table(text)` | Markdown 表格字符串 | 新闻项列表 `[{...}]` |
| `_parse_news_row(row)` | 单行文本 | 新闻字典 或 `None`（解析失败） |
| `_detect_sentiment(title, summary)` | 标题 + 摘要 | `"positive"` / `"negative"` / `"neutral"` |
| `_is_major(title, summary)` | 标题 + 摘要 | `True` / `False` |
| `_extract_code(symbol)` | `"sh601166"` | `"601166"` |
| `main()` | — | 写入 **news** 表 + 打印统计 |

### 输出到数据库

**news** 表字段: `date, code, title, summary, source, sentiment, major`

---

## 4. 依赖关系

| 方向 | 模块 | 方式 |
|------|------|------|
| **外部依赖** | Node.js 运行时 | 子进程 |
| **外部依赖** | `westock-data` 插件 (`scripts/index.js`) | Node.js CLI |
| **内部依赖** | [数据库访问层](./02-database-layer.md) | `from db_helper import get_watchlist, get_db` |
| **被调用** | [Web API 层](./01-api-server.md) | `POST /api/trigger/news` → `run_script("fetch_news.py")` |
| **被导入** | [同步引擎](./03-sync-engine.md) | `from fetch_news import fetch_news_node, _parse_news_table` |

---

## 5. 异常处理机制

| 场景 | 处理 |
|------|------|
| Node.js 子进程失败 | 捕获异常，打印日志，返回空列表 |
| 编码异常 | 先尝试 gbk，fallback utf-8（Windows 兼容） |
| 单条新闻解析失败 | `_parse_news_row` 返回 None，被 `if item:` 过滤 |
| 单条 DB 写入失败 | 忽略单条异常继续下一条 |
| 批量去重 | 基于 `(title, date, code)` 检查 DB + 内存 set |
