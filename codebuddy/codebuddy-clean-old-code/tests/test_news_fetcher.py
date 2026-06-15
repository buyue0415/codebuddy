"""P1 [CRITICAL] News fetcher tests — parsing, sentiment, classification.

Tests: _parse_news_table, _parse_news_row, _detect_sentiment, _is_major, _extract_code.
Runs without external dependencies or network.
"""
import os, sys, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'scripts'))

from conftest import StockTestBase

# ======================================================================
# Import fetch_news functions
# ======================================================================
_FETCH_IMPORTED = False
_FETCH_IMPORT_ERR = ''

try:
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        'fetch_news',
        os.path.join(ROOT, 'scripts', 'fetch_news.py')
    )
    fetch_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fetch_mod)

    _parse_news_table = fetch_mod._parse_news_table
    _parse_news_row = fetch_mod._parse_news_row
    _detect_sentiment = fetch_mod._detect_sentiment
    _is_major = fetch_mod._is_major
    _extract_code = fetch_mod._extract_code
    _FETCH_IMPORTED = True
except Exception as e:
    _FETCH_IMPORT_ERR = str(e)


# ======================================================================
# Sample markdown table output from NeoData
# ======================================================================

SAMPLE_NEWS_TABLE = """\
| time | id | custom | symbol | title | url | type | subtype | source_type | source | col10 | col11 | col12 | summary |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2026-05-26 09:00 | 12345 | data | sh601166 | 兴业银行落地首单汇率避险业务 | http://example.com/1 | type1 | sub1 | media | 证券之星 | | | | 兴业银行南京分行落地首单... |
| 2026-05-26 08:30 | 12346 | data | sh600036 | 招商银行发布年度分红方案 | http://example.com/2 | type1 | sub1 | media | 中国证券报 | | | | 招商银行计划每股分红... |
| 2026-05-25 15:00 | 12347 | data | sh601166 | 央行重磅政策影响银行业 | http://example.com/3 | type1 | sub1 | media | 证券之星 | | | | 央行发布新政策... |
"""

SINGLE_ROW = "| 2026-05-26 09:00 | 12345 | data | sh601166 | 兴业银行落地首单汇率避险业务 | http://example.com/1 | type1 | sub1 | media | 证券之星 | | | | 兴业银行南京分行落地首单... |"


# ======================================================================
# Tests
# ======================================================================

@unittest.skipIf(not _FETCH_IMPORTED, f"fetch_news import failed: {_FETCH_IMPORT_ERR}")
class TestExtractCode(StockTestBase):
    """Test stock code extraction from symbol strings."""

    def test_sh_prefix(self):
        self.assertEqual(_extract_code('sh601166'), '601166')

    def test_sz_prefix(self):
        self.assertEqual(_extract_code('sz000001'), '000001')

    def test_already_code(self):
        self.assertEqual(_extract_code('601166'), '601166')

    def test_no_digits(self):
        self.assertEqual(_extract_code('abc'), 'abc')


@unittest.skipIf(not _FETCH_IMPORTED, f"fetch_news import failed: {_FETCH_IMPORT_ERR}")
class TestDetectSentiment(StockTestBase):
    """Test keyword-based sentiment detection."""

    def test_positive_sentiment(self):
        score = _detect_sentiment('股票上涨突破新高，资金净流入', '')
        self.assertEqual(score, 'positive')

    def test_negative_sentiment(self):
        score = _detect_sentiment('股票下跌跌破支撑，资金净流出', '')
        self.assertEqual(score, 'negative')

    def test_neutral_sentiment(self):
        score = _detect_sentiment('公司召开董事会会议', '')
        self.assertEqual(score, 'neutral')

    def test_balanced_sentiment(self):
        """Equal positive and negative keywords → neutral."""
        title = '股票上涨同时存在风险'
        score = _detect_sentiment(title, '')
        self.assertEqual(score, 'neutral')

    def test_summary_also_checked(self):
        """Sentiment should also scan the summary text."""
        score = _detect_sentiment('公司公告', '今日股价大涨突破新高')
        self.assertEqual(score, 'positive')

    def test_all_positive_keywords(self):
        positives = ['上涨', '净流入', '买入', '利好', '增持', '盈利',
                     '分红', '看好', '增长', '回升', '突破', '新高', '受捧', '资金净流入']
        for kw in positives:
            with self.subTest(keyword=kw):
                score = _detect_sentiment(kw, '')
                self.assertEqual(score, 'positive')

    def test_all_negative_keywords(self):
        negatives = ['下跌', '净流出', '卖出', '利空', '减持', '亏损',
                     '风险', '看跌', '下滑', '承压', '跌破', '抛压', '资金净流出', '融资净卖出']
        for kw in negatives:
            with self.subTest(keyword=kw):
                score = _detect_sentiment(kw, '')
                self.assertEqual(score, 'negative')


@unittest.skipIf(not _FETCH_IMPORTED, f"fetch_news import failed: {_FETCH_IMPORT_ERR}")
class TestIsMajor(StockTestBase):
    """Test major news detection."""

    def test_major_keywords(self):
        majors = ['重大', '重磅', '政策', '利率', '降准', '加息', '监管', '央行', '国务院']
        for kw in majors:
            with self.subTest(keyword=kw):
                self.assertTrue(_is_major(kw, ''), f"'{kw}' should be major")

    def test_normal_news_not_major(self):
        self.assertFalse(_is_major('公司日常经营公告', ''))

    def test_summary_major(self):
        self.assertTrue(_is_major('日常新闻', '央行发布最新利率政策'))


@unittest.skipIf(not _FETCH_IMPORTED, f"fetch_news import failed: {_FETCH_IMPORT_ERR}")
class TestParseNewsRow(StockTestBase):
    """Test single news row parsing."""

    def test_parse_valid_row(self):
        item = _parse_news_row(SINGLE_ROW)
        self.assertIsNotNone(item)
        self.assertEqual(item['date'], '2026-05-26')
        self.assertEqual(item['code'], '601166')
        self.assertEqual(item['title'], '兴业银行落地首单汇率避险业务')
        self.assertEqual(item['source'], '证券之星')

    def test_parse_row_all_fields(self):
        item = _parse_news_row(SINGLE_ROW)
        for key in ['date', 'code', 'title', 'summary', 'source', 'sentiment', 'major', 'news_id']:
            self.assertIn(key, item)

    def test_parse_row_sentiment_auto(self):
        """Sentiment should be auto-detected from title."""
        item = _parse_news_row(SINGLE_ROW)
        self.assertIn(item['sentiment'], ['positive', 'negative', 'neutral'])

    def test_parse_row_major_auto(self):
        """Major flag should be auto-detected."""
        item = _parse_news_row(SINGLE_ROW)
        self.assertIn(item['major'], [0, 1])

    def test_parse_short_row_none(self):
        """Too few columns should return None."""
        short = "| 2026-01-01 | id |"
        self.assertIsNone(_parse_news_row(short))

    def test_parse_empty_row_none(self):
        self.assertIsNone(_parse_news_row(""))

    def test_parse_major_news_detected(self):
        """News with '重大' in title should have major=1."""
        major_row = "| 2026-05-26 09:00 | 12345 | data | sh601166 | 重大政策利好银行板块 | http://example.com | type | sub | media | 证券之星 | | | | 摘要内容 |"
        item = _parse_news_row(major_row)
        self.assertEqual(item['major'], 1)


@unittest.skipIf(not _FETCH_IMPORTED, f"fetch_news import failed: {_FETCH_IMPORT_ERR}")
class TestParseNewsTable(StockTestBase):
    """Test full markdown table parsing."""

    def test_parse_valid_table(self):
        items = _parse_news_table(SAMPLE_NEWS_TABLE)
        self.assertEqual(len(items), 3)

    def test_parsed_items_have_required_fields(self):
        items = _parse_news_table(SAMPLE_NEWS_TABLE)
        for item in items:
            self.assertIn('date', item)
            self.assertIn('code', item)
            self.assertIn('title', item)

    def test_parse_codes_correct(self):
        items = _parse_news_table(SAMPLE_NEWS_TABLE)
        codes = [it['code'] for it in items]
        self.assertIn('601166', codes)
        self.assertIn('600036', codes)

    def test_parse_empty_table(self):
        empty = "| time | id |\n| --- | --- |\n"
        items = _parse_news_table(empty)
        self.assertEqual(len(items), 0)

    def test_parse_no_header_table(self):
        """Table without header row should still parse data rows."""
        no_header = "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n" + SINGLE_ROW
        items = _parse_news_table(no_header)
        self.assertEqual(len(items), 1)

    def test_parse_malformed_data_skipped(self):
        """Rows that fail parsing should be silently skipped."""
        bad_row = "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n| invalid | row |\n"
        items = _parse_news_table(bad_row)
        self.assertEqual(len(items), 0)

    def test_sort_order_preserved(self):
        """Items should maintain their original row order."""
        items = _parse_news_table(SAMPLE_NEWS_TABLE)
        self.assertEqual(items[0]['date'], '2026-05-26')


# ======================================================================
# Run
# ======================================================================
if __name__ == '__main__':
    unittest.main(verbosity=2)
