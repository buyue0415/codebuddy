# 附录F: 已知问题与性能基线

---

## 已知问题

### 1. daily_update.py 与 sync_all.py 覆盖风险
两个脚本均会更新 `system_data.json`，存在互相覆盖风险。V0.6 推荐只使用 `sync_all.py`，`daily_update.py` 应逐步废弃。

### 2. 行情数据无自动数据源
`daily_update.py` 的 `quotes_update` 字典和 `sync_all.py` Step7 的行情数据均非实时行情。PE/PB/股息率字段硬编码为 0，需接入实时行情 API。

### 3. 数据注入依赖 HTML 格式
`reinject_from_db.py` 使用正则 `r'(let|const|var)( DATA = )\{.*?\};\n'` 匹配 JS 变量，依赖于前端代码保持特定格式。若前端重构改变了声明方式，注入将静默失败。

### 4. Python 版本不一致
`server.py` 使用 Python 3.14.3，`scheduler.py` 使用 Python 3.13.12。

### 5. 新闻无自动清理
`fetch_news.py` 无过期新闻清理，仅 `daily_update.py` 有 30 天过滤。长期运行后数据库可能膨胀。

### 6. 月K线无增量更新
`sync_all.py` Step7 仅在数据库无月K线时生成一次，后续月份不自动追加。需手动运行 `build_daily_kline.py` 或手动维护。

### 7. DELETE 端点的 JSON/SQLite 双写
`server.py` 删除自选股时同时清理 SQLite（9张表）和 JSON 文件，JSON 侧可能因写入失败而遗漏，导致数据不一致。

### 8. 并发同步仅支持单用户
`_refresh_in_progress` 锁是全局的，所有并发同步请求共享同一把锁。当前为单用户设计，不适合多用户场景。

---

## 废弃模块清单

### [DEPRECATED] build_daily_kline.py (原模块7)

- **文件**: `scripts/build_daily_kline.py`
- **废弃原因**: 功能已被 `sync_all.py` 完全取代
- **区别**: JSON 文件为目标（非 SQLite），季节因子硬编码，无预测回填
- **保留原因**: 兼容性参考，现有调度链路不再引用

---

## 性能基线

| 指标 | 典型值 | 说明 |
|------|--------|------|
| 全量同步耗时 | 30-60s (3只股票) | 取决于网络延迟和 NeoData 响应 |
| 单股票K线获取 | 5-15s | Node.js 子进程启动 + 网络开销 |
| API 响应时间 | < 100ms | SQLite 本地查询，无网络延迟 |
| 并行K线并发 | 4 (max_workers) | ThreadPoolExecutor 上限 |
| 数据库大小 | ~2-5 MB (3只股票) | 含 200 条日K线/股票 |
| 前端初始加载 | ~300-500 KB | `/api/v2/init` 全量数据 |

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
> - v2.0 (2026-05-26) — 从单文件拆分重构为 19 个子文档
> - v1.0 (2026-05-26) — 初始单文件完整版本
