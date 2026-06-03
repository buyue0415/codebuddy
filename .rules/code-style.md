# 代码风格规范 (Code Style Rules)

> **版本**: v1.0 | **级别**: 🔴 MUST | **更新日期**: 2026-06-03

---

## 1. 命名规范

### 1.1 文件命名
- **Python 脚本**: `snake_case.py`（如 `db_helper.py`, `sync_all.py`）
- **测试文件**: `test_<module>.py`（如 `test_db_helper.py`）
- **配置/数据**: `kebab-case.json` 或 `snake_case.json`
- **文档**: `kebab-case.md` 或 `XX-module-name.md`

### 1.2 Python 命名

| 实体 | 风格 | 示例 |
|------|------|------|
| 模块 | `snake_case` | `db_helper`, `fetch_news` |
| 函数 | `snake_case` | `get_watchlist()`, `calc_signals()` |
| 变量 | `snake_case` | `stock_code`, `daily_bars` |
| 常量 | `UPPER_SNAKE` | `SIGNALS`, `DB_PATH`, `MAX_WORKERS` |
| 类 | `PascalCase` | `StockTestBase`, `ThreadedHTTPServer` |
| 私有函数 | `_leading_underscore` | `_calc_fees()`, `_ema()` |
| 布尔变量 | `is_`/`has_`/`should_` 前缀 | `_refresh_in_progress`, `has_data` |

### 1.3 数据库命名

| 实体 | 风格 | 示例 |
|------|------|------|
| 表名 | `snake_case` | `kline_daily`, `learning_params` |
| 字段名 | `snake_case` | `avg_cost`, `update_count` |
| 索引 | `idx_<table>_<col>` | `idx_predictions_code` |

---

## 2. 代码格式

### 2.1 缩进与行长
- **MUST**: 使用 4 空格缩进，禁止 Tab
- **MUST**: 每行不超过 120 字符
- **SHOULD**: 每行不超过 100 字符（推荐）

### 2.2 空行
- 模块级函数之间：2 个空行
- 类方法之间：1 个空行
- 逻辑段落之间：1 个空行

### 2.3 Import 顺序
```python
# 1. 标准库
import os, sys, json, sqlite3
from datetime import datetime, timedelta

# 2. 第三方库
import numpy as np
from sklearn.ensemble import RandomForestClassifier

# 3. 项目内部
from db_helper import get_watchlist, get_kline_daily
from conftest import StockTestBase
```

### 2.4 字符串
- **MUST**: 优先使用 `f-string` 格式化
- **MUST**: 文件编码声明 `# -*- coding: utf-8 -*-` 或默认 UTF-8
- **SHOULD**: 长字符串使用括号拼接，避免反斜杠续行

---

## 3. 文档字符串 (Docstring)

### 3.1 模块级
```python
"""P1 [CRITICAL] Database layer tests — db_helper.py.

Covers: all 18 query functions, 12 write functions, edge cases.
Priority: HIGHEST — core data integrity.
"""
```

### 3.2 函数级
```python
def get_kline_daily(code: str) -> list:
    """获取指定股票的日K线数据。
    
    Args:
        code: 6位股票代码，如 '601166'
    
    Returns:
        list[list]: 按日期降序排列的K线数据
            每条: [date: str, open: float, close: float, high: float, low: float]
    
    Raises:
        sqlite3.Error: 数据库连接失败时抛出
    """
```

### 3.3 类级
```python
class StockTestBase(unittest.TestCase):
    """所有测试的基类，提供公共断言方法和测试基础设施。
    
    Attributes:
        maxDiff: 设置为 None 以显示完整 diff
        root: 项目根目录路径
    """
```

---

## 4. 错误处理

### 4.1 查询函数
```python
# MUST: 不封装 try/except，异常向上传播
def get_watchlist() -> list:
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    rows = db.execute("SELECT * FROM watchlist ORDER BY sort_order").fetchall()
    db.close()
    return [dict(r) for r in rows]
```

### 4.2 API 端点
```python
# MUST: 每个端点包裹 try/except，返回统一 JSON 格式
try:
    result = do_something()
    return json_response({'success': True, 'data': result})
except Exception as e:
    return json_response({'success': False, 'error': str(e), 'trace': traceback.format_exc()}, 500)
```

### 4.3 写入函数
```python
# MUST: 使用参数化查询防止 SQL 注入
db.execute("INSERT INTO kline_daily (code, date, open, close, high, low) VALUES (?,?,?,?,?,?)",
           (code, date, open_val, close_val, high_val, low_val))

# MUST NOT: 字符串拼接 SQL
# db.execute(f"INSERT INTO ... VALUES ('{code}', ...)")  # ❌ 禁止
```

### 4.4 子进程调用
```python
# MUST: 设置超时，捕获超时异常
result = subprocess.run(cmd, capture_output=True, text=True, timeout=timout_seconds)
# MUST: 输出截断（stdout max 3000, stderr max 1000）
```

---

## 5. 类型注解 (V0.7+)

### 5.1 新增代码 MUST 添加类型注解
```python
def calc_signals(kdata: list, seasonal_factor: float = 1.0) -> dict | None:
    ...

def get_watchlist() -> list[dict]:
    ...

def _calc_fees(qty: int, price: float, config: dict | None = None) -> dict:
    ...
```

### 5.2 公共函数 SHOULD 添加类型注解
已有代码逐步添加，新增代码强制要求。

---

## 6. 注释规范

### 6.1 分隔注释
```python
# ======================================================================
# Section: K-line queries
# ======================================================================
```

### 6.2 行内注释
- 与代码至少空 2 个空格
- 注释首字母大写
- 解释 WHY 而非 WHAT

```python
closed_prices = [k[2] for k in kdata]  # K线新在前，index 0=最新
```

### 6.3 TODO/FIXME/HACK
```python
# TODO(v0.8): 接入实时行情API替换硬编码PE/PB
# FIXME: 月K线增量更新在sync_all Step7未实现
# HACK: 正则匹配HTML DATA块，前端重构后需同步更新
```

---

## 7. 测试代码风格

### 7.1 测试类命名
```python
class Test<Module><Scenario>(StockTestBase):
    """简要说明测试范围"""
```

### 7.2 测试方法命名
```python
def test_<function>_<scenario>_<expected>(self):
    """可选的 docstring"""
```

示例:
- `test_get_watchlist_returns_list`
- `test_get_kline_daily_invalid_code`
- `test_calc_signals_insufficient_data_returns_none`

### 7.3 断言顺序
1. 类型断言 (`assertIsInstance`)
2. 结构断言 (`assertIn`, `assertEqual`)
3. 值断言 (`assertGreater`, `assertAlmostEqual`)
4. 边界断言

---

## 8. SQL 书写规范

```sql
-- MUST: 关键字大写，表名/字段名小写
SELECT code, date, open, close, high, low
FROM kline_daily
WHERE code = ?
ORDER BY date DESC
LIMIT 200

-- MUST: 多表 JOIN 显式写出关联条件
SELECT p.*, h.block, h.pred_close
FROM daily_predictions p
LEFT JOIN prediction_hourly h ON h.pred_id = p.id
WHERE p.code = ?
```
