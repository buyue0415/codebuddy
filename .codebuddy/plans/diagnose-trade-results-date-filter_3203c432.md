---
name: diagnose-trade-results-date-filter
overview: 诊断并修复 PaperTrading 页面"今日交易结果"模块日期筛选不生效的问题，确保切换日期后 suggestion 数据正确更新。
todos:
  - id: add-debug-logs
    content: 在 PaperTrading.vue 的 onDateChange 中添加 console.log 调试日志，并优化空数据提示文案为动态日期
    status: completed
  - id: rebuild-dist
    content: 执行 vite build 重新编译 dist 文件
    status: completed
    dependencies:
      - add-debug-logs
  - id: restart-server
    content: 重启 FastAPI 服务器并指导用户硬刷新浏览器
    status: completed
    dependencies:
      - rebuild-dist
---

## 用户需求

修复 PaperTrading 页面"今日交易结果"模块：通过日期选择器切换到历史日期（如6月4日）后，交易结果列表应显示对应日期的数据，而非始终显示今日数据。

## 排查结论

整条调用链代码逻辑完全正确：

- 数据库 `paper_suggestions` 表 6月4日和6月5日各有不同记录
- 源代码 `onDateChange` 已正确调用 `loadSuggestions('', selectedDate.value)`
- Pinia Store、API 层、后端路由、数据库查询函数均正确支持 date 参数
- Dist 编译文件 `PaperTrading-DGFpl8CW.js` 已包含正确逻辑

## 根因

Dist 文件已重新编译但浏览器可能缓存了旧版本，或 Vite 开发服务器未重启以加载新代码。

## 修复方案

在 PaperTrading.vue 中添加一个可见的版本标记（页面顶部日期标题），同时添加调试日志确保 onDateChange 触发，然后重新 build 并指导用户强制刷新。

## 实现方案

### 策略

在 PaperTrading.vue 的"今日交易结果"卡片标题区域增加日期显示变化验证点，同时添加 `console.log` 调试日志来确认 `onDateChange` 函数确实被触发且传入了正确的日期参数。最后重新编译 dist 并确保服务器重启。

### 修改文件

#### deliverables/v2/src/pages/PaperTrading.vue

**改动1：onDateChange 添加调试日志**
在第 184 行 `async function onDateChange()` 函数体开头添加：

```js
console.log('[PaperTrading] onDateChange triggered, selectedDate:', selectedDate.value)
```

用于验证日期变更事件是否被触发、传入的日期值是否正确。

**改动2：suggestions 卡片标题添加日期变化提示**
将第 73 行的标题从纯文本改为确保 computed 属性 `tradingTitle` 的变化能被用户感知。当前 `tradingTitle` 已正确计算，但可以添加一个微型版本标记来验证最新代码已加载：

```html
<h2>{{ tradingTitle }} <span style="font-size:10px;color:#9ca3af;font-weight:400">v2.1</span></h2>
```

这个版本标记 `v2.1` 是可选的，主要目的是让用户直观确认浏览器已加载最新代码。

**改动3：空数据状态文案优化**
第 95 行的空状态提示从静态文案"今日暂无自动交易结果"改为动态：

```html
<div class="empty">{{ selectedDate === todayStr ? '今日' : selectedDate }}暂无自动交易结果</div>
```

这样当切换到无数据的历史日期时，用户能明确看到日期已变化。

### 后续步骤

1. 运行 `vite build` 重新编译 dist
2. 重启 FastAPI 服务器（`start_v2.bat` 或 `start_v2_fastapi.bat`）
3. 浏览器硬刷新（Ctrl+Shift+R）
4. 打开 DevTools Console，切换日期验证日志输出