# 股票专家分析报告 — Skill 输出规范

⚠️ **最终输出必须是合法 JSON**，前端直接从数据库读取并渲染。

---

## JSON Schema

```json
{
  "date": "2026-05-22",
  "stocks": {
    "<股票代码>": {
      "decision": "BUY",
      "confidence": "中",
      "risk_level": "低",
      "position_pct": 30,
      "entry_price": 17.30,
      "target_price": 19.50,
      "stop_loss": 16.00,
      "scores": {
        "technical": 6,
        "fundamental": 8,
        "news": 5,
        "sentiment": 5,
        "risk": 7
      },
      "phase1": {
        "technical": "文本...",
        "fundamental": "文本...",
        "news": "文本...",
        "sentiment": "文本..."
      },
      "phase2": {
        "bull_args": [
          {"point": "多头论点1（完整句子）", "weight": 9},
          {"point": "多头论点2", "weight": 7}
        ],
        "bear_args": [
          {"point": "空头论点1", "weight": 6},
          {"point": "空头论点2", "weight": 5}
        ],
        "verdict": "综合裁决结论（1-2句话）"
      },
      "phase4": {
        "aggressive_score": 8,
        "conservative_score": 4,
        "neutral_score": 6,
        "final_risk_note": "最终风险评估结论文本"
      },
      "catalysts": ["催化剂事件1", "催化剂事件2"],
      "risks": ["风险事件1", "风险事件2"],
      "summary": "一句话总结（备用）"
    }
  }
}
```

---

## 字段详解

### 顶层

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `date` | string | ✅ | 报告日期 `YYYY-MM-DD` |
| `stocks` | object | ✅ | key 为6位股票代码，value 为单只股票分析 |

### 决策信息

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `decision` | string | ✅ | `BUY` `HOLD` `SELL` 之一 |
| `confidence` | string | ✅ | `高` `中` `低` 之一 |
| `risk_level` | string | ✅ | `高` `中` `低` 之一 |
| `position_pct` | number | ✅ | 建议仓位百分比 0–100 |
| `entry_price` | number | ✅ | 建议入场价 |
| `target_price` | number | ✅ | 目标价 |
| `stop_loss` | number | ✅ | 止损价 |

### 评分（五维雷达图）

| 字段 | 类型 | 必填 | 范围 |
|------|------|------|------|
| `scores.technical` | number | ✅ | 0–10 |
| `scores.fundamental` | number | ✅ | 0–10 |
| `scores.news` | number | ✅ | 0–10 |
| `scores.sentiment` | number | ✅ | 0–10 |
| `scores.risk` | number | ✅ | 0–10 |

> 雷达图显示顺序：技术面 → 基本面 → 新闻面 → 情绪面 → 风险面

### Phase1：四面分析（折叠面板）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `phase1.technical` | string | ✅ | 技术面分析，可含换行 |
| `phase1.fundamental` | string | ✅ | 基本面分析 |
| `phase1.news` | string | ✅ | 新闻面分析（如有） |
| `phase1.sentiment` | string | ✅ | 情绪面分析 |

### Phase2：多空辩论（柱状图+论点列表）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `phase2.bull_args` | array | ✅ | 多头论点列表 |
| `phase2.bull_args[].point` | string | ✅ | 论点文字 |
| `phase2.bull_args[].weight` | number | ✅ | 权重 1–10 |
| `phase2.bear_args` | array | ✅ | 空头论点列表 |
| `phase2.bear_args[].point` | string | ✅ | 论点文字 |
| `phase2.bear_args[].weight` | number | ✅ | 权重 1–10 |
| `phase2.verdict` | string | ✅ | 辩论裁决结论 |

> 柱状图显示：多头红色（`#dc2626`），空头绿色（`#16a34a`），横向条形图

### Phase4：风险评估三角（雷达图+结论）

| 字段 | 类型 | 必填 | 范围 |
|------|------|------|------|
| `phase4.aggressive_score` | number | ✅ | 0–10 |
| `phase4.conservative_score` | number | ✅ | 0–10 |
| `phase4.neutral_score` | number | ✅ | 0–10 |
| `phase4.final_risk_note` | string | ✅ | 风险评估结论文本 |

### 催化剂与风险事件（可选）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `catalysts` | array(string) | ❌ | 近期催化剂事件 |
| `risks` | array(string) | ❌ | 风险事件列表 |

### 总结（备用）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `summary` | string | ❌ | 一句话总结，暂未在前端显示 |

---

## 完整示例

```json
{
  "date": "2026-05-22",
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
        "technical": 6,
        "fundamental": 8,
        "news": 5,
        "sentiment": 5,
        "risk": 7
      },
      "phase1": {
        "technical": "兴业银行当前处于17.3元附近震荡，月线级别仍处于上升通道中。SMA20位于17.5元形成短期压制，SMA60位于17.0元形成支撑。MACD柱状图绿柱收窄，即将金叉。RSI约45处于中性区域，无明显超买超卖信号。短期支撑位17.0元、16.5元，阻力位17.8元、18.5元。",
        "fundamental": "市净率0.44倍处于历史极低分位（<5%），ROE约7.2%，营收增速平稳。不良率1.07%环比改善，拨备覆盖率>280%，资产质量稳定。股息率9.36%处于历史极值，高股息策略极具防御价值。",
        "news": "近期无重大负面新闻。银行板块整体表现稳健，市场对银行股高股息策略关注度提升。",
        "sentiment": "市场情绪偏中性，散户关注度一般。机构持仓稳定，北向资金近期小幅流入。"
      },
      "phase2": {
        "bull_args": [
          {"point": "股息率9.36%处于历史极值，高股息策略极具吸引力，泡沫风险极低", "weight": 9},
          {"point": "市净率0.44倍，估值修复空间巨大，均值回归概率高", "weight": 8},
          {"point": "MACD即将金叉，技术面短期有反弹需求", "weight": 6},
          {"point": "银行板块整体估值处于历史底部，安全边际充足", "weight": 7}
        ],
        "bear_args": [
          {"point": "宏观经济增速放缓，银行资产质量存在隐忧", "weight": 6},
          {"point": "短期SMA20压制明显，技术面反弹需要时间消化", "weight": 5},
          {"point": "利差收窄趋势下盈利能力承压", "weight": 5}
        ],
        "verdict": "多空力量对比：多头8：空头5。多头优势明显，核心逻辑是高股息+低估值组合提供强安全边际，建议伺机低吸。"
      },
      "phase4": {
        "aggressive_score": 8,
        "conservative_score": 5,
        "neutral_score": 6,
        "final_risk_note": "激进派认为当前是极佳买点，股息率提供安全垫，错失成本高；保守派指出短期技术面偏弱和宏观经济不确定性。综合来看，下行空间有限（股息率支撑），可在16.0-17.0区间分批建仓，止损设16.0元。"
      },
      "catalysts": ["中报业绩披露窗口（7-8月）", "银行板块高股息策略持续受关注", "MACD金叉信号出现"],
      "risks": ["宏观经济下行超预期", "房地产风险传导至银行", "利差持续收窄压缩利润"],
      "summary": "兴业银行：高股息+低估值双驱动，BUY评级，建议17.3元下方分批建仓"
    }
  }
}
```

---

## 多只股票示例

```json
{
  "date": "2026-05-22",
  "stocks": {
    "601166": { /* 兴业银行分析 */ },
    "600036": { /* 招商银行分析 */ },
    "600919": { /* 江苏银行分析 */ }
  }
}
```

> 各股票结构完全一致，前端按当前选中股票切发展示。
