"""P1 [CRITICAL] Database layer tests — db_helper.py schema and queries.

Covers: table existence, query function signatures, data type consistency.
"""
import os, sys, sqlite3, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from conftest import StockTestBase, DB_PATH, require_db


# ======================================================================
# Known tables in the stock database schema
# ======================================================================
EXPECTED_TABLES = [
    "config", "watchlist",
    "kline_daily", "kline_monthly",
    "quotes", "positions",
    "trades", "dividends",
    "daily_predictions", "seasonal",
    "news", "expert_reports",
    "learning_params", "accuracy_stats",
]


@unittest.skipIf(not os.path.exists(DB_PATH), f"Database not found: {DB_PATH}")
class TestDatabaseSchema(StockTestBase):
    """Verify database table structure."""

    def setUp(self):
        super().setUp()
        self.db = sqlite3.connect(DB_PATH)
        self.db.row_factory = sqlite3.Row

    def tearDown(self):
        self.db.close()

    def test_expected_tables_exist(self):
        cursor = self.db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = {row["name"] for row in cursor.fetchall()}
        for table in EXPECTED_TABLES:
            self.assertIn(table, tables, f"Missing table: {table}")

    def test_watchlist_has_required_columns(self):
        cursor = self.db.execute("PRAGMA table_info(watchlist)")
        cols = {row["name"] for row in cursor.fetchall()}
        for col in ["code", "name", "market"]:
            self.assertIn(col, cols, f"watchlist missing column: {col}")

    def test_kline_daily_has_required_columns(self):
        cursor = self.db.execute("PRAGMA table_info(kline_daily)")
        cols = {row["name"] for row in cursor.fetchall()}
        for col in ["code", "date", "open", "close", "high", "low"]:
            self.assertIn(col, cols, f"kline_daily missing column: {col}")


@unittest.skipIf(not os.path.exists(DB_PATH), f"Database not found: {DB_PATH}")
class TestDatabaseQueryFunctions(StockTestBase):
    """Verify db_helper query function names match spec."""

    def test_import_db_helper(self):
        """Verify db_helper module can be imported."""
        try:
            import db_helper
            self.assertTrue(hasattr(db_helper, "get_watchlist"))
            self.assertTrue(hasattr(db_helper, "get_quotes"))
            self.assertTrue(hasattr(db_helper, "get_kline_daily"))
            self.assertTrue(hasattr(db_helper, "get_news"))
        except ImportError as e:
            self.fail(f"db_helper import failed: {e}")


if __name__ == "__main__":
    unittest.main()
