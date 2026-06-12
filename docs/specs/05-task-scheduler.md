# 05 — 定时任务调度

> **核心文件**: `scripts/scheduler.py` (6KB) | **触发**: 外部定时器（Windows任务计划程序）
> **Python**: 3.12.6

---

## 1. 业务需求说明书

### 1.1 业务背景

系统需要支持外部定时器（如 Windows 任务计划程序）自动触发每日数据同步和纸面交易执行，无需用户手动操作。

### 1.2 核心目标

| 目标 | 说明 |
|------|------|
| 定时自动化 | 每日盘后自动同步 K线 + 预测 + 纸面交易 |
| CLI 灵活触发 | 支持命令行参数选择性执行 |
| 容错处理 | 脚本不存在自动跳过，超时捕获 |

---

## 2. 技术方案深度分析

### 2.1 设计决策

**为什么不用内置循环调度？**
- 调度器设计为被外部定时器调用，不内置 while True 循环
- Windows 任务计划程序管理触发时机，更可靠
- server_v2.py 的 `/api/trigger/*` 端点提供 Web手动触发备选

**两种触发路径**：

```
路径A（定时）: Windows任务计划程序 → python scheduler.py sync
路径B（手动）: 用户点击 [🔄刷新] → POST /api/trigger/predict → server_v2.py → subprocess sync_all.py
```

### 2.2 任务流

```
scheduler.py sync
  └── task_sync_all()
        ├── subprocess.run('sync_all.py', timeout=180)
        └── 成功后: task_paper_trading()
              ├── market_utils.is_market_open() 检查
              └── subprocess.run('paper_trading.py auto', timeout=30)
```

---

## 3. 功能介绍和实现方式

### 3.1 CLI 命令

```bash
python scheduler.py sync       # 全量同步 + 纸面交易
python scheduler.py statement  # 对账单更新
python scheduler.py paper      # 仅纸面交易
python scheduler.py intraday   # 盘中数据采集
```

### 3.2 核心函数

```python
def task_sync_all():
    """全量同步 + 纸面交易"""
    ok = run('sync_all.py', 180)
    if ok:
        task_paper_trading()  # 独立步骤（非嵌入 sync_all.py）
    return ok

def task_paper_trading():
    """纸面交易（含市场时间检查）"""
    from market_utils import is_market_open
    if not is_market_open(): return True  # 非交易日跳过
    return run('paper_trading.py auto', 30)

def task_statement_update():
    """对账单解析"""
    ok = run('update_from_statement.py', 30)
    return ok

def task_intraday_collect():
    """盘中数据采集（调用 collect_intraday.py）"""
    return run('collect_intraday.py once', 60)
```

### 3.3 数据更新频率

| 数据模块 | 更新频率 | 数据源 | 脚本 |
|---------|---------|--------|------|
| **intraday_quotes（分钟）** | **盘前 09:30 起每 60 分钟** | **westock-data minute** | **collect_intraday.py loop** |
| **intraday_quotes（日K线降级）** | **查询时按需生成 / scheduler.py intraday** | **kline_daily 表** | **db_helper._get_kline_intraday_fallback()** |
| kline_daily | 每日 15:35 | westock-data | sync_all.py Step2 |
| daily_predictions | 每日 15:35 | 信号计算 | sync_all.py Step6 |
| learning_params | 每日 15:35 | MWU自学习 | sync_all.py Step5 |
| accuracy_stats | 每日 15:35 | 准确率重算 | sync_all.py Step4 |
| quotes | 每日 15:35 | K线最新价 | sync_all.py Step7 |
| news | 每日 09:00 | NeoData | fetch_news.py |
| 持仓/交易 | ON_UPLOAD | 广发对账单 | update_from_statement.py |
| 纸面交易 | 每日 15:35 | daily_predictions | paper_trading.py |

### 3.4 注意

- **collect_intraday.py loop 未配置为后台常驻进程** — 当前仅通过 scheduler.py sync 流程中的 `task_intraday_collect()` 触发（单次运行 --days 5）
- 建议方案：Windows 任务计划程序每天 09:30~15:00 每 60 分钟触发 `python collect_intraday.py once`
- 无实盘分钟数据的历史日期（>5个交易日）自动降级为日K线概要

---

## 4. 用户操作流程

### 4.1 配置定时任务（一次性）

```
用户: 打开 Windows 任务计划程序
  → 创建任务 "StockSync"
  → 触发器: 每日 15:35
  → 操作: 启动程序 python.exe
  → 参数: scripts/scheduler.py sync
  → 起始于: C:\Users\28312\WorkBuddy\2026-05-18-task-15
```

### 4.2 手动命令行触发

```bash
# 仅同步数据
python scripts/scheduler.py sync

# 仅执行纸面交易
python scripts/scheduler.py paper

# 仅盘中数据采集
python scripts/scheduler.py intraday
```

---

## 5. 已知问题

1. **scheduler.py 仍引用旧脚本**：`rebuild_html()` 函数（`scheduler.py:50`）调用已删除的 `reinject_from_db.py`。该函数被 `task_statement_update()` 使用（`scheduler.py:90`），但 `task_statement_update` 自身不会被调用（CLI 无 `all` 或 `daily` 命令）
2. **docstring 引用过时**：顶部分注释提到 `reinject` 但该功能已废弃
