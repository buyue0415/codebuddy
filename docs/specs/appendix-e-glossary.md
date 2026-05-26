# 附录E: 术语表

| 术语 | 英文/缩写 | 定义 |
|------|----------|------|
| **自选股** | Watchlist | 用户关注的股票列表，存储于 **watchlist** 表 |
| **日K线** | Daily K-line | 每日 OHLC（开高低收）数据，前复权 |
| **月K线** | Monthly K-line | 由日K线合成的月度 OHLC + 成交量 |
| **复权** | Adjusted Price | 消除分红送股对价格的影响，前复权保持最新价不变 |
| **前复权** | QFQ | K线复权方式，最新价不变，历史价按比例调整 |
| **技术信号** | Signals | 7项指标：MACD / RSI / Bollinger / KDJ / Seasonal / ATR / Money Flow |
| **预测** | Prediction | 基于信号和自学习参数生成的次日方向/价格区间/分时走势 |
| **回填** | Backfill | 将实际行情数据填入历史预测的 `actual_*` 字段 |
| **方向命中** | Direction Hit | 预测的 bullish/bearish 与实际涨跌方向一致 |
| **区间命中** | Range Hit | 实际最高价 ≤ 预测最高价 且 实际最低价 ≥ 预测最低价 |
| **置信度** | Confidence | 预测方向的可信程度 (0.4–1.0)，贝塔二项 + 信号共识混合 |
| **自学习** | Self-learning | 基于预测-实际对比的在线参数优化 |
| **MWU** | Multiplicative Weights Update | 信号权重乘法更新算法 |
| **EG** | Exponentiated Gradient | 偏置参数的指数梯度下降算法 |
| **EMA** | Exponential Moving Average | 指数移动平均，权重随时间指数衰减 |
| **ATR** | Average True Range | 平均真实波幅，衡量价格波动性 |
| **RSI** | Relative Strength Index | 相对强弱指标，衡量超买超卖 |
| **MACD** | Moving Average Convergence Divergence | 异同移动平均线，趋势跟踪指标 |
| **Bollinger Bands** | 布林带 | 基于移动平均和标准差的价格通道 |
| **KDJ** | Stochastic Oscillator | 随机指标，衡量价格在高低区间内的位置 |
| **季节因子** | Seasonal Factor | 历史月度涨跌幅统计，缩放至 0.8~1.2 |
| **Beta-Binomial** | 贝塔二项分布 | 基于历史命中/失误计数的置信度模型 |
| **专家报告** | Expert Report | WorkBuddy 多 Agent 生成的五维分析报告 |
| **对账单** | Broker Statement | 广发证券导出的交易明细 Excel 文件 |
| **NeoData** | — | westock-data 插件提供的金融数据服务 |
| **WAL** | Write-Ahead Log | SQLite 日志模式，提升并发写入性能 |
| **CORS** | Cross-Origin Resource Sharing | 跨域资源共享，允许浏览器跨域请求 |
