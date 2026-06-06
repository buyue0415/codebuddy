---
name: unify-dividend-yield-ttm-label
overview: 将股息率走势图中的"K线预估"标签统一为"TTM推算"，消除前端对两种数据源的视觉区分，让所有股息率都以TTM推算方式展示。
todos:
  - id: fix-backend-estimated
    content: 修改 db_helper.py，将 is_estimated 固定为 False，source 统一为 ttm_calculated
    status: pending
  - id: fix-frontend-styling
    content: 修改 bank-stock-system.html 前端的条件分支，统一为 TTM推算的样式、标签和提示文字
    status: pending
    dependencies:
      - fix-backend-estimated
---

## 产品概述

统一股息率走势图的展示方式，无论分红数据来源于券商对账单还是K线除权缺口反推，前端均以"股息率(TTM推算)"标签、实线红色样式呈现，消除用户对"K线预估"和"TTM推算"两种模式的困惑。

## 核心功能

- 移除前端对 `dyEstimated` 的条件分支判断，统一为TTM推算的展示样式
- 后端将K线预估的 `is_estimated` 设为 `False`，`source` 统一为 `ttm_calculated`
- 保留分红除权日 ▼ 标记（有分红事件时显示）
- 统一 tooltip 和 hint 提示文字，不再区分数据来源

## 技术方案

### 实现策略

采用最小修改原则，仅修改样式和标签的分支逻辑，不改变底层TTM计算（`ttm_sum / close * 100`）。后端将 `is_estimated` 固定为 `False`，前端移除所有基于 `dyEstimated` 的条件渲染，始终输出TTM推算的视觉效果。

### 修改范围

**后端 `scripts/db_helper.py`**：

- 第818行：`is_estimated = True` 改为 `is_estimated = False`
- 第822行：`'source': 'kline_estimated'` 改为 `'source': 'ttm_calculated'`
- K线预估功能保留不变（`_estimate_dividends_from_kline`），只是不再标记为estimated

**前端 `deliverables/bank-stock-system.html`**：

- 第1212行：`dyBorderClr` 始终为 `'#dc2626'`
- 第1213行：`dyBgClr` 始终为 `'rgba(220,38,38,0.07)'`
- 第1214行：`dyDash` 始终为 `[]`（实线）
- 第1215行：`dyLabel` 始终为 `'股息率(TTM推算)'`
- 第1198行：fallback条件简化为 `!hasDivs`（去掉 `!dyEstimated`）
- 第1278行：tooltip 中始终显示"股息率(TTM推算)"
- 第1282-1283行：source标签统一处理
- 第1306行：hint 文字移除 `dyEstimated?' ｜ ⚠ 基于除权缺口预估'` 分支

### 实现注意事项

- 后端 `is_estimated` 字段可保留在返回体中（避免API契约变更），值设为 `False` 后前端不再使用
- K线预估的 `_estimate_dividends_from_kline()` 函数保留不变，仅修改其被调用后的标记逻辑
- 分红除权日 ▼ 标记逻辑（第1223行）依赖 `hasDivs`，不受本次修改影响
- `render_intelligence.js` 已经统一使用"TTM推算"，无需修改