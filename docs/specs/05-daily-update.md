# 模块5: 每日更新模块 [部分废弃]

> **核心文件**: ~~`scripts/daily_update.py`~~ | **状态**: ⚠️ **V3.0 已废弃**
> **旧版功能**: 自学习在线更新、HTML 重建（均已迁移至 `sync_all.py` + V2 API）

---

## 1. 功能概述

V0.5 时期的遗留脚本，原负责完整的每日数据更新流程。

| 版本 | 状态 | 说明 |
|------|------|------|
| V0.6 | ⚠️ 部分废弃 | 行情更新、K线获取、预测生成迁移到 sync_all.py |
| V3.0 | ⚠️ **完全废弃** | **HTML 重建功能**（依赖已删除的 `bank-stock-system.html`）不再可用 |

**当前替代方案**:

| 旧功能 | 当前替代 |
|--------|---------|
| 行情更新 | `sync_all.py` Step7 |
| K线获取 | `sync_all.py` Step3（并行 ThreadPoolExecutor） |
| 预测回填 + 自学习 | `sync_all.py` Step4-6（signals.py MWU 在线学习） |
| HTML 数据注入 | **已移除** — V2 前端通过 API 动态获取数据 |
| system_data.json 写 | 仅作旧版兼容保留 |

---

## 2. 遗留内容（仅参考）

### 2.1 原执行流程（6步）

```
Step 1: 行情更新 — 硬编码 quotes_update 字典覆盖 data["quotes"]
Step 2: 新闻追加 — 硬编码 new_news 列表，按 (date, code, title) 去重，保留近30天
Step 3: 月K线检查 — 检查是否已有当月数据
Step 4: 预测回填 + 自学习 — 预测验证 → MWU → EG → Beta-Binomial → 季节EMA
Step 5: HTML 重建 — 正则替换 DATA 块（V3.0: 不可用）
Step 6: 打印日报 — 汇总展示更新结果
```

> ⚠️ **Step 5 已失效**: 目标文件 `deliverables/bank-stock-system.html` 已删除。

### 2.2 原依赖关系

| 方向 | 模块 | 当前状态 |
|------|------|---------|
| **依赖** | `data/system_data.json` | 保留 |
| **依赖** | ~~`deliverables/bank-stock-system.html`~~ | **已删除** |
| **包含逻辑** | 自学习与预测算法 | 已迁移至 `signals.py` |
| **被替代** | 行情/K线/预测 → `sync_all.py` | ✅ Active |
| **被调用** | ~~定时任务调度 `task_daily_update()`~~ | 已停用 |

---

## 3. 清理建议

- 考虑彻底删除 `scripts/daily_update.py`
- `scheduler.py` 中的 `task_daily_update` 调度条目应移除
- `sync_all.py` Step8 的 `system_data.json` 写操作可考虑移除
