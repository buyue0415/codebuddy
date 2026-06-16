# 05 — 任务调度器

> **核心文件**: `scripts/scheduler.py` (7.9KB) | **驱动**: Windows 任务计划程序
> **调度周期**: 交易日每 30 分钟 | **同步脚本**: `sync_all.py`

---

## 1. 业务需求说明书

### 1.1 业务背景

股票数据具有强时效性，交易日需定时采集实时行情和新闻。系统需要一个轻量级调度器，在每日开盘期间自动触发数据同步。

### 1.2 核心目标

| 目标 | 说明 |
|------|------|
| 定时同步 | 交易时段内周期性触发数据同步 |
| 防重入 | 正在同步时跳过本次调度 |
| 日志记录 | 每次执行结果写入日志文件 |
| 假期感知 | 通过收益率变化判断是否为交易日 |

---

## 2. 调度策略

### 2.1 执行周期

| 时段 | 频率 | 说明 |
|------|------|------|
| 交易日 9:30 - 11:30 | 每30分钟 | 上午盘 |
| 交易日 13:00 - 15:00 | 每30分钟 | 下午盘 |
| 非交易时段 | 不执行 | 通过 return 跳过 |

### 2.2 假期检测

```python
def is_trading_day():
    """通过检查 watchlist 股票的最新K线收益率来判断是否为交易日
       如果今天已有K线数据(change_pct != 0)，则认为是交易日"""
    bars = get_kline_daily(code)  # 任选一只自选股
    if not bars:
        return False
    latest = bars[-1]
    return latest[7] != 0  # change_pct
```

---

## 3. 实现方式

### 3.1 调度器主循环

```python
def scheduler_loop():
    while True:
        now = datetime.now()
        # 检查是否在交易时段
        if is_trading_hours(now) and is_trading_day():
            if not is_running():
                run_sync()
        time.sleep(1800)  # 30分钟
```

### 3.2 Windows 任务计划程序配置

通过 XML 文件定义任务：

```xml
<Task>
  <Triggers>
    <CalendarTrigger>
      <StartBoundary>2026-01-01T09:00:00</StartBoundary>
      <Repetition>
        <Interval>PT30M</Interval>
        <Duration>PT6H</Duration>
      </Repetition>
    </CalendarTrigger>
  </Triggers>
  <Actions>
    <Exec>
      <Command>python</Command>
      <Arguments>C:\path\to\sync_all.py</Arguments>
    </Exec>
  </Actions>
</Task>
```

---

## 4. 日志

调度器执行日志输出到控制台和 `data/sync_log.txt`：

```
[2026-06-16 09:30:00] [SCHEDULER] 交易时段开始，触发同步
[2026-06-16 09:30:05] [SCHEDULER] 同步开始...
[2026-06-16 09:31:35] [SCHEDULER] 同步完成，用时 90s
[2026-06-16 10:00:00] [SCHEDULER] 下次调度 30分钟后
```

---

## 5. 安全与异常处理

| 场景 | 处理方式 |
|------|----------|
| 同步正在运行 | 跳过本次调度，下次继续 |
| 网络异常 | 记录错误日志，等待下次调度 |
| 超出交易时段 | 跳过执行 |
| Python 异常 | try/except 包裹 main 循环 |
