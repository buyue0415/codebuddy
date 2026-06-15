"""
审计报告：过期/无效文件清单
==========================

活跃核心 (保留):
  data/system_data.json           - 核心数据
  data/broker_statement.json      - 对账单
  deliverables/bank-stock-system.html - 主系统HTML
  scripts/parse_statement.py      - 对账单解析
  scripts/cleanup_data.py         - 数据清理
  scripts/audit_system.py         - 系统审计
  scripts/upgrade_learning.py     - 学习系统升级
  scripts/build_daily_kline.py    - 日K线构建
  scripts/reinject_data.py        - 数据注入工具
  data/watchlist.json (NEW)       - 待创建

已过期(删除):
  scripts/check_fees.py           - 手续费一次性debug
  scripts/check_fees2.py          - 手续费一次性debug
  scripts/check_data.py           - 老debug
  scripts/rebuild_trades.py       - 一次性trades修复
  scripts/fix_closed_trades.py    - 一次性持仓修复
  scripts/verify_fees_html.py     - 一次性验证
  scripts/verify_final.py         - 一次性验证
  scripts/verify_data.py          - 老验证
  scripts/calc_daily_signals.py   - 不完整(被build_daily_kline替代)
  scripts/gen_prediction_data.py  - 老预测生成(被upgrade_learning替代)
  scripts/prepare_data.py         - 老数据准备
  scripts/fetch_kline.py          - 老K线拉取(被westock-data替代)
  scripts/fetch_daily.py          - 老日线尝试
  scripts/peek_data.py            - 一次性窥探
  scripts/dividend_verification.py- 老分红验证
  scripts/trade_analysis.py       - 老交易分析
  scripts/build_system_data.py    - 老系统构建
  scripts/rebuild_html.py         - 老HTML重建
  data/601166_kline_3y.json       - 老NeoData月K(已入system_data)
  data/600036_kline_3y.json       - 同上
  data/analysis_data.json         - 老分析数据
  deliverables/bank-stock-dashboard.html - 老看板(被system替代)
  deliverables/trading-agent/     - 老交易分析输出
  response1-11.json               - API调试dump
  query_body.json                 - 老查询实验
  query_node.js                   - 老查询实验
"""
