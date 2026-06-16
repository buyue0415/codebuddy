# 18 — 公司关系图谱

> **前端页面**: `deliverables/v2/src/pages/CompanyGraph.vue` (新建)
> **路由**: `/company-graph` | **菜单**: 股票信息收集 → 公司关系图谱
> **新增依赖**: `@antv/g6` | **后端**: SQLite + FastAPI（不变）

---

## 1. 业务需求说明书

### 1.1 业务背景

股票投资不仅关注单只公司的基本面，还需要理解投资组合中各公司之间的隐性关联。通过企业关系图谱，用户可以直观了解所持股票之间的股权结构、高管交叉任职、供应链上下游以及行业竞争关系，辅助投资决策。

### 1.2 核心目标

| 目标 | 说明 |
|------|------|
| **股权结构** | 展示自选股前十大股东网络，标注持股比例和控股方向 |
| **高管关联** | 展示董事/监事/高管在不同公司的兼任关系 |
| **供应链网络** | 展示前五大供应商和客户关系，标注采购/销售比例 |
| **竞争关系** | 基于行业分类标注同行业竞争对手 |
| **主营业务** | 展示每家公司的核心主营业务描述（从东方财富公司概况采集） |
| **图谱交互** | 力导向图可视化，支持筛选/拖拽/缩放/点击查看详情 |
| **数据采集** | 通过东方财富公开API自动获取关系数据和主营业务信息，持久化到SQLite |

### 1.3 用户角色

| 角色 | 使用场景 |
|------|---------|
| 个人投资用户 | 查看自选股组合的关联网络，发现隐性风险（如过度集中持股、供应链依赖等） |

### 1.4 术语表

| 术语 | 说明 |
|------|------|
| 股权关系 | 公司间通过持股形成的权益关联，标注持股比例 |
| 高管关联 | 同一人在多家公司担任高管（董事/监事/高管）形成的关联 |
| 供应链关系 | 上下游供应商/客户关系，区分采购和销售方向 |
| 竞争关系 | 同行业或同业务领域的竞争企业关系 |
| 主营业务 | 公司核心经营业务描述，展示公司的商业模式和收入来源 |

---

## 2. 技术方案深度分析

### 2.1 架构概览

```mermaid
flowchart LR
    subgraph DS["数据源"]
        EM[东方财富 股东/高管/供应商/公司概况API]
        AS[a_stocks.json 行业分类]
    end
    subgraph SCR["采集脚本"]
        FC[fetch_company_relations.py 🔹新增]
    end
    subgraph DB["存储"]
        ST[(SQLite stock.db)]
        CR[company_relations 表 🔹新增]
        CB[company_business 表 🔹新增]
    end
    subgraph API["API层"]
        SV[server_v2.py 🔹新增3端点]
    end
    subgraph FE["前端"]
        CG[CompanyGraph.vue 🔹新增]
        G6[@antv/g6 力导向图]
        PS[Pinia companyGraph store 🔹新增]
    end

    EM-->FC
    AS-->FC
    FC-->CR
    FC-->CB
    CR-->SV
    CB-->SV
    SV-->CG
    G6-->CG
    PS-->CG
```

### 2.2 数据模型

#### company_relations 表 — 关系数据存储

```sql
CREATE TABLE IF NOT EXISTS company_relations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL,              -- 源股票代码（如 "601166"）
    related_code TEXT NOT NULL,      -- 关联对象代码（股票代码或人员ID）
    related_name TEXT NOT NULL,      -- 关联对象名称
    relation_type TEXT NOT NULL,     -- 关系大类: equity(股权)/executive(高管)/supply(供应链)/competition(竞争)
    relation_subtype TEXT DEFAULT '',-- 子类型: shareholder/hold/chairman/director/
                                     --          supervisor/supplier/customer/competitor
    relation_detail TEXT DEFAULT '', -- 关系详情描述（如"前十大股东-第1位"、"持股2.83%"）
    weight REAL DEFAULT 1.0,        -- 关系权重: 持股比例(%) / 供应链占比(%) / 重要性评分
    direction TEXT DEFAULT '',       -- 方向: in(被持股/上游流入)/out(持股/下游流出)/both(双向)
    extra_data TEXT DEFAULT '',      -- JSON扩展字段（如 {"share_pct":2.83,"rank":1,"position":"董事长"}）
    source TEXT DEFAULT 'web',       -- 数据来源: web(东方财富采集)/manual(手动录入)
    updated_at TEXT DEFAULT (datetime('now','localtime')),
    UNIQUE(code, related_code, relation_type, relation_subtype)
);

CREATE INDEX IF NOT EXISTS idx_cr_code ON company_relations(code);
CREATE INDEX IF NOT EXISTS idx_cr_type ON company_relations(relation_type);
CREATE INDEX IF NOT EXISTS idx_cr_relcode ON company_relations(related_code);
```

#### company_business 表 — 主营业务信息存储

```sql
CREATE TABLE IF NOT EXISTS company_business (
    code TEXT PRIMARY KEY,           -- 股票代码（如 "601166"）
    name TEXT NOT NULL,              -- 公司名称
    industry TEXT DEFAULT '',        -- 所属行业（如 "银行"）
    business TEXT DEFAULT '',        -- 主营业务描述
    source TEXT DEFAULT 'web',       -- 数据来源
    updated_at TEXT DEFAULT (datetime('now','localtime'))
);
```

### 2.3 数据采集策略

| 关系类型 | 数据来源 | API 接口 | 采集逻辑 |
|---------|---------|----------|---------|
| 股权结构(equity) | 东方财富股东研究 | `PC_HSF10/ShareholderResearch/PageAjax` | 取前十大股东，构建"公司→股东"持股关系，股东名相同则建立"股东→另一公司"关系 |
| 高管关联(executive) | 东方财富高管信息 | `PC_HSF10/Manager/PageAjax` | 取董监高名单，同一人名出现在多家公司则建立"人员→公司"兼任关系 |
| 供应链(supply) | 东方财富经营分析 | `PC_HSF10/Business/PageAjax` | 取前五大供应商/客户名称及占比，构建供应关系 |
| 竞争(competition) | a_stocks.json 行业分类 | 本地文件读取 | 根据股票行业代码匹配同行业其他A股公司 |
| 主营业务 | 东方财富公司概况 | `PC_HSF10/Company/PageAjax` | 获取公司核心业务描述，关联到节点详情展示 |

**代码格式转换**：东方财富API使用 `SH601166` 格式，系统内部统一使用 `601166` 无前缀格式。

### 2.4 前端 API 数据结构

`GET /api/v2/company-relations` 返回格式与 G6 兼容：

```json
{
  "success": true,
  "data": {
    "nodes": [
      { "id": "601166", "label": "兴业银行", "type": "stock",
        "code": "601166", "name": "兴业银行", "industry": "银行",
        "business": "企业金融业务、零售银行业务、金融市场业务" },
      { "id": "600036", "label": "招商银行", "type": "stock",
        "code": "600036", "name": "招商银行", "industry": "银行",
        "business": "零售金融业务、批发金融业务、财富管理业务" },
      { "id": "person_张", "label": "张XX", "type": "person" },
      { "id": "holder_香港中央结算", "label": "香港中央结算", "type": "company" }
    ],
    "edges": [
      { "source": "601166", "target": "holder_香港中央结算",
        "type": "equity", "subtype": "shareholder",
        "label": "持股2.83%", "weight": 2.83,
        "detail": "前十大股东-第1位", "direction": "in" },
      { "source": "person_张", "target": "601166",
        "type": "executive", "subtype": "director",
        "label": "独立董事", "weight": 1.0,
        "detail": "兴业银行独立董事", "direction": "both" }
    ]
  }
}
```

### 2.5 为什么用 @antv/g6

| 对比项 | vis-network | @antv/g6 v5 |
|--------|------------|-------------|
| 布局算法 | 仅力导向 | 力导向+同心圆+环形+Dagre等10+种 |
| 千级节点性能 | 卡顿 | LOD分级渲染，性能优秀 |
| 交互定制 | 有限 | 自定义Behavior/Shape/Animation |
| 中文文档 | 无 | 蚂蚁金服官方维护，文档完善 |
| 后续多股扩展 | 单一布局限制 | 可切换同心圆(按行业聚类)/环形(按类型排列) |

---

## 3. 功能介绍和实现方式

### 3.1 API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v2/company-relations` | 获取图谱数据，支持 `?type=equity|executive|supply|competition` 筛选 |
| GET | `/api/v2/company-relations/stats` | 获取四类关系数量统计 |
| POST | `/api/v2/company-relations/refresh` | 触发东方财富数据采集（子进程调用 fetch_company_relations.py） |

### 3.2 后端实现

#### 3.2.1 db_helper.py 新增函数

```python
def init_company_relations_tables():
    """创建 company_relations 表、company_business 表和索引（幂等）"""
    # 执行 CREATE TABLE IF NOT EXISTS + CREATE INDEX IF NOT EXISTS

def get_company_relations(code=None, type_filter=None):
    """获取关系数据
    Args:
        code: 股票代码过滤（可选）
        type_filter: 关系类型过滤 equity/executive/supply/competition（可选）
    Returns: 所有匹配的关系行列表
    """

def upsert_company_relation(record):
    """插入或更新一条关系记录（UNIQUE冲突时更新）"""

def clear_company_relations(type_filter=None):
    """清除关系数据（刷新前调用），可选按类型清除"""

def delete_company_relations_by_code(code, type_filter=None):
    """删除某只股票的所有关系数据"""

def get_company_business(codes=None):
    """获取公司主营业务信息
    Args:
        codes: 股票代码列表（可选）None表示返回全部
    Returns: {code: {name,industry,business}} 字典
    """

def upsert_company_business(record):
    """插入或更新一条主营业务记录（code冲突时更新）"""
```

#### 3.2.2 server_v2.py 新增端点

参考现有模式（如 `pattern-rules` 端点，第2010行），使用 `api_response()` 统一格式。

```python
# GET /api/v2/company-relations
@app.get("/api/v2/company-relations")
def api_company_relations_get(type: str = Query(default="")):
    """
    获取公司关系图谱数据
    - type 为空：返回全部关系
    - type=equity|executive|supply|competition：按类型筛选
    返回值：{success, data: {nodes: [...], edges: [...]}}
    """

# GET /api/v2/company-relations/stats
@app.get("/api/v2/company-relations/stats")
def api_company_relations_stats():
    """
    获取各类关系数量统计
    返回值：{success, data: {equity: N, executive: N, supply: N, competition: N, total: N}}
    """

# POST /api/v2/company-relations/refresh
@app.post("/api/v2/company-relations/refresh")
def api_company_relations_refresh():
    """
    触发关系数据采集
    通过 subprocess 调用 scripts/fetch_company_relations.py
    返回值：{success, message, output}
    """
```

#### 3.2.3 采集脚本 `scripts/fetch_company_relations.py`

```
采集流程：
1. 从 watchlist 表读取自选股列表
2. 清空 company_relations 表（刷新模式）
3. 对每只自选股：
   a. 调用东方财富公司概况API → 写入 company_business 表（主营业务、所属行业）
   b. 调用东方财富股东研究API → 写入股权关系
   c. 调用东方财富高管信息API → 写入高管关系
   d. 调用东方财富经营分析API → 写入供应链关系
4. 从 a_stocks.json 读取行业分类 → 写入竞争关系
5. 输出统计结果
```

### 3.3 前端实现

#### 3.3.1 页面布局（从上至下5区块）

```
┌──────────────────────────────────────────────────────┐
│  🔹 公司关系图谱    [全部][股权][高管][供应链][竞争]  │ ← 顶部操作栏
│                                    [🔄 刷新] 上次:X  │
├──────────────────────────────────────────────────────┤
│  ● 股权 10条  ● 高管 8条  ● 供应链 3条  ● 竞争 20条 │ ← 统计摘要栏
├──────────────────────────────────────────────────────┤
│  ─── 股权(蓝)  ┉┉ 高管(紫)  ─▶ 供应链(橙)  ═══ 竞(红)│ ← 图例行
├──────────────────────────────────────────────────────┤
│                                                      │
│        [G6 力导向网络图渲染区域]                       │ ← 主图谱区
│        ○ 兴业银行 ——— 香港中央结算                     │    背景 #f8fafc
│        ○ 招商银行 ⋮⋮⋮ 张XX                            │
│        ○ 工商银行 ═══ 建设银行                         │
│                                                      │
├─────────────────────────────────────┬────────────────┤
│                                     │  节点详情面板    │ ← 右侧滑入
│                                     │  兴业银行(601166)│    宽度320px
│                                     │  行业: 银行      │
│                                     │  ───────────    │
│                                     │  关联关系:       │
│                                     │  香港中央结算(股权)│
│                                     │  持股2.83%      │
│                                     │  张XX(高管)      │
│                                     │  独立董事        │
└─────────────────────────────────────┴────────────────┘
```

#### 3.3.2 G6 配置方案

```javascript
// G6 实例化配置要点
const graph = new Graph({
  container: 'graph-container',
  width: containerWidth,
  height: containerHeight,
  // 默认力导向布局
  layout: {
    type: 'force',
    preventOverlap: true,
    nodeStrength: -200,
    edgeStrength: 0.1,
  },
  // 节点配置
  node: {
    style: (model) => ({
      size: model.type === 'stock' ? 42 : model.type === 'person' ? 30 : 32,
      fill: model.type === 'stock' ? '#2563eb'
          : model.type === 'person' ? '#8b5cf6'
          : '#94a3b8',
      labelText: model.label,
      labelFill: '#ffffff',
      labelFontSize: model.type === 'stock' ? 14 : 12,
    }),
  },
  // 边配置
  edge: {
    style: (model) => ({
      stroke: model.type === 'equity' ? '#3b82f6'
            : model.type === 'executive' ? '#8b5cf6'
            : model.type === 'supply' ? '#f59e0b'
            : '#ef4444',
      lineWidth: model.type === 'equity' ? Math.max(1, model.weight * 0.3) : 1.5,
      lineDash: model.type === 'executive' ? [5, 5]
              : model.type === 'competition' ? [4, 4, 4, 4]
              : undefined,
      labelText: model.label || '',
      endArrow: model.type === 'supply',
    }),
  },
  behaviors: ['drag-canvas', 'zoom-canvas', 'drag-element'],
});
```

`GET /api/v2/company-relations` 接口在构建节点数据时，会联合查询 `company_business` 表，为每个 `type=stock` 或 `type=company` 的节点注入 `business` 和 `industry` 字段。`type=person` 的节点不包含这些字段。

#### 3.3.3 交互实现

| 交互 | 实现方式 |
|------|---------|
| 类型筛选 | 顶部 tab-btn 切换，调用 `graph.changeData(filteredData)` |
| 节点点击高亮 | 自定义 `click` behavior：选中节点+直达边透明度保持1.0，其余0.1 |
| 悬停 tooltip | G6 `tooltip` 插件，显示公司全称、代码和主营业务简述 |
| 详情面板 | Vue 响应式状态 `selectedNode`，点击节点时赋值，侧面板条件渲染 |
| 画布空白点击 | 取消选中，关闭详情面板 |
| 窗口自适应 | `onMounted` 时监听 `resize` 事件，调用 `graph.resize()` |
| 刷新 | 调用 `POST /api/v2/company-relations/refresh`，完成后重新加载数据 |

#### 3.3.4 Pinia Store

创建 `deliverables/v2/src/stores/companyGraph.js`：

```javascript
// companyGraph.js — 图谱数据状态管理
export const useCompanyGraphStore = defineStore('companyGraph', () => {
  const loading = ref(false)
  const refreshing = ref(false)
  const error = ref(null)
  const graphData = ref({ nodes: [], edges: [] })
  const stats = ref({ equity: 0, executive: 0, supply: 0, competition: 0, total: 0 })
  const lastRefresh = ref('')

  async function fetchData(type = '') { /* GET /api/v2/company-relations */ }
  async function fetchStats() { /* GET /api/v2/company-relations/stats */ }
  async function triggerRefresh() { /* POST /api/v2/company-relations/refresh */ }

  return { loading, refreshing, error, graphData, stats, lastRefresh,
           fetchData, fetchStats, triggerRefresh }
})
```

### 3.4 启动初始化

`server_v2.py` 启动时自动调用 `init_company_relations_tables()` 建表（类似于 `init_backtest_tables()` 的模式），仅在表不存在时执行。

---

## 4. 用户操作流程

### 4.1 查看关系图谱

```
用户: 导航栏 "股票信息收集" → "公司关系图谱"

页面初始加载:
┌───────────────────────────────────────────────────────────┐
│  🔹 公司关系图谱  [全部][股权][高管][供应链][竞争] [🔄刷新]│
│  ● 股权 10  ● 高管 8  ● 供应链 3  ● 竞争 20             │
│  ───股权(蓝) ┉┉高管(紫) ─▶供应(橙) ═══竞争(红)          │
├───────────────────────────────────────────────────────────┤
│  [力导向布局，自动计算节点位置]                            │
│                                                           │
│      ○ 兴业银行 ──── 香港中央结算                          │
│          ╲         ╱                                      │
│           ○ 招商银行                                       │
│          ╱         ╲                                      │
│      ○ 工商银行 ──── 中国平安                              │
│                                                           │
│  * 自选股为蓝色大圆节点                                    │
│  * 外部公司为灰色小圆节点                                  │
│  * 人员为紫色菱形节点                                      │
└───────────────────────────────────────────────────────────┘
```

### 4.2 按类型筛选

```
用户: 点击 [股权] 标签

图谱变化:
- 仅显示 equity 类型的关系边
- 布局重新计算
- 统计栏高亮"股权"
- 其他关系类型的边和无关节点隐藏
```

### 4.3 查看节点详情

```
用户: 点击 "兴业银行" 节点

交互反馈:
- 兴业银行节点 + 边框高亮放大
- 所有直接关联边保持不透明
- 其余元素透明度降至 0.1
- 右侧滑入详情面板:

┌──────────────────────────┐
│ 兴业银行           [✕]   │
│ 代码: 601166              │
│ 行业: 银行                │
│ 类型: 自选股              │
│                          │
│ 📋 主营业务               │
│ 企业金融业务、零售银行业务、│
│ 金融市场业务              │
├──────────────────────────┤
│ 关联关系 (5条)            │
│                          │
│ ▸ 香港中央结算           │
│   股权 · 持股2.83%       │
│                          │
│ ▸ 中国烟草总公司          │
│   股权 · 持股1.01%       │
│                          │
│ ▸ 张XX                   │
│   高管 · 独立董事         │
│                          │
│ ▸ 招商银行               │
│   竞争 · 同行业           │
│                          │
│ ▸ 工商银行               │
│   竞争 · 同行业           │
└──────────────────────────┘
```

### 4.4 刷新数据

```
用户: 点击 [🔄 刷新]

流程:
1. POST /api/v2/company-relations/refresh
   → 后端启动子进程: python scripts/fetch_company_relations.py
   → 采集进度输出到日志
2. 完成后自动调用 fetchData()
3. 图谱重新渲染，统计更新
4. 显示"✅ 刷新完成" + 时间戳
```

### 4.5 空数据态

首次使用或数据被清除时：

```
┌───────────────────────────────────────┐
│  🔹 公司关系图谱  [...标签...] [🔄刷新]│
│  ● 0  ● 0  ● 0  ● 0                  │
│  ──────── 图例 ────────               │
├───────────────────────────────────────┤
│                                       │
│         📊 暂无关系数据                │
│         点击 [🔄 刷新] 从               │
│         东方财富采集关系数据            │
│                                       │
└───────────────────────────────────────┘
```

### 4.6 错误态

采集失败时：

```
┌───────────────────────────────────────┐
│  ❌ 数据采集失败，请稍后重试            │
│  ⚠ 网络错误: 无法连接到东方财富服务器   │
└───────────────────────────────────────┘
```

---

## 5. 文件变更清单

### 新增文件（5个）

| 文件 | 说明 |
|------|------|
| `docs/specs/18-company-relations-graph.md` | 本规格文档 |
| `scripts/fetch_company_relations.py` | 关系数据采集脚本（含主营业务采集） |
| `deliverables/v2/src/stores/companyGraph.js` | 图谱数据 Pinia store |
| `deliverables/v2/src/pages/CompanyGraph.vue` | 图谱页面组件 |

### 修改文件（4个）—— 仅追加，不修改现有代码行

| 文件 | 修改内容 | 性质 |
|------|---------|------|
| `scripts/db_helper.py` | 末尾追加6个新函数（含 company_business CRUD） | 纯新增 |
| `server_v2.py` | 末尾追加3个新端点 | 纯新增 |
| `deliverables/v2/src/router.js` | routes数组追加1条路由 | 纯追加 |
| `deliverables/v2/src/App.vue` | navGroups追加1菜单项 + routeGroupMap追加1映射 | 纯追加 |

### 自动变更文件（2个）—— npm install 自动生成

| 文件 | 说明 |
|------|------|
| `package.json` | 新增 `@antv/g6` 依赖项 |
| `node_modules/` | 自动下载 |

---

## 6. 数据更新策略

### 6.1 更新方式：手动刷新（仅此一种）

关系图谱数据**不设定时自动采集**，完全由用户通过页面右上角 `[🔄 刷新]` 按钮手动触发。原因：

| 因素 | 说明 |
|------|------|
| 数据变化频率低 | 主营业务（年）、股权结构（季度）、高管（季度）、供应链（半年）、竞争（年） |
| 避免API请求浪费 | 东方财富公开接口无频率保证，频繁请求可能触发限制 |
| 与现有模式一致 | 项目现有新闻获取(`News.vue`)也是手动刷新模式 |

### 6.2 错误保护

采集脚本执行以下保护策略：

```
刷新流程：
1. 尝试从东方财富API采集新数据（超时30秒）
2. ✅ 采集成功 → 清空旧数据 → 写入新数据 → 返回成功
3. ❌ 采集失败 → 保留旧数据不变 → 返回错误信息（不清库）
```

这样即使网络出问题或接口变更，已有数据不会丢失。

### 6.3 数据新鲜度指示

页面上通过两条信息让用户了解数据状态：

| 指示 | 显示位置 | 示例 |
|------|---------|------|
| 上次刷新时间 | 顶部操作栏右侧 | `✅ 上次刷新: 14:10` |
| 空数据提示 | 图谱主区域 | 首次使用时显示"暂无关系数据，点击 [🔄 刷新] 从东方财富采集" |

无过期提醒机制（数据变化慢，无需主动提示）。

---

## 7. 风险与注意事项

### 7.1 东方财富API可用性

东方财富API为公开接口，无官方文档，接口地址可能变更。建议：
- 在采集脚本中加入请求超时和重试机制
- 请求失败时给出清晰的错误提示
- 预留手动录入关系的接口（未来扩展）

### 7.2 高管数据去重

不同公司的高管可能存在同名不同人情况（如"张伟"）。当前策略按姓名精确匹配，后续可引入高管ID或身份证号校验。

### 7.3 供应链关系准确度

东方财富经营分析API返回的供应商/客户为名称文本，不提供股票代码匹配。需要根据名称在 `a_stocks.json` 中模糊匹配，部分公司可能无法自动关联。

### 7.4 竞争关系范围

基于行业分类的竞争关系较为宽泛（如同一行业分类中的所有公司）。后续可加入主营产品关键词匹配来精确化竞争定义。

### 7.5 G6 版本兼容性

`@antv/g6` v5 是较新版本，API 与 v4 差异较大。实现时需要针对 v5 API 进行开发。安装前需确认最新版本号。

---

## 8. 更新历史

| 版本 | 日期 | 说明 |
|------|------|------|
| v1.0 | 2026-06-15 | 初稿 — 公司关系图谱规格文档 |
