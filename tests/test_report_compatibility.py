"""P1 [CRITICAL] 专家报告 JSON 兼容性处理测试。

覆盖：
  - 格式检测 (v1/v2/v3_flat/v3_array/v3_wrapped/unknown)
  - 字段名映射 & 模糊解析
  - v1/v2/v3 各版本的适配器转换
  - 驼峰字段、中文字段、缺失字段的兼容
  - 数组格式、外层包裹格式
  - 模糊回退适配器
  - 统一模型输出验证
  - import_report 完整链路
"""
import json, os, sys, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from report_compatibility import (
    detect_format,
    transform_report,
    normalize_to_v1,
    resolve_field_name,
    resolve_keys_in_dict,
    validate_report_structure,
    describe_format,
    UnifiedExpertReport,
    StockAnalysis,
    FIELD_NAME_ALIASES,
)


# ============================================================
# 测试数据：各格式的样本 JSON
# ============================================================

V1_SAMPLE = {
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
            "scores": {"technical": 6, "fundamental": 8, "news": 5, "sentiment": 5, "risk": 7},
            "phase1": {"technical": "技术面分析", "fundamental": "基本面分析",
                       "news": "新闻面分析", "sentiment": "情绪面分析"},
            "phase2": {"bull_args": [{"point": "股息率高", "weight": 9}],
                       "bear_args": [{"point": "宏观风险", "weight": 6}],
                       "verdict": "多头占优"},
            "phase4": {"aggressive_score": 8, "conservative_score": 5,
                       "neutral_score": 6, "final_risk_note": "风险适中"},
            "catalysts": ["中报窗口"],
            "risks": ["宏观下行"],
            "name": "兴业银行",
        }
    }
}

V2_SAMPLE = {
    "meta": {
        "date": "2026-05-23",
        "disclaimer": "仅供参考",
    },
    "stock": {
        "code": "601166",
        "name": "兴业银行",
        "price": 17.30,
        "pe_ttm": 5.5,
    },
    "module1_conclusion": {
        "user_question": "如何看待兴业银行？",
        "key_data_snapshot": [
            {"indicator": "PE", "value": "5.5", "direction": "up"},
        ],
        "roundtable_view": "全体专家认为当前估值偏低。",
        "core_viewpoints": [
            {"dimension": "估值", "judgment": "安全边际充足", "evidence": "PB=0.44"},
        ],
        "stance_distribution": {
            "votes": {"看多": 5, "观望": 1, "偏空": 1, "看空": 0},
        },
    },
    "module2_expert_opinions": [
        {
            "id": "signal-chief",
            "conclusion": "技术面走强",
            "key_findings": {
                "technical_confirmation": {"rsi6": 55, "macd": "金叉"},
            },
        },
        {
            "id": "fundamental-researcher",
            "conclusion": "基本面稳健",
            "key_findings": {
                "revenue_profit": {
                    "fy2024": {"revenue_yoy": "+5%", "np_yoy": "+3%"},
                    "fy2025": {"revenue_yoy": "+4%", "np_yoy": "+2%"},
                },
                "biggest_concern": {"issue": "利差收窄", "ar_to_profit": "影响-2%"},
            },
            "risk_honesty": "估值修复可能不及预期",
        },
    ],
    "module3_deep_thinking": {
        "host_notes": [{"num": 1, "title": "总结", "content": "建议低吸"}],
    },
    "module4_follow_up": {
        "key_variables_table": [],
        "invalidation_conditions": [],
    }
}

V3_FLAT_SAMPLE = {
    "date": "2026-06-01",
    "code": "600036",
    "name": "招商银行",
    "decision": "HOLD",
    "confidence": "中",
    "risk_level": "中",
    "position_pct": 15,
    "entry_price": 35.0,
    "target_price": 38.0,
    "stop_loss": 32.0,
    "scores": {"technical": 5, "fundamental": 6, "news": 5, "sentiment": 5, "risk": 5},
    "phase1": {"technical": "震荡", "fundamental": "稳健",
               "news": "中性", "sentiment": "观望"},
    "phase2": {"bull_args": [{"point": "估值合理", "weight": 6}],
               "bear_args": [{"point": "竞争加剧", "weight": 5}],
               "verdict": "中性"},
    "phase4": {"aggressive_score": 5, "conservative_score": 5,
               "neutral_score": 5, "final_risk_note": "中性"},
}

V3_ARRAY_SAMPLE = [
    {
        "code": "601166",
        "name": "兴业银行",
        "decision": "BUY",
        "entry_price": 17.3,
        "target_price": 19.5,
        "stop_loss": 16.0,
        "scores": {"technical": 6, "fundamental": 8, "news": 5, "sentiment": 5, "risk": 7},
        "phase1": {"technical": "技术面", "fundamental": "基本面",
                   "news": "新闻", "sentiment": "情绪"},
        "phase2": {"bull_args": [{"point": "好", "weight": 8}],
                   "bear_args": [{"point": "差", "weight": 4}],
                   "verdict": "看好"},
        "phase4": {"aggressive_score": 7, "conservative_score": 5,
                   "neutral_score": 6, "final_risk_note": "谨慎"},
    },
    {
        "code": "600036",
        "name": "招商银行",
        "decision": "HOLD",
        "scores": {"technical": 5, "fundamental": 5, "news": 5, "sentiment": 5, "risk": 5},
        "phase2": {"bull_args": [], "bear_args": [], "verdict": ""},
        "phase4": {"aggressive_score": 5, "conservative_score": 5,
                   "neutral_score": 5, "final_risk_note": ""},
    },
]

V3_WRAPPED_SAMPLE = {
    "success": True,
    "code": 0,
    "data": {
        "date": "2026-06-02",
        "stocks": {
            "601166": {
                "decision": "BUY",
                "confidence": "中",
                "risk_level": "低",
                "scores": {"technical": 6, "fundamental": 8, "news": 5, "sentiment": 5, "risk": 7},
                "phase1": {"technical": "好", "fundamental": "好", "news": "好", "sentiment": "好"},
                "phase2": {"bull_args": [], "bear_args": [], "verdict": ""},
                "phase4": {"aggressive_score": 6, "conservative_score": 6,
                           "neutral_score": 6, "final_risk_note": ""},
            }
        }
    }
}


# ============================================================
# 兼容性变体测试数据
# ============================================================

# 驼峰字段名
CAMEL_CASE_SAMPLE = {
    "reportDate": "2026-06-01",
    "stocks": {
        "601166": {
            "recommendation": "BUY",
            "conviction": "高",
            "riskRating": "低",
            "entryPrice": 17.3,
            "targetPrice": 19.5,
            "stopLoss": 16.0,
            "radarScores": {"technical": 6, "fundamental": 7, "news": 5, "sentiment": 5, "risk": 6},
            "analysis": {"tech": "技术好", "fundamentals": "基本面好",
                         "news": "新闻好", "sentiment": "情绪好"},
            "bullBear": {"bullishArguments": [{"point": "好", "weight": 8}],
                         "bearishArguments": [{"point": "差", "weight": 4}],
                         "conclusion": "看好"},
            "riskAssessment": {"aggressiveScore": 7, "conservativeScore": 5,
                               "neutralScore": 6, "riskNote": "适中"},
        }
    }
}

# 中文字段名
CHINESE_FIELD_SAMPLE = {
    "日期": "2026-06-01",
    "stocks": {
        "601166": {
            "结论": "BUY",
            "评分": {"技术面": 7, "基本面": 6, "新闻面": 5, "情绪面": 5, "风险": 6},
            "四面分析": {"技术面": "好", "基本面": "好", "新闻面": "好", "情绪面": "好"},
        }
    }
}

# 缺失部分字段的残缺 v1 (应能正常解析，默认值填充)
INCOMPLETE_V1 = {
    "date": "2026-06-01",
    "stocks": {
        "601166": {
            "decision": "BUY",
            "scores": {"technical": 6, "fundamental": 7, "news": 5, "sentiment": 5, "risk": 6},
            "phase2": {"bull_args": [], "bear_args": [], "verdict": ""},
            "phase4": {"aggressive_score": 6, "conservative_score": 6,
                       "neutral_score": 6, "final_risk_note": ""},
        }
    }
}

# 带有效包装的 data 格式（不含 success）
DATA_WRAPPER_SAMPLE = {
    "data": V1_SAMPLE,
}

# 只有评分和 phase2/4 外层包装的无 stocks dict
STOCK_KEY_DICT_SAMPLE = {
    "601166": {"decision": "BUY", "confidence": "中", "risk_level": "低",
               "scores": {"technical": 6, "fundamental": 7, "news": 5, "sentiment": 5, "risk": 6},
               "phase1": {"technical": "好", "fundamental": "好", "news": "好", "sentiment": "好"},
               "phase2": {"bull_args": [], "bear_args": [], "verdict": ""},
               "phase4": {"aggressive_score": 6, "conservative_score": 6,
                          "neutral_score": 6, "final_risk_note": ""},
               },
    "600036": {"decision": "HOLD",
               "scores": {"technical": 5, "fundamental": 5, "news": 5, "sentiment": 5, "risk": 5},
               "phase2": {"bull_args": [], "bear_args": [], "verdict": ""},
               "phase4": {"aggressive_score": 5, "conservative_score": 5,
                          "neutral_score": 5, "final_risk_note": ""},
               },
}


# ============================================================
# 测试套件
# ============================================================

class TestDetectFormat(unittest.TestCase):
    """格式检测测试。"""

    def test_detect_v1(self):
        v, feats = detect_format(V1_SAMPLE)
        self.assertEqual(v, "v1")
        self.assertTrue(feats["has_stocks"])
        self.assertTrue(feats["has_stock_code_decisions"])

    def test_detect_v2(self):
        v, feats = detect_format(V2_SAMPLE)
        self.assertEqual(v, "v2")
        self.assertTrue(feats["has_meta"])
        self.assertTrue(feats["has_module1"])
        self.assertTrue(feats["has_stock_info"])

    def test_detect_v3_flat(self):
        v, feats = detect_format(V3_FLAT_SAMPLE)
        self.assertEqual(v, "v3_flat")

    def test_detect_v3_array(self):
        v, feats = detect_format(V3_ARRAY_SAMPLE)
        self.assertEqual(v, "v3_array")

    def test_detect_v3_wrapped(self):
        v, feats = detect_format(V3_WRAPPED_SAMPLE)
        self.assertEqual(v, "v3_wrapped")

    def test_detect_camel_case(self):
        v, feats = detect_format(CAMEL_CASE_SAMPLE)
        # 驼峰字段通过模糊匹配仍能被识别为 v1
        self.assertEqual(v, "v1")
        self.assertTrue(feats["has_camel_case_fields"])

    def test_detect_chinese_fields(self):
        v, feats = detect_format(CHINESE_FIELD_SAMPLE)
        # 顶层有 stocks + 子项有 decision → v1
        self.assertIn(v, ("v1", "unknown"))

    def test_detect_data_wrapper(self):
        v, feats = detect_format(DATA_WRAPPER_SAMPLE)
        self.assertEqual(v, "v3_wrapped")

    def test_detect_empty(self):
        v, feats = detect_format({})
        self.assertEqual(v, "unknown")

    def test_detect_none(self):
        v, feats = detect_format(None)
        self.assertEqual(v, "unknown")


class TestFieldNameMapping(unittest.TestCase):
    """字段名映射测试。"""

    def test_resolve_standard(self):
        self.assertEqual(resolve_field_name("decision"), "decision")
        self.assertEqual(resolve_field_name("scores"), "scores")
        self.assertEqual(resolve_field_name("bull_args"), "bull_args")

    def test_resolve_aliases(self):
        self.assertEqual(resolve_field_name("recommendation"), "decision")
        self.assertEqual(resolve_field_name("conviction"), "confidence")
        self.assertEqual(resolve_field_name("riskRating"), "risk_level")
        self.assertEqual(resolve_field_name("symbol"), "code")
        self.assertEqual(resolve_field_name("stock_code"), "code")

    def test_resolve_chinese(self):
        self.assertEqual(resolve_field_name("结论"), "decision")
        self.assertEqual(resolve_field_name("评分"), "scores")
        self.assertEqual(resolve_field_name("风险"), "risks")

    def test_resolve_camel_to_snake(self):
        self.assertEqual(resolve_field_name("entryPrice"), "entry_price")
        self.assertEqual(resolve_field_name("stopLoss"), "stop_loss")
        self.assertEqual(resolve_field_name("targetPrice"), "target_price")

    def test_resolve_keys_in_dict(self):
        mapping = resolve_keys_in_dict({
            "recommendation": "BUY",
            "entryPrice": 17.3,
            "stockName": "兴业",
        })
        self.assertEqual(mapping.get("recommendation"), "decision")
        self.assertEqual(mapping.get("entryPrice"), "entry_price")

    def test_field_name_alias_completeness(self):
        """确保常用别名表覆盖了所有标准字段。"""
        standard_fields = ["decision", "confidence", "risk_level", "position_pct",
                           "entry_price", "target_price", "stop_loss",
                           "scores", "technical", "fundamental", "news", "sentiment",
                           "phase1", "phase2", "bull_args", "bear_args", "verdict",
                           "phase4", "aggressive_score", "conservative_score",
                           "neutral_score", "final_risk_note",
                           "catalysts", "risks",
                           "code", "name", "market", "date", "disclaimer"]
        for field in standard_fields:
            # 每种标准字段自身应在别名表中
            self.assertIn(field, FIELD_NAME_ALIASES.values(),
                          f"标准字段 '{field}' 缺少别名映射")


class TestTransformV1(unittest.TestCase):
    """v1 格式转换测试。"""

    def test_transform_v1_basic(self):
        report = transform_report(V1_SAMPLE)
        self.assertEqual(report.source_version, "v1")
        self.assertEqual(report.date, "2026-05-22")
        self.assertIn("601166", report.stocks)

    def test_transform_v1_stock_fields(self):
        report = transform_report(V1_SAMPLE)
        sa = report.stocks["601166"]
        self.assertEqual(sa.code, "601166")
        self.assertEqual(sa.name, "兴业银行")
        self.assertEqual(sa.decision, "BUY")
        self.assertEqual(sa.confidence, "中")
        self.assertEqual(sa.risk_level, "低")
        self.assertEqual(sa.entry_price, 17.30)
        self.assertEqual(sa.target_price, 19.50)
        self.assertEqual(sa.stop_loss, 16.00)
        self.assertEqual(sa.position_pct, 30)

    def test_transform_v1_scores(self):
        report = transform_report(V1_SAMPLE)
        sa = report.stocks["601166"]
        self.assertEqual(sa.score_technical, 6)
        self.assertEqual(sa.score_fundamental, 8)
        self.assertEqual(sa.score_news, 5)
        self.assertEqual(sa.score_sentiment, 5)
        self.assertEqual(sa.score_risk, 7)

    def test_transform_v1_phase1(self):
        report = transform_report(V1_SAMPLE)
        sa = report.stocks["601166"]
        self.assertEqual(sa.phase1_technical, "技术面分析")
        self.assertEqual(sa.phase1_fundamental, "基本面分析")

    def test_transform_v1_phase2(self):
        report = transform_report(V1_SAMPLE)
        sa = report.stocks["601166"]
        self.assertEqual(len(sa.bull_args), 1)
        self.assertEqual(sa.bull_args[0]["point"], "股息率高")
        self.assertEqual(sa.bear_args[0]["point"], "宏观风险")
        self.assertEqual(sa.verdict, "多头占优")

    def test_transform_v1_phase4(self):
        report = transform_report(V1_SAMPLE)
        sa = report.stocks["601166"]
        self.assertEqual(sa.aggressive_score, 8)
        self.assertEqual(sa.conservative_score, 5)
        self.assertEqual(sa.neutral_score, 6)

    def test_transform_v1_catalysts_risks(self):
        report = transform_report(V1_SAMPLE)
        sa = report.stocks["601166"]
        self.assertIn("中报窗口", sa.catalysts)
        self.assertIn("宏观下行", sa.risks)

    def test_transform_v1_incomplete_defaults(self):
        """缺失字段应使用默认值填充，不报错。"""
        report = transform_report(INCOMPLETE_V1)
        sa = report.stocks["601166"]
        self.assertEqual(sa.decision, "BUY")
        self.assertEqual(sa.confidence, "中")  # 默认
        self.assertEqual(sa.risk_level, "中")  # 默认
        self.assertIsNone(sa.entry_price)  # 无此字段
        self.assertEqual(sa.phase1_technical, "")  # 无此字段


class TestTransformV2(unittest.TestCase):
    """v2 圆桌格式转换测试。"""

    def test_transform_v2_basic(self):
        report = transform_report(V2_SAMPLE)
        self.assertEqual(report.source_version, "v2")
        self.assertEqual(report.date, "2026-05-23")
        self.assertIn("601166", report.stocks)

    def test_transform_v2_decision(self):
        report = transform_report(V2_SAMPLE)
        sa = report.stocks["601166"]
        # votes: 看多5 > 偏空1+看空0 → BUY
        self.assertEqual(sa.decision, "BUY")

    def test_transform_v2_scores(self):
        report = transform_report(V2_SAMPLE)
        sa = report.stocks["601166"]
        # 从 key_data_snapshot 和 stance 推导
        self.assertGreaterEqual(sa.score_technical, 1)
        self.assertGreaterEqual(sa.score_risk, 2)

    def test_transform_v2_bull_bear_args(self):
        report = transform_report(V2_SAMPLE)
        sa = report.stocks["601166"]
        self.assertGreaterEqual(len(sa.bull_args), 1)

    def test_transform_v2_phase1(self):
        report = transform_report(V2_SAMPLE)
        sa = report.stocks["601166"]
        # 从 expert opinions 填充
        self.assertIn("rsi6", sa.phase1_technical)
        self.assertIn("营收", sa.phase1_fundamental)

    def test_transform_v2_verdict(self):
        report = transform_report(V2_SAMPLE)
        sa = report.stocks["601166"]
        self.assertIn("建议低吸", sa.verdict)

    def test_transform_v2_risk_note(self):
        report = transform_report(V2_SAMPLE)
        sa = report.stocks["601166"]
        self.assertIn("利差收窄", sa.final_risk_note)

    def test_transform_v2_no_warnings(self):
        report = transform_report(V2_SAMPLE)
        self.assertEqual(len(report.warnings), 0)


class TestTransformV3Flat(unittest.TestCase):
    """v3 平面格式转换测试。"""

    def test_transform_v3_flat_basic(self):
        report = transform_report(V3_FLAT_SAMPLE)
        self.assertEqual(report.source_version, "v3_flat")
        self.assertEqual(report.date, "2026-06-01")
        self.assertIn("600036", report.stocks)

    def test_transform_v3_flat_fields(self):
        report = transform_report(V3_FLAT_SAMPLE)
        sa = report.stocks["600036"]
        self.assertEqual(sa.code, "600036")
        self.assertEqual(sa.name, "招商银行")
        self.assertEqual(sa.decision, "HOLD")
        self.assertEqual(sa.entry_price, 35.0)


class TestTransformV3Array(unittest.TestCase):
    """数组格式转换测试。"""

    def test_transform_array_basic(self):
        report = transform_report(V3_ARRAY_SAMPLE)
        self.assertEqual(report.source_version, "v3_array")
        self.assertIn("601166", report.stocks)
        self.assertIn("600036", report.stocks)

    def test_transform_array_multi_stock(self):
        report = transform_report(V3_ARRAY_SAMPLE)
        self.assertEqual(len(report.stocks), 2)
        self.assertEqual(report.stocks["601166"].decision, "BUY")
        self.assertEqual(report.stocks["600036"].decision, "HOLD")


class TestTransformV3Wrapped(unittest.TestCase):
    """外层包裹格式转换测试。"""

    def test_transform_wrapped_success_data(self):
        report = transform_report(V3_WRAPPED_SAMPLE)
        self.assertEqual(report.source_version, "v3_wrapped (v1)")
        self.assertIn("601166", report.stocks)

    def test_transform_data_wrapper(self):
        report = transform_report(DATA_WRAPPER_SAMPLE)
        self.assertEqual(report.source_version, "v3_wrapped (v1)")
        self.assertEqual(report.date, "2026-05-22")
        self.assertIn("601166", report.stocks)

    def test_transform_wrapper_no_data(self):
        report = transform_report({"status": "ok", "message": "no data"})
        # 没有 data/result/report → FuzzyFallback
        self.assertIn("fuzzy", report.source_version)


class TestTransformCamelCase(unittest.TestCase):
    """驼峰字段名兼容性测试。"""

    def test_transform_camel_case(self):
        report = transform_report(CAMEL_CASE_SAMPLE)
        sa = report.stocks["601166"]
        self.assertEqual(sa.decision, "BUY")
        self.assertEqual(sa.confidence, "高")
        self.assertEqual(sa.risk_level, "低")
        self.assertEqual(sa.entry_price, 17.3)

    def test_transform_camel_case_scores(self):
        report = transform_report(CAMEL_CASE_SAMPLE)
        sa = report.stocks["601166"]
        self.assertEqual(sa.score_technical, 6)
        self.assertEqual(sa.score_fundamental, 7)

    def test_transform_camel_case_args(self):
        report = transform_report(CAMEL_CASE_SAMPLE)
        sa = report.stocks["601166"]
        self.assertEqual(len(sa.bull_args), 1)
        self.assertEqual(sa.bull_args[0]["point"], "好")

    def test_transform_camel_case_phase4(self):
        report = transform_report(CAMEL_CASE_SAMPLE)
        sa = report.stocks["601166"]
        self.assertEqual(sa.aggressive_score, 7)
        self.assertEqual(sa.conservative_score, 5)

    def test_transform_camel_case_date(self):
        report = transform_report(CAMEL_CASE_SAMPLE)
        self.assertEqual(report.date, "2026-06-01")


class TestTransformChineseFields(unittest.TestCase):
    """中文字段名兼容性测试。"""

    def test_transform_chinese_fields(self):
        report = transform_report(CHINESE_FIELD_SAMPLE)
        self.assertIn("601166", report.stocks)

    def test_transform_chinese_decision(self):
        report = transform_report(CHINESE_FIELD_SAMPLE)
        sa = report.stocks["601166"]
        # "结论": "BUY" → resolve_field_name("结论") → "decision"
        self.assertEqual(sa.decision, "BUY")

    def test_transform_chinese_scores(self):
        report = transform_report(CHINESE_FIELD_SAMPLE)
        sa = report.stocks["601166"]
        # "评分": {"技术面": 7, ...}
        # 注意这里中文字段名在嵌套 map 中也会被解析
        self.assertEqual(sa.score_technical, 7)
        self.assertEqual(sa.score_fundamental, 6)


class TestFuzzyFallback(unittest.TestCase):
    """模糊回退适配器测试。"""

    def test_fallback_stock_key_dict(self):
        """以股票代码为 key 的 dict。"""
        report = transform_report(STOCK_KEY_DICT_SAMPLE)
        self.assertIn("fuzzy", report.source_version)
        self.assertIn("601166", report.stocks)
        self.assertIn("600036", report.stocks)

    def test_fallback_single_stock_dict(self):
        """单只股票，键名不是代码但内容有 decision。"""
        data = {"000001": {"decision": "BUY",
                           "scores": {"technical": 5, "fundamental": 5, "news": 5,
                                      "sentiment": 5, "risk": 5},
                           "phase2": {"bull_args": [], "bear_args": [], "verdict": ""},
                           "phase4": {"aggressive_score": 5, "conservative_score": 5,
                                      "neutral_score": 5, "final_risk_note": ""},
                           }}
        report = transform_report(data)
        self.assertIn("000001", report.stocks)

    def test_fallback_each_element_has_decision(self):
        """dict 中每个子项都有 decision 字段。"""
        data = {"sh600001": {"decision": "BUY",
                             "scores": {"technical": 5, "fundamental": 5, "news": 5,
                                        "sentiment": 5, "risk": 5},
                             "phase2": {"bull_args": [], "bear_args": [], "verdict": ""},
                             "phase4": {"aggressive_score": 5, "conservative_score": 5,
                                        "neutral_score": 5, "final_risk_note": ""},
                             },
                "sh600002": {"decision": "SELL",
                             "scores": {"technical": 3, "fundamental": 4, "news": 3,
                                        "sentiment": 3, "risk": 8},
                             "phase2": {"bull_args": [], "bear_args": [], "verdict": ""},
                             "phase4": {"aggressive_score": 3, "conservative_score": 7,
                                        "neutral_score": 5, "final_risk_note": ""},
                             }}
        report = transform_report(data)
        self.assertIn("sh600001", report.stocks)
        self.assertIn("sh600002", report.stocks)

    def test_fallback_empty_dict(self):
        report = transform_report({})
        self.assertEqual(len(report.stocks), 0)

    def test_fallback_empty_list(self):
        report = transform_report([])
        self.assertEqual(len(report.stocks), 0)


class TestUnifiedDataModel(unittest.TestCase):
    """统一数据模型测试。"""

    def test_to_v1_like(self):
        report = transform_report(V1_SAMPLE)
        v1 = report.to_v1_like()
        self.assertIn("date", v1)
        self.assertIn("stocks", v1)
        self.assertIn("601166", v1["stocks"])
        self.assertEqual(v1["stocks"]["601166"]["decision"], "BUY")
        self.assertIn("scores", v1["stocks"]["601166"])
        self.assertIn("phase2", v1["stocks"]["601166"])

    def test_to_v1_like_from_v2(self):
        report = transform_report(V2_SAMPLE)
        v1 = report.to_v1_like()
        self.assertIn("601166", v1["stocks"])
        self.assertEqual(v1["stocks"]["601166"]["decision"], "BUY")
        self.assertIn("scores", v1["stocks"]["601166"])

    def test_stock_analysis_defaults(self):
        sa = StockAnalysis(code="000001")
        self.assertEqual(sa.decision, "HOLD")
        self.assertEqual(sa.confidence, "中")
        self.assertEqual(sa.score_technical, 5)

    def test_back_to_v1_empty_stock(self):
        """空 StockAnalysis 转为 v1 兼容格式不会报错。"""
        sa = StockAnalysis(code="000001")
        report = UnifiedExpertReport(date="2026-01-01")
        report.stocks["000001"] = sa
        v1 = report.to_v1_like()
        self.assertEqual(v1["stocks"]["000001"]["decision"], "HOLD")
        self.assertEqual(v1["stocks"]["000001"]["confidence"], "中")


class TestValidateAndDescribe(unittest.TestCase):
    """验证与描述接口测试。"""

    def test_validate_ok(self):
        report = transform_report(V1_SAMPLE)
        issues = validate_report_structure(report)
        self.assertEqual(len(issues), 0)

    def test_validate_missing_date(self):
        report = UnifiedExpertReport(stocks={"601166": StockAnalysis(code="601166")})
        issues = validate_report_structure(report)
        self.assertTrue(any("缺少日期" in i for i in issues))

    def test_validate_missing_stocks(self):
        report = UnifiedExpertReport(date="2026-01-01")
        issues = validate_report_structure(report)
        self.assertTrue(any("未包含任何股票分析" in i for i in issues))

    def test_validate_bad_decision(self):
        sa = StockAnalysis(code="601166", decision="INVALID")
        report = UnifiedExpertReport(date="2026-01-01", stocks={"601166": sa})
        issues = validate_report_structure(report)
        self.assertTrue(any("INVALID" in i for i in issues))

    def test_describe_v1(self):
        desc = describe_format(V1_SAMPLE)
        self.assertIn("stocks", desc)

    def test_describe_v2(self):
        desc = describe_format(V2_SAMPLE)
        self.assertIn("圆桌", desc)

    def test_describe_flat(self):
        desc = describe_format(V3_FLAT_SAMPLE)
        self.assertIn("平面", desc)

    def test_describe_unknown(self):
        desc = describe_format({"foo": "bar"})
        self.assertIn("未知", desc)


class TestNormalizeToV1(unittest.TestCase):
    """normalize_to_v1 顶层接口测试。"""

    def test_normalize_v1_from_v1(self):
        result = normalize_to_v1(V1_SAMPLE)
        self.assertIn("stocks", result)
        self.assertEqual(result["stocks"]["601166"]["decision"], "BUY")

    def test_normalize_v1_from_v2(self):
        result = normalize_to_v1(V2_SAMPLE)
        self.assertIn("stocks", result)
        self.assertIn("601166", result["stocks"])

    def test_normalize_v1_from_flat(self):
        result = normalize_to_v1(V3_FLAT_SAMPLE)
        self.assertIn("stocks", result)
        self.assertIn("600036", result["stocks"])

    def test_normalize_v1_from_array(self):
        result = normalize_to_v1(V3_ARRAY_SAMPLE)
        self.assertIn("stocks", result)
        self.assertIn("601166", result["stocks"])
        self.assertIn("600036", result["stocks"])


class TestImportReportIntegration(unittest.TestCase):
    """import_report 完整链路测试（不依赖数据库）。"""

    def test_transform_v1_no_db(self):
        """验证 transform_report 流程，不依赖 DB。"""
        report = transform_report(V1_SAMPLE)
        self.assertGreater(len(report.stocks), 0)
        self.assertEqual(report.stocks["601166"].decision, "BUY")

    def test_transform_v2_no_db(self):
        report = transform_report(V2_SAMPLE)
        self.assertGreater(len(report.stocks), 0)
        self.assertEqual(report.stocks["601166"].decision, "BUY")

    def test_transform_array_no_db(self):
        report = transform_report(V3_ARRAY_SAMPLE)
        self.assertEqual(len(report.stocks), 2)
        self.assertEqual(report.stocks["601166"].decision, "BUY")
        self.assertEqual(report.stocks["600036"].decision, "HOLD")


if __name__ == "__main__":
    unittest.main(verbosity=2)
