# 附录F: 已知问题与性能基线

> **更新日期**: 2026-06-04 | **当前版本**: V0.8

---

## 已知问题

### 🔴 高严重度

### 1. ~~Python版本不一致~~ ✅ V0.8 已解决
~~`server.py` 使用 Python 3.14.3，`scheduler.py` 使用 Python 3.13.12。~~
**V0.8**: `server_v2.py` 统一使用系统 Python 3.12；原 `server.py` 保留兼容。

### 2. 数据注入依赖 HTML/JS 格式

### 2. 数据注入依赖 HTML/JS 格式
`reinject_from_db.py` 使用正则 `r'(let|const|var)( DATA = )\{.*?\};\n'` 匹配 JS 变量，脆弱地依赖于前端代码保持特定格式。若前端重构改变了声明方式或变量名，注入将静默失败。
- **影响**: 前端数据不更新，用户看到过期数据
- **建议**: 改为 API 数据驱动（V0.6+已推荐）或使用模板注入

### 3. 行情数据无自动实时源
`sync_all.py` Step7 的行情数据以K线收盘价近似，PE/PB/股息率字段硬编码为 0。需接入实时行情 API（如东方财富、新浪）。
- **影响**: 估值指标不可用，股息率计算不准确
- **建议**: 接入 `fetch_quotes.py` 独立实时行情刷新

### 🟡 中严重度

### 4. sync_all.py 模块级执行
`import sync_all` 会触发模块级代码执行，严重影响可测试性。测试必须复制代码片段而非导入模块。
- **影响**: 测试维护成本高，代码同步容易出错
- **建议**: 将执行逻辑包裹在 `if __name__ == '__main__'` 中

### 5. JSON/SQLite 双写不一致风险
DELETE自选股时 `server.py` 同时清理 SQLite（9张表）和 JSON 文件（`watchlist.json`等），JSON侧可能因写入失败导致数据不一致。
- **影响**: 前端显示与实际数据库状态不一致
- **建议**: 统一 SQLite 单写，移除 JSON 遗留文件

### 6. ~~全局同步锁（单用户瓶颈）~~ 🟢 V0.8 保留
`_refresh_in_progress` 锁是全局的，所有并发同步请求共享同一把锁。FastAPI 的 async 特性不影响此设计。
- **影响**: 单用户设计，影响可控

### 🟢 低严重度

### 7. 月K线无增量更新
`sync_all.py` Step7 仅在数据库无月K线时生成一次，后续月份不自动追加。
- **影响**: 月度图表不完整，季节性计算滞后
- **建议**: 改为 `INSERT OR REPLACE` 逐月追加+替换

### 8. 新闻无自动清理
`fetch_news.py` 无过期新闻清理，仅 `daily_update.py` 有 30 天过滤。长期运行后 news 表可能膨胀。
- **影响**: 数据库大小缓慢增长，查询性能下降
- **建议**: 添加 90 天保留策略 + 定期清理任务

### 9. db_helper 查询函数无统一异常处理
18 个查询函数不捕获异常，异常向上传播由调用方处理，增加上游代码复杂度。
- **影响**: API 端点需要各自包裹 try/except
- **建议**: 添加 `@handle_db_error` 装饰器统一处理

### 10. ~~子进程超时时间分散硬编码~~ ✅ V0.8 保持
超时值 (30s/60s/180s) 在 `server_v2.py` 和原版 `server.py` 中分别定义，行为一致。
- **影响**: 无，与 V0.7 行为完全相同

---

## 废弃模块清单

### [DEPRECATED] build_daily_kline.py (原模块7)

- **文件**: `scripts/build_daily_kline.py`
- **废弃原因**: 功能已被 `sync_all.py` 完全取代
- **区别**: JSON 文件为目标（非 SQLite），季节因子硬编码，无预测回填
- **保留原因**: 兼容性参考，现有调度链路不再引用

---

## 性能基线

| 指标 | 典型值 | 峰值 | 说明 |
|------|--------|------|------|
| 全量同步耗时 | 30-60s (3只股票) | 120s | 取决于网络延迟和 NeoData 响应 |
| 单股票K线获取 | 5-15s | 30s | Node.js 子进程启动 + 网络开销 |
| API 响应时间 | <100ms | 200ms | SQLite 本地查询，无网络延迟 |
| 并行K线并发 | 4 (max_workers) | - | ThreadPoolExecutor 上限 |
| ML模型训练 | 10-30s | 60s | RandomForest GridSearch (V0.7新增) |
| 数据库大小 | ~2-5 MB (3只股票) | ~10MB | 含 200 条日K线/股票 |
| 前端初始加载 | ~300-500 KB | 800KB | `/api/v2/init` 全量数据 |

## V0.8 升级记录

| 模块 | 文件 | 状态 | 说明 |
|------|------|------|------|
| API 服务层迁移 | `server_v2.py` | ✅ Active | 从 http.server 迁移至 FastAPI + Uvicorn |
| 原版保留 | `server.py` | 🔵 Retained | 端口 8765 保留，兼容回退 |
| 依赖新增 | `requirements_v2.txt` | ✅ Active | fastapi, uvicorn, python-multipart |
| 前端代理 | `vite.config.js` | ✅ Active | proxy target 8765 → 8766 |

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
> - v2.1 (2026-06-03) — V0.7更新：新增10个已知问题，按严重度分级，新增V0.7模块清单
> - v2.0 (2026-05-26) — 从单文件拆分重构为 19 个子文档
> - v1.0 (2026-05-26) — 初始单文件完整版本
