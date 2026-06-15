# 附录 F: 已知问题与性能基线

> **更新日期**: 2026-06-06 | **当前版本**: V0.9

---

## 已知问题

### 🔴 高严重度

#### 1. scheduler.py 引用已删除脚本
`scheduler.py:50-52` 的 `rebuild_html()` 函数调用 `reinject_from_db.py`，该脚本已在 V3.0 删除。
`scheduler.py:90` 的 `task_statement_update()` 仍调用 `rebuild_html()`。
- **影响**: `task_statement_update` 执行时 `reinject_from_db.py` 被标记 SKIP
- **建议**: 移除 `rebuild_html()` 函数及 `task_statement_update()` 中的调用

#### 2. 行情数据无自动实时源
`sync_all.py` Step7 行情以K线收盘价近似，PE/PB/股息率字段不准确。
- **影响**: 估值指标不精确
- **建议**: 接入 `refresh_quotes.py` 独立实时行情刷新（**已存在该脚本**）

### 🟡 中严重度

#### 3. config.json 端口不一致
`config.json` 中 `server_port: 8765`，但实际服务运行在 `8766`。
- **影响**: 配置文件与实际不一致，造成混淆
- **建议**: 更新为 `8766`

#### 4. scheduler.py Python 版本
`scheduler.py:31` 使用 `Python 3.12.6`，与 `appendix-c-configuration.md` 旧文档说的 `3.13.12` 不同。
- **影响**: 无（3.12.6 正确）
- **建议**: 文档已更新，无需修复

#### 5. 月K线无增量更新
仅当数据库无月K线时生成一次，后续月份不自动追加。
- **建议**: 改为 INSERT OR REPLACE 逐月追加

#### 6. 新闻无自动清理
`fetch_news.py` 无过期新闻清理机制。
- **建议**: 添加 90 天保留策略

#### 7. collect_intraday.py loop 未配置后台运行
`collect_intraday.py loop` 模式存在但无 Windows 任务计划或后台进程拉起。当前仅通过
`scheduler.py sync` 中的 `task_intraday_collect()` 触发（单次 --days 5 回填）。
- **影响**: 盘中分钟数据需手动触发采集，否则>5个交易日的日期使用日K线降级
- **建议**: 创建 Windows 任务计划，交易日 09:30~15:00 每 60 分钟执行 `python collect_intraday.py once`

### 🟢 低严重度

#### 8. db_helper 查询函数无统一异常处理
22 个查询函数不捕获异常，异常向上传播。
- **建议**: 添加 `@handle_db_error` 装饰器

#### 9. 全局同步锁
`_refresh_in_progress` 锁是全局的——单用户设计，影响可控。

---

## 性能基线

| 指标 | 典型值 | 峰值 | 说明 |
|------|--------|------|------|
| 全量同步时间 | 30-60s | 120s | 7只股票，含K线+预测+新闻 |
| 单股票K线获取 | 5-15s | 30s | Node.js子进程+网络 |
| API响应时间 | <100ms | 200ms | SQLite本地查询 |
| 并行K线并发 | 4 | — | ThreadPoolExecutor上限 |
| 回测单次运行 | 60-120s | 300s | 6只股票两阶段搜索 |
| 数据库大小 | ~2-5MB | ~10MB | 7只股票 |
| 前端初始加载 | ~500KB | 800KB | 15个API并行请求 |

---

## V3.0 清理记录（2026-06-06）

| 模块 | 文件 | 操作 |
|------|------|------|
| 旧版后端 | `server.py` | ➖ 删除 |
| 旧版前端 | `deliverables/bank-stock-system.html` | ➖ 删除 |
| 旧版JS/CSS | `deliverables/js/` `css/` | ➖ 删除 |
| 数据注入 | `scripts/reinject_from_db.py` | ➖ 删除 |
| HTML工具 | `add_ui_features.py` 等7个 | ➖ 删除 |
| 启动脚本 | `start_server.bat` `start_v2.bat` | ➖ 删除 |
| 根路由 | `server_v2.py:688` | 改为指向 V2 dist |
| 前端端口 | `Management.vue` `client.js` | 8765→8766 |

---

## V4.0 Specs 重写记录（2026-06-06）

| 操作 | 说明 |
|------|------|
| 删除 | 全部 25 个旧 specs 文件 |
| 新增 | 22 个新 specs 文件，按系统菜单结构组织 |
| 结构 | 5 系统基础 + 12 菜单功能 + 6 附录 |
| 每文件 | 含业务需求/技术分析/功能实现/用户流程四部分 |
| 数据 | 全部与最新代码 (`server_v2.py:70 routes`, `signals.py:SIGNALS=10`) 对齐 |
