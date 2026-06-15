"""专家分析报告 JSON 兼容性处理模块。

职责：
  1. 解析上传的 JSON 专家分析报告
  2. 自动识别格式版本（v1 旧版 / v2 圆桌 / v3 新版 / 变形）
  3. 适配字段名变化、层级嵌套调整、新增/缺失字段
  4. 归一化为统一内部数据模型 UnifiedExpertReport
  5. 兼容性处理逻辑确保不因格式差异而解析报错
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Callable


# ============================================================
# 1. 统一内部数据模型 (Unified Data Model)
# ============================================================

SCORE_KEYS = ["technical", "fundamental", "news", "sentiment", "risk"]
PHASE1_KEYS = ["technical", "fundamental", "news", "sentiment"]
PHASE4_KEYS = ["aggressive_score", "conservative_score", "neutral_score"]


@dataclass
class StockAnalysis:
    """单只股票的标准化内部表示，所有格式版本最终都归一化为此模型。"""
    code: str = ""
    name: str = ""
    market: str = "A股"

    # ── 决策信息 ──
    decision: str = "HOLD"        # BUY / HOLD / SELL
    confidence: str = "中"        # 高 / 中 / 低
    risk_level: str = "中"        # 高 / 中 / 低
    position_pct: float = 0
    entry_price: Optional[float] = None
    target_price: Optional[float] = None
    stop_loss: Optional[float] = None

    # ── 五维雷达评分 (0–10) ──
    score_technical: float = 5
    score_fundamental: float = 5
    score_news: float = 5
    score_sentiment: float = 5
    score_risk: float = 5

    # ── Phase1 四面分析文本 ──
    phase1_technical: str = ""
    phase1_fundamental: str = ""
    phase1_news: str = ""
    phase1_sentiment: str = ""

    # ── Phase2 多空辩论 ──
    bull_args: List[Dict[str, Any]] = field(default_factory=list)
    bear_args: List[Dict[str, Any]] = field(default_factory=list)
    verdict: str = ""

    # ── Phase4 风险评估 ──
    aggressive_score: float = 5
    conservative_score: float = 5
    neutral_score: float = 5
    final_risk_note: str = ""

    # ── 催化剂 & 风险事件 ──
    catalysts: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)

    # ── 原始数据快照 (调试/追溯用) ──
    raw_source: Dict[str, Any] = field(default_factory=dict)


@dataclass
class UnifiedExpertReport:
    """统一专家报告——标准化的顶层模型。"""
    date: str = ""
    source_version: str = "unknown"   # 检测到的版本标识
    detected_features: Dict[str, bool] = field(default_factory=dict)
    stocks: Dict[str, StockAnalysis] = field(default_factory=dict)
    disclaimer: str = ""
    raw_source: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)

    def to_v1_like(self) -> Dict[str, Any]:
        """将统一模型转回 v1 格式（兼容旧前端）。"""
        stocks_dict = {}
        for code, sa in self.stocks.items():
            stocks_dict[code] = {
                "name": sa.name,
                "market": sa.market,
                "decision": sa.decision,
                "confidence": sa.confidence,
                "risk_level": sa.risk_level,
                "position_pct": sa.position_pct,
                "entry_price": sa.entry_price,
                "target_price": sa.target_price,
                "stop_loss": sa.stop_loss,
                "scores": {k: getattr(sa, f"score_{k}") for k in SCORE_KEYS},
                "phase1": {k: getattr(sa, f"phase1_{k}") for k in PHASE1_KEYS},
                "phase2": {
                    "bull_args": sa.bull_args,
                    "bear_args": sa.bear_args,
                    "verdict": sa.verdict,
                },
                "phase4": {
                    "aggressive_score": sa.aggressive_score,
                    "conservative_score": sa.conservative_score,
                    "neutral_score": sa.neutral_score,
                    "final_risk_note": sa.final_risk_note,
                },
                "catalysts": sa.catalysts,
                "risks": sa.risks,
            }
        result: Dict[str, Any] = {
            "date": self.date,
            "source_version": self.source_version,
            "stocks": stocks_dict,
        }
        if self.disclaimer:
            result["disclaimer"] = self.disclaimer
        return result


# ============================================================
# 2. 字段名映射与模糊匹配
# ============================================================

# 规范化字段映射表 (可能出现的字段名 → 标准字段名)
FIELD_NAME_ALIASES: Dict[str, str] = {
    # 决策相关
    "decision": "decision",
    "recommendation": "decision",
    "rating": "decision",
    "opinion": "decision",
    "建议": "decision",
    "结论": "decision",
    # 置信度
    "confidence": "confidence",
    "conviction": "confidence",
    "certainty": "confidence",
    "确信度": "confidence",
    # 风险等级
    "risk_level": "risk_level",
    "risk": "risk_level",
    "riskRating": "risk_level",
    "risk_rating": "risk_level",
    "风险等级": "risk_level",
    # 仓位
    "position_pct": "position_pct",
    "position": "position_pct",
    "positionPercent": "position_pct",
    "仓位": "position_pct",
    # 价格
    "entry_price": "entry_price",
    "entryPrice": "entry_price",
    "buy_price": "entry_price",
    "buyPrice": "entry_price",
    "入场价": "entry_price",
    "target_price": "target_price",
    "targetPrice": "target_price",
    "priceTarget": "target_price",
    "目标价": "target_price",
    "stop_loss": "stop_loss",
    "stopLoss": "stop_loss",
    "stop_loss_price": "stop_loss",
    "止损价": "stop_loss",
    # 评分
    "scores": "scores",
    "ratings": "scores",
    "radar_scores": "scores",
    "scoring": "scores",
    "评分": "scores",
    "technical": "technical",
    "tech": "technical",
    "技术": "technical",
    "技术面": "technical",
    "fundamental": "fundamental",
    "fundamentals": "fundamental",
    "基本面": "fundamental",
    "news": "news",
    "新闻": "news",
    "新闻面": "news",
    "sentiment": "sentiment",
    "情绪": "sentiment",
    "情绪面": "sentiment",
    "risk_score": "risk",
    # Phase1 分析文本
    "phase1": "phase1",
    "analysis": "phase1",
    "sections": "phase1",
    "四面分析": "phase1",
    # Phase2
    "phase2": "phase2",
    "bull_bear": "phase2",
    "多空辩论": "phase2",
    "bull_args": "bull_args",
    "bullish": "bull_args",
    "bullish_arguments": "bull_args",
    "bullPoints": "bull_args",
    "多头": "bull_args",
    "bear_args": "bear_args",
    "bearish": "bear_args",
    "bearish_arguments": "bear_args",
    "bearPoints": "bear_args",
    "空头": "bear_args",
    "verdict": "verdict",
    "conclusion": "verdict",
    "裁决": "verdict",
    # Phase4
    "phase4": "phase4",
    "risk_assessment": "phase4",
    "风险评估": "phase4",
    "aggressive_score": "aggressive_score",
    "aggressiveScore": "aggressive_score",
    "激进": "aggressive_score",
    "conservative_score": "conservative_score",
    "conservativeScore": "conservative_score",
    "保守": "conservative_score",
    "neutral_score": "neutral_score",
    "neutralScore": "neutral_score",
    "neutral": "neutral_score",
    "中性": "neutral_score",
    "final_risk_note": "final_risk_note",
    "risk_note": "final_risk_note",
    "note": "final_risk_note",
    "总结": "final_risk_note",
    # 催化剂 & 风险
    "catalysts": "catalysts",
    "catalyst": "catalysts",
    "催化剂": "catalysts",
    "risks": "risks",
    "risk_events": "risks",
    "warnings": "risks",
    "风险": "risks",
    # 股票信息
    "code": "code",
    "stock_code": "code",
    "symbol": "code",
    "ticker": "code",
    "股票代码": "code",
    "name": "name",
    "stock_name": "name",
    "股票名称": "name",
    "market": "market",
    "exchange": "market",
    # 顶层
    "date": "date",
    "report_date": "date",
    "reportDate": "date",
    "日期": "date",
    "disclaimer": "disclaimer",
    "disclaimers": "disclaimer",
    "免责": "disclaimer",
}

# 命名风格转换：驼峰 → 下划线
_CAMEL_TO_SNAKE = re.compile(r"(?<!^)(?=[A-Z])")


def _camel_to_snake(name: str) -> str:
    return _CAMEL_TO_SNAKE.sub("_", name).lower()


def resolve_field_name(raw_name: str) -> str:
    """将任意字段名解析为标准字段名，支持别名表和驼峰转换。"""
    if not isinstance(raw_name, str):
        return raw_name
    normalized = raw_name.strip()
    # 精确匹配别名表
    if normalized in FIELD_NAME_ALIASES:
        return FIELD_NAME_ALIASES[normalized]
    # 尝试驼峰 → 下划线
    snake = _camel_to_snake(normalized)
    if snake != normalized and snake in FIELD_NAME_ALIASES:
        return FIELD_NAME_ALIASES[snake]
    # 尝试小写匹配
    low = normalized.lower()
    for alias, canonical in FIELD_NAME_ALIASES.items():
        if alias.lower() == low:
            return canonical
    return snake  # fallback


def resolve_keys_in_dict(d: Dict[str, Any]) -> Dict[str, str]:
    """返回 dict 中可解析字段名到标准名的映射。"""
    mapping: Dict[str, str] = {}
    for k in d:
        resolved = resolve_field_name(k)
        if resolved != k:
            mapping[k] = resolved
    return mapping


# ============================================================
# 3. 格式版本检测
# ============================================================

class FormatDetector:
    """基于特征的 JSON 格式版本检测器。

    检测策略：
      - 根据顶层/嵌套结构中的"特征指纹"判断版本
      - 支持模糊匹配（不要求 100% 精确结构）
      - 返回版本标识和检测到的特征列表
    """

    # 每个版本的检测规则：(版本名, [(检测路径, 预期类型或关键词), ...], 最小匹配数)
    VERSION_RULES: List[Tuple[str, List[Tuple[str, Any]], int]] = [
        ("v1", [
            ("stocks", dict),
            ("stocks.*.decision", str),
            ("stocks.*.scores", dict),
        ], 2),  # stocks + 至少一个子字段
        ("v2", [
            ("meta", dict),
            ("stock", dict),
            ("module1_conclusion", dict),
        ], 2),
        ("v2_minimal", [
            ("stock", dict),
            ("module1_conclusion", dict),
        ], 2),  # 无 meta 的简化版 v2
        ("v3_flat", [
            ("code", str),
            ("decision", str),
        ], 2),  # 平面结构：顶层直接包含 code + decision
        ("v3_array", [], 0),  # 数组格式：由 _detect_array 单独处理
        ("v3_wrapped", [
            ("data", dict),
        ], 1),  # 有 data 外层包装
    ]

    @classmethod
    def detect(cls, data: Any) -> Tuple[str, Dict[str, bool]]:
        """检测格式版本，返回 (version_id, features_dict)。

        返回的 features_dict 包含所有检测到的结构特征，
        方便后续转换器使用。
        """
        features: Dict[str, bool] = {
            "has_stocks": False,
            "has_stock_code_decisions": False,
            "has_meta": False,
            "has_stock_info": False,
            "has_module1": False,
            "has_module2": False,
            "has_module3": False,
            "has_module4": False,
            "is_array": False,
            "has_data_wrapper": False,
            "is_v1_like_scores": False,
            "has_roundtable_view": False,
            "has_camel_case_fields": False,
            "has_chinese_field_names": False,
        }

        if not isinstance(data, dict):
            if isinstance(data, list) and len(data) > 0:
                features["is_array"] = True
                return "v3_array", features
            return "unknown", features

        # 检测 stocks
        stocks = data.get("stocks")
        if isinstance(stocks, dict) and len(stocks) > 0:
            features["has_stocks"] = True
            sample_code = next(iter(stocks.keys()))
            sample = stocks[sample_code]
            if isinstance(sample, dict):
                has_decision = any(
                    resolve_field_name(k) == "decision" for k in sample
                )
                has_scores = any(
                    resolve_field_name(k) == "scores" for k in sample
                )
                features["has_stock_code_decisions"] = has_decision
                features["is_v1_like_scores"] = has_scores

        # v2 特征
        features["has_meta"] = isinstance(data.get("meta"), dict)
        features["has_stock_info"] = isinstance(data.get("stock"), dict)
        features["has_module1"] = isinstance(data.get("module1_conclusion"), dict)
        features["has_module2"] = isinstance(data.get("module2_expert_opinions"), list)
        features["has_module3"] = isinstance(data.get("module3_deep_thinking"), dict)
        features["has_module4"] = isinstance(data.get("module4_follow_up"), dict)
        features["has_roundtable_view"] = bool(
            data.get("module1_conclusion", {}).get("roundtable_view")
        )

        # 平面结构：顶层直接包含分析字段
        if isinstance(data.get("code"), str) and isinstance(data.get("decision"), str):
            features["has_stock_code_decisions"] = True

        # data 包装器
        features["has_data_wrapper"] = isinstance(data.get("data"), dict)

        # 命名风格检测（包括嵌套在 stocks 中的驼峰字段）
        camel_count = sum(
            1 for k in data if k != k.lower() and k[0].islower() and any(c.isupper() for c in k)
        )
        # 检查子层级中的驼峰字段
        stocks = data.get("stocks", {})
        if isinstance(stocks, dict):
            for sd in stocks.values():
                if isinstance(sd, dict):
                    camel_count += sum(
                        1 for k in sd if k != k.lower() and k[0].islower() and any(c.isupper() for c in k)
                    )
        features["has_camel_case_fields"] = camel_count >= 2

        chinese_count = sum(1 for k in data if re.search(r"[\u4e00-\u9fff]", k))
        features["has_chinese_field_names"] = chinese_count >= 2

        # 评分规则（v1/v2 规则）
        for version, rules, min_match in cls.VERSION_RULES:
            if version.startswith("v3"):
                continue
            match_count = 0
            for path, expected_type in rules:
                if cls._check_path(data, path, expected_type):
                    match_count += 1
            if match_count >= min_match:
                return version, features

        # v3 格式检测
        if features["is_array"]:
            return "v3_array", features
        if features["has_stock_code_decisions"] and not features["has_stocks"]:
            # 平面结构：顶层直接包含 code + decision，但不在 stocks 包裹中
            return "v3_flat", features
        if features["has_data_wrapper"]:
            return "v3_wrapped", features

        return "unknown", features

    @staticmethod
    def _get_by_path(data: Any, dotted_path: str) -> Any:
        """用点号路径访问嵌套 dict，支持 '*' 通配符。"""
        parts = dotted_path.split(".")
        current = data
        for part in parts:
            if part == "*":
                # 取任意一个子元素遍历
                if isinstance(current, dict):
                    if not current:
                        return None
                    # 取第一个非空子元素
                    for v in current.values():
                        if isinstance(v, dict):
                            current = v
                            break
                        elif isinstance(v, list) and v:
                            current = v[0]
                            break
                        else:
                            current = v
                            break
                    else:
                        return None
                elif isinstance(current, list) and current:
                    current = current[0]
                else:
                    return None
            elif isinstance(current, dict):
                current = _fuzzy_get(current, part)
            else:
                return None
        return current

    @classmethod
    def _check_path(cls, data: Any, path: str, expected_type: Any) -> bool:
        value = cls._get_by_path(data, path)
        if expected_type is None:
            return value is not None
        if expected_type is str:
            return isinstance(value, str) and len(value) > 0
        if isinstance(expected_type, type):
            return isinstance(value, expected_type)
        return value is not None


# ============================================================
# 4. 版本适配器基类
# ============================================================

class BaseAdapter:
    """版本适配器基类——每种格式版本实现自己的适配器。"""

    VERSION: str = "unknown"
    PRIORITY: int = 0  # 优先级，越高越优先匹配

    def detect(self, data: Any, features: Dict[str, bool]) -> bool:
        """判断此适配器是否能处理给定数据。"""
        raise NotImplementedError

    def transform(self, data: Any, features: Dict[str, bool]) -> UnifiedExpertReport:
        """将原始数据转换为 UnifiedExpertReport。"""
        raise NotImplementedError


# ============================================================
# 5. v1 适配器 (旧版 stocks 格式)
# ============================================================

DECISION_MAP = {"BUY": "BUY", "买入": "BUY", "买": "BUY", "看多": "BUY",
                "SELL": "SELL", "卖出": "SELL", "卖": "SELL", "看空": "SELL",
                "HOLD": "HOLD", "持有": "HOLD", "观望": "HOLD", "中性": "HOLD"}
CONFIDENCE_MAP = {"高": "高", "HIGH": "高", "high": "高",
                  "中": "中", "MEDIUM": "中", "medium": "中",
                  "低": "低", "LOW": "低", "low": "低"}
RISK_MAP = {"高": "高", "HIGH": "高", "high": "高",
            "中": "中", "MEDIUM": "中", "medium": "中",
            "低": "低", "LOW": "低", "low": "低"}


def _map_enum(value: Any, mapping: Dict[str, str], default: str) -> str:
    if not isinstance(value, str):
        return default
    return mapping.get(value.strip(), default)


def _safe_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.replace(",", "").replace("~", "").strip())
        except (ValueError, TypeError):
            return default
    return default


def _safe_int(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        try:
            return int(float(value))
        except (ValueError, TypeError):
            return default
    return default


def _clamp_score(value: Any, default: float = 5) -> float:
    f = _safe_float(value, default)
    return max(0.0, min(10.0, f))


def _fuzzy_get(d: Dict, key: str, default: Any = None) -> Any:
    """支持模糊字段名匹配的 dict.get()。"""
    if not isinstance(d, dict):
        return default
    if key in d:
        return d[key]
    # 在已解析的别名映射中查找
    resolved = resolve_keys_in_dict(d)
    for orig, canonical in resolved.items():
        if canonical == key:
            return d.get(orig, default)
    return default


def _fuzzy_get_typed(d: Dict, key: str, target_type: type, default: Any = None) -> Any:
    """模糊匹配并确保返回类型。"""
    val = _fuzzy_get(d, key)
    if isinstance(val, target_type):
        return val
    if val is None:
        return default
    if target_type is dict and isinstance(val, dict):
        return val
    if target_type is list and isinstance(val, list):
        return val
    return default


class V1Adapter(BaseAdapter):
    """适配 v1 旧版 stocks 格式（含模糊字段名匹配）。"""

    VERSION = "v1"
    PRIORITY = 100

    def detect(self, data: Any, features: Dict[str, bool]) -> bool:
        return features.get("has_stocks", False) and features.get("has_stock_code_decisions", False)

    def transform(self, data: Any, features: Dict[str, bool]) -> UnifiedExpertReport:
        report = UnifiedExpertReport(
            date=str(_fuzzy_get(data, "date", datetime.now().strftime("%Y-%m-%d"))),
            source_version="v1",
            detected_features=features,
            raw_source=data,
            disclaimer=str(data.get("disclaimer", "")),
        )

        stocks = data.get("stocks", {})
        if not isinstance(stocks, dict):
            report.warnings.append("v1: 'stocks' 字段不是 dict，跳过")
            return report

        for code, sd in stocks.items():
            if not isinstance(sd, dict):
                report.warnings.append(f"v1: 股票 '{code}' 的数据不是 dict，跳过")
                continue
            try:
                sa = self._parse_stock_entry(code, sd, data)
                report.stocks[code] = sa
            except Exception as e:
                report.warnings.append(f"v1: 股票 '{code}' 解析异常: {e}")

        return report

    def _parse_stock_entry(self, code: str, sd: Dict, raw: Any) -> StockAnalysis:
        sa = StockAnalysis(code=code, raw_source=sd)

        # ── 决策（使用模糊字段匹配） ──
        sa.decision = _map_enum(_fuzzy_get(sd, "decision"), DECISION_MAP, "HOLD")
        sa.confidence = _map_enum(_fuzzy_get(sd, "confidence"), CONFIDENCE_MAP, "中")
        sa.risk_level = _map_enum(_fuzzy_get(sd, "risk_level"), RISK_MAP, "中")
        sa.position_pct = _safe_float(_fuzzy_get(sd, "position_pct"), 0) or 0
        sa.entry_price = _safe_float(_fuzzy_get(sd, "entry_price"))
        sa.target_price = _safe_float(_fuzzy_get(sd, "target_price"))
        sa.stop_loss = _safe_float(_fuzzy_get(sd, "stop_loss"))

        # ── 评分（支持别名和中文键） ──
        scores = _fuzzy_get_typed(sd, "scores", dict, {})
        if isinstance(scores, dict):
            for k in SCORE_KEYS:
                val = _fuzzy_get(scores, k)
                setattr(sa, f"score_{k}", _clamp_score(val))

        # ── Phase1 ──
        phase1 = _fuzzy_get_typed(sd, "phase1", dict, {})
        if isinstance(phase1, dict):
            for k in PHASE1_KEYS:
                val = _fuzzy_get(phase1, k)
                setattr(sa, f"phase1_{k}", str(val) if val else "")

        # ── Phase2 ──
        phase2 = _fuzzy_get_typed(sd, "phase2", dict, {})
        if isinstance(phase2, dict):
            sa.bull_args = _fuzzy_get(phase2, "bull_args") or []
            sa.bear_args = _fuzzy_get(phase2, "bear_args") or []
            sa.verdict = str(_fuzzy_get(phase2, "verdict") or "")

        # ── Phase4 ──
        phase4 = _fuzzy_get_typed(sd, "phase4", dict, {})
        if isinstance(phase4, dict):
            sa.aggressive_score = _clamp_score(_fuzzy_get(phase4, "aggressive_score"), 5)
            sa.conservative_score = _clamp_score(_fuzzy_get(phase4, "conservative_score"), 5)
            sa.neutral_score = _clamp_score(_fuzzy_get(phase4, "neutral_score"), 5)
            sa.final_risk_note = str(_fuzzy_get(phase4, "final_risk_note") or "")

        # ── 催化剂 & 风险 ──
        sa.catalysts = [str(x) for x in (_fuzzy_get(sd, "catalysts") or []) if x]
        sa.risks = [str(x) for x in (_fuzzy_get(sd, "risks") or []) if x]

        # ── 名称 ──
        sa.name = str(_fuzzy_get(sd, "name") or "")
        sa.market = str(_fuzzy_get(sd, "market") or "A股")

        return sa


# ============================================================
# 6. v2 适配器 (圆桌讨论格式)
# ============================================================

class V2Adapter(BaseAdapter):
    """适配 v2 圆桌讨论格式。"""

    VERSION = "v2"
    PRIORITY = 90

    def detect(self, data: Any, features: Dict[str, bool]) -> bool:
        return (features.get("has_module1", False) and features.get("has_stock_info", False))

    def transform(self, data: Any, features: Dict[str, bool]) -> UnifiedExpertReport:
        meta = data.get("meta", {}) or {}
        stock_info = data.get("stock", {}) or {}
        module1 = data.get("module1_conclusion", {}) or {}
        module2 = data.get("module2_expert_opinions", []) or []
        module3 = data.get("module3_deep_thinking", {}) or {}
        module4 = data.get("module4_follow_up", {}) or {}

        report = UnifiedExpertReport(
            date=str(meta.get("date", stock_info.get("date", datetime.now().strftime("%Y-%m-%d")))),
            source_version="v2",
            detected_features=features,
            raw_source=data,
            disclaimer=str(meta.get("disclaimer", "") or ""),
        )

        code = str(stock_info.get("code", "") or "")
        if not code:
            report.warnings.append("v2: 未找到股票代码")
            return report

        try:
            sa = StockAnalysis(code=code, raw_source=data)
            self._fill_stock_info(sa, stock_info)
            self._fill_from_module1(sa, module1)
            self._fill_from_module2(sa, module2)
            self._fill_from_module3(sa, module3)
            self._fill_prices_from_module2(sa, module2)
            report.stocks[code] = sa
        except Exception as e:
            report.warnings.append(f"v2: 解析模块时异常: {e}")

        return report

    def _fill_stock_info(self, sa: StockAnalysis, info: Dict) -> None:
        sa.name = str(info.get("name", "") or "")
        sa.market = str(info.get("market", "A股") or "A股")
        sa.entry_price = _safe_float(info.get("price"))

    def _fill_from_module1(self, sa: StockAnalysis, m1: Dict) -> None:
        stance_dist = m1.get("stance_distribution", {}) or {}
        sa.decision = self._stance_to_decision(stance_dist)
        sa.verdict = str(m1.get("roundtable_view", "") or "")

        # 从核心观点填充 bull/bear args
        core_views = m1.get("core_viewpoints", []) or []
        if isinstance(core_views, list):
            bull_args, bear_args = self._classify_viewpoints(core_views)
            sa.bull_args = bull_args
            sa.bear_args = bear_args

        # 评分：从情绪和立场数据推导
        sa.score_technical = self._calc_technical_score(m1)
        sa.score_fundamental = self._calc_fundamental_score(m1)
        sa.score_news = self._calc_news_score(m1)
        sa.score_sentiment = self._calc_sentiment_score(stance_dist)
        sa.score_risk = self._calc_risk_score(stance_dist)

        # phase1：从 roundtable_view 填充（设为初始值，_fill_from_module2 会覆盖）
        rtv = str(m1.get("roundtable_view", "") or "")
        if rtv:
            sa.phase1_technical = rtv
            sa.phase1_fundamental = rtv
            sa.phase1_news = rtv
            sa.phase1_sentiment = rtv

    def _fill_from_module2(self, sa: StockAnalysis, m2: List) -> None:
        if not isinstance(m2, list):
            return

        # 从专家意见中提取详细分析文本（覆盖 module1 的兜底值）
        parts = {"technical": [], "fundamental": [], "news": [], "sentiment": []}
        risk_notes = []

        for expert in m2:
            eid = expert.get("id", "")
            findings = expert.get("key_findings", {}) or {}
            e_conclusion = str(expert.get("conclusion", "") or "")

            if eid == "signal-chief":
                tech = findings.get("technical_confirmation", {}) or {}
                lines = [f"{k}: {v}" for k, v in (tech or {}).items()]
                parts["technical"] = lines or [e_conclusion]
                sa.score_technical = max(sa.score_technical,
                                         self._rsi_score(tech.get("rsi6", 50)))
            elif eid == "fundamental-researcher":
                rev_profit = findings.get("revenue_profit", {}) or {}
                seg_lines = []
                if rev_profit:
                    fy24 = rev_profit.get("fy2024", {}) or {}
                    fy25 = rev_profit.get("fy2025", {}) or {}
                    seg_lines.append(
                        f"FY2024: 营收{fy24.get('revenue_yoy','')} 净利{fy24.get('np_yoy','')}"
                    )
                    seg_lines.append(
                        f"FY2025: 营收{fy25.get('revenue_yoy','')} 净利{fy25.get('np_yoy','')}"
                    )
                segments = findings.get("business_segments", {}) or {}
                for seg_name, seg_data in segments.items():
                    jdg = (seg_data or {}).get("judgment", "")
                    if jdg:
                        seg_lines.append(f"{seg_name}: {jdg}")
                parts["fundamental"] = seg_lines or [e_conclusion]
                sa.score_fundamental = max(sa.score_fundamental, 5)

                concern = findings.get("biggest_concern", {}) or {}
                if concern.get("issue"):
                    risk_notes.append(f"[财报] {concern.get('issue')}")
                sa.conservative_score = max(sa.conservative_score, 7)

            elif eid == "industry-strategist":
                parts["news"] = [e_conclusion]
            elif eid == "contrarian-investor":
                parts["sentiment"] = [e_conclusion]
                risk_honesty = expert.get("risk_honesty", "") or ""
                if risk_honesty:
                    risk_notes.append(f"[逆向] {risk_honesty}")
                sa.aggressive_score = max(sa.aggressive_score, 8)
            elif eid == "valuation-analyst":
                if findings.get("valuation_trap_risk"):
                    risk_notes.append(f"[估值] {findings.get('valuation_trap_risk')}")
                sa.conservative_score = max(sa.conservative_score, 7)

        # 用专家意见的详细信息覆盖 module1 的兜底值
        for key, lines in parts.items():
            if lines:
                combined = "\n".join(lines)
                setattr(sa, f"phase1_{key}", combined)

        if risk_notes:
            sa.final_risk_note = "\n".join(risk_notes)

        # 催化剂 & 风险
        catalysts, risks = self._extract_catalysts_risks(m2)
        sa.catalysts = catalysts
        sa.risks = risks

    def _fill_from_module3(self, sa: StockAnalysis, m3: Dict) -> None:
        """从 deep_thinking 模块提取裁决文本。"""
        if not isinstance(m3, dict):
            return
        host_notes = m3.get("host_notes", []) or []
        verdict_parts = []
        for item in host_notes:
            num = item.get("num", "")
            title = item.get("title", "")
            content = item.get("content", "")
            verdict_parts.append(f"[{num}] {title}: {content}")
        if verdict_parts:
            sa.verdict = "\n".join(verdict_parts)

    def _fill_prices_from_module2(self, sa: StockAnalysis, m2: List) -> None:
        """从专家意见推导目标价和止损价。"""
        if not isinstance(m2, list):
            return
        for expert in m2:
            eid = expert.get("id", "")
            findings = expert.get("key_findings", {}) or {}
            if eid == "shortterm-surfer" and sa.stop_loss is None:
                levels = findings.get("stop_loss_levels", []) or []
                for lv in levels:
                    price = lv.get("price", "")
                    pl = _safe_float(price)
                    if pl is not None:
                        sa.stop_loss = pl
                        break
            if eid == "contrarian-investor" and sa.target_price is None and sa.entry_price:
                sell_signals = findings.get("sell_signals", []) or []
                for sig in sell_signals:
                    if isinstance(sig, str) and "PE" in sig and "18" in sig:
                        pe_ttm = sa.raw_source.get("stock", {}).get("pe_ttm", 15) or 15
                        sa.target_price = round(sa.entry_price * 18 / pe_ttm, 2)
                        break
            if eid == "valuation-analyst" and sa.target_price is None:
                bands = findings.get("pe_bands", {}) or {}
                band_list = bands.get("bands", []) or []
                for b in band_list:
                    if b.get("percentile") == "50%":
                        sa.target_price = _safe_float(b.get("price"))
                        break

    # ── 辅助方法 ──

    @staticmethod
    def _stance_to_decision(stance_dist: Dict) -> str:
        if not isinstance(stance_dist, dict):
            return "HOLD"
        votes = stance_dist.get("votes", {}) or {}
        bullish = votes.get("看多", 0)
        bearish = votes.get("偏空", 0) + votes.get("看空", 0)
        neutral = votes.get("观望", 0)
        if bullish > bearish and bullish >= neutral:
            return "BUY"
        if bearish > bullish and bearish > neutral:
            return "SELL"
        return "HOLD"

    @staticmethod
    def _classify_viewpoints(core_views: List) -> Tuple[List, List]:
        """将核心观点分类为多头和空头论点。"""
        bull_keywords = ["安全边际", "机会", "分批建仓", "值得", "好", "支撑", "修复",
                         "方向对", "催化剂", "有底线", "会修复"]
        bear_keywords = ["弱", "风险", "不必", "陷阱", "无", "不猜", "最弱", "白搭",
                         "不突出", "不确定性", "警惕", "更优", "慢", "估值陷阱",
                         "EPS向下弯", "破净", "困难", "谨慎"]
        bull_args, bear_args = [], []
        for vp in core_views:
            dim = vp.get("dimension", "")
            judgment = vp.get("judgment", "")
            evidence = vp.get("evidence", "")
            point = f"[{dim}] {judgment}"
            bear_score = sum(2 for kw in bear_keywords if kw in judgment)
            bull_score = sum(2 for kw in bull_keywords if kw in judgment)
            if bear_score > bull_score:
                bear_args.append({"point": point, "weight": min(10, 4 + bear_score)})
            elif bull_score > bear_score:
                bull_args.append({"point": point, "weight": min(10, 4 + bull_score)})
            else:
                bear_args.append({"point": point, "weight": 3})
        return bull_args, bear_args

    @staticmethod
    def _rsi_score(rsi: Any) -> float:
        if not isinstance(rsi, (int, float)):
            return 5
        return max(1, min(10, round(rsi / 10, 1)))

    @staticmethod
    def _calc_technical_score(m1: Dict) -> float:
        snapshot = m1.get("key_data_snapshot", []) or []
        downs = sum(1 for s in snapshot if s.get("direction") == "down")
        ups = sum(1 for s in snapshot if s.get("direction") in ("up", "neutral"))
        total = downs + ups
        return max(1, min(10, round(ups / total * 5 + 2))) if total > 0 else 5

    @staticmethod
    def _calc_fundamental_score(m1: Dict) -> float:
        return 5

    @staticmethod
    def _calc_news_score(m1: Dict) -> float:
        return 5

    @staticmethod
    def _calc_sentiment_score(stance_dist: Dict) -> float:
        votes = (stance_dist or {}).get("votes", {}) or {}
        total = sum(votes.values()) or 1
        bullish_ratio = votes.get("看多", 0) / total
        return max(1, min(10, round(bullish_ratio * 7 + 1)))

    @staticmethod
    def _calc_risk_score(stance_dist: Dict) -> float:
        votes = (stance_dist or {}).get("votes", {}) or {}
        total = sum(votes.values()) or 1
        bearish_ratio = (votes.get("偏空", 0) + votes.get("看空", 0)) / total
        return max(2, min(10, round(bearish_ratio * 8 + 2)))

    @staticmethod
    def _extract_catalysts_risks(m2: List) -> Tuple[List[str], List[str]]:
        catalysts: List[str] = []
        risks: List[str] = []
        for expert in m2:
            triggers = expert.get("trigger_conditions", []) or []
            for t in triggers:
                if isinstance(t, str) and t not in catalysts:
                    catalysts.append(t)
            right_side = expert.get("right_side_signals", []) or []
            for t in right_side:
                if isinstance(t, str) and t not in catalysts:
                    catalysts.append(t)
            risk_text = expert.get("risk_honesty", "") or ""
            if risk_text:
                risks.append(risk_text[:120])
            signal_decay = expert.get("key_findings", {}).get("signal_decay", []) or []
            for d in signal_decay:
                if isinstance(d, str) and d not in risks:
                    risks.append(d)
        return catalysts[:12], risks[:12]


# ============================================================
# 7. v3 适配器 (平面/扁平格式 — 顶层直接包含分析字段)
# ============================================================

class V3FlatAdapter(BaseAdapter):
    """适配 v3 平面格式：顶层直接包含分析字段（code, decision, scores…）。"""

    VERSION = "v3_flat"
    PRIORITY = 50

    def detect(self, data: Any, features: Dict[str, bool]) -> bool:
        if not isinstance(data, dict):
            return False
        # 顶层有 code + decision + (scores || phase1)
        has_code = isinstance(data.get("code"), str)
        has_decision = isinstance(data.get("decision"), str)
        has_scores = isinstance(data.get("scores"), dict)
        has_phase1 = isinstance(data.get("phase1"), dict)
        # 确保不是 v1（没有 stocks 包裹，但有 stocks 时会误判）
        if features.get("has_stocks"):
            return False
        return has_code and has_decision and (has_scores or has_phase1)

    def transform(self, data: Any, features: Dict[str, bool]) -> UnifiedExpertReport:
        report = UnifiedExpertReport(
            date=str(data.get("date", datetime.now().strftime("%Y-%m-%d"))),
            source_version="v3_flat",
            detected_features=features,
            raw_source=data,
        )
        code = str(data.get("code", "") or "")
        if not code:
            report.warnings.append("v3_flat: 未找到股票代码")
            return report
        sa = V1Adapter()._parse_stock_entry(code, data, data)
        sa.name = str(data.get("name", "") or "") or sa.name
        report.stocks[code] = sa
        return report


# ============================================================
# 8. 数组格式适配器
# ============================================================

class V3ArrayAdapter(BaseAdapter):
    """适配数组格式：[{code, decision, scores, ...}, ...]。"""

    VERSION = "v3_array"
    PRIORITY = 40

    def detect(self, data: Any, features: Dict[str, bool]) -> bool:
        if not isinstance(data, list) or len(data) == 0:
            return False
        # 至少一个元素是 dict 且包含 code 和 decision
        for item in data:
            if isinstance(item, dict):
                raw_code = item.get("code") or item.get("stock_code") or item.get("symbol")
                raw_d = item.get("decision") or item.get("recommendation") or item.get("rating")
                if raw_code and raw_d:
                    return True
        return False

    def transform(self, data: Any, features: Dict[str, bool]) -> UnifiedExpertReport:
        report = UnifiedExpertReport(
            date=datetime.now().strftime("%Y-%m-%d"),
            source_version="v3_array",
            detected_features=features,
            raw_source=data,
        )
        for item in data:
            if not isinstance(item, dict):
                continue
            # 尝试在元素中找 code
            code = item.get("code") or item.get("stock_code") or item.get("symbol") or ""
            if not code:
                continue
            try:
                sa = V1Adapter()._parse_stock_entry(str(code), item, data)
                report.stocks[str(code)] = sa
            except Exception as e:
                report.warnings.append(f"v3_array: 解析条目 {code} 异常: {e}")
        return report


# ============================================================
# 9. 带外层包装的格式适配器 (data/report/success 包裹)
# ============================================================

class V3WrappedAdapter(BaseAdapter):
    """适配带外层包装的格式：{success, data: {stocks: ...}} 或 {data: [...], ...}。"""

    VERSION = "v3_wrapped"
    PRIORITY = 30

    def detect(self, data: Any, features: Dict[str, bool]) -> bool:
        if not isinstance(data, dict):
            return False
        # 有 data / result / report 包装
        wrapper = self._unwrap(data)
        return wrapper is not None

    def transform(self, data: Any, features: Dict[str, bool]) -> UnifiedExpertReport:
        wrapper = self._unwrap(data)
        if wrapper is None:
            return UnifiedExpertReport(
                source_version="v3_wrapped",
                detected_features=features,
                raw_source=data,
                warnings=["v3_wrapped: 无法识别外层包裹"],
            )
        # 递归解析内层数据
        inner_features = FormatDetector.detect(wrapper)[1]
        inner_report = transform_report(wrapper)
        inner_report.source_version = f"v3_wrapped ({inner_report.source_version})"
        inner_report.raw_source = data
        inner_report.detected_features = features
        if not inner_report.date:
            inner_report.date = str(data.get("date", ""))
        return inner_report

    @staticmethod
    def _unwrap(data: Dict) -> Optional[Any]:
        """尝试从外层包裹中提取真正的报告数据。"""
        for key in ("data", "result", "report", "response"):
            val = data.get(key)
            if isinstance(val, (dict, list)) and val:
                return val
        return None


# ============================================================
# 10. 通用模糊适配器 (fallback: 尝试从任意 dict 中提取)
# ============================================================

class FuzzyFallbackAdapter(BaseAdapter):
    """最后手段：尝试从任意 dict 或列表中提取专家分析数据。"""

    VERSION = "fuzzy_fallback"
    PRIORITY = 10

    def detect(self, data: Any, features: Dict[str, bool]) -> bool:
        return isinstance(data, (dict, list))

    def transform(self, data: Any, features: Dict[str, bool]) -> UnifiedExpertReport:
        report = UnifiedExpertReport(
            source_version="fuzzy_fallback",
            detected_features=features,
            raw_source=data,
        )
        try:
            if isinstance(data, dict):
                self._try_extract_from_dict(data, report)
            elif isinstance(data, list):
                self._try_extract_from_list(data, report)
        except Exception as e:
            report.warnings.append(f"fuzzy_fallback 解析异常: {e}")

        if not report.date:
            report.date = datetime.now().strftime("%Y-%m-%d")
        return report

    def _try_extract_from_dict(self, data: Dict, report: UnifiedExpertReport) -> None:
        resolved = resolve_keys_in_dict(data)

        # 尝试找 stocks
        for key, std_key in resolved.items():
            if std_key == "stocks" and isinstance(data[key], dict):
                v1_adapter = V1Adapter()
                # 检测是否符合 v1 样式
                sample = next(iter(data[key].values()), None)
                if isinstance(sample, dict) and any(
                    resolve_field_name(k) == "decision" for k in sample
                ):
                    sub = v1_adapter.transform({"stocks": data[key], "date": data.get("date", "")},
                                                {"has_stocks": True, "has_stock_code_decisions": True})
                    report.stocks.update(sub.stocks)
                    if sub.date:
                        report.date = sub.date
                    return

        # 检查是否每个子项都是股票样式
        stock_entries = {}
        for k, v in data.items():
            if isinstance(v, dict) and "decision" in v:
                resolved_k = resolve_field_name(k)
                if resolved_k not in ("meta", "stock", "module1_conclusion", "module2_expert_opinions"):
                    stock_entries[k] = v

        if stock_entries:
            for code, sd in stock_entries.items():
                try:
                    sa = V1Adapter()._parse_stock_entry(code, sd, data)
                    report.stocks[code] = sa
                except Exception:
                    pass

        # 处理中文键名的 dict
        for k, v in data.items():
            if re.search(r"[\u4e00-\u9fff]", k) and isinstance(v, dict):
                # 可能是 { "金融街": { decision: "BUY", ... } }
                if "decision" in v or "recommendation" in v:
                    try:
                        sa = V1Adapter()._parse_stock_entry(k, v, data)
                        report.stocks[k] = sa
                    except Exception:
                        pass

    @staticmethod
    def _try_extract_from_list(data: List, report: UnifiedExpertReport) -> None:
        for item in data:
            if not isinstance(item, dict):
                continue
            code = item.get("code") or item.get("stock_code") or item.get("symbol") or ""
            if code and ("decision" in item or "recommendation" in item):
                try:
                    sa = V1Adapter()._parse_stock_entry(str(code), item, data)
                    report.stocks[str(code)] = sa
                except Exception:
                    pass


# ============================================================
# 11. 主调度器
# ============================================================

# 所有适配器列表（按优先级降序）
_ADAPTERS: List[BaseAdapter] = sorted([
    V1Adapter(),
    V2Adapter(),
    V3FlatAdapter(),
    V3ArrayAdapter(),
    V3WrappedAdapter(),
    FuzzyFallbackAdapter(),
], key=lambda a: -a.PRIORITY)


def detect_format(data: Any) -> Tuple[str, Dict[str, bool]]:
    """检测输入数据的格式版本，返回 (version_id, features)。"""
    return FormatDetector.detect(data)


def transform_report(data: Any, strict: bool = False) -> UnifiedExpertReport:
    """将任意格式的输入数据转换为 UnifiedExpertReport。

    Args:
        data: 输入的 JSON 数据（dict 或 list）
        strict: 若为 True，无法识别时抛出异常；否则使用 FuzzyFallbackAdapter

    Returns:
        UnifiedExpertReport 统一报告对象

    Raises:
        ValueError: 当 strict=True 且无法识别格式时
    """
    version, features = FormatDetector.detect(data)

    # 选择第一个能处理的适配器
    for adapter in _ADAPTERS:
        if adapter.detect(data, features):
            result = adapter.transform(data, features)
            result.detected_features = features
            return result

    if strict:
        raise ValueError(f"无法识别报告格式。检测特征: {features}")

    # Fallback: 使用 FuzzyFallbackAdapter
    result = FuzzyFallbackAdapter().transform(data, features)
    result.detected_features = features
    result.warnings.append("模糊匹配模式：结果可能不完整，建议验证")
    return result


def normalize_to_v1(data: Any) -> Dict[str, Any]:
    """将任意格式归一化为 v1 兼容格式（用于兼容旧前端/数据存储）。"""
    report = transform_report(data)
    return report.to_v1_like()


# ============================================================
# 12. 批量验证 & 报告接口
# ============================================================

def validate_report_structure(report: UnifiedExpertReport) -> List[str]:
    """验证统一报告的完整性，返回问题列表（非空表示有问题）。"""
    issues: List[str] = []
    if not report.date:
        issues.append("报告缺少日期")
    if not report.stocks:
        issues.append("报告未包含任何股票分析")
    for code, sa in report.stocks.items():
        if not code or len(str(code)) < 4:
            issues.append(f"股票代码 '{code}' 可能不合法")
        if sa.decision not in ("BUY", "HOLD", "SELL"):
            issues.append(f"股票 {code}: decision '{sa.decision}' 不是 BUY/HOLD/SELL")
        # 检查必填字段
        if not sa.phase1_technical and not sa.phase1_fundamental:
            issues.append(f"股票 {code}: 缺少 phase1 分析文本")
    return issues


def describe_format(data: Any) -> str:
    """人性化的格式描述。"""
    v, features = FormatDetector.detect(data)
    desc = {
        "v1": "旧版 stocks 格式",
        "v2": "圆桌讨论格式",
        "v2_minimal": "简化圆桌格式",
        "v3_flat": "平面结构格式",
        "v3_array": "数组格式",
        "v3_wrapped": "外层包裹格式",
        "unknown": "未知格式",
    }.get(v, v)
    extra = []
    if features.get("has_camel_case_fields"):
        extra.append("驼峰字段")
    if features.get("has_chinese_field_names"):
        extra.append("中文字段")
    if features.get("is_v1_like_scores"):
        extra.append("v1 风格评分")
    detail = f"{'/' .join(extra)}" if extra else ""
    return f"{desc} ({detail})" if detail else desc
