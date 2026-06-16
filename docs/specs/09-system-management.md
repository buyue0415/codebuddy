# 09 — 管理设置

> **页面文件**: `pages/Management.vue` (19.96 KB, 485行) | **路由**: `/manage`
> **Store**: `stores/data.js` (useDataStore) + `stores/industry.js` (useIndustryStore)
> **组件**: `StockSelector.vue` | **API**: 自选股CRUD / 对账单上传 / 专家报告导入 / 服务器状态

---

## 1. 业务需求说明书

### 1.1 业务背景

系统需要管理入口来维护自选股列表、上传对账单、导入专家报告，以及查看系统运行状态。

### 1.2 核心目标

| 目标 | 说明 |
|------|------|
| 自选股管理 | 搜索、添加、删除自选股 |
| 对账单上传 | 上传广发证券对账单 ZIP 文件并解析 |
| 专家报告导入 | 导入外部AI生成的专家分析报告 |
| 服务器状态 | 查看服务器运行状态、数据源连通性 |
| 系统配置 | 展示和修改系统费率等配置 |

---

## 2. 页面布局

```
┌──────────────────────────────────────────────────────────┐
│ ┌─ 自选股管理 ─────────────────────────────────────────┐ │
│ │ ┌─ [StockSelector 组件 ── 搜索股票/行业筛选/添加] ─┐ │ │
│ │ │  搜索: [______________] 4596只                     │ │
│ │ │  [银行] [保险] [证券] [白酒] ...                   │ │
│ │ │  ┌─ 兴业银行(601166) sh  [＋ 添加]                 │ │
│ │ │  │ 招商银行(600036) sh  [＋ 添加]                  │ │
│ │ │  └─ 工商银行(601398) sh  [＋ 添加]                 │ │
│ │ └────────────────────────────────────────────────────┘│ │
│ │ ┌─ 已添加的自选股 ───────────────────────────────┐    │ │
│ │ │ 兴业银行 601166 [删除]                          │    │ │
│ │ │ 招商银行 600036 [删除]                          │    │ │
│ │ └────────────────────────────────────────────────┘    │ │
│ └───────────────────────────────────────────────────────┘│
│                                                          │
│ ┌─ 对账单上传 ─────────────────────────────────────────┐ │
│ │  选择文件: [选择文件]  broker_statement.zip          │ │
│ │  [上传并解析]                                        │ │
│ │  状态: 上次上传 2026-06-15，解析成功 (3条新持仓)    │ │
│ │  (仅支持广发证券对账单 ZIP 格式)                     │ │
│ └───────────────────────────────────────────────────────┘│
│                                                          │
│ ┌─ 专家报告导入 ───────────────────────────────────────┐ │
│ │  选择文件: [选择文件]  report.json                    │ │
│ │  [导入]                                               │ │
│ │  状态: 上次导入 2026-06-14，导入成功 (1条报告)       │ │
│ └───────────────────────────────────────────────────────┘│
│                                                          │
│ ┌─ 系统信息 ───────────────────────────────────────────┐ │
│ │  服务器: 127.0.0.1:8766 运行中                        │ │
│ │  数据源: NeoData [已连接] / Westock [未配置]           │ │
│ │  数据库: stock.db (5.72MB) 27张表                     │ │
│ │  最后同步: 2026-06-16 10:01:35                        │ │
│ │  [全量刷新]                                           │ │
│ └───────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────┘
```

---

## 3. 业务逻辑

### 3.1 自选股管理

使用 `StockSelector.vue` 组件：

| 功能 | 实现 |
|------|------|
| 搜索 | 实时过滤行业名称/股票名称/股票代码 |
| 行业分组 | 二级切换：行业标签 → 股票列表 |
| 添加 | 点击 → POST /api/v2/watchlist → 本地乐观更新CSS类 |
| 删除 | 点击当前自选股删除按钮 → DELETE /api/v2/watchlist/{code} |
| 状态同步 | 添加后 industryStore.markWatchlistStocks() 更新本地状态 |

### 3.2 对账单上传

```javascript
async function uploadStatement(file) {
    const formData = new FormData()
    formData.append('file', file)
    const r = await fetch('/api/upload/statement', { method: 'POST', body: formData })
    // 后端验证:
    //   1. 文件大小 > 100 字节
    //   2. 魔数 PK\x03\x04 (ZIP格式)
    // 通过后 subprocess → update_from_statement.py
    // 解析结果写入 SQLite
    // 完成后前端自动刷新所有数据
}
```

### 3.3 专家报告导入

```javascript
async function importExpertReport(file) {
    const formData = new FormData()
    formData.append('file', file)
    const r = await apiCall('POST', '/api/v2/expert/import', formData)
    // 后端解析报告 JSON → 写入 expert_reports 表
    // 完成后前端刷新专家报告列表
}
```

专家报告 JSON 格式（根据 `data/expert_report_template.md`）：

```json
{
  "code": "601166",
  "date": "2026-06-15",
  "summary": "兴业银行...",
  "decision": "buy",
  "confidence": 85,
  "risk_level": 2,
  "data": {
    "technical": { "...": "..." },
    "fundamental": { "...": "..." },
    "sentiment": { "...": "..." },
    "debate": { "bullish": [...], "bearish": [...] },
    "risk_assessment": { "...": "..." }
  }
}
```

---

## 4. 交互流程

```
路由 /manage → 组件挂载
  → useIndustryStore.fetchIndustries() 加载行业数据
  → StockSelector 组件渲染行业标签和股票列表
  → 加载当前 watchlist 展示已添加股票
```

### 4.1 自选股管理操作
```
搜索股票 → 输入文本 → 300ms 防抖 → 过滤行业/股票
添加自选股 → POST /api/v2/watchlist → 本地乐观更新
删除自选股 → DELETE /api/v2/watchlist/{code} → 列表即时更新
```

### 4.2 对账单上传流程
```
选择 ZIP 文件 → 点击上传
  → POST /api/upload/statement (multipart)
  → 后端校验 → subprocess update_from_statement.py
  → 解析写入 SQLite
  → 返回结果 → 前端刷新数据
```

### 4.3 全量刷新
```
点击 [全量刷新]
  → useDataStore.triggerFullRefresh()
  → POST /api/trigger/predict
  → 后端运行 sync_all.py
  → 完成后重载数据
```
