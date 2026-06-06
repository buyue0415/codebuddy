---
name: fix-expert-report-not-showing
overview: 修复专家分析报告导入后页面不显示的问题，根因是导入成功后未刷新 Pinia store，以及 Expert 页面挂载时未重新加载专家报告数据。
todos:
  - id: fix-management-import-refresh
    content: 在 Management.vue 的 importReport() 成功后添加 await data.fetchAll() 刷新
    status: completed
  - id: fix-expert-mount-refresh
    content: 在 Expert.vue 的 onMounted 中移除 if 条件，始终调用 data.fetchAll()
    status: completed
---

## 问题描述

用户在管理页面新增了股票"工商银行"(601398)到自选股后，通过"导入专家分析报告"功能导入了JSON格式的专家分析报告（Management.vue 中 `importReport()` 函数处理后端 API `/api/v2/expert/import`）。系统显示"导入成功"，但切换到专家分析页面（Expert.vue）后，页面显示"暂无专家分析报告"，没有显示新导入的数据。

## 根因分析

通过完整追踪数据链路（导入Management.vue `importReport()` -> 后端 `POST /api/v2/expert/import` -> 数据库写入 -> Expert.vue 加载 `GET /api/v2/expert`），发现两个问题：

### 问题1（主要原因）：Management.vue 导入成功后未刷新 Store

- 位置：`deliverables/v2/src/pages/Management.vue` 第 212-222 行
- 对比 `addStock()`（第 177 行调用了 `await data.fetchAll()`）和 `removeStock()`（第 188 行也调用了 `await data.fetchAll()`），`importReport()` 在第 219 行成功后仅清空了 `expertJson.value = ''`，**没有调用 `data.fetchAll()`** 刷新 Pinia store 中的 `expertReports`
- 结果：数据虽已写入后端数据库，但前端 `data.expertReports` 仍为空，Expert 页面自然不显示

### 问题2（次要）：Expert.vue 挂载时条件判断导致不重新加载

- 位置：`deliverables/v2/src/pages/Expert.vue` 第 183-184 行
- 条件 `if (!data.watchlist.length) await data.fetchAll()` 意味着如果 `watchlist` 已有数据（用户在 Management 页面已添加过股票），则不会调用 `fetchAll()`，导致 `expertReports` 不会更新
- 即使用户在 Expert 页面手动刷新，如果 watchlist 非空，也不会重新拉取报告数据

## 技术栈

- 前端：Vue 3 + Pinia 状态管理 + Vite 构建
- 后端：Python FastAPI + SQLite 数据库
- 数据流转：后端 `GET /api/v2/expert` -> `db_helper.get_expert_reports()` -> Pinia store `expertReports` -> Expert.vue computed `stockReports`

## 修复方案

遵循**最小改动原则**，仅修复2个文件共2处代码。

### 修复1：Management.vue - import 成功后刷新数据

**文件**：`deliverables/v2/src/pages/Management.vue` 第 219 行

**当前代码**（第 219-220 行）：

```javascript
    expertStatus.value = r?.success ? '✅ 导入成功' : '❌ ' + (r?.error || '失败')
    if (r?.success) expertJson.value = ''
```

**修复后**：

```javascript
    expertStatus.value = r?.success ? '✅ 导入成功' : '❌ ' + (r?.error || '失败')
    if (r?.success) { expertJson.value = ''; await data.fetchAll() }
```

**设计理由**：

- 复用现有模式：`addStock()`（第177行）和 `removeStock()`（第188行）成功后都调用了 `await data.fetchAll()`
- 一致性：所有修改数据操作成功后都应刷新 store
- 最小改动：仅增加 `await data.fetchAll()` 调用

### 修复2：Expert.vue - 进入页面时始终刷新数据

**文件**：`deliverables/v2/src/pages/Expert.vue` 第 183-184 行

**当前代码**：

```javascript
onMounted(async () => {
  if (!data.watchlist.length) await data.fetchAll()
  ...
})
```

**修复后**：

```javascript
onMounted(async () => {
  await data.fetchAll()
  ...
})
```

**设计理由**：

- 确保每次进入专家分析页面时数据都是最新的
- `data.fetchAll()` 内部已有 `loading.value` 和 `refreshing.value` 防重复保护机制
- 虽然会发起全量请求，但页面切换不频繁，且用户期望看到最新数据，性能影响可接受
- 如果考虑性能优化，未来可改为仅调用 `loadData('expert', '/api/v2/expert')` 增量刷新，但当前保持与现有模式一致

## Agent Extensions

### Skill

- **systematic-debugging**: 按照系统调试技能的四阶段流程（根因调查 -> 模式分析 -> 假设验证 -> 修复实施）排查了问题，确定了数据不显示的根本原因，并提出了精准的修复方案。
- 使用方式：[skill:systematic-debugging] 遵循其Phase 1（根因调查）和Phase 2（模式分析）的原则

### SubAgent

- **code-explorer**: 用于快速探索项目结构，定位专家分析功能相关的关键文件路径（Management.vue, Expert.vue, data.js, client.js, server_v2.py, import_expert_report.py, db_helper.py），追踪完整数据流转链路。
- 使用方式：[subagent:code-explorer] 已调用完成

### 修复后验证

- **verification-before-completion**: 修复完成后，使用 [skill:verification-before-completion] 技能验证修复结果