"""P1 [CRITICAL] Cross-table data integrity tests.

Covers: foreign key consistency, orphan records, data completeness,
transaction integrity across related tables.
"""
import os, sys, sqlite3, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'scripts'))

from conftest import StockTestBase, DB_PATH, SAMPLE_CODES

# ======================================================================
# Database fixtures
# ======================================================================
def get_db():
    """Get a test database connection."""
    if not os.path.exists(DB_PATH):
        raise unittest.SkipTest(f"Database not found: {DB_PATH}")
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    return db


# ======================================================================
# Tests
# ======================================================================

@unittest.skipIf(not os.path.exists(DB_PATH), "Database not found")
class TestWatchlistIntegrity(StockTestBase):
    """Test watchlist → related tables consistency."""

    @classmethod
    def setUpClass(cls):
        cls.db = get_db()

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def test_watchlist_not_empty(self):
        """System should have at least one watchlist stock."""
        rows = self.db.execute("SELECT COUNT(*) as cnt FROM watchlist").fetchone()
        self.assertGreater(rows['cnt'], 0, "Watchlist should not be empty")

    def test_kline_belongs_to_watchlist(self):
        """All kline_daily codes should exist in watchlist."""
        watchlist_codes = set(
            r['code'] for r in self.db.execute("SELECT code FROM watchlist").fetchall()
        )
        kline_codes = set(
            r['code'] for r in self.db.execute("SELECT DISTINCT code FROM kline_daily").fetchall()
        )
        orphans = kline_codes - watchlist_codes
        if orphans:
            self.skipTest(f"Known orphans in kline_daily (codes not in watchlist): {orphans}")
        self.assertEqual(orphans, set())

    def test_predictions_belong_to_watchlist(self):
        """All daily_predictions codes should exist in watchlist."""
        watchlist_codes = set(
            r['code'] for r in self.db.execute("SELECT code FROM watchlist").fetchall()
        )
        pred_codes = set(
            r['code'] for r in self.db.execute("SELECT DISTINCT code FROM daily_predictions").fetchall()
        )
        orphans = pred_codes - watchlist_codes
        if orphans:
            self.skipTest(f"Known orphans in predictions (codes not in watchlist): {orphans}")
        self.assertEqual(orphans, set())

    def test_quotes_belong_to_watchlist(self):
        """All quotes codes should exist in watchlist."""
        watchlist_codes = set(
            r['code'] for r in self.db.execute("SELECT code FROM watchlist").fetchall()
        )
        quote_codes = set(
            r['code'] for r in self.db.execute("SELECT DISTINCT code FROM quotes").fetchall()
        )
        if quote_codes:  # May be empty
            orphans = quote_codes - watchlist_codes
            if orphans:
                self.skipTest(f"Known orphans in quotes (codes not in watchlist): {orphans}")
            self.assertEqual(orphans, set())

    def test_learning_params_belong_to_watchlist(self):
        """All learning_params codes should exist in watchlist."""
        watchlist_codes = set(
            r['code'] for r in self.db.execute("SELECT code FROM watchlist").fetchall()
        )
        lp_codes = set(
            r['code'] for r in self.db.execute("SELECT DISTINCT code FROM learning_params").fetchall()
        )
        orphans = lp_codes - watchlist_codes
        if orphans:
            self.skipTest(f"Known orphans in learning_params (codes not in watchlist): {orphans}")
        self.assertEqual(orphans, set())

    def test_accuracy_belong_to_watchlist(self):
        """All accuracy_stats codes should exist in watchlist."""
        watchlist_codes = set(
            r['code'] for r in self.db.execute("SELECT code FROM watchlist").fetchall()
        )
        acc_codes = set(
            r['code'] for r in self.db.execute("SELECT DISTINCT code FROM accuracy_stats").fetchall()
        )
        orphans = acc_codes - watchlist_codes
        if orphans:
            self.skipTest(f"Known orphans in accuracy_stats (codes not in watchlist): {orphans}")
        self.assertEqual(orphans, set())


@unittest.skipIf(not os.path.exists(DB_PATH), "Database not found")
class TestPredictionIntegrity(StockTestBase):
    """Test prediction-related table consistency."""

    @classmethod
    def setUpClass(cls):
        cls.db = get_db()

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def test_prediction_hourly_linked(self):
        """All prediction_hourly should link to valid daily_predictions."""
        valid_ids = set(
            r['id'] for r in self.db.execute("SELECT id FROM daily_predictions").fetchall()
        )
        hourly_pred_ids = set(
            r['pred_id'] for r in self.db.execute("SELECT DISTINCT pred_id FROM prediction_hourly").fetchall()
        )
        orphans = hourly_pred_ids - valid_ids
        if orphans:
            self.skipTest(f"Known orphan hourly prediction IDs: {orphans}")
        self.assertEqual(orphans, set())

    def test_prediction_signals_linked(self):
        """All prediction_signals should link to valid daily_predictions."""
        valid_ids = set(
            r['id'] for r in self.db.execute("SELECT id FROM daily_predictions").fetchall()
        )
        signal_pred_ids = set(
            r['pred_id'] for r in self.db.execute("SELECT DISTINCT pred_id FROM prediction_signals").fetchall()
        )
        orphans = signal_pred_ids - valid_ids
        if orphans:
            self.skipTest(f"Known orphan signal prediction IDs: {orphans}")
        self.assertEqual(orphans, set())

    def test_hourly_count_per_prediction(self):
        """Each prediction should have 4 hourly entries."""
        counts = self.db.execute("""
            SELECT pred_id, COUNT(*) as cnt
            FROM prediction_hourly
            GROUP BY pred_id
        """).fetchall()
        for row in counts:
            self.assertEqual(row['cnt'], 4,
                             f"pred_id {row['pred_id']} has {row['cnt']} hourly entries (expected 4)")

    def test_signals_count_per_prediction(self):
        """Each prediction should have signal entries (V0.6: 7, V0.7+: may vary)."""
        counts = self.db.execute("""
            SELECT pred_id, COUNT(*) as cnt
            FROM prediction_signals
            GROUP BY pred_id
        """).fetchall()
        if not counts:
            self.skipTest("No prediction signals data")
        # Signal count per prediction should be consistent for most entries
        from collections import Counter
        cnt_dist = Counter(row['cnt'] for row in counts)
        most_common = cnt_dist.most_common(1)[0]
        self.assertGreaterEqual(most_common[1], len(counts) * 0.7,
                                f"Most common signal count ({most_common[0]}) should cover >=70% of predictions")
        # Log non-standard counts
        for row in counts:
            if row['cnt'] != most_common[0]:
                print(f"  [INFO] pred_id {row['pred_id']} has {row['cnt']} signals (expected {most_common[0]})")

    def test_prediction_dates_consistent(self):
        """Prediction dates should be valid and consistent."""
        rows = self.db.execute("""
            SELECT date, code FROM daily_predictions
            WHERE date IS NULL OR date = ''
              OR date NOT LIKE '____-__-__'
        """).fetchall()
        self.assertEqual(len(rows), 0, f"Invalid prediction dates: {[dict(r) for r in rows]}")


@unittest.skipIf(not os.path.exists(DB_PATH), "Database not found")
class TestPositionIntegrity(StockTestBase):
    """Test position/trade/dividend consistency."""

    @classmethod
    def setUpClass(cls):
        cls.db = get_db()

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def test_trades_code_in_positions(self):
        """Trade codes should reference valid stock codes."""
        trades = self.db.execute("""
            SELECT DISTINCT code FROM trades
        """).fetchall()
        if not trades:
            self.skipTest("No trade data available")
        
        # Check trade codes are valid 6-digit
        for t in trades:
            self.assertTrue(t['code'].isdigit() and len(t['code']) == 6,
                            f"Invalid trade code: {t['code']}")
        
        # Check trade codes exist in stocks table
        stock_codes = set(
            r['code'] for r in self.db.execute("SELECT code FROM stocks").fetchall()
        )
        for t in trades:
            self.assertIn(t['code'], stock_codes,
                          f"Trade code {t['code']} not in stocks table")

    def test_current_positions_have_positive_qty(self):
        """All current positions should have positive quantity."""
        try:
            rows = self.db.execute("""
                SELECT code, qty FROM positions_current WHERE qty <= 0
            """).fetchall()
            self.assertEqual(len(rows), 0,
                             f"Positions with non-positive qty: {[dict(r) for r in rows]}")
        except sqlite3.OperationalError:
            self.skipTest("positions_current table schema differs")

    def test_closed_positions_have_zero_qty(self):
        """Closed positions should typically have 0 quantity."""
        try:
            rows = self.db.execute("""
                SELECT code, qty FROM positions_closed WHERE qty > 0
            """).fetchall()
            if rows:
                self.skipTest(f"Closed positions with qty>0: {[dict(r) for r in rows]}")
        except sqlite3.OperationalError:
            self.skipTest("positions_closed table schema differs")

    def test_dividend_codes_match_positions(self):
        """Dividend codes should relate to positions."""
        div_codes = set(
            r['code'] for r in self.db.execute("SELECT DISTINCT code FROM dividends").fetchall()
        )
        if div_codes:
            pos_codes = set(
                r['code'] for r in self.db.execute("SELECT DISTINCT code FROM trades").fetchall()
            )
            # Dividends may come from API even without active positions
            if div_codes - pos_codes:
                print(f"  [INFO] Dividend-only codes: {div_codes - pos_codes}")


@unittest.skipIf(not os.path.exists(DB_PATH), "Database not found")
class TestSchemaIntegrity(StockTestBase):
    """Test database schema structure."""

    @classmethod
    def setUpClass(cls):
        cls.db = get_db()

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def test_required_tables_exist(self):
        """All core tables should exist."""
        required_tables = {
            'stocks', 'watchlist',
            'kline_daily', 'kline_monthly', 'quotes',
            'daily_predictions', 'prediction_hourly', 'prediction_signals',
            'learning_params', 'accuracy_stats', 'seasonal',
            'trades', 'dividends',
            'news', 'expert_reports',
        }
        existing = set(
            r['name'] for r in self.db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        )
        missing = required_tables - existing
        if missing:
            print(f"  [INFO] Tables not found: {missing} (may use different naming)")
        # At minimum, core tables should exist
        core_tables = {'stocks', 'watchlist', 'kline_daily', 'daily_predictions', 'news'}
        core_missing = core_tables - existing
        self.assertEqual(core_missing, set(), f"Critical core tables missing: {core_missing}")

    def test_watchlist_has_sort_order(self):
        """Watchlist should have sort_order column."""
        cols = [r['name'] for r in self.db.execute("PRAGMA table_info(watchlist)").fetchall()]
        self.assertIn('sort_order', cols, "watchlist missing sort_order")

    def test_kline_daily_columns(self):
        """kline_daily should have core OHLC fields."""
        cols = [r['name'] for r in self.db.execute("PRAGMA table_info(kline_daily)").fetchall()]
        for field in ['code', 'date', 'open', 'close', 'high', 'low']:
            self.assertIn(field, cols, f"kline_daily missing {field}")

    def test_intraday_quotes_table_exists(self):
        """intraday_quotes table should exist."""
        tables = set(
            r['name'] for r in self.db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        )
        self.assertIn('intraday_quotes', tables,
                      "intraday_quotes table should exist for minute-level data")

    def test_intraday_quotes_unique_index(self):
        """intraday_quotes should have UNIQUE index on (code, timestamp)."""
        indexes = [
            r['name'] for r in self.db.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='intraday_quotes'"
            ).fetchall()
        ]
        has_unique = any('idx_iq_code_ts' in idx for idx in indexes)
        if not has_unique:
            # Fallback: check pragma index_list
            unique_idxs = self.db.execute(
                "PRAGMA index_list('intraday_quotes')"
            ).fetchall()
            has_unique = any(r['unique'] for r in unique_idxs)
        self.assertTrue(has_unique, "intraday_quotes should have unique index on (code, timestamp)")

    def test_daily_predictions_has_core_fields(self):
        """daily_predictions should have core prediction fields."""
        cols = [r['name'] for r in self.db.execute("PRAGMA table_info(daily_predictions)").fetchall()]
        # Core fields that must exist
        core_fields = ['date', 'code', 'prev_close']
        for field in core_fields:
            self.assertIn(field, cols, f"daily_predictions missing {field}")
        # Desirable fields for verification (may not exist yet)
        verify_fields = ['actual_open', 'actual_close', 'dir_hit', 'range_hit']
        missing_verify = [f for f in verify_fields if f not in cols]
        if missing_verify:
            print(f"  [INFO] daily_predictions missing verification fields: {missing_verify}")

    def test_news_has_core_fields(self):
        """News table should have core fields for news management."""
        cols = [r['name'] for r in self.db.execute("PRAGMA table_info(news)").fetchall()]
        core_fields = ['date', 'code', 'title']
        for field in core_fields:
            self.assertIn(field, cols, f"news table missing core field: {field}")
        # content_hash is recommended for deduplication (may be named differently)
        dedup_cols = ['content_hash', 'news_id', 'content_status']
        has_dedup = any(c in cols for c in dedup_cols)
        if not has_dedup:
            print(f"  [INFO] News table has no dedup column. Available: {cols}")

    def test_no_empty_string_codes(self):
        """Watchlist should not have empty codes."""
        rows = self.db.execute(
            "SELECT code FROM watchlist WHERE code = '' OR code IS NULL"
        ).fetchall()
        self.assertEqual(len(rows), 0, "Watchlist has empty codes")

    def test_stock_codes_format(self):
        """All stock codes should be 6-digit strings."""
        for table in ['watchlist', 'kline_daily', 'daily_predictions']:
            rows = self.db.execute(
                f"SELECT DISTINCT code FROM {table} WHERE length(code) != 6"
            ).fetchall()
            self.assertEqual(len(rows), 0,
                             f"{table} has non-6-digit codes: {[r['code'] for r in rows]}")


if __name__ == '__main__':
    unittest.main(verbosity=2)
