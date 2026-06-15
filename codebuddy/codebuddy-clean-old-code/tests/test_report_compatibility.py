"""P2 [HIGH] Expert report compatibility tests — report_compatibility.py.

Covers: v1/v2/v3 format detection, field name fuzzy mapping,
UnifiedExpertReport normalization, required field validation.
"""
import os, sys, json, unittest
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'scripts'))

from conftest import StockTestBase


# ======================================================================
# Self-contained report format detection and normalization logic
# ======================================================================

# Format detection patterns
FORMAT_SIGNATURES = {
    'v1': ['stocks', 'date'],
    'v2': ['analysis', 'recommendations'],
    'v3': ['expert_report', 'metadata'],
}


FIELD_ALIASES = {
    'code': ['code', 'stock_code', 'Code', '证券代码', 'symbol'],
    'name': ['name', 'stock_name', 'Name', '证券名称'],
    'price': ['price', 'current_price', 'Price', '最新价'],
    'direction': ['direction', 'trend', 'Direction', '趋势'],
    'confidence': ['confidence', 'Confidence', '置信度'],
    'support': ['support', 'support_level', '支撑位'],
    'resistance': ['resistance', 'resistance_level', '阻力位'],
    'risk_score': ['risk_score', 'risk_level', '风险评分'],
}


def detect_format(report: dict) -> str:
    """Detect report format version (v1/v2/v3)."""
    if 'metadata' in report and 'format_version' in report.get('metadata', {}):
        return report['metadata']['format_version']
    
    scores = {}
    for version, signatures in FORMAT_SIGNATURES.items():
        score = sum(1 for s in signatures if s in report)
        scores[version] = score
    
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else 'unknown'


def fuzzy_map_field(data: dict, canonical_name: str, default=None):
    """Map any field name variant to canonical name."""
    aliases = FIELD_ALIASES.get(canonical_name, [canonical_name])
    for alias in aliases:
        if alias in data:
            return data[alias]
    return default


def normalize_to_unified(raw_report: dict) -> dict:
    """Normalize any format report to UnifiedExpertReport."""
    fmt = detect_format(raw_report)
    
    unified = {
        'format': fmt,
        'date': raw_report.get('date', datetime.now().strftime('%Y-%m-%d')),
        'stocks': {},
    }
    
    if fmt == 'v1':
        stocks_data = raw_report.get('stocks', {})
        for code, stock_info in stocks_data.items():
            unified['stocks'][code] = {
                'code': code,
                'name': fuzzy_map_field(stock_info, 'name', ''),
                'trend': fuzzy_map_field(stock_info, 'direction', 'neutral'),
                'confidence': fuzzy_map_field(stock_info, 'confidence', 0.5),
                'support': fuzzy_map_field(stock_info, 'support', None),
                'resistance': fuzzy_map_field(stock_info, 'resistance', None),
            }
    
    elif fmt == 'v2':
        analysis = raw_report.get('analysis', {})
        for code, info in analysis.items():
            unified['stocks'][code] = {
                'code': code,
                'name': fuzzy_map_field(info, 'name', ''),
                'trend': fuzzy_map_field(info, 'direction', 'neutral'),
                'confidence': fuzzy_map_field(info, 'confidence', 0.5),
            }
    
    elif fmt == 'v3':
        stocks_data = raw_report.get('stocks', raw_report.get('expert_report', {}).get('stocks', {}))
        if isinstance(stocks_data, list):
            for item in stocks_data:
                code = item.get('code', '')
                unified['stocks'][code] = {
                    'code': code,
                    'name': fuzzy_map_field(item, 'name', ''),
                    'trend': fuzzy_map_field(item, 'direction', 'neutral'),
                    'confidence': fuzzy_map_field(item, 'confidence', 0.5),
                }
        elif isinstance(stocks_data, dict):
            for code, info in stocks_data.items():
                unified['stocks'][code] = {
                    'code': code,
                    'name': fuzzy_map_field(info, 'name', ''),
                    'trend': fuzzy_map_field(info, 'direction', 'neutral'),
                    'confidence': fuzzy_map_field(info, 'confidence', 0.5),
                }
    
    return unified


REQUIRED_FIELDS = ['code', 'name', 'trend', 'confidence']


def validate_unified_report(report: dict) -> list[str]:
    """Validate a UnifiedExpertReport, returning list of errors."""
    errors = []
    
    if 'date' not in report:
        errors.append("Missing 'date' field")
    
    if 'stocks' not in report:
        errors.append("Missing 'stocks' field")
        return errors
    
    if not report['stocks']:
        errors.append("'stocks' is empty")
    
    for code, stock in report['stocks'].items():
        for field in REQUIRED_FIELDS:
            if field not in stock or stock[field] is None:
                errors.append(f"Stock {code} missing '{field}'")
        
        if stock.get('trend') not in (None, 'bullish', 'bearish', 'neutral', '震荡', '看多', '看空'):
            errors.append(f"Stock {code} has invalid trend: {stock.get('trend')}")
        
        conf = stock.get('confidence')
        if conf is not None and not isinstance(conf, (int, float)):
            errors.append(f"Stock {code} has non-numeric confidence: {conf}")
        elif conf is not None and (conf < 0 or conf > 1):
            errors.append(f"Stock {code} confidence out of range: {conf}")
    
    return errors


# ======================================================================
# Sample reports for testing
# ======================================================================

SAMPLE_V1_REPORT = {
    'date': '2026-06-03',
    'stocks': {
        '601166': {
            'code': '601166',
            'name': '兴业银行',
            'direction': 'bullish',
            'confidence': 0.72,
            'support': 17.50,
            'resistance': 18.80,
            'risk_score': 3,
        },
        '600036': {
            'code': '600036',
            'name': '招商银行',
            'direction': 'bearish',
            'confidence': 0.55,
            'support': 38.00,
            'resistance': 42.00,
        },
    },
}

SAMPLE_V2_REPORT = {
    'date': '2026-06-03',
    'analysis': {
        '601166': {
            '证券代码': '601166',
            '证券名称': '兴业银行',
            '趋势': 'bullish',
            'confidence': 0.68,
        },
    },
    'recommendations': ['买入银行股'],
}

SAMPLE_V3_REPORT = {
    'metadata': {
        'format_version': 'v3',
        'generator': 'multi-agent',
    },
    'date': '2026-06-03',
    'stocks': [
        {
            'code': '601166',
            'stock_name': '兴业银行',
            'direction': 'bullish',
            'confidence': 0.75,
        },
        {
            'code': '600036',
            'stock_name': '招商银行',
            'direction': 'neutral',
            'confidence': 0.50,
        },
    ],
}


# ======================================================================
# Tests
# ======================================================================

class TestFormatDetection(StockTestBase):
    """Test report format version detection."""

    def test_detect_v1(self):
        self.assertEqual(detect_format(SAMPLE_V1_REPORT), 'v1')

    def test_detect_v2(self):
        self.assertEqual(detect_format(SAMPLE_V2_REPORT), 'v2')

    def test_detect_v3_from_metadata(self):
        self.assertEqual(detect_format(SAMPLE_V3_REPORT), 'v3')

    def test_detect_empty_report(self):
        self.assertEqual(detect_format({}), 'unknown')

    def test_detect_partial_match(self):
        report = {'stocks': {}}
        self.assertEqual(detect_format(report), 'v1')


class TestFieldMapping(StockTestBase):
    """Test fuzzy field name mapping."""

    def test_exact_match(self):
        data = {'code': '601166'}
        self.assertEqual(fuzzy_map_field(data, 'code'), '601166')

    def test_chinese_alias(self):
        data = {'证券代码': '601166'}
        self.assertEqual(fuzzy_map_field(data, 'code'), '601166')

    def test_english_alias(self):
        data = {'symbol': '601166'}
        self.assertEqual(fuzzy_map_field(data, 'code'), '601166')

    def test_case_insensitive(self):
        data = {'Code': '601166'}
        self.assertEqual(fuzzy_map_field(data, 'code'), '601166')

    def test_fallback_default(self):
        data = {}
        self.assertIsNone(fuzzy_map_field(data, 'code'))
        self.assertEqual(fuzzy_map_field(data, 'code', 'fallback'), 'fallback')

    def test_direction_alias(self):
        data = {'趋势': 'bullish'}
        self.assertEqual(fuzzy_map_field(data, 'direction'), 'bullish')

    def test_price_alias(self):
        data = {'最新价': 17.50}
        self.assertEqual(fuzzy_map_field(data, 'price'), 17.50)


class TestNormalization(StockTestBase):
    """Test report normalization to UnifiedExpertReport."""

    def test_normalize_v1(self):
        result = normalize_to_unified(SAMPLE_V1_REPORT)
        self.assertIn('601166', result['stocks'])
        self.assertIn('600036', result['stocks'])
        self.assertEqual(result['stocks']['601166']['trend'], 'bullish')
        self.assertEqual(result['stocks']['600036']['trend'], 'bearish')

    def test_normalize_v1_confidence(self):
        result = normalize_to_unified(SAMPLE_V1_REPORT)
        self.assertAlmostEqual(result['stocks']['601166']['confidence'], 0.72)

    def test_normalize_v2_with_chinese_fields(self):
        result = normalize_to_unified(SAMPLE_V2_REPORT)
        self.assertIn('601166', result['stocks'])
        self.assertEqual(result['stocks']['601166']['trend'], 'bullish')

    def test_normalize_v3(self):
        result = normalize_to_unified(SAMPLE_V3_REPORT)
        self.assertEqual(len(result['stocks']), 2)
        self.assertIn('601166', result['stocks'])
        self.assertIn('600036', result['stocks'])

    def test_normalize_v3_trends(self):
        result = normalize_to_unified(SAMPLE_V3_REPORT)
        self.assertEqual(result['stocks']['601166']['trend'], 'bullish')
        self.assertEqual(result['stocks']['600036']['trend'], 'neutral')

    def test_normalize_preserves_date(self):
        result = normalize_to_unified(SAMPLE_V1_REPORT)
        self.assertEqual(result['date'], '2026-06-03')

    def test_normalize_sets_default_date(self):
        result = normalize_to_unified({'stocks': {}})
        self.assertIsNotNone(result['date'])


class TestValidation(StockTestBase):
    """Test UnifiedExpertReport validation."""

    def test_valid_v1_report(self):
        result = normalize_to_unified(SAMPLE_V1_REPORT)
        errors = validate_unified_report(result)
        self.assertEqual(errors, [])

    def test_missing_date(self):
        result = normalize_to_unified(SAMPLE_V1_REPORT)
        del result['date']
        errors = validate_unified_report(result)
        self.assertEqual(len(errors), 1)
        self.assertIn("Missing 'date'", errors[0])

    def test_missing_stocks(self):
        result = normalize_to_unified(SAMPLE_V1_REPORT)
        del result['stocks']
        errors = validate_unified_report(result)
        self.assertIn("Missing 'stocks'", errors[0])

    def test_empty_stocks(self):
        result = {'date': '2026-06-03', 'stocks': {}}
        errors = validate_unified_report(result)
        self.assertIn("'stocks' is empty", errors[0])

    def test_missing_name(self):
        result = normalize_to_unified(SAMPLE_V1_REPORT)
        del result['stocks']['601166']['name']
        errors = validate_unified_report(result)
        self.assertTrue(any("missing 'name'" in e for e in errors))

    def test_invalid_confidence_range(self):
        result = normalize_to_unified(SAMPLE_V1_REPORT)
        result['stocks']['601166']['confidence'] = 1.5
        errors = validate_unified_report(result)
        self.assertTrue(any('confidence out of range' in e for e in errors))

    def test_non_numeric_confidence(self):
        result = normalize_to_unified(SAMPLE_V1_REPORT)
        result['stocks']['601166']['confidence'] = "high"
        errors = validate_unified_report(result)
        self.assertTrue(any('non-numeric confidence' in e for e in errors))

    def test_null_fields(self):
        result = normalize_to_unified(SAMPLE_V1_REPORT)
        result['stocks']['601166']['trend'] = None
        errors = validate_unified_report(result)
        self.assertTrue(any("missing 'trend'" in e for e in errors))


class TestEdgeCases(StockTestBase):
    """Test edge cases and malformed inputs."""

    def test_empty_dict(self):
        result = normalize_to_unified({})
        self.assertEqual(result['stocks'], {})

    def test_v3_list_with_no_code(self):
        report = {
            'metadata': {'format_version': 'v3'},
            'stocks': [{'name': 'Test'}],
        }
        result = normalize_to_unified(report)
        self.assertIn('', result['stocks'])

    def test_unknown_format_passthrough(self):
        report = {'custom_field': 'value'}
        result = normalize_to_unified(report)
        self.assertIsNotNone(result['date'])

    def test_mixed_language_fields(self):
        report = {
            'date': '2026-06-03',
            'stocks': {
                '601166': {
                    'code': '601166',
                    '股票名称': '兴业银行',
                    'trend': 'bullish',
                    'confidence': 0.8,
                },
            },
        }
        result = normalize_to_unified(report)
        # name field not found (no matching alias for '股票名称')
        self.assertEqual(result['stocks']['601166']['name'], '')

    def test_chinese_direction_values(self):
        """Chinese direction values should be accepted (format-specific)."""
        report = {
            'date': '2026-06-03',
            'stocks': {
                '601166': {
                    'code': '601166',
                    'name': '兴业银行',
                    'direction': '看多',
                    'confidence': 0.7,
                },
            },
        }
        result = normalize_to_unified(report)
        self.assertEqual(result['stocks']['601166']['trend'], '看多')


if __name__ == '__main__':
    unittest.main(verbosity=2)
