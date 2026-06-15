# 遗留 JSON 文件重构方案

> 日期：2026-06-03 | 版本：1.0

---

## 一、数据源现状与目标

| 文件 | 大小 | 现状 | 目标 | SQLite 已就绪？ |
|------|------|------|------|:---:|
| `data/a_stocks.json` | 335KB | `server.py` 读 | `server.py` 改用 `get_stock_search()` | ✅ |
| `data/system_data.json` | 74KB | `build_daily_kline.py` 读写 | 废弃，全走 SQLite | ✅ |
| `data/broker_statement.json` | 27KB | `parse_statement.py` 写 | 直写 SQLite | ✅ |

---

## 二、数据结构映射

### 2.1 `a_stocks.json` → SQLite `stocks` 表

**JSON 结构（4596条）：**
```json
[
  {"code": "000001", "name": "平安银行", "market": "sz", "py": "payh"}
]
```

**SQLite `stocks` 表：**
```sql
CREATE TABLE stocks (
  code TEXT PRIMARY KEY,     -- 股票代码
  name TEXT NOT NULL,        -- 名称
  market TEXT DEFAULT 'sh',  -- 市场(sh/sz)
  py TEXT DEFAULT '',        -- 拼音缩写
  watchlist INTEGER DEFAULT 0
);
```

**映射关系：** `code→code, name→name, market→market, py→py`

**读取接口：** `db_helper.get_stock_search(keyword)` — 支持模糊搜索/前缀匹配

---

### 2.2 `system_data.json` → 多个 SQLite 表

**JSON 顶层结构 → SQLite 表映射：**

| JSON Key | SQLite 表 | 读取接口 |
|----------|-----------|----------|
| `generated` | —（生成时间戳，废弃） | — |
| `watchlist` | `watchlist` | `get_watchlist()` |
| `kline_daily` | `kline_daily` | `get_kline_daily(code)` |
| `daily_predictions` | `daily_predictions` + `prediction_hourly` + `prediction_signals` | `get_daily_predictions(code)` |
| `seasonal` | `seasonal` | `get_seasonal(code)` |
| `kline`（月K） | `kline_monthly` | `get_kline_monthly(code)` |
| `quotes` | `quotes` | `get_quotes()` |

**字段映射示例（kline_daily）：**
```
JSON:   [["2026-05-25", 37.01, 36.94, 37.26, 36.90]]
         ↓
SQL:   (code, date, open, close, high, low)
DB:    (601166, 2026-05-25, 37.01, 36.94, 37.26, 36.90)
```

**字段映射示例（daily_predictions）：**
```
JSON:   {"date":"2026-05-25","code":"601166","prev_close":17.64,
         "next_day":{"direction":"bearish","confidence":0.8,...},
         "hourly":[...], "signals":{...}, "actual":{...}}
         ↓
SQL:   daily_predictions: (code, date, prev_close, direction, confidence, high, low, advice, entry_zone)
       prediction_hourly: (pred_id FK, block, pred_open, pred_high, pred_low, pred_close, direction, strength, note)
       prediction_signals: (pred_id FK, name, value, direction, raw_value)
```

---

### 2.3 `broker_statement.json` → 多个 SQLite 表

**JSON 顶层结构 → SQLite 表映射：**

| JSON Key | SQLite 表 | 写入接口 |
|----------|-----------|----------|
| `account` | `config.json` | —（config 层） |
| `broker` | `config.json` | —（config 层） |
| `current_positions` | `positions` | `upsert_positions()` |
| `closed_positions` | `closed_positions` | `upsert_positions()` |
| `all_trades` | `trades` | `upsert_positions()` |
| `import_time` | —（无需持久化） | — |
| `stats` | —（计算字段） | — |

**current_positions 字段映射：**
```
JSON:
{"code":"600036","name":"招商银行","qty":2500,"total_cost":97250.0,
 "avg_cost":38.9,"realized_pnl":0,"dividends":[{...}],"trades":[{...}]}
         ↓
SQL positions table: (code, name, qty, total_cost, avg_cost, realized_pnl)
SQL dividends table:  (code, date, amount, price, ex_date, source='statement')
SQL trades table:     (date, time, code, name, type, qty, price, commission, stamp_tax, settlement)
```

**closed_positions 字段映射：**
```
JSON:
{"code":"600900","name":"长江电力","realized_pnl":252.43,"dividends_total":42.0,
 "total_commission":0,"total_stamp_tax":0,"total_other_fees":0}
         ↓
SQL closed_positions: (code, name, realized_pnl, dividends_total, total_commission, total_stamp_tax, total_other_fees)
```

**all_trades → trades 字段映射：**
```
JSON:
{"date":"2026-01-05","time":"14:43:51","code":"600036","name":"招商银行",
 "type":"证券买入","qty":200,"price":42.3,"commission":4.46,
 "stamp_tax":0.0,"settlement":-8465.0}
         ↓
SQL trades: (date, time, code, name, type, qty, price, commission, stamp_tax, settlement)
```

---

## 三、API 接口设计

### 3.1 股票搜索（改造）

| 项目 | 说明 |
|------|------|
| **方法** | `GET` |
| **路径** | `/api/v2/search/stocks` |
| **参数** | `?keyword=关键词` |
| **数据源** | **SQLite `stocks` 表**（不再读 JSON） |
| **接口函数** | `db_helper.get_stock_search(keyword)` |

**请求示例：**
```
GET /api/v2/search/stocks?keyword=平安
```

**响应格式：**
```json
{
  "success": true,
  "data": [
    {"code": "000001", "name": "平安银行", "market": "sz", "py": "payh"}
  ],
  "count": 1,
  "source": "sqlite"
}
```

**错误响应：**
```json
{"success": false, "error": "搜索服务不可用: 数据库连接失败"}
```

---

### 3.2 日K线（已有 API，保留不变）

| 项目 | 说明 |
|------|------|
| **方法** | `GET` |
| **路径** | `/api/v2/kline/daily` |
| **参数** | 无（返回所有自选股） |
| **数据源** | SQLite `kline_daily` 表 |

---

### 3.3 对账单导入（改造）

| 项目 | 说明 |
|------|------|
| **方法** | `POST` |
| **路径** | `/api/v2/statement/import` |
| **Content-Type** | `multipart/form-data` |
| **参数** | `file`: 广发对账单 xlsx 文件 |
| **数据目标** | **直写 SQLite**（不再写 JSON） |

**请求示例：**
```
POST /api/v2/statement/import
Content-Type: multipart/form-data

file: 广发易淘金PC版-普通对账单结果查询.xlsx
```

**响应格式：**
```json
{
  "success": true,
  "data": {
    "import_time": "2026-06-03 18:50:00",
    "stats": {
      "total_trades": 37,
      "valid_trades": 37,
      "current_stocks": 2,
      "closed_stocks": 4
    },
    "current_positions": {
      "600036": {"name": "招商银行", "qty": 2500, "avg_cost": 38.90},
      "601166": {"name": "兴业银行", "qty": 6300, "avg_cost": 17.907}
    }
  },
  "source": "sqlite"
}
```

**错误响应：**
```json
{"success": false, "error": "文件解析失败: 不支持的文件格式"}
```

**错误处理层次：**
1. 文件格式校验 → 400
2. xlsx 解析失败 → 422
3. 数据验证失败（金额/数量异常）→ 422
4. SQLite 写入失败 → 500 + 自动回滚

---

### 3.4 对账单状态查询（新增）

| 项目 | 说明 |
|------|------|
| **方法** | `GET` |
| **路径** | `/api/v2/statement/status` |
| **数据源** | SQLite `positions`/`trades` 表 |

**响应格式：**
```json
{
  "success": true,
  "data": {
    "last_import": "2026-06-03 14:54:34",
    "current_stocks": 2,
    "total_trades": 37,
    "source": "sqlite"
  }
}
```

---

### 3.5 系统快照导出（新增，替代 `system_data.json`）

| 项目 | 说明 |
|------|------|
| **方法** | `GET` |
| **路径** | `/api/v2/snapshot` |
| **数据源** | SQLite（多表聚合） |

**响应格式：**
```json
{
  "success": true,
  "data": {
    "generated": "2026-06-03T18:50:00",
    "watchlist": [...],
    "quotes": {...},
    "daily_predictions": [...],
    "seasonal": {...},
    "source": "sqlite"
  },
  "tables_used": ["watchlist", "quotes", "daily_predictions", "seasonal", "kline_daily", "kline_monthly"]
}
```

---

## 四、错误处理机制

### 4.1 统一错误响应格式

```json
{
  "success": false,
  "error": "人类可读错误信息",
  "code": "ERR_CODE",
  "detail": "技术详情（可选）"
}
```

### 4.2 错误码定义

| HTTP Status | code | 说明 |
|-------------|------|------|
| 400 | `BAD_REQUEST` | 参数缺失/格式错误 |
| 404 | `NOT_FOUND` | 资源不存在 |
| 422 | `VALIDATION_FAILED` | 数据验证失败 |
| 500 | `DB_ERROR` | 数据库操作失败 |
| 500 | `INTERNAL_ERROR` | 未知内部错误 |
| 503 | `SERVICE_UNAVAILABLE` | 服务不可用 |

### 4.3 SQLite 操作保护

```python
def _safe_execute(db, sql, params):
    """带超时和回滚保护的 SQL 执行"""
    try:
        db.execute("BEGIN")
        db.execute(sql, params)
        db.commit()
    except sqlite3.Error as e:
        db.rollback()
        raise RuntimeError(f"DB operation failed: {e}")
```

---

## 五、迁移影响范围

| 脚本 | 变更 | 影响 |
|------|------|------|
| `server.py:284` | `_load_stocks()` → `get_stock_search()` | 股票搜索改用 SQLite |
| `server.py:365` | `account`/`broker` 硬编码 → `get_config()` | 配置统一 |
| `build_daily_kline.py` | JSON 读写 → SQLite 读写 | 废弃 `system_data.json` |
| `cleanup_data.py` | JSON 操作 → SQLite `DELETE`/`VACUUM` | 废弃 JSON 依赖 |
| `parse_statement.py` | JSON 写 → `upsert_positions()` | 对账单直写 DB |
| `update_from_statement.py` | JSON 读 → `get_positions()` | 对账单直读 DB |

**向后兼容性：** 三个 JSON 文件保留为备份（`.bak`），不影响现有功能。
