"""初始化33条标准K线形态规则到 pattern_rules 表。"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.db_helper import (
    init_pattern_rules_tables, insert_pattern_rule, count_pattern_rules
)
import json

RULES = [
    # ============ 第一类 · 单K线形态（6条） ============
    {
        "rule_id": "C1-01", "name": "长阳线", "name_en": "Long Bullish",
        "category": "single", "direction": "bullish", "strength": 3, "span_days": 1,
        "conditions": json.dumps({"candles": [{"idx": 0, "label": "当前K线", "rules": [
            {"field": "close", "op": ">", "ref": "open", "type": "self"},
            {"field": "body_ratio", "op": ">=", "ref": 0.6, "type": "value"}
        ]}]}, ensure_ascii=False),
        "memo": "实体占比≥60%的阳线，强烈上涨信号"
    },
    {
        "rule_id": "C1-02", "name": "长阴线", "name_en": "Long Bearish",
        "category": "single", "direction": "bearish", "strength": 3, "span_days": 1,
        "conditions": json.dumps({"candles": [{"idx": 0, "label": "当前K线", "rules": [
            {"field": "close", "op": "<", "ref": "open", "type": "self"},
            {"field": "body_ratio", "op": ">=", "ref": 0.6, "type": "value"}
        ]}]}, ensure_ascii=False),
        "memo": "实体占比≥60%的阴线，强烈下跌信号"
    },
    {
        "rule_id": "C1-03", "name": "十字星", "name_en": "Doji",
        "category": "single", "direction": "neutral", "strength": 1, "span_days": 1,
        "conditions": json.dumps({"candles": [{"idx": 0, "label": "当前K线", "rules": [
            {"field": "body_ratio", "op": "<=", "ref": 0.15, "type": "value"}
        ]}]}, ensure_ascii=False),
        "memo": "实体占比≤15%，多空力量均衡，等待方向确认"
    },
    {
        "rule_id": "C1-04", "name": "锤子线", "name_en": "Hammer",
        "category": "single", "direction": "bullish", "strength": 5, "span_days": 1,
        "conditions": json.dumps({"candles": [{"idx": 0, "label": "当前K线", "rules": [
            {"field": "close", "op": ">", "ref": "open", "type": "self"},
            {"field": "lower_shadow", "op": ">=", "ref_field": "body", "ref_factor": 2, "type": "field_factor"},
            {"field": "upper_shadow", "op": "<=", "ref_field": "body", "ref_factor": 0.3, "type": "field_factor"}
        ]}]}, ensure_ascii=False),
        "memo": "下影线≥实体×2，上影线≤实体×0.3，低位出现为见底反转信号"
    },
    {
        "rule_id": "C1-05", "name": "上吊线", "name_en": "Hanging Man",
        "category": "single", "direction": "bearish", "strength": 5, "span_days": 1,
        "conditions": json.dumps({"candles": [{"idx": 0, "label": "当前K线", "rules": [
            {"field": "close", "op": "<", "ref": "open", "type": "self"},
            {"field": "lower_shadow", "op": ">=", "ref_field": "body", "ref_factor": 2, "type": "field_factor"},
            {"field": "upper_shadow", "op": "<=", "ref_field": "body", "ref_factor": 0.3, "type": "field_factor"}
        ]}]}, ensure_ascii=False),
        "memo": "下影线≥实体×2，上影线≤实体×0.3，高位出现为见顶反转信号"
    },
    {
        "rule_id": "C1-06", "name": "倒锤子", "name_en": "Inverted Hammer",
        "category": "single", "direction": "bullish", "strength": 5, "span_days": 1,
        "conditions": json.dumps({"candles": [{"idx": 0, "label": "当前K线", "rules": [
            {"field": "close", "op": ">", "ref": "open", "type": "self"},
            {"field": "upper_shadow", "op": ">=", "ref_field": "body", "ref_factor": 2, "type": "field_factor"},
            {"field": "lower_shadow", "op": "<=", "ref_field": "body", "ref_factor": 0.3, "type": "field_factor"}
        ]}]}, ensure_ascii=False),
        "memo": "上影线≥实体×2，下影线≤实体×0.3，低位出现为反转信号"
    },

    # ============ 第二类 · 双K线形态（6条） ============
    {
        "rule_id": "C2-01", "name": "看涨吞没", "name_en": "Bullish Engulfing",
        "category": "double", "direction": "bullish", "strength": 6, "span_days": 2,
        "conditions": json.dumps({"candles": [
            {"idx": 0, "label": "K2（当前）", "rules": [
                {"field": "close", "op": ">", "ref": "open", "type": "self"},
                {"field": "open", "op": "<", "ref": "close_1", "type": "prev"},
                {"field": "close", "op": ">", "ref": "open_1", "type": "prev"}
            ]},
            {"idx": 1, "label": "K1（前日）", "rules": [
                {"field": "close", "op": "<", "ref": "open", "type": "self"}
            ]}
        ]}, ensure_ascii=False),
        "memo": "阴线后被阳线完全吞没实体，强烈的反转看涨信号"
    },
    {
        "rule_id": "C2-02", "name": "看跌吞没", "name_en": "Bearish Engulfing",
        "category": "double", "direction": "bearish", "strength": 6, "span_days": 2,
        "conditions": json.dumps({"candles": [
            {"idx": 0, "label": "K2（当前）", "rules": [
                {"field": "close", "op": "<", "ref": "open", "type": "self"},
                {"field": "open", "op": ">", "ref": "close_1", "type": "prev"},
                {"field": "close", "op": "<", "ref": "open_1", "type": "prev"}
            ]},
            {"idx": 1, "label": "K1（前日）", "rules": [
                {"field": "close", "op": ">", "ref": "open", "type": "self"}
            ]}
        ]}, ensure_ascii=False),
        "memo": "阳线后被阴线完全吞没实体，强烈的反转看跌信号"
    },
    {
        "rule_id": "C2-03", "name": "曙光初现", "name_en": "Piercing Line",
        "category": "double", "direction": "bullish", "strength": 5, "span_days": 2,
        "conditions": json.dumps({"candles": [
            {"idx": 0, "label": "K2（当前）", "rules": [
                {"field": "close", "op": ">", "ref": "open", "type": "self"},
                {"field": "open", "op": "<", "ref": "low_1", "type": "prev"},
                {"field": "close", "op": ">", "ref": "midpoint_1", "type": "prev"}
            ]},
            {"idx": 1, "label": "K1（前日）", "rules": [
                {"field": "close", "op": "<", "ref": "open", "type": "self"}
            ]}
        ]}, ensure_ascii=False),
        "memo": "低开高走阳线收盘深入前阴线实体50%以上，看涨反转"
    },
    {
        "rule_id": "C2-04", "name": "乌云盖顶", "name_en": "Dark Cloud Cover",
        "category": "double", "direction": "bearish", "strength": 5, "span_days": 2,
        "conditions": json.dumps({"candles": [
            {"idx": 0, "label": "K2（当前）", "rules": [
                {"field": "close", "op": "<", "ref": "open", "type": "self"},
                {"field": "open", "op": ">", "ref": "high_1", "type": "prev"},
                {"field": "close", "op": "<", "ref": "midpoint_1", "type": "prev"}
            ]},
            {"idx": 1, "label": "K1（前日）", "rules": [
                {"field": "close", "op": ">", "ref": "open", "type": "self"}
            ]}
        ]}, ensure_ascii=False),
        "memo": "高开低走阴线收盘深入前阳线实体50%以下，看跌反转"
    },
    {
        "rule_id": "C2-05", "name": "旭日东升", "name_en": "Bullish Counterattack",
        "category": "double", "direction": "bullish", "strength": 5, "span_days": 2,
        "conditions": json.dumps({"candles": [
            {"idx": 0, "label": "K2（当前）", "rules": [
                {"field": "close", "op": ">", "ref": "open", "type": "self"},
                {"field": "open", "op": "<", "ref": "close_1", "type": "prev"},
                {"field": "close_diff_1", "op": "<=", "ref": 0.01, "type": "value"}
            ]},
            {"idx": 1, "label": "K1（前日）", "rules": [
                {"field": "close", "op": "<", "ref": "open", "type": "self"}
            ]}
        ]}, ensure_ascii=False),
        "memo": "低开后大幅拉升收于前阴收盘价附近，两收同价"
    },
    {
        "rule_id": "C2-06", "name": "断头铡刀", "name_en": "Bearish Counterattack",
        "category": "double", "direction": "bearish", "strength": 5, "span_days": 2,
        "conditions": json.dumps({"candles": [
            {"idx": 0, "label": "K2（当前）", "rules": [
                {"field": "close", "op": "<", "ref": "open", "type": "self"},
                {"field": "open", "op": ">", "ref": "close_1", "type": "prev"},
                {"field": "close_diff_1", "op": "<=", "ref": 0.01, "type": "value"}
            ]},
            {"idx": 1, "label": "K1（前日）", "rules": [
                {"field": "close", "op": ">", "ref": "open", "type": "self"}
            ]}
        ]}, ensure_ascii=False),
        "memo": "高开后大幅下挫收于前阳收盘价附近，两收同价"
    },

    # ============ 第三类 · 三K线形态（9条） ============
    {
        "rule_id": "C3-01", "name": "红三兵", "name_en": "Three White Soldiers",
        "category": "triple", "direction": "bullish", "strength": 6, "span_days": 3,
        "conditions": json.dumps({"candles": [
            {"idx": 0, "label": "K3（当前）", "rules": [
                {"field": "close", "op": ">", "ref": "open", "type": "self"},
                {"field": "body_ratio", "op": ">=", "ref": 0.5, "type": "value"},
                {"field": "upper_shadow", "op": "<=", "ref_field": "body", "ref_factor": 0.3, "type": "field_factor"},
                {"field": "close_ascend", "op": "==", "ref": 1, "type": "value"}
            ]},
            {"idx": 1, "label": "K2", "rules": [
                {"field": "close", "op": ">", "ref": "open", "type": "self"},
                {"field": "body_ratio", "op": ">=", "ref": 0.5, "type": "value"},
                {"field": "upper_shadow", "op": "<=", "ref_field": "body", "ref_factor": 0.3, "type": "field_factor"}
            ]},
            {"idx": 2, "label": "K1", "rules": [
                {"field": "close", "op": ">", "ref": "open", "type": "self"},
                {"field": "body_ratio", "op": ">=", "ref": 0.5, "type": "value"},
                {"field": "upper_shadow", "op": "<=", "ref_field": "body", "ref_factor": 0.3, "type": "field_factor"}
            ]}
        ]}, ensure_ascii=False),
        "memo": "连续三根阳线，实体逐步放大且上影线短，强势上涨延续"
    },
    {
        "rule_id": "C3-02", "name": "三只乌鸦", "name_en": "Three Black Crows",
        "category": "triple", "direction": "bearish", "strength": 6, "span_days": 3,
        "conditions": json.dumps({"candles": [
            {"idx": 0, "label": "K3（当前）", "rules": [
                {"field": "close", "op": "<", "ref": "open", "type": "self"},
                {"field": "body_ratio", "op": ">=", "ref": 0.5, "type": "value"},
                {"field": "lower_shadow", "op": "<=", "ref_field": "body", "ref_factor": 0.3, "type": "field_factor"},
                {"field": "close_descend", "op": "==", "ref": 1, "type": "value"}
            ]},
            {"idx": 1, "label": "K2", "rules": [
                {"field": "close", "op": "<", "ref": "open", "type": "self"},
                {"field": "body_ratio", "op": ">=", "ref": 0.5, "type": "value"},
                {"field": "lower_shadow", "op": "<=", "ref_field": "body", "ref_factor": 0.3, "type": "field_factor"}
            ]},
            {"idx": 2, "label": "K1", "rules": [
                {"field": "close", "op": "<", "ref": "open", "type": "self"},
                {"field": "body_ratio", "op": ">=", "ref": 0.5, "type": "value"},
                {"field": "lower_shadow", "op": "<=", "ref_field": "body", "ref_factor": 0.3, "type": "field_factor"}
            ]}
        ]}, ensure_ascii=False),
        "memo": "连续三根阴线，实体逐步放大且下影线短，强势下跌延续"
    },
    {
        "rule_id": "C3-03", "name": "早晨之星", "name_en": "Morning Star",
        "category": "triple", "direction": "bullish", "strength": 8, "span_days": 3,
        "conditions": json.dumps({"candles": [
            {"idx": 0, "label": "K3（当前）", "rules": [
                {"field": "close", "op": ">", "ref": "open", "type": "self"},
                {"field": "body_ratio", "op": ">=", "ref": 0.6, "type": "value"},
                {"field": "close", "op": ">=", "ref": "midpoint_2", "type": "prev"}
            ]},
            {"idx": 1, "label": "K2", "rules": [
                {"field": "body_ratio", "op": "<=", "ref": 0.15, "type": "value"}
            ]},
            {"idx": 2, "label": "K1", "rules": [
                {"field": "close", "op": "<", "ref": "open", "type": "self"},
                {"field": "body_ratio", "op": ">=", "ref": 0.6, "type": "value"}
            ]}
        ]}, ensure_ascii=False),
        "memo": "长阴→小实体（跳空低开）→长阳（收于K1实体50%以上），强烈见底反转"
    },
    {
        "rule_id": "C3-04", "name": "黄昏之星", "name_en": "Evening Star",
        "category": "triple", "direction": "bearish", "strength": 8, "span_days": 3,
        "conditions": json.dumps({"candles": [
            {"idx": 0, "label": "K3（当前）", "rules": [
                {"field": "close", "op": "<", "ref": "open", "type": "self"},
                {"field": "body_ratio", "op": ">=", "ref": 0.6, "type": "value"},
                {"field": "close", "op": "<=", "ref": "midpoint_2", "type": "prev"}
            ]},
            {"idx": 1, "label": "K2", "rules": [
                {"field": "body_ratio", "op": "<=", "ref": 0.15, "type": "value"}
            ]},
            {"idx": 2, "label": "K1", "rules": [
                {"field": "close", "op": ">", "ref": "open", "type": "self"},
                {"field": "body_ratio", "op": ">=", "ref": 0.6, "type": "value"}
            ]}
        ]}, ensure_ascii=False),
        "memo": "长阳→小实体（跳空高开）→长阴（收于K1实体50%以下），强烈见顶反转"
    },
    {
        "rule_id": "C3-05", "name": "三绿一红", "name_en": "Three Green One Red",
        "category": "triple", "direction": "bullish", "strength": 3, "span_days": 4,
        "conditions": json.dumps({"candles": [
            {"idx": 0, "label": "K4（当前）", "rules": [
                {"field": "close", "op": ">", "ref": "open", "type": "self"}
            ]},
            {"idx": 1, "label": "K3", "rules": [
                {"field": "close", "op": "<", "ref": "open", "type": "self"}
            ]},
            {"idx": 2, "label": "K2", "rules": [
                {"field": "close", "op": "<", "ref": "open", "type": "self"}
            ]},
            {"idx": 3, "label": "K1", "rules": [
                {"field": "close", "op": "<", "ref": "open", "type": "self"}
            ]}
        ]}, ensure_ascii=False),
        "memo": "连续3阴线后第4日阳线，止跌反弹信号（弱信号）"
    },
    {
        "rule_id": "C3-06", "name": "三红一绿", "name_en": "Three Red One Green",
        "category": "triple", "direction": "bearish", "strength": 3, "span_days": 4,
        "conditions": json.dumps({"candles": [
            {"idx": 0, "label": "K4（当前）", "rules": [
                {"field": "close", "op": "<", "ref": "open", "type": "self"}
            ]},
            {"idx": 1, "label": "K3", "rules": [
                {"field": "close", "op": ">", "ref": "open", "type": "self"}
            ]},
            {"idx": 2, "label": "K2", "rules": [
                {"field": "close", "op": ">", "ref": "open", "type": "self"}
            ]},
            {"idx": 3, "label": "K1", "rules": [
                {"field": "close", "op": ">", "ref": "open", "type": "self"}
            ]}
        ]}, ensure_ascii=False),
        "memo": "连续3阳线后第4日阴线，滞涨回落信号（弱信号）"
    },
    {
        "rule_id": "C3-07", "name": "两阳夹一阴", "name_en": "Bullish Sandwich",
        "category": "triple", "direction": "bullish", "strength": 5, "span_days": 3,
        "conditions": json.dumps({"candles": [
            {"idx": 0, "label": "K3（当前）", "rules": [
                {"field": "close", "op": ">", "ref": "open", "type": "self"},
                {"field": "close", "op": ">", "ref": "close_2", "type": "prev"}
            ]},
            {"idx": 1, "label": "K2", "rules": [
                {"field": "close", "op": "<", "ref": "open", "type": "self"},
                {"field": "close", "op": ">=", "ref": "low_2", "type": "prev"},
                {"field": "close", "op": "<=", "ref": "high_2", "type": "prev"}
            ]},
            {"idx": 2, "label": "K1", "rules": [
                {"field": "close", "op": ">", "ref": "open", "type": "self"}
            ]}
        ]}, ensure_ascii=False),
        "memo": "阳→阴（在前阳范围内）→阳（收盘超前阳），上涨中继"
    },
    {
        "rule_id": "C3-08", "name": "两阴夹一阳", "name_en": "Bearish Sandwich",
        "category": "triple", "direction": "bearish", "strength": 5, "span_days": 3,
        "conditions": json.dumps({"candles": [
            {"idx": 0, "label": "K3（当前）", "rules": [
                {"field": "close", "op": "<", "ref": "open", "type": "self"},
                {"field": "close", "op": "<", "ref": "close_2", "type": "prev"}
            ]},
            {"idx": 1, "label": "K2", "rules": [
                {"field": "close", "op": ">", "ref": "open", "type": "self"},
                {"field": "close", "op": ">=", "ref": "low_2", "type": "prev"},
                {"field": "close", "op": "<=", "ref": "high_2", "type": "prev"}
            ]},
            {"idx": 2, "label": "K1", "rules": [
                {"field": "close", "op": "<", "ref": "open", "type": "self"}
            ]}
        ]}, ensure_ascii=False),
        "memo": "阴→阳（在前阴范围内）→阴（收盘超前阴），下跌中继"
    },
    {
        "rule_id": "C3-09", "name": "启明星", "name_en": "Morning Doji Star",
        "category": "triple", "direction": "bullish", "strength": 9, "span_days": 3,
        "conditions": json.dumps({"candles": [
            {"idx": 0, "label": "K3（当前）", "rules": [
                {"field": "close", "op": ">", "ref": "open", "type": "self"},
                {"field": "body_ratio", "op": ">=", "ref": 0.6, "type": "value"},
                {"field": "close", "op": ">=", "ref": "midpoint_2", "type": "prev"}
            ]},
            {"idx": 1, "label": "K2", "rules": [
                {"field": "body_ratio", "op": "<=", "ref": 0.1, "type": "value"}
            ]},
            {"idx": 2, "label": "K1", "rules": [
                {"field": "close", "op": "<", "ref": "open", "type": "self"},
                {"field": "body_ratio", "op": ">=", "ref": 0.6, "type": "value"}
            ]}
        ]}, ensure_ascii=False),
        "memo": "长阴→十字星→长阳（收于K1中点以上），极强反转信号"
    },

    # ============ 第四类 · 多K线形态（6条） ============
    {
        "rule_id": "C4-01", "name": "上升三法", "name_en": "Rising Three Methods",
        "category": "multi", "direction": "bullish", "strength": 7, "span_days": 5,
        "conditions": json.dumps({"candles": [
            {"idx": 0, "label": "K5（当前）", "rules": [
                {"field": "close", "op": ">", "ref": "open", "type": "self"},
                {"field": "close", "op": ">", "ref": "close_4", "type": "prev"},
                {"field": "body_ratio", "op": ">=", "ref": 0.6, "type": "value"}
            ]},
            {"idx": 1, "label": "K4", "rules": [
                {"field": "close", "op": "<", "ref": "open", "type": "self"},
                {"field": "close", "op": ">=", "ref": "low_4", "type": "prev"},
                {"field": "high", "op": "<=", "ref": "high_4", "type": "prev"}
            ]},
            {"idx": 2, "label": "K3", "rules": [
                {"field": "close", "op": "<", "ref": "open", "type": "self"},
                {"field": "close", "op": ">=", "ref": "low_4", "type": "prev"}
            ]},
            {"idx": 3, "label": "K2", "rules": [
                {"field": "close", "op": "<", "ref": "open", "type": "self"},
                {"field": "close", "op": ">=", "ref": "low_4", "type": "prev"}
            ]},
            {"idx": 4, "label": "K1", "rules": [
                {"field": "close", "op": ">", "ref": "open", "type": "self"},
                {"field": "body_ratio", "op": ">=", "ref": 0.6, "type": "value"}
            ]}
        ]}, ensure_ascii=False),
        "memo": "长阳→三小阴（不破K1低点）→长阳（收盘超K1），上涨中继"
    },
    {
        "rule_id": "C4-02", "name": "下降三法", "name_en": "Falling Three Methods",
        "category": "multi", "direction": "bearish", "strength": 7, "span_days": 5,
        "conditions": json.dumps({"candles": [
            {"idx": 0, "label": "K5（当前）", "rules": [
                {"field": "close", "op": "<", "ref": "open", "type": "self"},
                {"field": "close", "op": "<", "ref": "close_4", "type": "prev"},
                {"field": "body_ratio", "op": ">=", "ref": 0.6, "type": "value"}
            ]},
            {"idx": 1, "label": "K4", "rules": [
                {"field": "close", "op": ">", "ref": "open", "type": "self"},
                {"field": "close", "op": "<=", "ref": "high_4", "type": "prev"},
                {"field": "low", "op": ">=", "ref": "low_4", "type": "prev"}
            ]},
            {"idx": 2, "label": "K3", "rules": [
                {"field": "close", "op": ">", "ref": "open", "type": "self"},
                {"field": "high", "op": "<=", "ref": "high_4", "type": "prev"}
            ]},
            {"idx": 3, "label": "K2", "rules": [
                {"field": "close", "op": ">", "ref": "open", "type": "self"},
                {"field": "high", "op": "<=", "ref": "high_4", "type": "prev"}
            ]},
            {"idx": 4, "label": "K1", "rules": [
                {"field": "close", "op": "<", "ref": "open", "type": "self"},
                {"field": "body_ratio", "op": ">=", "ref": 0.6, "type": "value"}
            ]}
        ]}, ensure_ascii=False),
        "memo": "长阴→三小阳（不破K1高点）→长阴（收盘超K1），下跌中继"
    },
    {
        "rule_id": "C4-03", "name": "塔形底", "name_en": "Tower Bottom",
        "category": "multi", "direction": "bullish", "strength": 8, "span_days": 9,
        "conditions": json.dumps({"candles": [{"idx": 0, "label": "塔形底（复合形态）", "rules": [
            {"field": "tower_bottom", "op": "==", "ref": 1, "type": "value"}
        ]}]}, ensure_ascii=False),
        "memo": "连续下跌→横盘→连续上涨，跨度≥9天，大级别反转"
    },
    {
        "rule_id": "C4-04", "name": "塔形顶", "name_en": "Tower Top",
        "category": "multi", "direction": "bearish", "strength": 8, "span_days": 9,
        "conditions": json.dumps({"candles": [{"idx": 0, "label": "塔形顶（复合形态）", "rules": [
            {"field": "tower_top", "op": "==", "ref": 1, "type": "value"}
        ]}]}, ensure_ascii=False),
        "memo": "连续上涨→横盘→连续下跌，跨度≥9天，大级别反转"
    },
    {
        "rule_id": "C4-05", "name": "双底（W底）", "name_en": "Double Bottom",
        "category": "multi", "direction": "bullish", "strength": 7, "span_days": 5,
        "conditions": json.dumps({"candles": [{"idx": 0, "label": "W底（复合形态）", "rules": [
            {"field": "double_bottom", "op": "==", "ref": 1, "type": "value"}
        ]}]}, ensure_ascii=False),
        "memo": "两个相近低点（差≤2%），中间反弹后第二底收阳突破颈线"
    },
    {
        "rule_id": "C4-06", "name": "双顶（M顶）", "name_en": "Double Top",
        "category": "multi", "direction": "bearish", "strength": 7, "span_days": 5,
        "conditions": json.dumps({"candles": [{"idx": 0, "label": "M顶（复合形态）", "rules": [
            {"field": "double_top", "op": "==", "ref": 1, "type": "value"}
        ]}]}, ensure_ascii=False),
        "memo": "两个相近高点（差≤2%），中间回调后第二顶收阴跌破颈线"
    },

    # ============ 第五类 · 特殊结构（6条） ============
    {
        "rule_id": "C5-01", "name": "向上跳空缺口", "name_en": "Up Gap",
        "category": "special", "direction": "bullish", "strength": 4, "span_days": 2,
        "conditions": json.dumps({"candles": [
            {"idx": 0, "label": "K2（当前）", "rules": [
                {"field": "gap_up", "op": "==", "ref": 1, "type": "value"},
                {"field": "gap_pct", "op": ">=", "ref": 0.003, "type": "value"}
            ]},
            {"idx": 1, "label": "K1", "rules": []}
        ]}, ensure_ascii=False),
        "memo": "当日最低价>前日最高价且跳空幅度≥0.3%，不回补为强势信号"
    },
    {
        "rule_id": "C5-02", "name": "向下跳空缺口", "name_en": "Down Gap",
        "category": "special", "direction": "bearish", "strength": 4, "span_days": 2,
        "conditions": json.dumps({"candles": [
            {"idx": 0, "label": "K2（当前）", "rules": [
                {"field": "gap_down", "op": "==", "ref": 1, "type": "value"},
                {"field": "gap_pct", "op": ">=", "ref": 0.003, "type": "value"}
            ]},
            {"idx": 1, "label": "K1", "rules": []}
        ]}, ensure_ascii=False),
        "memo": "当日最高价<前日最低价且跳空幅度≥0.3%，不回补为弱势信号"
    },
    {
        "rule_id": "C5-04", "name": "长下影探底", "name_en": "Long Lower Shadow",
        "category": "special", "direction": "bullish", "strength": 6, "span_days": 1,
        "conditions": json.dumps({"candles": [{"idx": 0, "label": "当前K线", "rules": [
            {"field": "lower_shadow", "op": ">=", "ref_field": "body", "ref_factor": 3, "type": "field_factor"},
            {"field": "upper_shadow", "op": "<=", "ref_field": "body", "ref_factor": 0.5, "type": "field_factor"},
            {"field": "close", "op": ">", "ref": "midpoint", "type": "self"}
        ]}]}, ensure_ascii=False),
        "memo": "下影线≥实体×3，上影线≤实体×0.5，收盘在顶部1/3，探底回升"
    },
    {
        "rule_id": "C5-05", "name": "长上影探顶", "name_en": "Long Upper Shadow",
        "category": "special", "direction": "bearish", "strength": 6, "span_days": 1,
        "conditions": json.dumps({"candles": [{"idx": 0, "label": "当前K线", "rules": [
            {"field": "upper_shadow", "op": ">=", "ref_field": "body", "ref_factor": 3, "type": "field_factor"},
            {"field": "lower_shadow", "op": "<=", "ref_field": "body", "ref_factor": 0.5, "type": "field_factor"},
            {"field": "close", "op": "<", "ref": "midpoint", "type": "self"}
        ]}]}, ensure_ascii=False),
        "memo": "上影线≥实体×3，下影线≤实体×0.5，收盘在底部1/3，冲高回落"
    },
    {
        "rule_id": "C5-06", "name": "阴阳孕线", "name_en": "Harami Cross",
        "category": "special", "direction": "neutral", "strength": 4, "span_days": 2,
        "conditions": json.dumps({"candles": [
            {"idx": 0, "label": "K2（当前）", "rules": [
                {"field": "body_ratio", "op": "<=", "ref": 0.2, "type": "value"},
                {"field": "high", "op": "<=", "ref": "high_1", "type": "prev"},
                {"field": "low", "op": ">=", "ref": "low_1", "type": "prev"}
            ]},
            {"idx": 1, "label": "K1", "rules": [
                {"field": "body_ratio", "op": ">=", "ref": 0.6, "type": "value"}
            ]}
        ]}, ensure_ascii=False),
        "memo": "长实体后小实体完全包含在前实体范围内，趋势可能反转"
    },
]


def main():
    """初始化：建表 + 写入33条规则（幂等）。"""
    print("=" * 50)
    print("K线形态规则初始化")
    print("=" * 50)

    # 建表
    init_pattern_rules_tables()
    print("  [OK] pattern_rules 表已就绪")

    # 检查是否已有数据
    existing = count_pattern_rules()
    if existing > 0:
        print(f"  [SKIP] 已有 {existing} 条规则，跳过初始化（如需重新初始化请清空表后重试）")
        return

    # 写入规则
    count = 0
    for rule in RULES:
        try:
            insert_pattern_rule(rule)
            count += 1
            print(f"  [INSERT] {rule['rule_id']} - {rule['name']}")
        except Exception as e:
            print(f"  [ERROR] {rule['rule_id']} 写入失败: {e}")

    print(f"\n  共写入 {count}/{len(RULES)} 条规则")


if __name__ == "__main__":
    main()
