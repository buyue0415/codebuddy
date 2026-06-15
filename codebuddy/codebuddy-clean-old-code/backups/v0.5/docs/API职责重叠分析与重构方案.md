# API 职责重叠分析与重构方案

## 1. 问题发现：三个端点共享同一底层调用

### 1.1 实际调用链追踪

经过代码审查，发现以下三个 API 端点最终都调用了同一个脚本 `reinject_from_db.py`：

```
┌─────────────────────────────────────────────────────────────────┐
│                    三层 API 与底层调用映射                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  /api/expert/import         /api/trigger/reload_db   /api/v2/fullsync
│  (POST, body=JSON报告)        (POST, body={})           (GET, 无参)   │
│       │                           │                         │       │
│       ├─ import_report()          │                         │       │
│       │  ├─ validate_report()     │                         │       │
│       │  ├─ INSERT expert_reports │                         │       │
│       │  └─ return (ok,msg)       │                         │       │
│       │                           │                         │       │
│       └─ run_script("           ─┼─ run_script("         ─┼─ subprocess │
│           reinject_from_db.py")   │   reinject_from_db.py") │   .run(..) │
│           timeout=15s             │   timeout=15s            │   timeout=30│
│               │                   │       │                 │       │    │
│               └───────────────┬───┴───────┴─────────────────┘       │
│                               │                                      │
│                               ▼                                      │
│                  ┌─────────────────────────┐                        │
│                  │   reinject_from_db.py   │                        │
│                  │                         │                        │
│                  │  1. SQLite.readAll()    │                        │
│                  │     ├─ watchlist        │                        │
│                  │     ├─ quotes           │                        │
│                  │     ├─ kline_daily      │                        │
│                  │     ├─ kline_monthly    │                        │
│                  │     ├─ positions        │                        │
│                  │     ├─ trades           │                        │
│                  │     ├─ predictions      │                        │
│                  │     ├─ news             │                        │
│                  │     └─ expert_reports   │                        │
│                  │                         │                        │
│                  │  2. json.dumps(data)    │                        │
│                  │  3. regex.replace()     │                        │
│                  │     → 写入 HTML 中      │                        │
│                  │     const DATA={...};   │                        │
│                  └─────────────────────────┘                        │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 重叠矩阵

| 维度 | `/api/expert/import` | `/api/trigger/reload_db` | `/api/v2/fullsync` |
|------|---------------------|-------------------------|-------------------|
| **HTTP 方法** | POST | POST | **GET** ⚠️ |
| **请求体** | JSON 报告对象 | `{}`（空） | 无 |
| **核心业务** | 导入专家报告 → DB | — | — |
| **HTML注入** | ✅ reinject_db(15s) | ✅ reinject_db(15s) | ✅ reinject_db(30s) |
| **超时** | 15s | 15s | 30s |
| **目标用户** | 管理员/专家 | 普通用户 | 普通用户 |
| **触发频率** | 低频（每次导入） | 低频（手动） | 低频（手动） |
| **数据库写** | INSERT 1行 | 无 | 无 |
| **幂等性** | ❌ 重复导入报错 | ✅ | ✅ |
| **前端入口** | 📤 导入报告 | 💉 从DB刷新页面 | 🔄 全量数据同步 |

## 2. 职责分析：按 RESTful 维度拆解

### 2.1 资源语义分析

```
RESTful 黄金法则: 一个端点 = 一个资源的一种操作

/api/expert/import
  → 资源: expert_reports 表
  → 操作: CREATE（创建一条专家报告记录）
  → 语义: "导入一份新的专家分析报告"

/api/trigger/reload_db
  → 资源: 整个 HTML 文件（容器）
  → 操作: UPDATE（全量覆写嵌入式 DATA）
  → 语义: "将数据库最新数据重新注入 HTML"

/api/v2/fullsync
  → 资源: 同上
  → 操作: UPDATE（全量覆写嵌入式 DATA）
  → 语义: 同上，但超时更长、无额外参数
```

**结论**：`/api/trigger/reload_db` 与 `/api/v2/fullsync` 是**完全同义**的两个端点，唯一的区别是超时时间（15s vs 30s）和 HTTP 方法（POST vs GET）。

### 2.2 `/api/expert/import` 的职责违规

该端点在同一个请求-响应周期内完成了**两个完全不同层级**的操作：

```
┌──────────────────────────────────────────┐
│          /api/expert/import              │
├──────────────────────────────────────────┤
│                                          │
│  第1层：业务逻辑（domain concern）         │
│  ├─ 校验报告 JSON 结构                   │
│  ├─ 校验评分范围 [0,10]                  │
│  ├─ 校验决策字段 BUY/HOLD/SELL           │
│  └─ INSERT INTO expert_reports           │
│                                          │
│  第2层：基础设施（infrastructure concern）│
│  └─ 全量重写 HTML 文件 ← 越界！           │
│      ├─ 读取 stocks/quotes/kline/...     │
│      ├─ 读取 positions/trades/preds/...  │
│      └─ 覆盖 const DATA = {...};         │
│                                          │
│  风险：                                   │
│  • import_report() 成功但 reinject 失败   │
│    → DB 已写入但前端不可见                │
│  • 导入1条报告触发全量 500条K线重读        │
│    → 性能浪费                            │
│  • 两个操作强耦合在同一个事务性请求中       │
│    → 违反单一职责原则                     │
└──────────────────────────────────────────┘
```

### 2.3 冗余度评估

| 风险项 | 严重度 | 说明 |
|--------|--------|------|
| **职责模糊** | 🔴 高 | `/api/expert/import` 同时承担"写DB"和"写HTML"两个无关职责 |
| **全量注入冗余** | 🔴 高 | 导入1条报告 → 读取所有表 → 重写整个HTML → 完全不必要 |
| **端点冗余** | 🟡 中 | `reload_db` 和 `fullsync` 语义完全重复 |
| **GET 副作用** | 🟡 中 | `GET /api/v2/fullsync` 执行写操作，违反 RESTful GET 幂等安全约束 |
| **事务不完整** | 🟡 中 | import_report(DB) 成功但 reinject(HTML) 失败 → 状态不一致 |
| **超时不一致** | 🟢 低 | 同一操作有 15s 和 30s 两个超时配置 |

## 3. 重构方案

### 3.1 方案对比

```
方案A：合并 + 参数化                 方案B：分离 + 链式调用
┌──────────────────────┐            ┌──────────────────────────────┐
│ /api/v2/sync         │            │ /api/expert/import  (纯业务)  │
│   ?scope=full        │            │   → INSERT expert_reports    │
│   ?scope=experts     │            │   → 返回 {success, id}       │
│                      │            │                              │
│ 缺点: 引入查询参数    │            │ /api/v2/sync (纯基础设施)     │
│ 控制写范围，增加复杂度│            │   → 读取所有表 → 写HTML       │
│                      │            │   → 返回 {success, message}  │
└──────────────────────┘            │                              │
                                    │ 前端链式:                     │
                                    │ import → 成功 → sync → reload │
                                    └──────────────────────────────┘
```

### 3.2 推荐方案：B — 分离职责 + 前端编排

采用**"关注点分离"原则**，将业务层API与基础设施层API彻底解耦：

```
重构前:                                   重构后:
┌───────────────────┐                    ┌───────────────────┐
│ POST /api/expert/ │                    │ POST /api/expert/ │
│       import      │                    │       import      │
│                   │                    │                   │
│ 1. import_report  │                    │ 1. import_report  │
│ 2. reinject_db ←X │  ── 分离 ──→      │ 2. return {id}    │ ← 只做业务
└───────────────────┘                    └───────────────────┘
                                                      │
┌───────────────────┐                    ┌───────────────────┐
│ POST /api/trigger │                    │ POST /api/v2/sync │ ← 统一入口
│   /reload_db      │                    │                   │
│                   │                    │ → reinject_db.py  │ ← 只做基础设施
│ → reinject_db.py  │  ── 合并 ──→      │                    │
├───────────────────┤                    └───────────────────┘
│ GET /api/v2/      │
│      fullsync     │                    ┌───────────────────┐
│                   │                    │ 前端编排:          │
│ → reinject_db.py  │  ── 合并 ──→      │                   │
└───────────────────┘                    │ importReport()    │
                                         │  → /api/expert/   │
                                         │    /import        │
                                         │  → if success:    │
                                         │    syncHTML()     │
                                         │    → /api/v2/sync │
                                         │    → reload(true) │
                                         └───────────────────┘
```

### 3.3 推荐重构后的接口定义

#### 3.3.1 新接口：`POST /api/v2/sync`（统一的 HTML 注入端点）

```json
// 请求
POST /api/v2/sync
Content-Type: application/json
{}

// 成功响应 (200)
{
    "success": true,
    "message": "数据同步完成: 8张表 523条K线 4个持仓 12条新闻",
    "stats": {
        "tables": 8,
        "kline_count": 523,
        "positions": 4,
        "news_count": 12
    }
}

// 失败响应 (500)
{
    "success": false,
    "error": "reinject_from_db.py 执行失败",
    "detail": "...stderr..."
}
```

#### 3.3.2 精简化接口：`POST /api/v2/expert/import`（纯业务端点）

```json
// 请求
POST /api/v2/expert/import
Content-Type: application/json
{
    "date": "2026-05-22",
    "stocks": {
        "600036": {
            "decision": "BUY",
            "confidence": "高",
            ...
        }
    }
}

// 成功响应 (201 Created)
{
    "success": true,
    "message": "导入成功: 2026-05-22 — 600036(BUY)",
    "report_id": 42,
    "warnings": []
}

// 注意：不再包含 HTML 注入的副作用！
```

#### 3.3.3 废弃的旧端点

| 旧端点 | 状态 | 替代方案 |
|--------|------|---------|
| `POST /api/trigger/reload_db` | ⚠️ 标记废弃（保留兼容） | 内部转发到 `POST /api/v2/sync` |
| `GET /api/v2/fullsync` | ⚠️ 标记废弃（保留兼容） | 返回301重定向或转发到 `POST /api/v2/sync` |
| `POST /api/expert/import` | ⚠️ 标记废弃（保留兼容） | 内部转发到 `POST /api/v2/expert/import` |

### 3.4 前端编排逻辑

```javascript
// 重构后的 importExpertReport() —— 职责清晰的两步法
async function importExpertReport() {
    if (!hasAPI()) { alert('需要通过本地服务器访问'); return; }

    var text = document.getElementById('expert-json-text').value.trim();
    if (!text) { alert('请先选择JSON文件或粘贴报告内容'); return; }

    var st = document.getElementById('expert-import-status');
    st.style.color = '#6b7280';

    try {
        // Step 1: 纯业务操作 —— 导入报告到数据库
        st.textContent = '正在导入报告...';
        var data = JSON.parse(text);
        var r = await apiCall('POST', '/api/v2/expert/import', data);

        if (!r || !r.success) {
            st.style.color = '#dc2626';
            st.textContent = '导入失败: ' + ((r && r.error) || '未知');
            return;
        }

        st.style.color = '#16a34a';
        st.textContent = r.message;

        // Step 2: 基础设施操作 —— 同步 HTML（仅当成功）
        st.textContent = r.message + ' | 正在同步页面...';
        var sync = await apiCall('POST', '/api/v2/sync', {});

        if (sync && sync.success) {
            st.textContent = r.message + ' | 同步完成，即将刷新';
            setTimeout(function () { location.reload(true); }, 800);
        } else {
            st.textContent = r.message + ' | 同步失败，请手动刷新';
        }

    } catch (e) {
        st.style.color = '#dc2626';
        st.textContent = '错误: ' + e.message;
    }
}
```

## 4. 向后兼容方案

### 4.1 过渡期双端点策略

```
阶段1 (当前版本):  旧端点 + 新端点共存
阶段2 (下一版本):  旧端点返回 Deprecation Warning header
阶段3 (未来版本):  移除旧端点
```

### 4.2 兼容性 Adapter 实现

```python
# server.py 中的兼容层
elif path == "/api/trigger/reload_db":
    # 旧端点 → 内部转发到新端点
    ok, out = run_script("reinject_from_db.py", 15)
    json_response(self, {
        "success": ok,
        "output": out[-500:] if out else "",
        "message": "数据已从数据库刷新到页面" if ok else "刷新失败",
        "_deprecated": True,
        "_migrate_to": "/api/v2/sync"
    })

elif path == "/api/v2/sync":
    # 新统一端点
    ok, out = run_script("reinject_from_db.py", 30)
    # 解析 stats 返回结构化信息
    json_response(self, {
        "success": ok,
        "message": "数据同步完成" if ok else "同步失败",
        "stats": _parse_sync_stats(out) if ok else None
    })

elif path == "/api/expert/import":
    # 旧端点 → 仅做业务逻辑（移除 HTML 注入副作用）
    import warnings
    from import_expert_report import import_report as _import_report
    ok, msg, warnings_list = _import_report(report_json)
    json_response(self, {
        "success": ok,
        "message": msg,
        "warnings": warnings_list,
        "_deprecated": True,
        "_migrate_to": "/api/v2/expert/import",
        "_note": "导入成功后请调用 POST /api/v2/sync 同步到页面"
    })

elif path == "/api/v2/expert/import":
    # 新纯业务端点（不带任何基础设施副作用）
    from import_expert_report import import_report as _import_report
    ok, msg, warnings_list = _import_report(report_json)
    json_response(self, {
        "success": ok,
        "message": msg,
        "warnings": warnings_list
    })
```

## 5. 最终 API 矩阵（重构后）

| # | 方法 | 路径 | 职责层级 | 数据库写 | HTML写 | 状态 |
|---|------|------|---------|---------|--------|------|
| 1 | POST | `/api/v2/expert/import` | 业务层 | ✅ INSERT 1行 | ❌ | 🆕 新增 |
| 2 | POST | `/api/v2/sync` | 基础设施层 | ❌ | ✅ 全量注入 | 🆕 新增 |
| 3 | POST | `/api/expert/import` | 业务层（旧） | ✅ | ❌ | ⚠️ 废弃 |
| 4 | POST | `/api/trigger/reload_db` | 基础设施（旧） | ❌ | ✅ | ⚠️ 废弃 |
| 5 | GET | `/api/v2/fullsync` | 基础设施（旧） | ❌ | ✅ | ⚠️ 废弃 |

## 6. 影响评估

| 维度 | 重构前 | 重构后 |
|------|--------|--------|
| **端点总数** | 5个（3重复） | 2个核心 + 3兼容 |
| **导入性能** | 导入+全量注入（~15s） | 导入(~1s) + 注入(~15s) 可并行 |
| **职责清晰度** | 混杂 | 业务/基础设施 分离 |
| **前端控制力** | 黑盒（无法选择是否注入） | 白盒（可决定是否 sync） |
| **错误恢复** | 无法回滚 | 导入成功→sync失败→手动重试 |
| **可测试性** | 难以 mock HTML注入 | 可独立测试两个端点 |
| **向后兼容** | — | 3个旧端点保留 |
