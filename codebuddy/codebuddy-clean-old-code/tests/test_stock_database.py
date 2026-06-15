"""P2 [HIGH] Stock database tests — A-stock data and symbol management.

Covers: stock code format, market prefix, data file structure.
"""
import os, sys, json, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from conftest import StockTestBase, WATCHLIST_PATH


# ======================================================================
# Stock code format rules
# ======================================================================
SH_PREFIXES = ["600", "601", "603", "605", "688"]
SZ_PREFIXES = ["000", "001", "002", "003", "300"]
MARKET_PREFIXES = {"sh": SH_PREFIXES, "sz": SZ_PREFIXES}


class TestStockCodeFormat(StockTestBase):
    """Verify stock code formats."""

    def test_stock_code_length(self):
        """A-share codes should be 6 digits."""
        valid = True
        for prefixes in MARKET_PREFIXES.values():
            for p in prefixes:
                code = p + "000"
                if len(code) != 6:
                    valid = False
                    break
        self.assertTrue(valid)

    def test_market_prefix_mapping(self):
        """Verify market prefix assignments."""
        test_cases = [
            ("601166", "sh"), ("600036", "sh"),
            ("000001", "sz"), ("300750", "sz"),
        ]
        for code, expected_market in test_cases:
            prefix = code[:3]
            market = None
            for m, prefixes in MARKET_PREFIXES.items():
                if prefix in prefixes:
                    market = m
                    break
            self.assertEqual(market, expected_market,
                             f"Code {code} should map to {expected_market}")


@unittest.skipIf(not os.path.exists(WATCHLIST_PATH),
                 f"Watchlist file not found: {WATCHLIST_PATH}")
class TestStockWatchlistFile(StockTestBase):
    """Verify A-stock watchlist file structure."""

    def test_watchlist_file_is_valid_json(self):
        with open(WATCHLIST_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertIsInstance(data, (list, dict))

    def test_watchlist_entries_have_code(self):
        with open(WATCHLIST_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            for item in data:
                self.assertIn("code", item)
        elif isinstance(data, dict):
            self.assertIn("code", data) if "code" in data else \
                self.assertTrue(all("code" in v for v in data.values()))


if __name__ == "__main__":
    unittest.main()
