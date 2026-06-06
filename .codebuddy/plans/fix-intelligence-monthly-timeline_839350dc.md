---
name: fix-intelligence-monthly-timeline
overview: 修复智能预测月度走势图：使预测从最后一个历史月份的下一月开始连续延伸6个月，同时统一X轴标签为YYYY-MM格式。
todos:
  - id: fix-prediction-labels
    content: 修复 intelligence.js 中 predL 生成逻辑：从最后一个历史月份的下一月开始，生成连续6个 YYYY-MM 格式标签，同时修正 predV 的季节索引计算
    status: completed
---

## 用户需求

智能预测功能的月度走势图存在两个问题：

1. **月份不连续**：预测从当前月份（如 2026-06）开始，但历史数据可能只覆盖到 2025-08，中间 2025-09 至 2026-05 共 9 个月出现断裂，时间线不连贯
2. **X 轴标签格式不一致**：历史月份使用 `YYYY-MM` 格式（如 "2025-08"），预测月份使用 `M月` 中文格式（如 "6月"），视觉上突兀跳变

## 用户期望

月份必须连续无断裂。过去的月份显示真实历史数据，未来的月份（从最后一个历史月份的下一月开始）显示预测数据。X 轴标签格式统一。

## 技术方案

### 问题根因

`deliverables/js/intelligence.js` 第 84-93 行：

```javascript
var histL = klineMK.slice(-12).map(function(k){return k[0].substring(0,7);});
var predL = months.slice(nowMonth-1).concat(months.slice(0,nowMonth-1)).slice(0,6);
```

- `predL` 起点硬编码为 `nowMonth`（当前月），而非 `histL` 最后一个月份的下一个月
- `predL` 使用 `months` 数组的 `"M月"` 格式，与 `histL` 的 `"YYYY-MM"` 不统一

### 修复策略

将 `predL` 起点改为**解析最后一个历史月份的下一个月**，并统一使用 `YYYY-MM` 格式：

1. 从 `histL` 最后一条解析出年月（如 `"2025-08"` → `year=2025, month=8`）
2. 计算下一个月作为预测起点（`month+1`，跨年时 `month=1, year++`）
3. 若 `histL` 为空则回退到当前月份
4. 生成连续 6 个 `YYYY-MM` 标签，月份补齐前导零
5. `predV` 的季节索引 `mi` 改为基于实际预测月份计算（`mi = pm - 1`，0-based），而非当前月份偏移

**边缘情况处理**：

- `histL` 为空：使用 `nowMonth` 作为预测起点
- 跨年：`predStartMonth` 超过 12 时进位到下一年 1 月
- 季节数据缺失：`sea[mi] || 0` 已有 fallback

### 影响范围

- 仅修改 `deliverables/js/intelligence.js` 第 87-89 行（`predL` 和 `predV` 生成逻辑）
- `months` 数组和季节展望卡片（第 52 行）保持不变
- 不涉及 API、数据库、其他 JS 文件