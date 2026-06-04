# 模块6: 定时任务调度引擎

> **核心文件**: `scripts/scheduler.py` | **触发**: 外部定时器 (Windows任务计划程序 / cron)

---

## 1. 功能概述

统一的任务编排器，将多个独立脚本按业务时序组合执行。设计为被外部定时器调用，**不内置循环调度**。

> **与 server_v2.py trigger 的关系**: `scheduler.py` 用于外部定时器触发（如 Windows 任务计划程序）；`server_v2.py` 的 `/api/trigger/*` 端点用于 Web 手动触发。两者互为备用，功能等价但调用方式不同。

---

## 2. 核心业务逻辑

### 2.1 任务定义

| 任务函数 | 脚本 | 超时 | 说明 |
|---------|------|------|------|
| `task_sync_all()` | `sync_all.py` | 120s | 全模块同步 |
| `task_daily_update()` | `daily_update.py` | 60s | 每日更新（自学习+注入） |
| `task_statement_update()` | `update_from_statement.py` → `reinject_data.py` | 30s + 10s | 对账单解析+注入 |

### 2.2 CLI 模式

```bash
python scheduler.py daily      # 仅每日更新
python scheduler.py sync       # 仅全量同步
python scheduler.py statement  # 仅对账单更新
python scheduler.py all        # sync → daily (顺序执行)
```

### 2.3 子进程执行

通过 `subprocess.run()` 调用，捕获 stdout/stderr：
- 成功: 打印 `[OK]`
- 失败: 打印 `[FAIL]` + 输出截断（各最后 200 字符）
- 超时: 打印 `[TIMEOUT]`
- 脚本不存在: 打印 `[SKIP]`

---

## 3. 数据更新频率表

| 数据模块 | 更新频率 | 数据源 | 执行脚本 |
|---------|---------|-------|---------|
| kline_daily | 每日 15:35 | westock-data Node 插件 | sync_all.py |
| daily_predictions | 每日 15:35 | 信号计算 | sync_all.py |
| learning_params | 每日 15:35 | 自学习算法 | daily_update.py |
| accuracy_stats | 每日 15:35 | 准确率重算 | daily_update.py |
| quotes | 实时/每日 | ⚠️ 硬编码 | daily_update.py |
| news | 每日 09:00 | NeoData | fetch_news.py |
| expert_reports | 每周一 09:00 | WorkBuddy 多 Agent | 手动触发 |
| 持仓/交易/费用 | ON_UPLOAD | 广发对账单.xlsx | update_from_statement.py |
| seasonal | 手动 | 历史统计 | 手动维护 |
| watchlist | ON_ADD/DEL | Web 管理页 | server_v2.py API |

---

## 4. 依赖关系

| 方向 | 模块 | 方式 |
|------|------|------|
| **依赖库** | `json`, `subprocess`, `os`, `sys`, `datetime`, `argparse` | Python 标准库 |
| **子进程调用** | [同步引擎](./03-sync-engine.md) | `run('sync_all.py')` |
| **子进程调用** | [每日更新](./05-daily-update.md) | `run('daily_update.py')` |
| **子进程调用** | [对账单解析](./09-statement-parser.md) | `run('update_from_statement.py')` |
| **子进程调用** | [数据注入](./11-data-injection.md) | `run('reinject_data.py')` |
| **调用链** | 外部定时器 → scheduler.py → 各后台脚本 | |



## 5. 异常处理机制

| 场景 | 处理 |
|------|------|
| 脚本不存在 | 打印 `[SKIP]` 并返回 `False` |
| 脚本超时 | TimeoutExpired → 打印 `[TIMEOUT]` 并返回 `False` |
| 返回码非零 | 打印 `[FAIL]` + stdout/stderr 截断 |
| 子进程其他异常 | 捕获并返回 `False` |
| 链式调用失败 | `task_statement_update` 在 `update_from_statement` 失败时仍尝试 `reinject` |
