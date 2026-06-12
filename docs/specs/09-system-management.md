# 09 — 管理设置

> **前端页面**: `deliverables/v2/src/pages/Management.vue` (12KB)
> **路由**: `/manage` | **菜单**: 个人交易数据 → 管理设置

---

## 1. 业务需求说明书

### 1.1 业务背景

用户需要一个集中管理页面，用于维护自选股列表、上传对账单、触发数据同步、导入专家报告等系统级操作。

### 1.2 核心目标

| 目标 | 说明 |
|------|------|
| 自选股管理 | 添加/删除自选股，含A股搜索和自动行情刷新 |
| 对账单上传 | 上传广发证券Excel对账单，自动解析持仓 |
| 系统触发 | 手动刷新行情/同步预测/抓取新闻/导入报告 |
| 状态监控 | 显示系统连接状态、监控股票数量 |

---

## 2. 技术方案深度分析

### 2.1 自选股增删

**添加流程**：
```
用户搜索 → GET /api/search/stocks?keyword=兴业
  → get_stock_search() 从 a_stocks.json 模糊匹配（含拼音）
  → 用户选择 → POST /api/v2/watchlist {code, name, market}
  → add_watchlist() 写入 watchlist + 标记 stocks.watchlist=1
  → 自动行情刷新（add_watchlist 内触发K线获取）
```

**删除流程**：
```
用户点击删除 → DELETE /api/v2/watchlist/{code}
  → remove_watchlist() 清理分析层数据（kline/predictions/learning）
  → 保留交易层数据（positions/trades/dividends）
```

### 2.2 对账单上传

```python
# server_v2.py:1421
@app.post("/api/upload/statement")
async def api_v2_upload_statement(file: UploadFile):
    # Layer 1: 文件大小检查（>100字节）
    # Layer 2: 魔数检测（PK\x03\x04 ZIP -> xlsx格式）
    # Layer 3: 保存 + 自动备份（.bak_{timestamp} + .upload_bak）
    # Layer 4: subprocess → update_from_statement.py → SQLite
```

---

## 3. 功能介绍和实现方式

### 3.1 API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/search/stocks?keyword=` | 搜索A股股票 |
| POST | `/api/v2/watchlist` | 添加自选股 |
| DELETE | `/api/v2/watchlist/{code}` | 删除自选股 |
| POST | `/api/upload/statement` | 上传对账单Excel |
| POST | `/api/trigger/predict` | 全量同步 |
| POST | `/api/trigger/news` | 抓取新闻 |
| POST | `/api/trigger/expert` | 导入专家报告 |
| POST | `/api/v2/quotes/refresh` | 刷新行情 |
| GET | `/api/audit` | 系统审计 |
| GET | `/api/v2/statement/status` | 对账单导入状态 |

### 3.2 前端实现

```vue
<!-- Management.vue 核心结构 -->
<template>
  <!-- 系统状态 -->
  <div class="status-bar">
    已连接 · 端口8766 · 监控{{ watchlist.length }}只股票
  </div>

  <!-- 自选股管理 -->
  <section>
    <h3>自选股管理</h3>
    <SearchBar @search="searchStocks" />
    <ResultList :results="searchResults" @add="addToWatchlist" />
    <WatchlistTable :data="watchlist" @remove="removeFromWatchlist" />
  </section>

  <!-- 对账单上传 -->
  <section>
    <h3>对账单上传</h3>
    <FileUpload accept=".xlsx" @upload="uploadStatement" />
    <UploadStatus :status="statementStatus" />
  </section>

  <!-- 系统操作 -->
  <section>
    <h3>系统操作</h3>
    <Button @click="triggerPredict">🔄 全量刷新</Button>
    <Button @click="triggerNews">📰 抓取新闻</Button>
    <Button @click="triggerExpert">📊 导入专家报告</Button>
    <Button @click="runAudit">🔍 系统审计</Button>
  </section>
</template>
```

### 3.3 搜索功能

```python
# db_helper.py:20
def get_stock_search(keyword):
    """A股模糊搜索，返回15条匹配结果"""
    # 从 stocks 表查询：代码匹配 + 名称匹配 + 拼音匹配
    db.execute("""
        SELECT code, name, market, py FROM stocks
        WHERE code LIKE ? OR name LIKE ? OR py LIKE ?
        LIMIT 15
    """, [f"%{kw}%", f"%{kw}%", f"%{kw}%"])
```

---

## 4. 用户操作流程

### 4.1 添加自选股

```
用户: 管理设置 → 搜索框输入 "兴业"
  → 搜索结果: 601166 兴业银行, 601997 贵阳银行, ...
  → 点击 "601166 兴业银行" 旁边的 [添加]
  → 前端: POST /api/v2/watchlist {code:"601166", name:"兴业银行", market:"sh"}
  → 后端: 添加到 watchlist 表 + 自动触发行情获取
  → 前端: 自选股列表刷新，显示新增股票
```

### 4.2 上传对账单

```
用户: 管理设置 → 点击 [上传对账单]
  → 选择桌面上的 "普通对账单结果查询.xlsx"
  → 前端: POST /api/upload/statement (multipart/form-data)
  → 后端: 保存 → 备份 → 解析 → 写入 DB
  → 返回: {success: true, message: "对账单已更新，刷新页面查看"}
  → 持仓/交易/分红数据自动更新
```

### 4.3 删除自选股

```
用户: 管理设置 → 自选股列表中点击 [删除]
  → 前端: 确认弹窗 → DELETE /api/v2/watchlist/601166
  → 后端: 清理分析层数据（kline/predictions/learning）
  → 保留交易层数据（历史 trades/dividends 不删除）
  → 前端: 自选股列表移除该项
```

### 4.4 系统审计

```
用户: 管理设置 → 点击 [🔍 系统审计]
  → GET /api/audit
  → 返回各股票数据完整性报告
  → 显示: K线条数/预测数/学习参数状态/新闻数等
```
