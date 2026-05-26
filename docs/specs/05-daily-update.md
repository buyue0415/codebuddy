# 模块5: 每日更新模块 [部分废弃]

> **核心文件**: `scripts/daily_update.py` | **状态**: ⚠️ V0.6 中行情/K线/预测已迁移到 sync_all.py
> **保留功能**: 自学习在线更新、HTML 重建

---

## 1. 功能概述

V0.5 时期的遗留脚本，原负责完整的每日数据更新流程。V0.6 中行情更新、K线获取、预测生成已迁移到 [同步引擎](./03-sync-engine.md)，现仅保留**自学习在线更新**和**HTML 重建**功能。

> ⚠️ **硬编码风险**: 行情数据 (`quotes_update`) 和新闻 (`new_news`) 均为脚本内硬编码字典，需手动每日维护。无自动行情数据源接入。

---

## 2. 核心业务逻辑

### 2.1 执行流程（6步）

```
Step 1: 行情更新 — 硬编码 quotes_update 字典覆盖 data["quotes"]
Step 2: 新闻追加 — 硬编码 new_news 列表，按 (date, code, title) 去重，保留近30天
Step 3: 月K线检查 — 检查是否已有当月数据
Step 4: 预测回填 + 自学习 — direction_hit/range_hit 验证 → MWU → EG → Beta-Binomial → 季节EMA → 准确率重算
Step 5: HTML 重建 — 正则替换 DATA 块 + system_data.json 保存
Step 6: 打印日报 — 汇总展示更新结果
```

> **修复说明**: 原 v1.0 使用 Step 2-6 编号（缺少 Step 1），v2.0 统一为连续编号 1-6。

### 2.2 数据源

| 数据 | 来源 | 说明 |
|------|------|------|
| 行情报价 | `quotes_update` 硬编码字典 | 需每日手动填写 PE/PB/股息率 |
| 新闻 | `new_news` 硬编码列表 | 需每日手动追加 |
| 历史数据 | `data/system_data.json` | 读取上次运行结果 |
| 自学习 | 计算得出 | 基于预测-实际对比 |

---

## 3. 输入输出参数定义

| 输入 | 来源 | 输出 |
|------|------|------|
| `data/system_data.json` | 上次运行全量数据 | `system_data.json`（更新后） |
| 硬编码 `quotes_update` | 脚本内字典 | — |
| 硬编码 `new_news` | 脚本内列表 | — |
| — | — | `bank-stock-system.html`（重新注入后） |

---

## 4. 依赖关系

| 方向 | 模块 |
|------|------|
| **依赖** | `data/system_data.json` |
| **依赖** | `deliverables/bank-stock-system.html` |
| **包含逻辑** | [自学习与预测算法](./04-self-learning.md)（自学习更新部分） |
| **被替代** | 行情/K线/预测 → [同步引擎](./03-sync-engine.md) |
| **被调用** | [定时任务调度](./06-scheduler.md) `task_daily_update()` |

---

## 5. 异常处理机制

| 场景 | 处理 |
|------|------|
| 股票无预测 | 打印日志并 `continue` |
| 股票无行情数据 | 打印日志并 `continue` |
| 股票无 learning_params | 跳过自学习 |
| HTML 重建失败 | 打印错误但不中断主流程 |
| 预测方向为 neutral | 方向命中判定为 False |
