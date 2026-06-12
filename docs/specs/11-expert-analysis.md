# 11 — 专家分析

> **前端页面**: `deliverables/v2/src/pages/Expert.vue` (12KB)
> **路由**: `/expert` | **菜单**: 股票分析预测 → 专家分析

---

## 1. 业务需求说明书

### 1.1 业务背景

系统支持导入由 WorkBuddy 多 Agent 系统生成的股票专家分析报告，包含五维评分（技术/基本/新闻/情绪/风险）、多空辩论和综合建议，为用户提供比纯技术指标更全面的分析视角。

### 1.2 核心目标

| 目标 | 说明 |
|------|------|
| 五维雷达图 | 技术面/基本面/新闻/情绪/风险评分可视化 |
| 多空辩论 | 多头论据 vs 空头论据的权重对比 |
| 综合建议 | BUY/HOLD/SELL 决策 + 入场价/目标价/止损 |
| 报告导入 | POST API 或 CLI 导入 JSON 格式报告 |

---

## 2. 技术方案深度分析

### 2.1 报告 Schema

```json
{
  "date": "2026-06-05",
  "stocks": {
    "601166": {
      "decision": "BUY",
      "confidence": "中",
      "risk_level": "低",
      "position_pct": 30,
      "entry_price": 17.30,
      "target_price": 19.50,
      "stop_loss": 16.00,
      "scores": {
        "technical": 6, "fundamental": 8,
        "news": 5, "sentiment": 5, "risk": 7
      },
      "phase2": {
        "bull_args": [{"point": "...", "weight": 9}],
        "bear_args": [{"point": "...", "weight": 6}]
      },
      "summary": "..."
    }
  }
}
```

### 2.2 导入验证规则

| 字段 | 约束 |
|------|------|
| `decision` | 必须为 BUY/HOLD/SELL |
| `confidence` | 高/中/低，否则自动修正 |
| `scores.*` | 0-10 范围 |
| `bull_args[i].point` | 必须为 string |
| `bull_args[i].weight` | 1-10 |

### 2.3 数据流

```
WorkBuddy 多 Agent
  → POST /api/v2/expert/import (JSON body)
  → import_expert_report.py（验证 + 标准化 + 写入）
  → expert_reports 表 (date, report_data)
  → GET /api/v2/expert
  → Expert.vue 渲染
```

---

## 3. 功能介绍和实现方式

### 3.1 API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v2/expert` | 获取专家报告列表 |
| POST | `/api/v2/expert/import` | 导入新报告 |
| POST | `/api/expert/import` | 旧版兼容接口 |

### 3.2 后端实现

```python
# scripts/import_expert_report.py
def validate_report(data: dict) -> tuple[bool, list]:
    """验证报告格式，返回 (是否有效, 警告列表)"""
    # 1. 根对象必须为 dict
    # 2. stocks 不能为空
    # 3. 逐股票验证 7 个必需字段
    # 4. 枚举值自动修正（confidence/risk_level → '中'）
    # 5. 评分裁剪到 0-10

def import_report(data: dict) -> dict:
    """导入报告到 expert_reports 表"""
    # INSERT INTO expert_reports (date, report_data)
    # report_data 以 JSON 文本存储
```

### 3.3 前端实现

```vue
<!-- Expert.vue 核心结构 -->
<template>
  <!-- 股票选择 -->
  <Dropdown v-model="selectedCode" />

  <!-- 五维雷达图 -->
  <RadarChart :data="scores" />

  <!-- 综合建议卡片 -->
  <DecisionCard>
    <Badge :type="decision">{{ decision }}</Badge>
    <div>入场: ¥{{ entry_price }}</div>
    <div>目标: ¥{{ target_price }}</div>
    <div>止损: ¥{{ stop_loss }}</div>
  </DecisionCard>

  <!-- 多空辩论 -->
  <BullBearDebate>
    <BullArgs :args="bull_args" />
    <BearArgs :args="bear_args" />
    <Verdict :text="verdict" />
  </BullBearDebate>

  <!-- 风险提示 -->
  <RiskSummary :text="summary" :risks="risks" />
</template>
```

---

## 4. 用户操作流程

### 4.1 查看专家报告

```
用户: 导航栏 "股票分析预测" → "专家分析"
  → 下拉选择股票 "兴业银行"
  → 显示五维雷达图（技术6/基本8/新闻5/情绪5/风险7）
  → 综合建议: BUY · 中置信 · 低风险
  → 入场 ¥17.30 | 目标 ¥19.50 | 止损 ¥16.00
  → 多空辩论: 多头权重9分 vs 空头权重6分
  → 总结: "兴业银行基本面稳健，技术面出现金叉信号..."
```

### 4.2 导入新报告

```
方式1（API）:
  管理设置 → 点击 [导入专家报告]
  → POST /api/v2/expert/import
  → Body: 专家报告 JSON
  → 返回 {success: true, message: "报告已导入"}

方式2（CLI）:
  python scripts/import_expert_report.py report.json
```
