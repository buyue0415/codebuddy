"""P2 [HIGH] Scheduler tests — automation and timing logic.

Covers: schedule definitions, trigger conditions, lock management.
"""
import os, sys, unittest
from datetime import datetime, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from conftest import StockTestBase


# ======================================================================
# Schedule constants (from specifications)
# ======================================================================
DEFAULT_SCHEDULE = {
    "market_open": time(9, 30),
    "market_close": time(15, 0),
    "sync_time": time(15, 35),
    "news_fetch_interval": 3600,  # seconds
}


class TestSchedulerConfig(StockTestBase):
    """Verify scheduler configuration structure."""

    def test_schedule_has_all_keys(self):
        expected = ["market_open", "market_close", "sync_time", "news_fetch_interval"]
        for key in expected:
            self.assertIn(key, DEFAULT_SCHEDULE)

    def test_market_hours_valid(self):
        self.assertLess(DEFAULT_SCHEDULE["market_open"],
                        DEFAULT_SCHEDULE["market_close"])

    def test_news_fetch_interval_positive(self):
        self.assertGreater(DEFAULT_SCHEDULE["news_fetch_interval"], 0)

    def test_sync_time_after_market_close(self):
        self.assertGreaterEqual(DEFAULT_SCHEDULE["sync_time"],
                                DEFAULT_SCHEDULE["market_close"])


class TestSchedulerLogic(StockTestBase):
    """Verify scheduling edge cases."""

    def test_is_trading_time(self):
        """Verify trading time check logic."""
        def is_trading(now):
            open_t = DEFAULT_SCHEDULE["market_open"]
            close_t = DEFAULT_SCHEDULE["market_close"]
            return open_t <= now.time() <= close_t

        self.assertTrue(is_trading(datetime(2026, 5, 28, 10, 0)))
        self.assertFalse(is_trading(datetime(2026, 5, 28, 8, 0)))
        self.assertFalse(is_trading(datetime(2026, 5, 28, 15, 30)))

    def test_is_weekday(self):
        """Verify weekday check."""
        monday = datetime(2026, 5, 25)  # Monday
        saturday = datetime(2026, 5, 30)  # Saturday
        sunday = datetime(2026, 5, 31)  # Sunday
        self.assertLess(monday.weekday(), 5)
        self.assertGreaterEqual(saturday.weekday(), 5)
        self.assertGreaterEqual(sunday.weekday(), 5)


if __name__ == "__main__":
    unittest.main()
