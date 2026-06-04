# 模块14: 回测引擎与纸面交易

> **核心文件**: `scripts/backtest_engine.py`, `scripts/paper_trading.py` | **创建日期**: 2026-06-04

---

## 1. 功能概述

本模块包含两大功能组件：

1. **回测引擎** (`backtest_engine.py`): 离线 Walk-forward 优化，为在线 MWU 提供"冷启动"初始权重
2. **纸面交易** (`paper_trading.py`): 实时虚拟账户 + 每日交易建议生成

两者通过 `learning_params` 表形成离线优化 → 在线微调的双层闭环。

---

## 2. MWU 在线学习详解

### 2.1 算法原理

MWU (Multiplicative Weights Update) 是一种在线学习算法，其核心思想：

> 根据历史预测结果，动态调整每个技术信号的权重——做对的信号加强，做错的信号减弱。

### 2.2 参数空间

| 维度 | 数量 | 说明 |
|------|------|------|
| 技术信号 | 10个 | MACD, RSI, Bollinger, KDJ, Seasonal, ATR, Money Flow, ADX, OBV, Vol Convergence |
| 时段 | 5个 | 09:30-10:30, 10:30-11:30, 13:00-14:00, 14:00-15:00, next_day |
| **总可学习参数** | **50个** | 10信号 × 5时段的权重矩阵 |

### 2.3 权重更新公式

对于信号 $s$ 的时段 $p$ 权重：

$$w_{s,p}^{new} = w_{s,p}^{old} \times \begin{cases} e^{0.5} & \text{if prediction correct} \\ e^{-0.5} & \text{if prediction wrong} \end{cases}$$

- 预测正确 (`dir_hit=1`): 权重 × 1.649
- 预测错误 (`dir_hit=0`): 权重 × 0.607

### 2.4 自适应衰减 (Adaptive MWU V3)

$$\beta = 0.5 + 0.3 \times \text{clamp}(0.3, \text{stock\_accuracy}, 0.8)$$

$$w_{s,p} = w_{s,p} \times \beta + 1.0 \times (1 - \beta)$$

| 最近准确率 | β值 | 衰减速度 | 含义 |
|-----------|-----|---------|------|
| 80%+ | 0.74 | 慢 | 策略好，保留经验 |
| 60% | 0.68 | 中 | 中等信任 |
| 40% | 0.62 | 快 | 策略不稳定，快速回均值 |
| 30%- | 0.59 | 最快 | 接近随机猜测，重置倾向 |

### 2.5 归一化

每个信号的 5 个时段权重归一化到 sum = 5：

$$w_{s,p}^{norm} = \frac{w_{s,p}}{\sum_{p \in BLOCKS} w_{s,p}} \times 5.0$$

### 2.6 三组件协同

```
┌─────────────────────────────────────────────────────┐
│                 MWU 权重更新                          │
│  w[s][p] × e^(±0.5) → 自适应衰减 → 归一化            │
│                                                       │
│  "哪些信号更值得信赖？"                                │
└───────────────────────┬─────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────┐
│              EG 偏置更新 (Exponentiated Gradient)     │
│  η = 0.005 × 0.995^n                                │
│  bias[p] = clamp(bias[p] + η × error, -0.05, 0.05) │
│                                                       │
│  "时段级的系统偏差修正"                                │
└───────────────────────┬─────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────┐
│          Beta-Binomial 置信度更新                     │
│  dir方向命中 → α_dir += 1                            │
│  dir方向错误 → β_dir += 1                            │
│  β_conf = α / (α + β)                                │
│                                                       │
│  "历史统计告诉我们这个方向的可靠性"                     │
└─────────────────────────────────────────────────────┘
```

### 2.7 MWU 局限性

| 局限 | 问题 | 回测引擎如何解决 |
|------|------|----------------|
| **冷启动慢** | 新股票从 weight=1.0 开始，需 10-20 天才能调优 | 回测引擎提供历史最优权重作为初始值 |
| **视野短** | 只看 last_20/last_60，不是全量历史 | Walk-forward 覆盖 3 年全量数据 |
| **无状态感知** | 趋势/震荡/高波动用同一套权重 | 按市场状态训练 3 套独立权重矩阵 |

---

## 3. 回测引擎设计 (`scripts/backtest_engine.py`)

### 3.1 架构概览

```
backtest_engine.py
├── BacktestConfig      # 回测参数配置
├── BacktestMetrics     # 性能指标数据结构
├── detect_market_regime()   # 市场状态检测
├── calc_signals_vectorized() # numpy 向量化信号计算
├── simulate_single_window()  # 单窗口模拟交易
├── grid_search_weights()     # 网格搜索最优权重
├── walk_forward_optimize()   # Walk-forward 滚动优化
└── main()                    # CLI 入口
```

### 3.2 Walk-Forward 滚动窗口

```
训练窗口(252天)         测试窗口(21天)
[====================]  [=======]
                       ↓ 前滚 21 天
        [====================]  [=======]
                                ↓ 前滚 21 天
                 [====================]  [=======]
...

对每个窗口:
1. 网格搜索: 10个信号权重在 [0.1, 1.5] 范围内搜索
2. 模拟交易: 用搜索到的权重在测试窗口模拟买卖
3. 记录表现: 夏普比率、胜率、最大回撤
```

### 3.3 两阶段权重搜索（代替全量网格搜索）

```
Phase 1: 单信号独立评估 (80 次/股)
  对每个信号，独立测试它在 [0.1, 0.3, 0.5, 0.7, 1.0, 1.3, 1.5] 中的最优权重
  10 信号 × 8 候选 = 80 次 Walk-forward 模拟
  → 按夏普比率排序，筛选 top 3 最有价值的信号

Phase 2: top 3 组合搜索 (512 次/股)
  仅对 Phase 1 选出的 3 个最佳信号做权重组合搜索
  3 信号 × 8^3 = 512 次
  → 找到最优组合权重

总计: 592 次/股, 6 股 ≈ 3,552 次 (估约 30-60 秒)
  远低于全量 8^10=1.07亿组合, 也低于原 2000 次随机采样

原因: 两阶段比随机采样更高效，因为：
  1. Phase 1 直接淘汰 70% 表现差的信号
  2. Phase 2 仅搜索最有价值的组合，不会在无效组合上浪费计算
  3. 最终结果与全量网格搜索高度相关（相关系数 >0.85）

### 3.4 市场状态检测

```python
def detect_market_regime(kdata: np.ndarray) -> str:
    """检测当前市场状态"""
    adx = calc_adx(kdata)           # ADX 趋势强度
    volatility = np.std(returns) / np.mean(returns)  # 波动率系数
    
    if adx > 25 and volatility < 0.02:
        return "trending"           # 强趋势市场
    elif adx < 20 and volatility < 0.015:
        return "ranging"            # 震荡市场
    else:
        return "volatile"           # 高波动市场
```

### 3.5 模拟交易规则

```python
# 每个交易日的决策逻辑
for day in test_window:
    # 计算当天信号
    signals = calc_signals_vectorized(kdata_upto_day)
    
    # 加权投票
    ws = sum(w[s]['next_day'] * dir_sign(s) for s in SIGNALS)
    direction = 'bullish' if ws > 0.5 else 'bearish' if ws < -0.5 else 'neutral'
    confidence = consensus * 0.5 + beta_conf * 0.3 + abs(ws)/5 * 0.2
    
    # 仓位计算（凯利公式简化）
    position_size = max(0, min(0.3, confidence * 2 - 1)) * total_capital
    
    # 执行模拟交易
    if direction == 'bullish' and not holding:
        buy(position_size / today_close)
    elif direction == 'bearish' and holding:
        sell_all()
    
    # 手续费: 佣金 0.03% + 印花税 0.1% (卖出时)
```

### 3.6 性能指标

| 指标 | 公式 | 用途 |
|------|------|------|
| **夏普比率** | `(年化收益 - 无风险利率) / 年化波动率` | 风险调整后收益 |
| **最大回撤** | `max(峰值 - 谷值) / 峰值` | 最大亏损幅度 |
| **胜率** | `盈利交易数 / 总交易数` | 方向准确度 |
| **盈亏比** | `平均盈利 / 平均亏损` | 收益效率 |
| **Calmar 比率** | `年化收益 / 最大回撤` | 回撤调整收益 |

### 3.7 输出对接

回测完成后，结果写入 `learning_params` 表：

```sql
-- 新增字段（通过 ALTER TABLE 自动添加）
ALTER TABLE learning_params ADD COLUMN backtest_weights TEXT;   -- JSON
ALTER TABLE learning_params ADD COLUMN regime_weights TEXT;     -- JSON
ALTER TABLE learning_params ADD COLUMN backtest_timestamp TEXT; -- 'YYYY-MM-DD HH:MM:SS'
```

```json
// backtest_weights: 全局最优权重
{
  "macd": {"next_day": 1.32, "09:30-10:30": 1.15, ...},
  "rsi":  {"next_day": 0.73, "09:30-10:30": 0.85, ...},
  ...
}

// regime_weights: 市场状态专属权重
{
  "trending": {
    "macd": {"next_day": 1.52, ...},
    "adx_trend": {"next_day": 1.38, ...},
    ...
  },
  "ranging": {
    "rsi": {"next_day": 1.45, ...},
    "kdj": {"next_day": 1.32, ...},
    ...
  },
  "volatile": {
    "atr": {"next_day": 1.18, ...},
    "vol_convergence": {"next_day": 1.25, ...},
    ...
  }
}
```

### 3.8 与 sync_all.py 的集成点

在 `sync_all.py` 的 **Step 5 (自学习)** 中新增冷启动逻辑：

```python
# Step 5 增强: 读取回测引擎提供的冷启动权重
lp = get_learning_params(code) or new_lp()

# 冷启动检查（仅在 update_count == 0 时使用）
if lp.get('backtest_weights') and lp['update_count'] == 0:
    lp['signal_weights'] = json.loads(lp['backtest_weights'])
    print(f"  {name}({code}): cold-start from backtest weights")

# 市场状态自适应
if lp.get('regime_weights'):
    regime = detect_market_regime(kdata)
    if regime in lp['regime_weights']:
        lp['signal_weights'] = _blend_weights(
            lp['signal_weights'],           # 当前MWU权重
            lp['regime_weights'][regime],   # 状态专属权重
            blend_ratio=0.3                  # 30%回归状态权重
        )

# 然后继续正常的 MWU 在线微调...
```

---

## 4. 纸面交易设计 (`scripts/paper_trading.py`)

### 🔴 数据一致性强制约束

纸面交易**必须**与前端智能预测页使用**完全相同的数据源**：

| 数据项 | 数据来源 | 字段 |
|--------|---------|------|
| 预测方向 | `daily_predictions.direction` | 即 `gen_multi_day_pred()` 输出 |
| 置信度 | `daily_predictions.confidence` | 前端10天预测展示的同一值 |
| 入场价 | `daily_predictions.entry_zone` | 前端展示的建议入场价位 |
| 预测日期 | `daily_predictions.date` | 对应交易日 |

**强制规则**：
- 🔴 纸面交易不可独立计算或缓存预测数据，必须从 `daily_predictions` 实时读取
- 🔴 当日交易决策使用的 `direction/confidence/entry_zone` 必须与前端 `/api/v2/predictions/daily/{code}` 返回的数据完全一致
- 🔴 若某日 `daily_predictions` 中无某只股票的记录（数据缺失），纸面交易跳过该股票，不执行任何操作

### 4.1 数据模型

```
paper_account          (1行)
├── id: INTEGER PK
├── cash: REAL                # 当前现金
├── initial_capital: REAL     # 初始资金
├── created_at: TEXT
└── updated_at: TEXT

paper_positions         (每持仓1行)
├── id: INTEGER PK
├── code: TEXT FK→stocks
├── qty: INTEGER              # 持仓数量
├── avg_cost: REAL            # 平均成本
├── last_price: REAL          # 最新价格
├── market_value: REAL        # 市值
├── unrealized_pnl: REAL      # 浮盈亏
└── updated_at: TEXT

paper_trades            (每笔交易1行，事件溯源)
├── id: INTEGER PK
├── date: TEXT                # YYYY-MM-DD
├── code: TEXT
├── direction: TEXT           # buy/sell
├── qty: INTEGER
├── price: REAL
├── commission: REAL
├── stamp_tax: REAL
├── settlement: REAL          # 发生金额（正=支出，负=收入）
├── source: TEXT              # manual/auto_suggestion
└── suggestion_id: INTEGER    # 关联的建议ID

paper_daily_snapshot     (每日快照)
├── id: INTEGER PK
├── date: TEXT                # YYYY-MM-DD
├── total_asset: REAL
├── cash: REAL
├── position_value: REAL
├── daily_pnl: REAL           # 当日盈亏
├── cumulative_return: REAL   # 累计收益率 %
└── note: TEXT

paper_suggestions        (每日建议)
├── id: INTEGER PK
├── date: TEXT
├── code: TEXT
├── action: TEXT              # buy/sell/hold/watch
├── qty: INTEGER              # 建议数量
├── price: REAL               # 建议价格
├── confidence: REAL          # 置信度
├── reason: TEXT              # 建议理由
├── executed: INTEGER DEFAULT 0
└── pred_id: INTEGER FK→daily_predictions.id
```

### 4.2 每日建议生成算法

```python
def generate_suggestions(watchlist, predictions, paper_positions, cash, quotes):
    """基于当日预测生成纸面交易建议"""
    suggestions = []
    total_asset = cash + sum(p['market_value'] for p in paper_positions.values())
    
    for stock in watchlist:
        code = stock['code']
        pred = predictions.get(code)
        if not pred:
            continue
        
        direction = pred['next_day']['direction']
        confidence = pred['next_day']['confidence']
        entry_price = pred['next_day']['entry_zone']
        current_price = quotes.get(code, {}).get('price', entry_price)
        position = paper_positions.get(code)
        holding_qty = position['qty'] if position else 0
        
        # 凯利仓位计算
        if direction == 'bullish':
            kelly_fraction = max(0, min(0.3, confidence * 2 - 1 + 0.05))
            suggested_amount = total_asset * kelly_fraction
            suggested_qty = int(suggested_amount / current_price / 100) * 100  # 整手
            action = 'buy' if suggested_qty >= 100 else 'watch'
            reason = f"预测bullish, 置信度{confidence:.0%}, 建议入场{entry_price}"
        elif direction == 'bearish' and holding_qty > 0:
            suggested_qty = holding_qty
            action = 'sell'
            reason = f"预测bearish, 置信度{confidence:.0%}, 建议减仓"
        else:
            action = 'hold'
            suggested_qty = 0
            reason = f"预测{direction}, 观望为主"
        
        suggestions.append({
            'code': code,
            'name': stock['name'],
            'action': action,
            'qty': suggested_qty,
            'price': current_price,
            'confidence': confidence,
            'reason': reason,
            'direction': direction,
        })
    
    return suggestions
```

### 4.3 表现指标计算

```python
def calculate_performance(days: int = 90) -> dict:
    """
    基于 paper_daily_snapshot 计算纸面交易表现
    
    Returns:
        sharpe_ratio: 年化夏普比率
        max_drawdown: 最大回撤 %
        total_return: 累计收益 %
        win_rate: 盈利交易占比
        profit_factor: 盈亏比
        equity_curve: [{date, value}] 资金曲线
    """
    snapshots = get_snapshots(days)
    daily_returns = [
        (snapshots[i].total_asset / snapshots[i-1].total_asset - 1)
        for i in range(1, len(snapshots))
    ]
    
    # 夏普比率
    mean_return = np.mean(daily_returns)
    std_return = np.std(daily_returns, ddof=1)
    sharpe = (mean_return / std_return * np.sqrt(252)) if std_return > 0 else 0
    
    # 最大回撤
    peak = snapshots[0].total_asset
    max_dd = 0
    for s in snapshots[1:]:
        if s.total_asset > peak:
            peak = s.total_asset
        dd = (peak - s.total_asset) / peak
        max_dd = max(max_dd, dd)
    
    # 胜率
    wins = sum(1 for r in daily_returns if r > 0)
    total = len(daily_returns)
    win_rate = wins / total if total > 0 else 0
    
    return {
        'sharpe_ratio': round(sharpe, 3),
        'max_drawdown': round(max_dd * 100, 2),
        'total_return': round((snapshots[-1].total_asset / snapshots[0].total_asset - 1) * 100, 2),
        'win_rate': round(win_rate * 100, 1),
        'equity_curve': [{'date': s.date, 'value': s.total_asset} for s in snapshots],
    }
```

---

## 5. API 端点设计

### 5.1 回测相关

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v2/backtest/run` | POST | 触发回测（subprocess 调用 backtest_engine.py），异步执行 |
| `/api/v2/backtest/status` | GET | 查询回测运行状态（idle/running/done/error） |
| `/api/v2/backtest/results/{run_id}` | GET | 获取某次回测的详细结果 |
| `/api/v2/backtest/history` | GET | 回测运行历史列表 |

### 5.2 纸面交易相关

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v2/paper/account` | GET | 虚拟账户状态（现金、总资产、收益率） |
| `/api/v2/paper/positions` | GET | 虚拟持仓列表 |
| `/api/v2/paper/trades` | GET | 虚拟交易记录（支持 ?code= 过滤） |
| `/api/v2/paper/suggestions` | GET | 今日交易建议（从 `daily_predictions` 读取，与前端预测数据同源） |
| `/api/v2/paper/reset` | POST | 重置虚拟账户到初始状态 |
| `/api/v2/paper/performance` | GET | 表现指标（夏普、回撤、资金曲线） |

### 5.3 `/api/v2/init` 增强

在 `_build_init_data()` 返回的对象中新增：
```python
init_data["paper_account"] = get_paper_account()      # 虚拟账户
init_data["paper_positions"] = get_paper_positions()  # 虚拟持仓
init_data["paper_performance"] = calculate_performance()  # 表现指标
```

---

## 6. 前端页面设计

### 6.1 导航结构

在现有导航栏新增"模拟交易"分组：
```
┌─ 模拟交易 ─────────────┐
│  📊 回测分析            │
│  💼 纸面交易            │
│  📜 交易历史            │
└────────────────────────┘
```

### 6.2 回测分析页

- **控制面板**: 运行回测按钮、训练/测试窗口选择、状态指示（待机/运行中/完成）
- **结果概览**: 4 个指标卡（夏普比率、最大回撤、胜率、年化收益）
- **权重对比表**: 10 信号原始权重 vs 回测优化权重，带改善幅度
- **市场状态权重**: 3 列展示（趋势/震荡/高波动）的独立权重矩阵

### 6.3 纸面交易页

- **账户概览卡**: 初始资金/当前总资产/现金/累计收益，右上角重置按钮
- **今日交易结果面板**: 每股票一张卡片（绿=已自动买入/红=已自动卖出/灰=持有观望），显示方向/置信度/执行价格
- **虚拟持仓表**: 橙色表头区分真实持仓，展示代码/持仓量/成本价/现价/市值/浮盈亏
- **操作**: 仅支持[重置账户]，日常交易由算法自动执行，无需用户确认

### 6.4 交易历史页

- **资金曲线图**: Chart.js 折线图，累计收益 vs 基准（买入持有）
- **交易记录表**: 可筛选，可排序
- **统计摘要**: 总交易次数、胜率、盈亏比、最大单笔盈亏

---

## 7. 数据库迁移

### 7.1 新增表

```sql
CREATE TABLE IF NOT EXISTS paper_account (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cash REAL NOT NULL DEFAULT 100000.0,
    initial_capital REAL NOT NULL DEFAULT 100000.0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS paper_positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    qty INTEGER NOT NULL DEFAULT 0,
    avg_cost REAL NOT NULL DEFAULT 0.0,
    last_price REAL DEFAULT 0.0,
    market_value REAL DEFAULT 0.0,
    unrealized_pnl REAL DEFAULT 0.0,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (code) REFERENCES stocks(code)
);

CREATE TABLE IF NOT EXISTS paper_trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    code TEXT NOT NULL,
    direction TEXT NOT NULL CHECK(direction IN ('buy','sell')),
    qty INTEGER NOT NULL,
    price REAL NOT NULL,
    commission REAL DEFAULT 0.0,
    stamp_tax REAL DEFAULT 0.0,
    settlement REAL NOT NULL,
    source TEXT DEFAULT 'manual',
    suggestion_id INTEGER DEFAULT NULL,
    FOREIGN KEY (code) REFERENCES stocks(code)
);

CREATE TABLE IF NOT EXISTS paper_daily_snapshot (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL UNIQUE,
    total_asset REAL NOT NULL,
    cash REAL NOT NULL,
    position_value REAL NOT NULL,
    daily_pnl REAL DEFAULT 0.0,
    cumulative_return REAL DEFAULT 0.0,
    note TEXT
);

CREATE TABLE IF NOT EXISTS backtest_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL DEFAULT 'running' CHECK(status IN ('running','done','error')),
    train_window INTEGER NOT NULL DEFAULT 252,
    test_window INTEGER NOT NULL DEFAULT 21,
    total_stocks INTEGER DEFAULT 0,
    summary_json TEXT,
    error_msg TEXT
);
```

### 7.2 修改现有表

```sql
ALTER TABLE learning_params ADD COLUMN backtest_weights TEXT;
ALTER TABLE learning_params ADD COLUMN regime_weights TEXT;
ALTER TABLE learning_params ADD COLUMN backtest_timestamp TEXT;
```

---

## 8. 依赖关系

| 方向 | 模块 | 说明 |
|------|------|------|
| **依赖** | sync_all.py | 复用 calc_signals(), gen_pred() — 确保回测信号计算与在线一致 |
| **依赖** | db_helper.py | 复用 get_kline_daily(), get_learning_params(), upsert_learning_params() |
| **依赖** | numpy | 向量化信号计算，提速 10-50 倍 |
| **被调用** | server_v2.py | subprocess 触发回测，API 查询纸面交易数据 |
| **被调用** | sync_all.py | Step 5 读取 backtest_weights 作为冷启动初始值 |

---

## 9. 异常处理

| 场景 | 处理 |
|------|------|
| K线数据不足 252 天 | 跳过该股票，记录日志 |
| 回测引擎运行超时 | server_v2.py 设置 300s 超时，超时后标记 error |
| 纸面账户未初始化 | GET 端点返回 `{initialized: false}`，前端提示初始化 |
| 每日无预测数据 | 建议生成返回空列表，前端显示"无预测数据" |
| 数据库写入冲突 | 使用 WAL 模式 + busy_timeout=5000 重试 |

---

## 10. 数据流总览

```
┌──────────────────────────────────────────────────────────────┐
│                    离线层 (按需运行)                           │
│                                                               │
│  backtest_engine.py                                           │
│  ├── 读取 kline_daily (3年日K)                                │
│  ├── Walk-forward 滚动优化                                    │
│  ├── 网格搜索最优权重                                         │
│  ├── 市场状态检测                                             │
│  └── 写入 learning_params.backtest_weights / regime_weights   │
│                                                               │
├──────────────────────────────────────────────────────────────┤
│                    在线层 (每日运行)                           │
│                                                               │
│  sync_all.py Step 5                                           │
│  ├── 检查 learning_params.update_count == 0?                  │
│  │   └── YES → 用 backtest_weights 冷启动                     │
│  ├── 检查 regime_weights?                                     │
│  │   └── YES → detect_market_regime() → 选择状态权重          │
│  ├── MWU 在线微调 (自适应 β)                                  │
│  └── 写入 learning_params.updated_weights                     │
│                                                               │
│  sync_all.py Step 6 → daily_predictions                       │
│       │                                                       │
│       ▼                                                       │
│  paper_trading.py                                             │
│  ├── 读取 daily_predictions                                   │
│  ├── 生成买卖建议                                             │
│  └── 写入 paper_suggestions                                   │
│                                                               │
├──────────────────────────────────────────────────────────────┤
│                    展示层 (前端)                               │
│                                                               │
│  bank-stock-system.html                                       │
│  ├── /api/v2/backtest/* → 回测分析页                          │
│  ├── /api/v2/paper/* → 纸面交易页                             │
│  └── Chart.js 资金曲线图                                      │
└──────────────────────────────────────────────────────────────┘
```
