---
name: fix-intelligence-monthly-timeline
overview: 修复智能预测走势图月度时间线显示问题：将预测标签从"M月"中文格式统一为"YYYY-MM"格式，与历史数据标签保持一致。
todos:
  - id: fix-monthly-xaxis-labels
    content: 修复 intelligence.js 第87行 predL 生成逻辑，使预测月份标签统一使用 YYYY-MM 格式并正确处理跨年
    status: pending
---

## 用户需求

智能预测功能中的月度走势图，X 轴时间线显示存在格式不一致问题：历史月份显示为 `YYYY-MM` 格式（如 `2025-08`），而预测月份显示为中文 `M月` 格式（如 `6月`），导致时间线视觉断裂，从 `2025-08` 直接跳到 `6月`，用户无法理解预测月份对应的具体年份。

## 修复目标

将预测月份标签统一为 `YYYY-MM` 格式，使其与历史月份标签格式一致，并正确处理跨年场景（如当前为 11 月时，预测第 3 个月应显示 `2027-01`）。

## 核心修复点

- 仅修改 `deliverables/js/intelligence.js` 中 `predL` 的生成逻辑（第 87 行）
- 保持 `months` 数组不变（它仍被季节展望卡片使用，那里 `M月` 格式是合适的）
- 保持 `predV` 预测值计算逻辑不变

## 技术方案

### 问题根因

`deliverables/js/intelligence.js` 第 86-87 行：

```javascript
var histL = klineMK.slice(-12).map(function(k){return k[0].substring(0,7);});  // "2025-08"
var predL = months.slice(nowMonth-1).concat(months.slice(0,nowMonth-1)).slice(0,6); // "6月"
```

`histL` 使用 `YYYY-MM` 格式，`predL` 使用 `M月` 格式，两者拼接后 X 轴标签格式不一致。

### 修复策略

将 `predL` 的生成逻辑改为动态计算 `YYYY-MM` 格式，包含正确的年份：

```javascript
var nowYear = now.getFullYear();
var predL = [];
for (var i = 0; i < 6; i++) {
  var totalMonths = nowMonth - 1 + i;
  var py = nowYear + Math.floor(totalMonths / 12);
  var pm = (totalMonths % 12) + 1;
  predL.push(py + '-' + (pm < 10 ? '0' : '') + pm);
}
```

- `totalMonths`：当前月份偏移量（0-based），用于统一计算跨年
- `py`：通过 `Math.floor(totalMonths / 12)` 处理年份进位
- `pm`：通过 `% 12 + 1` 转换为 1-based 月份
- 月份补齐前导零（如 `"06"`），保持与历史标签一致的两位数字格式

### 影响范围

- 仅修改 `deliverables/js/intelligence.js` 第 87 行
- 不影响其他代码路径：`months` 数组在第 52 行季节展望卡片中的使用保持不变
- 不影响 `predV` 预测值计算（第 88-89 行保持原样）