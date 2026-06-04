# 模块14: 用户操作流程 (User Flow)

> **文档类型**: 用户操作流程说明 | **版本**: v1.0 | **创建日期**: 2026-06-04
> **前置阅读**: [业务需求说明书](./14-business-requirements.md), [技术设计方案](./14-backtest-paper-trading.md)
> **基础状态**: 6只自选股, 12,066条日K线, 201条预测, SQLite 20+张表

---

## 流程总览

```
阶段A: 首次使用 (一次性)
  └→ 运行回测 → 获取冷启动权重

阶段B: 每日自动 (无需用户操作)
  └→ sync_all.py 定时运行 → 预测生成 → 纸面交易自动执行

阶段C: 日常查看 (用户主动)
  └→ 查看10天预测 → 查看纸面交易结果 → 对比真实持仓
```

```
阶段A ──→ 阶段B ──循环──→ 阶段C ──循环──→ 阶段B ──循环──→ ...
         (每日)           (每日)           (次日)
```

---

## 阶段A: 首次使用 — 运行回测

### 前置状态

| 条件 | 当前状态 |
|------|---------|
| 自选股 | 6只已配置 (601166兴业, 600036招行, 600050联通, 600941移动, 002594比亚迪, 600900长江电力) |
| 日K线 | 5只2000条 (2018~2026), 1只1066条 (2022~2026) |
| 预测数据 | 201条，覆盖到30个交易日后的未来 |
| 回测权重 | **未运行过回测，learning_params.backtest_weights = NULL** |
| 纸面交易 | **未初始化，paper_account 表为空** |

### 步骤 A1: 用户进入回测页

```
用户操作: 浏览器打开 http://localhost:5173/
        → 点击导航栏 "模拟交易" → "回测分析"

页面响应:
┌────────────────────────────────────────────────────────┐
│  📊 回测分析                  [首次使用, 请运行回测]      │
│                                                         │
│  [▶ 运行回测]  [训练: 252天 ▼]  [测试: 21天 ▼]         │
│                                                         │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────┐ │
│  │ 夏普比率 │ │ 最大回撤 │ │  胜 率   │ │ 年化收益  │ │
│  │   --     │ │   --     │ │   --     │ │   --      │ │
│  └──────────┘ └──────────┘ └──────────┘ └───────────┘ │
│                                                         │
│  暂无回测记录                                            │
└────────────────────────────────────────────────────────┘

API调用: GET /api/v2/backtest/history → {data: [], count: 0}
```

### 步骤 A2: 用户启动回测

```
用户操作: 点击 [▶ 运行回测]

前端:
  → 状态变更为 ●运行中
  → 按钮禁用，显示 "回测运行中..."
  → POST /api/v2/backtest/run {train_window: 252, test_window: 21}

后端:
  → server_v2.py 收到请求
  → 检查 _backtest_in_progress == false
  → 启动后台线程: subprocess.run([PYTHON, 'scripts/backtest_engine.py', ...])
  → 插入 backtest_runs 表: status='running'
  → 返回 {run_id: 1, status: 'running'}

回测引擎 (backtest_engine.py):
  → 读取 watchlist: 6只股票
  → 对每只股票:
     1. 从 kline_daily 读取全部K线 (2000条)
     2. numpy向量化计算10个技术信号
     3. Walk-forward: 252天训练 → 21天测试 → 前滚21天 → 重复
     4. 网格搜索: 10信号权重在 [0.1, 0.3, 0.5, 0.7, 1.0, 1.3, 1.5] 中随机采样
     5. 模拟交易: 资金校验 → 买卖 → 盈亏计算
     6. 市场状态检测: ADX + 波动率 → trending/ranging/volatile
     7. 输出: 最优权重 + 状态专属权重 + 夏普/回撤/胜率/Calmar
  → 写入 learning_params.backtest_weights (JSON)
  → 写入 learning_params.regime_weights (JSON)
  → 更新 backtest_runs: status='done', summary_json={...}
  → 预计耗时: 60~120秒

前端轮询:
  → setInterval GET /api/v2/backtest/status (每2秒)
  → 显示进度: "3/6 兴业银行..."
  → 状态变为 done → 停止轮询
```

### 步骤 A3: 查看回测结果

```
页面自动刷新:
┌────────────────────────────────────────────────────────┐
│  📊 回测分析                           ✓ 完成 (68s)      │
│                                                         │
│  [▶ 运行回测]  [训练: 252天 ▼]  [测试: 21天 ▼]         │
│                                                         │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────┐ │
│  │ 夏普比率 │ │ 最大回撤 │ │  胜 率   │ │ 年化收益  │ │
│  │  0.85    │ │ -12.5%   │ │ 58.3%    │ │ +15.7%    │ │
│  │ 🟢       │ │ 🟡       │ │ 🟢       │ │ 🟢        │ │
│  └──────────┘ └──────────┘ └──────────┘ └───────────┘ │
│                                                         │
│  股票权重优化对比                                        │
│  ┌────────┬──────────┬──────────┬──────────┬─────────┐ │
│  │ 股票   │ 原MWU    │ 回测优化 │ 改善     │ 夏普    │ │
│  │601166  │ 55.2%    │ 62.1%    │ ↑ +6.9%  │ 0.92    │ │
│  │600036  │ 53.1%    │ 58.5%    │ ↑ +5.4%  │ 0.78    │ │
│  │...     │          │          │          │         │ │
│  └────────┴──────────┴──────────┴──────────┴─────────┘ │
│                                                         │
│  市场状态权重矩阵 (趋势/震荡/高波动)                       │
│  ┌──────────┬──────┬──────┬────────┬──────┐            │
│  │ 信号     │ 趋势 │ 震荡 │ 高波动 │ 通用 │            │
│  │ macd     │ 1.52 │ 0.65 │ 0.92   │ 1.10 │            │
│  │ rsi      │ 0.73 │ 1.45 │ 0.86   │ 0.95 │            │
│  │ ...      │      │      │        │      │            │
│  └──────────┴──────┴──────┴────────┴──────┘            │
└────────────────────────────────────────────────────────┘

API调用: GET /api/v2/backtest/results/1

数据库状态变更:
  learning_params (每只股票):
    backtest_weights = '{"macd":{"next_day":1.32,...},...}'
    regime_weights = '{"trending":{...},"ranging":{...},"volatile":{...}}'
    backtest_timestamp = '2026-06-04 15:30:00'
```

> **关键数据流**: 回测权重写入后，下次 sync_all.py Step 5 运行时，MWU 将以 backtest_weights 作为初始权重启动，而非从 1.0 随机摸索。

---

## 阶段B: 每日自动运行 — 预测 + 纸面交易

### 前置状态

| 条件 | 之前 | 之后(阶段A后) |
|------|------|-------------|
| learning_params.backtest_weights | NULL | ✅ 已填充 |
| paper_account | 不存在 | 需先初始化 |

### 步骤 B0: 纸面账户初始化 (一次性)

```
用户操作: 点击导航栏 "模拟交易" → "纸面交易"

页面响应:
┌────────────────────────────────────────────────────────┐
│  💼 纸面交易                                            │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │  ⚠️ 虚拟账户未初始化                              │   │
│  │  初始资金: ¥100,000                              │   │
│  │  [初始化账户]                                     │   │
│  └─────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────┘

用户操作: 点击 [初始化账户]

API调用: POST /api/v2/paper/reset {initial_capital: 100000}

后端:
  → INSERT paper_account (cash=100000, initial_capital=100000)
  → 返回 {success: true, data: {cash: 100000, ...}}

数据库状态:
  paper_account: 1行 (cash=100000.00, initial_capital=100000.00)
  paper_positions: 0行
  paper_trades: 0行
```

### 步骤 B1-定时: 外部定时器触发 (每日15:35)

```
Windows 任务计划程序:
  → 每日15:35 自动执行
  → python scripts/scheduler.py sync
  → scheduler.py 调用 subprocess.run([PYTHON, 'scripts/sync_all.py'])
```

### 步骤 B1-手动: 用户手动刷新 (任意时间)

```
触发位置: "股票分析预测" → "智能预测" 页面的 [🔄 刷新] 按钮

使用场景:
  场景1: 刚添加新自选股 → 立即获取该股票的K线和预测
  场景2: 盘中想基于最新行情更新预测
  场景3: 定时任务失败/未执行 → 手动补救
  场景4: 开发调试 → 快速验证预测效果

用户操作: 点击 [🔄 刷新]
  → 按钮变为 "刷新中..."，按钮禁用
  → POST /api/trigger/predict (timeout=180s)
  → server_v2.py subprocess.run(scripts/sync_all.py)

后端行为: 与定时触发执行完全相同的 sync_all.py 8步流程。

⚠️ 重要提示:
  1. 手动刷新不仅更新预测，同时触发纸面交易自动执行 (Step 6.5)
  2. 同一天多次点击刷新 → 纸面交易检测当日已执行 (executed=1)，
     自动跳过重复交易，不会重复买卖
  3. 刷新期间整个同步流程运行 (约60-120秒)，前端显示状态文字
```

---

两种触发方式执行完全相同的 `sync_all.py` 8步流程:

Step 1: 获取新闻 (6只股票, 并行)
  → 输出: "News for 兴业银行(601166): 15 items"

Step 1.5-1.6: 分红数据

Step 2: 并行获取K线 (ThreadPoolExecutor, max_workers=4)
  → 输出: "兴业银行(601166): 2000 bars"
  → 输出: "比亚迪(002594): 2000 bars"
  → ...
  → 写入 kline_daily 表 (upsert: 新数据插入, 已有数据更新)

Step 3: 回填预测验证
  → 查找 dir_hit IS NULL 的历史预测 (今天之前的)
  → 用实际K线验证: 比较预测方向 vs 实际涨跌
  → 更新 daily_predictions.dir_hit, range_hit
  → 输出: "兴业银行(601166) 2026-07-14: dir=HIT, range=MISS"

Step 4: 重新计算准确率
  → 统计 last_20 / last_60 窗口的方向和区间命中率
  → 写入 accuracy_stats 表

Step 4.5: 回测基线 + 熔断
  → 等权多数投票计算 baseline 准确率
  → 对比加权投票: "learned=58.3% baseline=55.2% Δ=↑3.1%"
  → 熔断检查: 连续5次错误 → 重置 learning_params

Step 5: 自学习 (Adaptive MWU) ← 🔴 回测权重冷启动在此生效
  ┌──────────────────────────────────────────────────┐
  │ lp = get_learning_params(code)                    │
  │ BACKTEST WEIGHTS COLD-START:                      │
  │   if lp['update_count'] == 0:                     │
  │       lp['signal_weights'] = backtest_weights   │  ← 第一次: 使用回测权重
  │   # MARKET REGIME ADAPTIVE:                       │
  │   regime = detect_market_regime(kdata)            │
  │   if regime in lp['regime_weights']:              │
  │       lp['signal_weights'] = blend(               │
  │           lp['signal_weights'],                   │
  │           lp['regime_weights'][regime],            │
  │           ratio=0.3)                              │  ← 30%倾向当前市场状态权重
  │                                                    │
  │ # 然后正常 MWU 微调:                               │
  │ β = 0.5 + 0.3 * clamp(0.3, accuracy, 0.8)        │
  │ w[s][p] = w[s][p] * e^(±0.5)                     │
  │ w[s][p] = w[s][p] * β + 1.0 * (1-β)               │
  │ normalize to sum=5 per signal                      │
  │                                                    │
  │ upsert_learning_params(code, lp)                   │
  └──────────────────────────────────────────────────┘
  → 输出: "兴业银行(601166): learning updated (count=1, beta=0.68)"

Step 6: 生成10天预测 ← 🔴 纸面交易的数据源
  → 清除今日及未来预测
  → 调用 calc_signals(kdata) → 计算10个信号
  → 调用 gen_multi_day_pred(code, kdata, info, lp, num_days=10)
  → 输出未来10个交易日的预测 (Day 1全信号, Day 2-10动量投影)
  → 写入 daily_predictions 表 (每条含: direction, confidence, entry_zone, ...)

Step 6.5: 纸面交易自动执行 ← 🔴 新增步骤
  ┌──────────────────────────────────────────────────┐
  │ from paper_trading import auto_execute            │
  │ auto_execute()                                    │
  │   for stock in watchlist:                        │
  │     pred = get_daily_predictions(code, TODAY)    │  ← 从Step 6的预测读取
  │     if not pred: continue                        │
  │                                                   │
  │     direction = pred['direction']                 │
  │     confidence = pred['confidence']               │
  │     entry_zone = pred['entry_zone']               │
  │                                                   │
  │     if direction == 'bullish' and conf > 0.5:     │
  │         kelly = min(0.3, conf * 2 - 1 + 0.05)   │
  │         qty = int(total * kelly / price / 100)*100│
  │         INSERT paper_trades (buy)                 │
  │         UPSERT paper_positions                    │
  │         UPDATE paper_account.cash                 │
  │     elif direction == 'bearish' and has_position: │
  │         INSERT paper_trades (sell)                │
  │         UPDATE/DELETE paper_positions             │
  │         UPDATE paper_account.cash                 │
  │     else: pass  # hold/watch                     │
  │                                                   │
  │     INSERT paper_suggestions                      │
  │     UPSERT paper_daily_snapshot                   │
  └──────────────────────────────────────────────────┘
  → 输出: "Paper: 买入 兴业银行 300股 @17.05 | 卖出 比亚迪 200股 | 招商银行 hold"

Step 7: 季节性 + 月K线 + 行情
Step 8: 完成
```

### B1 完成后数据库状态

```
daily_predictions: 每条股票新增30条预测 (6×30=180条, 累计201+180=381条)
  ├── 601166 2026-06-05: bullish, conf=65%, entry=17.05
  ├── 601166 2026-06-06: bullish, conf=62%, entry=17.10
  ├── ... (共10天)
  └── 601166 2026-06-17: neutral, conf=15%

paper_suggestions: 6条 (今天每只股票一条)
  ├── 601166: action=buy, qty=300, price=17.05, executed=1
  ├── 600036: action=hold, executed=0
  └── ...

paper_trades: 新增N条 (取决于有多少 buy/sell 信号)
paper_positions: 新增M条 (新买入的股票)
paper_daily_snapshot: 新增1条 (今天)
paper_account: 更新 cash 和 total_asset
learning_params: update_count += 1, signal_weights 已微调
```

---

## 阶段C: 日常查看 — 用户主动交互

### 操作时间轴

```
每日流程 (典型交易日):
  08:30  用户打开系统
  08:31  查看智能预测 (10天滚动预测)
  08:35  查看纸面交易 (昨日自动执行的结果)
  08:40  对比真实持仓
  09:00  参考纸面交易建议做真实投资决策
```

### 步骤 C1: 查看10天预测

```
用户操作: 导航栏 "股票分析预测" → "智能预测"

页面响应:
┌────────────────────────────────────────────────────────┐
│  📈 智能预测                     [兴业银行 ▼] [日期▼]   │
│                                                         │
│  当前: ¥17.37   预测: bullish ↑   置信度: 65%           │
│  预测区间: ¥17.05 ~ ¥17.85   建议: 低吸为主              │
│                                                         │
│  10天走势预测:                                           │
│  ┌──────┬──────┬──────┬──────┬──────┬──────┐           │
│  │06-05 │06-06 │06-09 │06-10 │ ...  │07-15 │           │
│  │🟢↑   │🟢↑   │🟡→   │🟡→   │ ...  │⚪→   │           │
│  │17.35 │17.42 │17.38 │17.40 │      │17.50 │           │
│  │65%   │62%   │48%   │45%   │      │15%   │           │
│  └──────┴──────┴──────┴──────┴──────┴──────┘           │
│                                                         │
│  技术信号详情 (10个):                                     │
│  MACD +0.15% ↑ | RSI 55.2 → | Bollinger 1.2σ → | ...   │
└────────────────────────────────────────────────────────┘

API调用: GET /api/v2/predictions/daily/601166
        → 返回该股票全部预测 (含10天未来 + 历史验证)
数据源: daily_predictions 表 ← gen_multi_day_pred() 输出
```

### 步骤 C2: 查看纸面交易结果

```
用户操作: 导航栏 "模拟交易" → "纸面交易"

页面响应:
┌────────────────────────────────────────────────────────┐
│  💼 纸面交易                          [🔄 重置账户]      │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │ 虚拟账户                                        │   │
│  │ 初始资金: ¥100,000   当前总资产: ¥100,850        │   │
│  │ 可用现金: ¥82,745    持仓市值: ¥18,105           │   │
│  │ 累计收益: +0.85%     (运行1天)                   │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  📋 今日交易结果 (2026-06-05, 自动执行)                 │
│  ┌─ ✅ 兴业银行 601166 ─────────────────────────────┐  │
│  │ 自动买入 300股 @ ¥17.05                          │  │
│  │ 预测 bullish, 置信度 65%, 仓位 12%                │  │
│  │ 理由: 10信号中6看多, MACD金叉, RSI上穿55          │  │
│  └──────────────────────────────────────────────────┘  │
│  ┌─ ⚪ 招商银行 600036 ─────────────────────────────┐  │
│  │ 持有观望                                          │  │
│  │ 预测 neutral, 置信度 42%, 信号分歧较大             │  │
│  └──────────────────────────────────────────────────┘  │
│  ┌─ ✅ 比亚迪 002594 ───────────────────────────────┐  │
│  │ 自动卖出 200股 @ ¥268.50                          │  │
│  │ 预测 bearish, 置信度 58%                          │  │
│  │ 实现盈亏: +¥1,240 (+2.3%)                         │  │
│  └──────────────────────────────────────────────────┘  │
│                                                         │
│  📦 虚拟持仓 (橙色表头)                                  │
│  ┌────────┬──────┬──────┬──────┬──────┬────────────┐  │
│  │ 代码   │ 持仓 │ 成本 │ 现价 │ 市值 │ 浮盈亏     │  │
│  │601166  │ 300  │17.05 │17.37 │5,211 │ +96 (+1.9%)│  │
│  │600900  │1000  │28.50 │28.65 │28,650│ +150(0.5%) │  │
│  └────────┴──────┴──────┴──────┴──────┴────────────┘  │
└────────────────────────────────────────────────────────┘

API调用:
  GET /api/v2/paper/account → 账户状态
  GET /api/v2/paper/suggestions → 今日交易建议/结果
  GET /api/v2/paper/positions → 虚拟持仓
```

### 步骤 C3: 查看资金曲线

```
用户操作: 导航栏 "模拟交易" → "交易历史"

页面响应:
┌────────────────────────────────────────────────────────┐
│  📜 交易历史                                            │
│                                                         │
│  资金曲线 [30天] [90天] [180天]                          │
│  ┌──────────────────────────────────────────────────┐  │
│  │  ¥110,000                                         │  │
│  │  ¥105,000    ████████████░░░░░░  ← 纸面账户(蓝)   │  │
│  │  ¥100,000 ████░░░░░░░░░░░░░░░░  ← 买入持有(灰)   │  │
│  │   ¥95,000                                         │  │
│  │          06-01  06-02  06-03  06-04  06-05        │  │
│  └──────────────────────────────────────────────────┘  │
│                                                         │
│  统计摘要                                                │
│  总交易: 3次 | 胜率: 66.7% | 盈亏比: 2.1               │
│                                                         │
│  交易记录                               [全部 ▼]         │
│  ┌─────────┬──────┬──────┬──────┬──────┬──────────┐   │
│  │ 日期    │ 代码 │ 方向 │ 数量 │ 价格 │ 盈亏     │   │
│  │06-05    │601166│ 买入 │ 300  │17.05 │ —        │   │
│  │06-05    │002594│ 卖出 │ 200  │268.50│+1,240    │   │
│  │06-05    │600900│ 买入 │1000  │28.50 │ —        │   │
│  └─────────┴──────┴──────┴──────┴──────┴──────────┘   │
└────────────────────────────────────────────────────────┘

API调用:
  GET /api/v2/paper/trades → 交易记录
  GET /api/v2/paper/performance?days=90 → 表现指标 + 资金曲线
```

---

## 异常与边界情况

### 情况1: 回测运行时K线数据不足

```
触发条件: 某只股票K线 < 252条

系统行为:
  → 跳过该股票
  → 日志输出: "002366: insufficient K-line data (200 bars, need 252), skip"
  → 回测结果中不包含该股票
  → 该股票的 learning_params 不更新
  → 该股票继续使用在线 MWU 学习 (从 weight=1.0 开始)
```

### 情况2: 纸面交易资金不足

```
触发条件: 买入金额 > 可用现金

系统行为:
  → 跳过该买入建议
  → 日志输出: "601166: buy skipped, cash 5,230 < need 5,205"
  → 不影响其他股票的交易执行
  → 次日有足够现金时会继续尝试
```

### 情况3: 当日无预测数据

```
触发条件: daily_predictions 中 date=TODAY 的记录不存在
  (例如: 预测生成失败、系统刚启动尚未运行 sync_all.py)

系统行为:
  → auto_execute() 读取预测 → 结果为空
  → 不执行任何纸面交易
  → 日志输出: "Paper trading: no predictions for today, skip"
  → GET /api/v2/paper/suggestions → {data: [], count: 0}
  → 前端显示: "今日暂无预测数据，纸面交易未执行"
```

### 情况4: 熔断触发

```
触发条件: 某只股票连续5次预测错误

系统行为:
  → 重置 learning_params 到 new_lp() (V3 defaults)
  → 日志输出: "⚠️ 兴业银行(601166): 5 consecutive misses! Resetting learning params to baseline."
  → 但 backtest_weights 和 regime_weights 保留 (下次冷启动仍可用)
  → 该股票的纸面交易权重暂时回到初始值
```

### 情况5: 用户手动重置纸面账户

```
用户操作: 纸面交易页 → 点击 [🔄 重置账户] → 确认弹窗 → 确认

系统行为:
  → POST /api/v2/paper/reset
  → UPDATE paper_account.cash = 100000
  → DELETE FROM paper_positions (清空虚拟持仓, 但历史交易保留)
  → paper_trades 表不动 (保留完整交易历史)
  → 返回 {success: true, message: "虚拟账户已重置", cash: 100000}
```

### 情况6: 同一天多次手动刷新

```
触发条件: 用户在同一天内多次点击 [🔄 刷新]

系统行为:
  → 每次刷新都会执行 sync_all.py 完整流程
  → Step 6.5 纸面交易检测到当日已存在 paper_suggestions
    → SELECT * FROM paper_suggestions WHERE date=TODAY AND executed=1
    → 若已存在已执行记录 → 跳过重复交易
    → 日志输出: "Paper trading: already executed today, skip"
  → 预测数据会更新 (latest K-line → 重新计算10信号 → 重新生成10天预测)
  → 但纸面交易不会重复执行，避免同一日内的重复买卖
```

---

## 完整数据依赖关系

```
┌─────────────────────────────────────────────────────────────┐
│  阶段A (一次性):                                             │
│    kline_daily ──→ backtest_engine.py ──→ learning_params    │
│                                              .backtest_weights│
│                                              .regime_weights │
├─────────────────────────────────────────────────────────────┤
│  阶段B (每日自动):                                           │
│    kline_daily + learning_params ──→ sync_all.py Step 5      │
│      ├── cold-start: backtest_weights → signal_weights      │
│      ├── regime: regime_weights[regime] → 30% blend         │
│      └── MWU online: e^(±0.5) + adaptive β                  │
│                                     ↓                        │
│                            学习后权重 + kline_daily          │
│                                     ↓                        │
│                             sync_all.py Step 6               │
│                               calc_signals() + gen_pred()    │
│                                     ↓                        │
│                             daily_predictions (10天)         │
│                                     │                        │
│                    ┌────────────────┼────────────────┐       │
│                    ▼                ▼                ▼       │
│             前端智能预测    paper_trading.py    回填验证     │
│             (用户查看)     (自动交易)        (dir_hit更新)  │
│                                │                            │
│                     ┌──────────┼──────────┐                 │
│                     ▼          ▼          ▼                 │
│              paper_trades  paper_positions paper_snapshot   │
├─────────────────────────────────────────────────────────────┤
│  阶段C (用户查看):                                           │
│    前端 ←─ GET /api/v2/predictions/daily/{code}              │
│    前端 ←─ GET /api/v2/paper/account                         │
│    前端 ←─ GET /api/v2/paper/suggestions                     │
│    前端 ←─ GET /api/v2/paper/positions                       │
│    前端 ←─ GET /api/v2/paper/trades                          │
│    前端 ←─ GET /api/v2/paper/performance                     │
└─────────────────────────────────────────────────────────────┘
```

---

## 页面导航完整映射

```
App.vue 导航栏
├── 个人交易数据
│   ├── /overview       → Overview.vue       (持仓总览)
│   ├── /trades          → Trades.vue         (交易记录)
│   ├── /fees            → Fees.vue           (手续费分析)
│   └── /manage          → Management.vue     (管理设置)
├── 股票分析预测
│   ├── /intelligence    → Intelligence.vue   (智能预测, 10天)
│   └── /expert          → Expert.vue         (专家分析)
├── 股票信息收集
│   ├── /news            → News.vue           (新闻动态)
│   └── /kline           → Kline.vue          (K线走势)
└── 🔴 模拟交易 (新增)
    ├── /backtest        → BacktestPage.vue   (回测分析)
    ├── /paper           → PaperTrading.vue   (纸面交易)
    └── /paper/history   → PaperHistory.vue   (交易历史)
```
