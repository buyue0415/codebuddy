# 股票投资管理系统 V2 — 规格文档

> **版本**: V0.7 | **后端**: Python FastAPI + SQLite | **前端**: Vue 3 + Vite + Pinia
> **端口**: 8766 | **最终用户**: 个人 A 股投资者 | **数据源**: 广发证券对账单 + NeoData 金融数据服务

---

## 一、系统概述

股票投资管理系统是一个本地运行的个人投资分析工具。系统通过对券商对账单的自动解析、多源行情数据的实时采集、技术指标分析及 ML 预测模型，提供从交易记录管理到智能决策辅助的全链路服务。

### 1.1 核心能力

| 能力 | 说明 |
|------|------|
| 对账单解析 | 自动读取广发证券对账单 ZIP/Excel，提取全部持仓、交易、分红数据 |
| 实时行情 | 多数据源回退链：Westock → NeoData → 东方财富 → 新浪 → 腾讯 |
| K 线数据 | 日K + 月K，前复权处理，含成交量、成交额、换手率 |
| 技术信号 | 10 大技术信号：MACD、RSI、布林带、KDJ、ATR、ADX、OBV、季节动量、资金流向、波动率 |
| ML 预测 | RandomForest + Ridge 混合模型，30+ 特征，10 日滚动预测 |
| 自学习引擎 | MWU + EG + Beta-Binomial 三算法融合，在线参数更新 |
| 形态识别 | 33 条标准 K 线形态规则库 |
| 回测引擎 | Walk-forward 两阶段搜索，多种费用模型 |
| 纸面交易 | 虚拟账户 + 凯利公式仓位管理 + 日内分时级自动执行 |
| 公司关系图谱 | 供应链 / 股权 / 高管 / 竞争关系可视化 |
| 智能新闻 | 情感分析 + 重大性判断 + 历史回溯 |

### 1.2 技术栈

```
后端: Python 3.10+ / FastAPI / Uvicorn / sqlite3
前端: Vue 3 (Composition API) / Vite / Pinia / Vue Router 4
可视化: Chart.js (chart.js, chartjs-chart-financial) / @antv/g6 (关系图谱)
数据源: akshare (东方财富), Westock 本地版, NeoData API
```

---

## 二、功能模块索引

### 导航组 1 — 个人交易数据

| 编号 | 页面 | 路由 | 说明 |
|------|------|------|------|
| 06 | 持仓总览 | `/overview` | 当前持仓、浮动盈亏、已清仓、分红明细 |
| 07 | 交易记录 | `/trades` | 全部交易流水 + 月度交易时间线图 |
| 08 | 手续费分析 | `/fees` | 佣金/印花税/其他费用 + 构成/趋势图 |
| 09 | 管理设置 | `/manage` | 自选股管理、对账单上传、专家报告导入、服务器状态 |

### 导航组 2 — 股票分析预测

| 编号 | 页面 | 路由 | 说明 |
|------|------|------|------|
| 10 | 智能预测 | `/intelligence` | 次日预测 + 10 日走势 + 技术信号 + 准确率统计 |
| 11 | 专家分析 | `/expert` | AI 专家报告（五维雷达/多空辩论/风险评估） |

### 导航组 3 — 股票信息收集

| 编号 | 页面 | 路由 | 说明 |
|------|------|------|------|
| 12 | 新闻动态 | `/news` | 股票新闻浏览、情感分析、趋势图 |
| 13 | 股票数据 | `/stock-data` | 实时行情、行业筛选、数据卡片 |
| 14 | K 线走势 | `/kline` | 日K/月K、Chart.js 金融图表、斐波那契回调 |
| 15 | 形态规则 | `/pattern-rules` | K 线形态规则 CRUD、规则管理 |
| 16 | 公司关系图谱 | `/company-graph` | 供应链/股权/高管/竞争关系图谱 |

### 导航组 4 — 模拟交易

| 编号 | 页面 | 路由 | 说明 |
|------|------|------|------|
| 17 | 回测分析 | `/backtest` | Walk-forward 回测、进度监控、结果分析 |
| 18 | 纸面交易 | `/paper` | 虚拟账户、建议、交易执行、资金曲线 |

---

## 三、文档结构

| 文件 | 内容 |
|------|------|
| `01-system-architecture.md` | 系统架构、API 服务层、前端路由、脚本编排、部署方式 |
| `02-database-layer.md` | 数据库表结构、db_helper 数据访问层、Schema 演进 |
| `03-data-sync-engine.md` | 8 步数据同步流水线、多源回退、K 线采集 |
| `04-self-learning-engine.md` | 10 信号技术分析、MWU/EG/Beta-Binomial 学习算法 |
| `05-task-scheduler.md` | 定时任务配置、Windows 任务计划程序集成 |
| `06-positions-overview.md` | 持仓总览页面（Overview.vue） |
| `07-trade-records.md` | 交易记录页面（Trades.vue） |
| `08-fee-analysis.md` | 手续费分析页面（Fees.vue） |
| `09-system-management.md` | 管理设置页面（Management.vue） |
| `10-intelligence-prediction.md` | 智能预测页面（Intelligence.vue） |
| `11-expert-analysis.md` | 专家分析页面（Expert.vue） |
| `12-news-feed.md` | 新闻动态页面（News.vue） |
| `13-stock-data.md` | 股票数据页面（StockData.vue） |
| `14-kline-charts.md` | K 线走势页面（Kline.vue） |
| `15-pattern-rules.md` | 形态规则页面（PatternRules.vue） |
| `16-company-relations-graph.md` | 公司关系图谱页面（CompanyGraph.vue） |
| `17-backtest-engine.md` | 回测分析页面（BacktestPage.vue） |
| `18-paper-trading.md` | 纸面交易页面（PaperTrading.vue） |
| `appendix-a-database-schema.md` | 完整数据库 Schema 参考 |
| `appendix-b-api-reference.md` | 完整 API 端点参考 |
| `appendix-c-configuration.md` | 系统配置说明 |
| `appendix-d-dependencies.md` | 模块依赖关系 |
| `appendix-e-glossary.md` | 术语表 |
| `appendix-f-known-issues.md` | 已知问题与限制 |

---

## 四、快速导航

- [架构总览](01-system-architecture.md)
- [数据库设计](02-database-layer.md)
- [数据同步](03-data-sync-engine.md)
- [智能预测](10-intelligence-prediction.md)
- [回测引擎](17-backtest-engine.md)
- [纸面交易](18-paper-trading.md)
- [配置参考](appendix-c-configuration.md)
- [已知问题](appendix-f-known-issues.md)
