# 附录F: 已知问题与性能基线

> **更新日期**: 2026-06-06 | **当前版本**: V0.9

---

## 已知问题

### 🔴 高严重度

### 1. ~~Python版本不一致~~ ✅ V0.8 已解决
~~`server.py` 使用 Python 3.14.3，`scheduler.py` 使用 Python 3.13.12。~~
**V0.8**: `server_v2.py` 统一使用系统 Python 3.12。

### 2. ~~数据注入依赖 HTML/JS 格式~~ ✅ V2 已移除
~~`reinject_from_db.py` 使用正则匹配 JS 变量，脆弱地依赖于前端代码保持特定格式。~~
**V3.0**: `reinject_from_db.py` 已彻底移除，V2 前端通过 API 动态获取数据。

### 3. 行情数据无自动实时源
`sync_all.py` Step7 的行情数据以K线收盘价近似，PE/PB/股息率字段硬编码为 0。需接入实时行情 API（如东方财富、新浪）。
- **影响**: 估值指标不可用，股息率计算不准确
- **建议**: 接入 `refresh_quotes.py` 独立实时行情刷新

### 🟡 中严重度

### 4. sync_all.py 模块级执行
`import sync_all` 会触发模块级代码执行，严重影响可测试性。测试必须复制代码片段而非导入模块。
- **影响**: 测试维护成本高，代码同步容易出错
- **建议**: 将执行逻辑包裹在 `if __name__ == '__main__'` 中

### 5. JSON/SQLite 双写不一致风险
DELETE自选股时 `server_v2.py` 同时清理 SQLite（分析层表）和 JSON 文件（`watchlist.json`等），JSON侧可能因写入失败导致数据不一致。
- **影响**: 前端显示与实际数据库状态不一致
- **建议**: 统一 SQLite 单写，移除 JSON 遗留文件

### 6. ~~全局同步锁（单用户瓶颈）~~ 🟢 保留
`_refresh_in_progress` 锁是全局的，所有并发同步请求共享同一把锁。FastAPI 的 async 特性不影响此设计。
- **影响**: 单用户设计，影响可控

### 🟢 低严重度

### 7. 月K线无增量更新
`sync_all.py` Step7 仅在数据库无月K线时生成一次，后续月份不自动追加。
- **影响**: 月度图表不完整，季节性计算滞后
- **建议**: 改为 `INSERT OR REPLACE` 逐月追加+替换

### 8. 新闻无自动清理
`fetch_news.py` 无过期新闻清理，仅 `daily_runner.py` 有 30 天过滤。长期运行后 news 表可能膨胀。
- **影响**: 数据库大小缓慢增长，查询性能下降
- **建议**: 添加 90 天保留策略 + 定期清理任务

### 9. db_helper 查询函数无统一异常处理
18 个查询函数不捕获异常，异常向上传播由调用方处理，增加上游代码复杂度。
- **影响**: API 端点需要各自包裹 try/except
- **建议**: 添加 `@handle_db_error` 装饰器统一处理

### 10. ~~子进程超时时间分散硬编码~~ ✅ 保留
超时值 (30s/60s/180s/300s) 在 `server_v2.py` 中定义。
- **影响**: 无

---

## 废弃模块清单

| 模块 | 文件 | 废弃版本 | 废弃原因 | 替代方案 |
|------|------|---------|---------|---------|
| 旧版后端 | `server.py` | V3.0 ✅ 已删除 | 已迁移至 FastAPI | `server_v2.py` |
| 旧版前端 | `deliverables/bank-stock-system.html` | V3.0 ✅ 已删除 | 已迁移至 Vue 3 SPA | `deliverables/v2/dist/index.html` |
| 旧版JS | `deliverables/js/*.js` (12个) | V3.0 ✅ 已删除 | Vue 组件替代 | `deliverables/v2/` |
| 旧版CSS | `deliverables/css/app.css` | V3.0 ✅ 已删除 | Vue scoped CSS 替代 | `deliverables/v2/` |
| 数据注入 | `scripts/reinject_from_db.py` | V3.0 ✅ 已删除 | API 动态数据替代 | Vue `/api/v2/*` 调用 |
| HTML工具 | `scripts/add_ui_features.py` | V3.0 ✅ 已删除 | 旧版前端专用 | — |
| HTML调试 | `scripts/check_html.py` | V3.0 ✅ 已删除 | 旧版前端专用 | — |
| HTML修复 | `scripts/fix_head.py` | V3.0 ✅ 已删除 | 旧版前端专用 | — |
| 数据验证 | `scripts/validate_data.py` | V3.0 ✅ 已删除 | 旧版前端专用 | — |
| 迁移验证 | `scripts/verify_step2.py` | V3.0 ✅ 已删除 | 旧版专用 | — |
| 迁移验证 | `scripts/verify_step3.py` | V3.0 ✅ 已删除 | 旧版专用 | — |
| K线构建 | `scripts/build_daily_kline.py` | V0.7 | 被 sync_all.py 取代 | `sync_all.py` |
| 旧版启动 | `start_server.bat` | V3.0 ✅ 已删除 | 被 start.bat 替代 | `start.bat` |
| 旧版组合启动 | `start_v2.bat` | V3.0 ✅ 已删除 | 被 start.bat 替代 | `start.bat` |

---

## 性能基线

| 指标 | 典型值 | 峰值 | 说明 |
|------|--------|------|------|
| 全量同步耗时 | 30-60s (7只股票) | 120s | 取决于网络延迟和 NeoData 响应 |
| 单股票K线获取 | 5-15s | 30s | Node.js 子进程启动 + 网络开销 |
| API 响应时间 | <100ms | 200ms | SQLite 本地查询，无网络延迟 |
| 并行K线并发 | 4 (max_workers) | - | ThreadPoolExecutor 上限 |
| ML模型训练 | 10-30s | 60s | RandomForest GridSearch (V0.7新增) |
| 数据库大小 | ~2-5 MB (7只股票) | ~10MB | 含 2000 条日K线/股票 |
| 前端初始加载 | ~300-500 KB | 800KB | 15 个 API 并行请求 |

## V3.0 清理记录

| 模块 | 文件 | 操作 | 说明 |
|------|------|------|------|
| 根路由 | `server_v2.py:688` | 🔄 修改 | 从旧版 HTML 改为 V2 dist index.html |
| 前端路由 | `server_v2.py:698` | ➕ 新增 | 新增 `/assets/{path}` / `/chart.*.js` 路由 |
| 旧版路由 | `server_v2.py:1473` | ➖ 删除 | 移除 `/deliverables/{path}` 通用静态路由 |
| Reinject调用 | `server_v2.py:1278` | ➖ 删除 | 移除 `trigger/update_statement` 中的 reinject 调用 |
| Reinject调用 | `server_v2.py:1454` | ➖ 删除 | 移除 `upload/statement` 中的 reinject 调用 |
| 旧版后端 | `server.py` | ➖ 删除 | 整体删除 |
| 旧版前端 | `deliverables/bank-stock-system.html` | ➖ 删除 | 整体删除（含 js/ css/ 目录） |
| 旧版专用脚本 | `scripts/reinject_from_db.py` 等7个 | ➖ 删除 | 整体删除 |
| 启动脚本 | `start_server.bat` / `start_v2.bat` | ➖ 删除 | 重命名 `start_v2_fastapi.bat` → `start.bat` |
| 前端端口引用 | `Management.vue:241` | 🔄 修复 | 8765 → 8766 |
| 前端端口引用 | `Placeholder.vue:36` | 🔄 修复 | 移除旧版链接 |
| 前端索引引用 | `Placeholder.vue` | 🔄 修复 | 修复缺失的 computed 导入 |

## V0.8 升级记录

| 模块 | 文件 | 状态 | 说明 |
|------|------|------|------|
| API 服务层迁移 | `server_v2.py` | ✅ Active | 从 http.server 迁移至 FastAPI + Uvicorn |
| 依赖新增 | `requirements_v2.txt` | ✅ Active | fastapi, uvicorn, python-multipart |
| 前端代理 | `vite.config.js` | ✅ Active | proxy target → 8766 |

## V0.7 新增模块

| 模块 | 文件 | 行数 | 状态 | 说明 |
|------|------|------|------|------|
| ML增强预测 | `scripts/optimize_predict.py` | ~1000 | ✅ Active | V3.0 混合集成架构 |
| 分红抓取 | `scripts/fetch_dividends.py` | ~200 | ✅ Active | 东方财富公开API |
| 行情刷新 | `scripts/refresh_quotes.py` | ~250 | ✅ Active | TTM股息率计算 |
| 专家报告兼容层 | `scripts/report_compatibility.py` | ~1300 | ✅ Active | v1/v2/v3格式归一化 |

---

## 文档维护指南

1. 修改代码后，定位到对应模块的 `.md` 文件进行更新
2. 新增模块时在 `README.md` 的导航表中添加条目
3. 新增 API 端点时在 `appendix-b-api.md` 中添加
4. 修改数据库 Schema 时在 `appendix-a-schema.md` 中同步
5. 术语变更时更新 `appendix-e-glossary.md`
6. 发现新问题时追加到本文档的"已知问题"清单

---

> **版本历史**:
> - v3.0 (2026-06-06) — V2 系统重构：移除所有旧版代码引用，更新废弃模块清单，添加 V3.0 清理记录
> - v2.1 (2026-06-03) — V0.7更新：新增10个已知问题，按严重度分级，新增V0.7模块清单
> - v2.0 (2026-05-26) — 从单文件拆分重构为 19 个子文档
> - v1.0 (2026-05-26) — 初始单文件完整版本
