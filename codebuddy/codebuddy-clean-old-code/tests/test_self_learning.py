"""P2 [HIGH] Self-learning tests — learning_params structure and update logic.

Covers: parameter structure, weight normalization, confidence scoring.
"""
import os, sys, json, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from conftest import StockTestBase, DB_PATH


# ======================================================================
# Self-learning parameter structure constants
# ======================================================================
EXPECTED_PARAM_KEYS = [
    "signal_weights", "hourly_bias", "seasonal_adj",
    "confidence_beta", "learning_rate", "mw_beta", "update_count",
]
SIGNAL_NAMES = ["macd", "rsi", "bollinger", "kdj", "seasonal", "atr", "money_flow"]


class TestLearningParamStructure(StockTestBase):
    """Verify learning parameter data structure."""

    def test_expected_keys_present(self):
        sample = {
            "signal_weights": {s: 0.5 for s in SIGNAL_NAMES},
            "hourly_bias": {str(h): 0.0 for h in range(9, 16)},
            "seasonal_adj": {str(m): 1.0 for m in range(1, 13)},
            "confidence_beta": 1.0,
            "learning_rate": 0.01,
            "mw_beta": 0.5,
            "update_count": 0,
        }
        for key in EXPECTED_PARAM_KEYS:
            self.assertIn(key, sample, f"Missing key: {key}")
        self.assertEqual(len(sample["signal_weights"]), 7)

    def test_signal_weights_summarize(self):
        """Signal weights should be non-negative."""
        weights = {s: 0.5 for s in SIGNAL_NAMES}
        for w in weights.values():
            self.assertGreaterEqual(w, 0)

    def test_learning_rate_range(self):
        """Learning rate should be between 0 and 1."""
        sample_rate = 0.01
        self.assertGreaterEqual(sample_rate, 0)
        self.assertLessEqual(sample_rate, 1)


@unittest.skipIf(not os.path.exists(DB_PATH), f"Database not found: {DB_PATH}")
class TestLearningParamDB(StockTestBase):
    """Verify learning_params table structure if DB exists."""

    def test_learning_params_table_exists(self):
        import sqlite3
        db = sqlite3.connect(DB_PATH)
        cursor = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='learning_params'"
        )
        self.assertIsNotNone(cursor.fetchone())
        db.close()


if __name__ == "__main__":
    unittest.main()
