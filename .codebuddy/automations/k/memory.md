# 日K预测数据同步 - 执行记录

## 最近执行: 2026-06-02 09:02

### 执行结果
- **sync_all.py**: 成功，2只股票（兴业银行601166、招商银行600036），各200条K线，40条新闻，2条预测
- **reinject_from_db.py**: 成功，24顶层键注入HTML（watchlist:2, kline_daily:1600, positions:2, closed:3, trades:33, preds:12, news:158）
- **预测方向**: 均为 neutral conf=50%
- **自学习**: 兴业银行 update_count=26，招商银行 update_count=26
- **季节数据**: 各11条月线，兴业银行最新涨幅3.6%，招商银行0.5%
- **变化**: 监视列表从3只减少到2只（中国联通600050已不在列表中）

### 注意事项
- 需使用 `cmd /c` 执行，直接 PowerShell 会触发 0xC0000142 (DLL初始化失败)
- HTML 输出: deliverables/bank-stock-system.html
