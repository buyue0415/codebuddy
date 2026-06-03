# 业务逻辑规则 (Business Logic Rules)

> **版本**: v1.0 | **级别**: 🔴 MUST | **更新日期**: 2026-06-03

---

## 1. 数据一致性规则

### 1.1 自选股增删

**MUST**:
- 添加自选股: 同时更新 `watchlist` 表和 `stocks.watchlist = 1`
- 删除自选股: 级联清理以下9张表
  ```
  watchlist, kline_daily, kline_monthly, quotes,
  daily_predictions, prediction_hourly, prediction_signals,
  learning_params, accuracy_stats, seasonal
  ```
- 删除后触发 `sync_all.py` 重新加载全量数据

**MUST NOT**:
- 删除后遗留关联表数据（孤儿记录）
- 忽略 JSON 遗留文件的同步更新

### 1.2 预测回填规则

**MUST**:
- 仅回填 `dir_hit IS NULL` 的历史预测记录
- 跳过当日预测（数据不可验证）
- 验证逻辑:
  ```python
  # 方向命中: 预测bullish且实际涨 OR 预测bearish且实际跌
  dir_hit = (pred_dir == 'bullish' and actual_close > prev_close) or \
            (pred_dir == 'bearish' and actual_close < prev_close)
  
  # 区间命中: 实际 high 不超过预测 high，实际 low 不低于预测 low
  range_hit = actual_high <= pred_high and actual_low >= pred_low
  ```

### 1.3 准确率重算规则

**MUST**:
- 使用已验证预测（`dir_hit IS NOT NULL`）的数据
- 区分两个窗口: `last_20`（最近20条）、`last_60`（最近60条）
- 同时计算 direction 和 range 命中率
- 写入 `accuracy_stats` 表前先清除旧数据

### 1.4 交易日检测

**MUST**:
- 新闻抓取时检测是否为交易日
- 非交易日 (周末/节假日) 可跳过预测生成
- 通过 NeoData 返回数据判断（有数据=交易日）

---

## 2. 预测生成规则

### 2.1 技术信号计算

**MUST**:
- K线数据不少于 14 条才能计算信号
- EMA 使用真正的指数移动平均（非 SMA）
- RSI 分母为零时返回 100（而非除零错误）

**信号方向判定阈值**:

| 信号 | Bullish | Bearish | Neutral |
|------|---------|---------|---------|
| MACD | DIF > Signal | DIF < Signal | - |
| RSI | > 55 | < 45 | 45-55 |
| Bollinger | 价格 < 下轨×1.02 | 价格 > 上轨×0.98 | 其他 |
| KDJ | J < 20 | J > 80 | 20-80 |
| Seasonal | factor > 1.0 | factor ≤ 1.0 | - |
| Money Flow | 3日>1% 且 10日>0 | 3日<-1% 且 10日<0 | 其他 |

### 2.2 加权投票公式

```python
# MUST: 使用此公式计算日内方向
weighted_score = SUM(signal_weight[s]['next_day'] * direction(s)) for s in SIGNALS
weighted_score += seasonal_adj[month] * 2

direction = 'bullish' if ws > 0.5 else 'bearish' if ws < -0.5 else 'neutral'
```

### 2.3 置信度计算

```python
# MUST: 置信度 ∈ [0.4, 1.0]
consensus = 同向信号数 / (bullish数 + bearish数)  # neutral不参与
beta_conf = alpha / (alpha + beta)                # Beta-Binomial后验均值
confidence = max(0.4, 0.6 * consensus + 0.4 * beta_conf)
```

### 2.4 价格区间

```python
# MUST: 使用此公式计算预测高低点
daily_range = ATR * 2.5
pred_high = close + daily_range * 0.6
pred_low = close - daily_range * 0.4
```

---

## 3. 自学习规则

### 3.1 MWU 权重更新

```python
# MUST: 信号正确时乘e^1.0，错误时乘e^-1.0
new_weight = old_weight * (e^1.0 if correct else e^-1.0)

# MUST: 衰减平滑 → approach 1.0
weight = weight * 0.7 + 1.0 * 0.3    # mw_beta = 0.7

# MUST: 跨5个时段归一化到 sum=5
weights = {b: w * 5 / total for b, w in weights.items()}
```

### 3.2 EG 偏置更新

```python
# MUST: 衰减学习率
eta = 0.01 * 0.995 ^ update_count

# MUST: 偏置裁剪到 [-0.05, 0.05]
bias = clamp(bias + eta * error, -0.05, 0.05)
```

### 3.3 更新条件

| 条件 | 行为 |
|------|------|
| `dir_hit IS NOT NULL` | 执行全部更新 |
| 预测方向为 neutral | 跳过 Beta-Binomial 更新 |
| 无 `learning_params` 记录 | 跳过自学习 |
| `update_count = 0` | 使用学习率初始值 |

---

## 4. 交易计算规则

### 4.1 费用计算

```python
# MUST: 使用 config.json 中的费率
fee_rates = config['fee_rates']

# 过户费: 成交金额 × 0.01‰  (上海), 0 (深圳)
transfer_fee = amount * fee_rates['transfer_fee_per_1000'] / 1000

# 规费: 成交金额 × 0.02‰
regulatory_fee = amount * fee_rates['regulatory_fee_per_1000'] / 1000

# 经手费: 成交金额 × 费率
handling_fee = amount * fee_rates['handling_fee_per_1000'] / 1000
```

### 4.2 持仓计算

```python
# MUST: 按时间顺序处理交易
trade_records.sort(key=lambda t: (t['date'], t['time']))

# MUST: 买入增仓，卖出减仓，分红追加记录
for trade in trade_records:
    if trade['type'] in ('buy', '买入'):
        position['qty'] += trade['qty']
        position['cost_basis'] += trade['amount'] + trade['commission']
    elif trade['type'] in ('sell', '卖出'):
        position['qty'] -= trade['qty']
        if position['qty'] == 0:
            # 清仓，计算实现盈亏
            realized_pnl = total_sell - total_buy_cost
```

### 4.3 分红计算

```python
# MUST: 每股分红 = 分红总额 / 股权登记日持仓股数
per_share_dividend = total_dividend_amount / shares_before_ex_date

# MUST: 股息率 = 每股分红 / 当前价格
dividend_yield = per_share / current_price
```

---

## 5. 新闻处理规则

### 5.1 情感分析

```python
# POSITIVE 关键词 (14个):
POSITIVE_WORDS = ['增长', '盈利', '利好', '突破', '买入', '增持', '分红',
                   '业绩', '超预期', '扩张', '创新高', '回购', '龙头', '稳健']

# NEGATIVE 关键词 (14个):
NEGATIVE_WORDS = ['下跌', '亏损', '利空', '风险', '减持', '卖出', '下滑',
                   '处罚', '诉讼', '暴雷', '踩雷', '监管', '违约', '退市']
```

### 5.2 重大性判断

```python
# MUST: 满足以下任一条件为重大新闻
is_major = (
    sentiment in ('positive', 'negative') and  # 有明确情感
    (len(title) > 20 or keyword_count >= 3)    # 标题较长或关键词多
)
```

### 5.3 去重规则

```python
# MUST: 使用 content_hash 去重
import hashlib
content_hash = hashlib.md5((title + summary).encode()).hexdigest()
```

---

## 6. 对账单解析规则

### 6.1 列名映射

```python
# MUST: 支持中英文列名自动映射
COLUMN_MAP = {
    '成交日期': 'date', 'Trade Date': 'date',
    '证券代码': 'code', 'Code': 'code',
    '证券名称': 'name', 'Name': 'name',
    '买卖方向': 'type', 'Type': 'type',
    '成交数量': 'qty', 'Quantity': 'qty',
    '成交价格': 'price', 'Price': 'price',
    '成交金额': 'amount', 'Amount': 'amount',
    '手续费': 'commission', 'Commission': 'commission',
}
```

### 6.2 重复检测

```python
# MUST: 基于 (date, code, type, qty, price) 五元组去重
trade_key = (trade['date'], trade['code'], trade['type'], trade['qty'], trade['price'])
```

### 6.3 备份保护

```python
# MUST: 上传新文件前创建 .bak 备份
original_path = '广发易淘金PC版-普通对账单结果查询.xlsx'
backup_path = original_path + '.bak_' + timestamp
shutil.copy(original_path, backup_path)
```

---

## 7. API 响应规则

### 7.1 统一响应格式

```python
# MUST: 所有 API 端点返回此结构
# 成功
{ "success": true, "data": <any>, "count?": <number>, "message?": "<string>" }

# 失败
{ "success": false, "error": "<string>", "trace?": "<string>" }
```

### 7.2 HTTP 状态码映射

| 场景 | HTTP Code | 说明 |
|------|-----------|------|
| 正常处理 | 200 | `success: true` |
| 参数缺失/无效 | 400 | 缺少必填字段 |
| 资源不存在 | 404 | 未知端点或空结果 |
| 重复添加 | 409 | 股票已存在 |
| 并发冲突 | 429 | 同步任务运行中 |
| 服务端异常 | 500 | 未捕获异常 |

### 7.3 响应大小限制

```python
# SHOULD: 全量数据响应 (/api/v2/init) 不超过 1MB
# SHOULD: 单端点响应不超过 500KB
# MUST: stdout 截断 3000 字符, stderr 截断 1000 字符
```
