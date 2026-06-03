# 系统架构全面深度分析与规范更新 实施计划

> **For Claude:** 按 Task 逐项执行，每完成一个 Task 验证后再进入下一个。

**Goal:** 对股票投资管理系统 V0.7 进行架构深度分析，系统性更新 specs/rules/tests

**Architecture:** 分 4 个阶段 — 架构分析文档 → Specs 更新 → Rules 创建 → Tests 完善

**Tech Stack:** Python 3.13+, Markdown, SQLite, unittest

---

### Task 1: 创建架构深度分析文档

**Files:**
- Create: `docs/refactor/architecture-deep-analysis.md`

**内容:**
- 核心组件清单与功能分析
- 模块间依赖关系图 (Mermaid)
- 数据流完整路径
- 瓶颈识别（8 个已知问题 + 新增风险点）
- 性能基线数据
- 改进建议

**Step 1:** 写入完整的架构分析文档

**Step 2:** 验证文档结构与内容完整性

---

### Task 2: 更新 Specs 文档体系

**Files:**
- Modify: `docs/specs/README.md` — 版本号 V0.6→V0.7，新增 optimize_predict 模块
- Modify: `docs/specs/01-api-server.md` — 新增 V0.7 端点
- Modify: `docs/specs/02-database-layer.md` — 确认函数列表完整性
- Modify: `docs/specs/03-sync-engine.md` — 反映 V0.7 实际流程
- Modify: `docs/specs/04-self-learning.md` — 补充 ML 增强信息
- Modify: `docs/specs/05-daily-update.md` — 更新废弃状态
- Modify: `docs/specs/appendix-b-api.md` — 确保 42 端点完整
- Modify: `docs/specs/appendix-f-known-issues.md` — 更新已知问题清单
- Create: `docs/specs/13-ml-prediction-optimization.md` — optimize_predict 模块 spec

**Step 1:** 逐个更新所有 spec 文件

**Step 2:** 验证 README.md 导航表包含所有文档

---

### Task 3: 创建 Rules 规范文档

**Files:**
- Create: `.rules/code-style.md` — 代码风格规范
- Create: `.rules/architecture-constraints.md` — 架构约束
- Create: `.rules/business-logic-rules.md` — 业务逻辑规则
- Create: `.rules/README.md` — 规则体系总览

**Step 1:** 创建代码风格规范（命名、格式、文档字符串、错误处理）
**Step 2:** 创建架构约束（分层原则、依赖方向、模块边界）
**Step 3:** 创建业务逻辑规则（数据一致性、预测生成规则、交易计算规则）
**Step 4:** 创建规则体系总览

---

### Task 4: 完善测试覆盖

**Files:**
- Create: `tests/test_optimize_predict.py` — ML 增强预测模块测试
- Create: `tests/test_report_compatibility.py` — 报告兼容层测试
- Create: `tests/test_data_integrity.py` — 跨表数据完整性测试
- Modify: `tests/test_api_server.py` — 补充 429/409/500 状态码测试
- Modify: `tests/test_db_helper.py` — 补充写入函数覆盖

**Step 1:** 创建 optimize_predict 测试
**Step 2:** 创建 report_compatibility 测试
**Step 3:** 创建数据完整性测试
**Step 4:** 补充 API 错误处理测试
**Step 5:** 补充 DB 写入测试

---

### Task 5: 验证与总结

**Files:**
- Modify: `docs/specs/README.md` — 更新维护日期

**Step 1:** 运行所有测试验证通过
**Step 2:** 检查文档一致性
