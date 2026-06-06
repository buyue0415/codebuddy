---
name: fix-601398-monthly-seasonal-data
overview: 诊断并修复工商银行(601398)月度涨跌幅和季节性规律数据不显示的问题，原因是 sync_all.py 在 Step 7 的 K线聚合链路断裂
todos:
  - id: fix-step7a-db-fallback
    content: 在 sync_all.py Step 7a 添加 DB 回退：当 kline_results[code] 为空时从 kline_daily 表读取数据
    status: completed
  - id: fix-step7-quotes-fallback
    content: 同步修复 Step 7 quotes 写入的 DB 回退（同理缺少回退机制）
    status: completed
    dependencies:
      - fix-step7a-db-fallback
  - id: rerun-sync-and-verify
    content: 手动运行 sync_all.py 重新同步，验证工商银行月度涨跌幅和季节性规律数据正常显示
    status: completed
    dependencies:
      - fix-step7-quotes-fallback
---

## 问题描述

新增工商银行(601398)到自选股后，月度涨跌幅柱状图和季节性规律(月均涨跌幅%)图表显示为空白，没有数据。但其他股票(兴业银行、招商银行)的对应数据正常显示，且工商银行的日K线走势图正常。

## 核心需求

修复工商银行月度涨跌幅和季节性规律数据不显示的问题，确保新增股票后相关数据能够正确生成和展示。

## 技术方案

### 根因

`scripts/sync_all.py` 的 Step 7a（第601行）在聚合月K线时，**只依赖本次同步的内存数据** `kline_results[code]`，**没有 DB 回退机制**。这与 Step 3 和 Step 6 已经实现的 DB 回退逻辑不一致。

**故障链路**：

1. Step 2 并行获取7只股票日K线，`sh601398` 的 Node.js 子进程可能因超时/限流返回空
2. `kline_results['601398'] = []`（空列表）
3. Step 7a 检查 `kline_results[code]` 为 falsy → 跳过月K线聚合和写入
4. `kline_monthly` 表没有 601398 的数据
5. Step 7b 的 `_calc_seasonal_pct('601398')` 从空表读取 → 返回 `[0.0]*12`
6. 前端 `DATA['monthly_changes_601398']` 和 `DATA.seasonal['601398']` 都为空 → 图表空白

**日K线正常的原因**：`kline_daily` 表在更早的同步中已成功写入，前端直接读取 DB 渲染日K线图，不受本次同步影响。

### 修复方案

在 `sync_all.py` 的 Step 7a（第601行）和 Step 7 quotes（第634行）中添加 DB 回退机制，与 Step 3（第242-255行）保持一致的回退逻辑：

```
修改前:
  if code in kline_results and kline_results[code]:
      daily = kline_results[code]

修改后:
  daily = kline_results.get(code, [])
  if not daily:
      # 从 kline_daily 表回退读取
      fb_rows = db.execute("SELECT date, open, close, high, low FROM kline_daily WHERE code=? ORDER BY date DESC", [code]).fetchall()
      if fb_rows:
          daily = [[r['date'], r['open'], r['close'], r['high'], r['low']] for r in fb_rows]
  
  if daily:
      monthly = {}
      for bar in daily: ...
```

DB 回退数据格式 `[date, open, close, high, low]` 与 `kline_results` 中 NeoData 解析后的格式完全一致，保证 bar[1]=open, bar[2]=close, bar[3]=high, bar[4]=low 的索引映射正确。

### 实施步骤

1. 修改 `scripts/sync_all.py` Step 7a 加上 DB 回退
2. 同时修复 Step 7 quotes 写入的 DB 回退
3. 手动运行一次 `sync_all.py` 重新生成缺失数据
4. 刷新前端页面验证数据正常显示

### 设计说明

- 遵循 DRY 原则，复用与 Step 3/6 相同的 DB 回退模式
- 最小化改动范围，只修复数据获取路径，不改动聚合逻辑本身
- 向后兼容：已有数据的股票不受影响