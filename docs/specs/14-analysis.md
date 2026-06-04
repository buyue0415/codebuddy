# 模块14: 技术方案深度分析

> **文档类型**: 技术审查报告 | **版本**: v1.0 | **创建日期**: 2026-06-04
> **审查范围**: 回测引擎 + 纸面交易技术方案，含与现有系统的集成点

---

## 1. 架构设计审查

### 1.1 🔴 高风险: sync_all.py 单体膨胀

**问题描述**: 当前方案将纸面交易自动执行 (Step 6.5) 直接嵌入 `sync_all.py` 的 8 步流程中。sync_all.py 已有约 950 行，承担新闻抓取、K线同步、预测回填、自学习、预测生成、季节性计算等工作。新增 Step 6.5 后，该文件将进一步膨胀。

**影响**:
- 单一文件违反单一职责原则
- 任一子步骤失败可能影响全流程（如 K 线拉取失败 → 预测跳过 → 纸面交易跳过）
- 排查问题需要跟踪 8+ 步的完整流程，调试困难

**优化方向**:
```python
# 改进: 将纸面交易作为独立调用，而非嵌入 sync_all.py
# sync_all.py 完成后，scheduler.py 或 server_v2.py 主动调用
# python scripts/scheduler.py sync  →  sync_all.py (Step 1-7)
#                                   →  paper_trading.py auto_execute (独立步骤)
```
**约束**: 纸面交易必须在 Step 6 完成后调用，依赖 `daily_predictions` 表中今日数据。

---

### 1.2 🔴 高风险: 回测引擎信号计算与实际预测不一致

**问题描述**: `backtest_engine.py` 需要独立实现 `calc_signals()` 来评估历史权重组合。但该实现可能与 `sync_all.py` 中的 `calc_signals()` 存在细微差异（如 numpy 向量化带来的数值精度、边界条件处理差异）。

**影响**:
- 回测评估的权重在实际预测中表现不同（"回测好 ≠ 实盘好"的根源）
- 冷启动权重可能并非真正最优
- 排查这种差异极其困难（回测与实盘运行在不同代码路径）

**优化方向**:
```python
# 改进: backtest_engine.py 不应重新实现 calc_signals
# 方案A: import 同步引擎的信号计算函数
from sync_all import calc_signals, gen_pred

# 方案B: 抽取共享模块
# scripts/signals.py        # 技术信号计算 (纯函数)
# scripts/prediction.py     # 预测生成逻辑
# scripts/backtest_engine.py  # 导入 signals.py
# scripts/sync_all.py         # 导入 signals.py + prediction.py
```
**约束**: 抽取公共模块不得改变现有 API 和 sync_all.py 的行为，需通过回归测试。

---

### 1.3 🟡 中风险: 冷启动权重与 MWU 在线微调的冲突

**问题描述**: 当前设计中，`backtest_weights` 仅在 `update_count == 0` 时作为冷启动使用。但对于已有学习历史的股票，回测权重不会生效。同时 `regime_weights` 的 30% blend 可能被 MWU 的 `e^(±0.5)` 快速覆盖。

**影响**:
- 已学习股票运行回测后，"最新"的优化权重无法完全替换在线 MWU 权重
- MWU 在线微调可能在 5-10 次更新后完全覆盖 regime_weights 的影响
- 回测优化的价值对已成熟股票打折扣

**优化方向**:
```python
# 可选改进: 增加定期回测校准策略
# 方案A: 每月运行回测后，用回测权重替换当前权重的 50%
if lp['backtest_timestamp'] is recent:
    lp['signal_weights'] = blend(
        lp['signal_weights'],     # 当前在线权重
        backtest_weights,          # 回测最优权重
        ratio=0.5                  # 50% 倾向回测
    )

# 方案B: regime_weights 使用更高 blend ratio (0.5 而非 0.3)
```
**注意**: 高频替换可能丢失 MWU 对最新市场变化的适应性，需平衡。

---

## 2. 性能瓶颈分析

### 2.1 🔴 高风险: 网格搜索计算量

**问题描述**: 10 个信号 × 每个信号 `next_day` 权重在 [0.1, 0.3, 0.5, 0.7, 1.0, 1.3, 1.5] 中搜索 = 8^10 ≈ 1.07 亿组合。即使限 2000 次随机采样，每次采样需模拟 3 年交易。按每窗口约 200 次买卖，6 只股票 × 2000 采样 × (3×252 天 / 21 天步长) ≈ 6 × 2000 × 36 = 432,000 次模拟。

**量化估算**:
- 单次信号计算 (numpy): ~0.01 秒（含 2000 天 × 10 信号向量化）
- 单次模拟交易: ~0.002 秒
- 每窗口模拟: 0.01 + 21天 × 0.002 = 0.052 秒
- 每股票 2000 采样: 2000 × 0.052 = 104 秒
- 6 只股票: 6 × 104 = **624 秒** (> 300 秒 API 超时!)

**影响**:
- 实际运行时间可能远超 120 秒估算，触发 API 超时
- ThreadPoolExecutor 在 Windows 上受 GIL 限制，并行效果有限
- 长时间计算阻塞后端线程

**优化方向**:
```python
# 1. 两阶段优化代替全量网格搜索
# Phase 1: 单信号独立评估 (10 × 8 = 80 次) → 筛选 top 3 信号
# Phase 2: top 3 信号的权重组合搜索 (8^3 = 512 次) → 仅需 3.4 秒/股

# 2. 步长优化
# 不用 0.1 步长，用对数分布: [0.1, 0.25, 0.5, 0.75, 1.0, 1.5]
# 6^10 = 60M → 2000 次该足够

# 3. 缓存优化
# 每只股票只计算一次 cal_signals 的历史结果，缓存到内存
# 2000 次采样复用同一信号数据，只改变权重投票
```
**约束**: 限 2000 次/股，总运行时间必须 < 300 秒。

---

### 2.2 🟡 中风险: SQLite 写入竞争

**问题描述**: `sync_all.py` Step 6 写入预测 + Step 6.5 写入纸面交易数据，全部通过 `db_helper.py` 串行写入 SQLite。WAL 模式允许并发读但写仍然串行。6 只股票 × 10 天 = 60 条预测 + 6 条交易 + 持仓更新 + 快照 ≈ 80+ 次写操作。

**影响**:
- 写入串行化可能拖慢整体流程 5-10 秒
- 多个 `get_db()` → `close()` 调用增加连接开销

**优化方向**:
```python
# 批量写入代替逐条插入
def insert_daily_predictions_batch(predictions: list) -> int:
    db = get_db()
    try:
        db.executemany(
            "INSERT OR REPLACE INTO daily_predictions (...) VALUES (...)",
            [(p['code'], p['date'], ...) for p in predictions]
        )
        db.commit()
    finally:
        db.close()
```
**约束**: 保持事务原子性，失败时不部分写入。

---

### 2.3 🟢 低风险: 前端预测图表渲染

**问题描述**: Intelligence.vue 加载全部历史预测 + K 线数据到 `allPreds` 和 `kline` computed 属性。Chart.js 每次切换股票需重建图表。

**影响**: 内存中存储大量数据，切换股票时有 100-300ms 延迟。

**优化方向**: 已在 `futurePreds.slice(0, 10)` 中实现，无需改进。历史数据量取决于 `daily_predictions` 表大小（当前~200 条，可接受）。

---

## 3. 安全性审查

### 3.1 🔴 高风险: subprocess 参数注入

**问题描述**: `backtest_engine.py` 通过 `subprocess.run([PYTHON, script_path, '--codes', codes])` 调用，其中 `codes` 来自用户 API 请求。虽然由 Python list 传递不经过 shell 解析，但 `codes` 值未经严格校验。

**影响**:
- 恶意 codes 值如 `"; rm -rf /"` 在某些 subprocess 模式下可能被 shell 解析
- 即使当前使用 list 模式安全，未来修改可能引入风险

**当前方案已有保护**:
```python
# server_v2.py run_script() 使用 list 参数，不经过 shell
subprocess.run([PYTHON, script_path], cwd=ROOT, capture_output=True)
```
**优化方向**: 在 API 层校验 `codes` 参数，仅允许 `[0-9a-zA-Z,]+` 模式。

---

### 3.2 🟡 中风险: 无 API 认证

**问题描述**: server_v2.py 所有端点（含 POST 回测执行、纸面账户重置）无认证保护。本地运行场景下风险较低，但如果局域网内暴露端口则存在风险。

**影响**:
- 局域网内任何设备可触发回测、重置账户
- 不涉及真实资金，但可能造成数据损坏

**当前**: 启动时绑定 `127.0.0.1`，仅本地可访问。
**优化方向**: 如需局域网访问，添加简单的 API Key 认证中间件。

---

### 3.3 🟢 低风险: SQL 注入

**问题描述**: `db_helper.py` 使用参数化查询 (`?` 占位符)，`paper_trading.py` 新增代码也应遵循此模式。

**约束**: db_helper.py 中所有新函数必须使用参数化查询，Code Review 必须检查。

---

## 4. 可扩展性限制

### 4.1 🟡 中风险: 硬编码信号数量

**问题描述**: 信号权重矩阵结构硬编码为 10 信号 × 5 时段。新增信号（如将来加入第 11 个信号）需要修改：
- `calc_signals()` 信号计算
- `learning_params` 权重矩阵维度和升级逻辑
- 回测引擎搜索空间

**影响**: 新增信号需要改动 3+ 个文件，兼容性处理复杂（已有 V2→V3 升级的痛苦）。

**优化方向**:
```python
# 信号配置化
SIGNAL_CONFIG = {
    'macd': {'label': 'MACD', 'layer': 1},
    'rsi':  {'label': 'RSI', 'layer': 1},
    # ...
}
# 权重矩阵自动扩展
def ensure_weight_dims(weights, signal_config):
    for s in signal_config:
        if s not in weights:
            weights[s] = {b: 1.0 for b in BLOCKS}
```
**约束**: 向下兼容现有 `learning_params` 中已存储的权重矩阵。

---

### 4.2 🟡 中风险: 市场状态类型固定

**问题描述**: 当前设计将市场状态硬编码为 trend/ranging/volatile 3 种。这种分类可能不够精细（如需要区分"强上升趋势"和"弱上升趋势"）。

**当前方案**已较好：`regime_weights` 作为 JSON 存储，未来可扩展更多状态类型而不改变表结构。
**优化方向**: 无需立即改进，但回测引擎的 `detect_market_regime()` 应设计为可配置函数。

---

### 4.3 🟢 低风险: 单用户设计

**问题描述**: 系统设计为单用户本地使用。多用户场景不考虑。
**结论**: 符合项目定位——个人银行股投资管理工具，无需多用户支持。

---

## 5. 可维护性评估

### 5.1 🔴 高风险: 缺少集成测试覆盖

**问题描述**: 当前方案包含 39 项验收标准，但设计文档中仅提到一个集成测试文件 `test_backtest_paper.py`。回测引擎的 Walk-forward 模拟、纸面交易的事件溯源、sync_all 冷启动逻辑等核心流程缺少自动化测试。

**影响**:
- 未来修改 sync_all.py Step 5/6 时可能破坏纸面交易
- 回测权重计算错误难以及时发现
- 回归测试无法自动化

**优化方向**:
```python
# 必须覆盖的测试场景:
class TestBacktestEngine:
    def test_calc_signals_matches_sync_all(self): ...
    def test_walk_forward_produces_valid_weights(self): ...
    def test_grid_search_terminates_within_limit(self): ...
    def test_regime_detection_with_known_data(self): ...

class TestPaperTrading:
    def test_auto_execute_buys_on_bullish(self): ...
    def test_auto_execute_sells_on_bearish_with_position(self): ...
    def test_skips_on_insufficient_cash(self): ...
    def test_rounds_to_lot_size(self): ...
    def test_event_sourcing_replay_consistency(self): ...
    def test_daily_snapshot_updated(self): ...

class TestSyncIntegration:
    def test_cold_start_reads_backtest_weights(self): ...
    def test_regime_blend_on_existing_stock(self): ...
```

---

### 5.2 🟡 中风险: 事件溯源实现复杂度

**问题描述**: 纸面交易采用事件溯源模式，状态通过重放 `paper_trades` 表计算。虽然设计合理，但实现时需注意：

**具体问题**:
1. 快照冗余 (`paper_daily_snapshot`) 与事件重算可能不一致
2. 重置账户后历史交易与当前持仓断开
3. 手续费计算变更后，历史事件口径变化

**优化方向**:
```python
# 明确状态计算优先级
def get_paper_account():
    # 优先从 paper_account 表读取 (快照)
    # 如快照日期不是今天，从 paper_trades 重算最新状态
    snap = get_latest_snapshot()
    trades = get_trades_since(snap.date)
    return replay_trades(snap, trades)
```
**约束**: 每次 `execute_paper_trade` 后同步更新 `paper_account` + `paper_daily_snapshot`。

---

### 5.3 🟢 低风险: 文档充分但分散

**问题描述**: 设计产出包括 5 份文档（业务需求、技术设计、用户流程、架构约束、MWU 设计），信息丰富但分散。

**当前状态**: 已通过 `docs/specs/README.md` 建立导航索引。
**优化方向**: 无需额外改进，主要设计决策已在本文档中汇总。

---

## 问题汇总与优先级

| # | 问题 | 维度 | 级别 | 必须修复? |
|----|------|------|------|----------|
| 1 | 回测引擎信号计算与实际预测不一致风险 | 架构 | 🔴 高 | ✅ 是 |
| 2 | 网格搜索计算量可能超时 (>300s) | 性能 | 🔴 高 → 🟢 已解决 | ✅ 已解决(两阶段搜索) |
| 3 | sync_all.py 单体膨胀 | 架构 | 🔴 高 | 🟡 建议 |
| 4 | 缺少集成测试覆盖 | 可维护性 | 🔴 高 | ✅ 是 |
| 5 | subprocess 参数注入风险 | 安全 | 🔴 高 | 🟡 低优先级(仅本地) |
| 6 | 冷启动与 MWU 在线微调冲突 | 架构 | 🟡 中 | 🟡 观察 |
| 7 | SQLite 写入竞争 | 性能 | 🟡 中 → 🟢 纳入修复 | ✅ 是 (批量写入) |
| 8 | 事件溯源实现复杂度 | 可维护性 | 🟡 中 | 🟡 文档化 |
| 9 | 硬编码信号数量 | 可扩展性 | 🟡 中 | 🟢 下版本 |
| 10 | API 无认证 | 安全 | 🟡 中 | 🟢 仅本地 |

---

## 关键结论

| 结论 | 说明 |
|------|------|
| **架构总体合理** | 四层分离、数据同源、事件溯源等设计决策正确 |
| **必须开发中修复 2 项** | ①信号计算一致性(共享模块) ②SQLite 批量写入 |
| **已解决 1 项** | ③网格搜索超时风险 → 已采纳两阶段搜索方案 |
| **建议开发中修复 2 项** | ③集成测试覆盖率 ④SQLite 批量写入 |
| **可延迟到下版本 6 项** | 单体膨胀、冷启动冲突、安全认证等 |
