# 模块10: 专家报告导入模块

> **核心文件**: `scripts/import_expert_report.py` | **Schema**: `data/expert_report_template.md`
> **触发**: `POST /api/v2/expert/import` 或 CLI

---

## 1. 功能概述

验证并导入 WorkBuddy 多 Agent 生成的股票专家分析报告 JSON，存入 SQLite 的 **expert_reports** 表，供前端渲染五维雷达图、多空辩论柱状图等内容。

---

## 2. 核心业务逻辑

### 2.1 验证规则

| 字段 | 约束 |
|------|------|
| 根对象 | 必须为 `dict` |
| `stocks` | 必须为 `dict`，不能为空 |
| `decision` | 必须为 `BUY` / `HOLD` / `SELL` |
| `confidence` | 必须是 `高` / `中` / `低`，否则自动修正为 `中` |
| `risk_level` | 必须是 `高` / `中` / `低`，否则自动修正为 `中` |
| `scores.technical` ~ `scores.risk` | 必须在 0–10 范围 |
| `phase2.bull_args[i]` / `bear_args[i]` | 每项必须有 `point` (string) 和 `weight` (number 1-10) |
| `phase4.aggressive_score` ~ `neutral_score` | 必须在 0–10 范围 |

### 2.2 必需字段（11个）

`decision`, `confidence`, `risk_level`, `position_pct`, `entry_price`, `target_price`, `stop_loss`, `scores`, `phase1`, `phase2`, `phase4`

### 2.3 报告 Schema

详见 `data/expert_report_template.md`，核心结构：

```json
{
  "date": "2026-05-26",
  "stocks": {
    "<code>": {
      "decision": "BUY",
      "confidence": "中",
      "risk_level": "低",
      "position_pct": 30,
      "entry_price": 17.30,
      "target_price": 19.50,
      "stop_loss": 16.00,
      "scores": { "technical": 6, "fundamental": 8, "news": 5, "sentiment": 5, "risk": 7 },
      "phase1": { "technical": "...", "fundamental": "...", "news": "...", "sentiment": "..." },
      "phase2": {
        "bull_args": [{"point": "...", "weight": 9}],
        "bear_args": [{"point": "...", "weight": 6}],
        "verdict": "..."
      },
      "phase4": {
        "aggressive_score": 8, "conservative_score": 5, "neutral_score": 6,
        "final_risk_note": "..."
      },
      "catalysts": ["..."],
      "risks": ["..."],
      "summary": "..."
    }
  }
}
```

### 2.4 导入方式

| 方式 | 命令 |
|------|------|
| CLI | `python scripts/import_expert_report.py report.json` |
| API | `POST /api/v2/expert/import` (JSON body) |
| Markdown 内 JSON | 支持正则提取 ` ```json ... ``` ` 代码块 |

### 2.5 日期自动填充

若 JSON 中无 `date` 字段，自动填入当前日期。

---

## 3. 输入输出参数定义

```
输入: 专家报告 JSON (符合 data/expert_report_template.md 的 Schema)
输出: { "success": bool, "message": "<导入结果>", "warnings": ["<警告1>", ...] }
```

---

## 4. 依赖关系

| 方向 | 模块 |
|------|------|
| **依赖** | [数据库访问层](./02-database-layer.md) `get_db()` |
| **被调用** | [Web API 层](./01-api-server.md) `POST /api/v2/expert/import` |
| **数据源** | WorkBuddy 多 Agent (trading-analysis skill) |
| **前端读取** | `GET /api/v2/expert` |

---

## 5. 异常处理机制

| 场景 | 处理 |
|------|------|
| 根非 dict | 返回非法格式错误 |
| 缺少 `stocks` | 返回格式错误 |
| 非标准枚举值 (confidence/risk_level) | 自动修正为 `中`，记录 `warnings` |
| 评分越界 (0-10) | 记录 `warnings`，不阻断导入 |
| `bull_args/bear_args` 缺少 `point/weight` | 记录 `warnings` |
| DB 写入失败 | 返回错误信息 |
| JSON 解析失败 | CLI 模式下尝试从 Markdown 代码块提取；API 模式返回 500 |
