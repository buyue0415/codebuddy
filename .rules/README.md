# 项目规则体系 (Project Rules)

> **版本**: v1.0 | **创建日期**: 2026-06-03 | **适用范围**: 股票投资管理系统全部代码

---

## 规则文档导航

| 文档 | 用途 | 强制执行级别 |
|------|------|-------------|
| [代码风格规范](./code-style.md) | 命名、格式、文档、错误处理 | 🔴 强制 (MUST) |
| [架构约束](./architecture-constraints.md) | 四层架构、依赖方向、目录结构、模块交互、强制校验 | 🔴 强制 (MUST) |
| [业务逻辑规则](./business-logic-rules.md) | 数据一致性、预测生成、交易计算、月K线/季节性计算 | 🔴 强制 (MUST) |

---

## 强制执行级别定义

| 级别 | 关键词 | 含义 |
|------|--------|------|
| 🔴 MUST / MUST NOT | 强制 | 必须遵守，违反即Bug |
| 🟡 SHOULD / SHOULD NOT | 推荐 | 强烈建议，特殊情况可豁免 |
| 🟢 MAY | 可选 | 允许但不强制 |

---

## 开发过程规则

### 规范文档与代码同步（R001）

**级别**: 🔴 MUST | **适用范围**: 全部开发活动

**任何代码变更，无论大小，都必须同步更新对应的 `docs/specs/` 规范文档**：

1. **新增功能** → 补充对应 spec 文件的功能描述、数据流、代码示例
2. **修改功能** → 同步更新 spec 中的实现逻辑、参数、返回值
3. **删除功能** → 从 spec 中移除对应描述或标记为已废弃
4. **Bug 修复** → 更新 `appendix-f-known-issues.md`（新增记录或更新状态）

对应 spec 文件索引：
| 变更类型 | 需更新的 spec |
|----------|---------------|
| 后端 API / 数据层 | `03-data-sync-engine.md` / `02-database-layer.md` / `appendix-b-api-reference.md` |
| 前端页面 / 组件 | 对应页面 spec（`14-kline-charts.md` 等）|
| 数据库结构 | `appendix-a-database-schema.md` |
| Bug 修复 | `appendix-f-known-issues.md` |
| 依赖变更 | `appendix-d-dependencies.md` |

**文档更新必须在代码变更的同一提交中完成，不允许事后补文档。**

---

## 强制执行级别定义

| 级别 | 关键词 | 含义 |
|------|--------|------|
| 🔴 MUST / MUST NOT | 强制 | 必须遵守，违反即Bug |
| 🟡 SHOULD / SHOULD NOT | 推荐 | 强烈建议，特殊情况可豁免 |
| 🟢 MAY | 可选 | 允许但不强制 |

---

## 使用方式

### 开发前
1. 阅读 `architecture-constraints.md` 确认模块边界和依赖方向
2. 阅读 `business-logic-rules.md` 确认业务规则

### 实现时
1. 遵循 `code-style.md` 中的命名、格式、文档规范
2. 所有新代码添加 docstring 和类型注解

### Code Review 时
1. 检查是否违反架构约束（跨层调用、循环依赖）
2. 检查是否违反业务规则（数据一致性、计算逻辑）
3. 检查代码风格合规性

### 测试时
1. 每个新增功能必须有对应测试
2. 测试命名: `test_<module>_<scenario>_<expected_behaviour>`

---

## 规则变更流程

1. 提出变更 → 评估影响范围
2. 修改规则文档 → 同步更新关联 specs
3. 更新测试 → 确保覆盖新规则
4. 执行代码适配 → 使现有代码符合新规则
