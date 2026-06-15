# 附录 E: 术语表

| 术语 | 英文/缩写 | 定义 |
|------|----------|------|
| 自选股 | Watchlist | 用户关注的股票列表，存储于 watchlist 表 |
| 日K线 | Daily K-line | 每日 O/H/L/C 数据，前复权，上限2000条 |
| 月K线 | Monthly K-line | 由日K线合成的月度 OHLC + 成交量 |
| 前复权 | QFQ | K线复权方式，最新价不变历史价按比例调整 |
| 技术信号 | Signals | **10项指标**: MACD/RSI/Bollinger/KDJ/Seasonal/ATR/Money Flow/ADX_Trend/OBV_Divergence/Vol_Convergence |
| 预测 | Prediction | 基于10信号+自学习参数生成的次日方向/价格区间/分时走势，含10天滚动 |
| 回填 | Backfill | 将实际行情填入历史预测的 actual_* 字段 |
| 方向命中 | Direction Hit | 预测的 bullish/bearish 与实际涨跌一致 |
| 区间命中 | Range Hit | 实际高低价在预测区间内 |
| 置信度 | Confidence | 预测可信程度 (0.4–1.0)，贝塔二项+信号共识混合，随天数衰减 |
| 自学习 | Self-learning | 预测-实际对比 → MWU + EG + Beta-Binomial 参数优化 |
| MWU | Multiplicative Weights Update | 乘法权重更新：正确 ×1.649，错误 ×0.607 |
| EG | Exponentiated Gradient | 指数梯度偏置更新算法 |
| EMA | Exponential Moving Average | 指数移动平均 |
| ATR | Average True Range | 平均真实波幅 |
| ADX | Average Directional Index | 趋势强度指标 |
| OBV | On-Balance Volume | 累积量价指标 |
| 季节因子 | Seasonal Factor | 12个月历史涨跌幅统计，缩放 0.8~1.2 |
| Beta-Binomial | 贝塔二项 | 基于历史命中/失误计数的置信度模型 |
| 专家报告 | Expert Report | WorkBuddy 多Agent生成的五维分析报告 |
| 对账单 | Broker Statement | 广发证券交易明细 Excel |
| NeoData | — | westock-data 插件提供的金融数据服务 |
| WAL | Write-Ahead Log | SQLite 日志模式 |
| 回测 | Backtest | Walk-forward 滚动优化，为MWU提供冷启动权重 |
| 纸面交易 | Paper Trading | 虚拟资金模拟真实交易，不涉及真实金钱 |
| 凯利公式 | Kelly Criterion | 根据胜率+赔率计算最优仓位比例 |
| 夏普比率 | Sharpe Ratio | 收益/波动率，风险调整收益指标 |
| 冷启动 | Cold Start | 新股票首次预测无历史学习经验 |
| 事件溯源 | Event Sourcing | 通过重放不可变交易事件计算当前状态 |
| Walk-forward | 滚动窗口优化 | 训练期→测试期→前滚→重复，防止过拟合 |
| 两阶段搜索 | Two-Phase Search | 代替全量网格搜索的高效权重搜索算法 |
