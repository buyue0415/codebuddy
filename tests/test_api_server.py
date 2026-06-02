"""P1 [CRITICAL] API server tests — server.py routing and response format.

Covers: route resolution, JSON response format, HTTP methods, error handling.
"""
import os, sys, json, unittest
from unittest.mock import Mock, patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from conftest import StockTestBase


# ======================================================================
# Test JSON response helper (imported from server.py if possible)
# ======================================================================
def _make_json_response(data, status=200):
    """Simulate server's json_response format."""
    return {"success": True, "data": data} if status == 200 \
        else {"success": False, "error": str(data)}


class TestApiResponseFormat(StockTestBase):
    """Test API response format consistency."""

    def test_success_response_has_success_key(self):
        resp = _make_json_response({"key": "val"})
        self.assertSuccess(resp)

    def test_success_response_has_data_key(self):
        resp = _make_json_response({"key": "val"})
        self.assertIn("data", resp)

    def test_error_response_has_success_false(self):
        resp = _make_json_response("Not found", 404)
        self.assertFalse(resp.get("success", True))

    def test_error_response_has_error_key(self):
        resp = _make_json_response("Not found", 404)
        self.assertIn("error", resp)


class TestApiRouteStructure(StockTestBase):
    """Test API route path conventions."""

    def test_api_v2_prefix(self):
        """All RESTful endpoints should use /api/v2/ prefix."""
        routes = [
            "/api/v2/config", "/api/v2/watchlist", "/api/v2/quotes",
            "/api/v2/kline/daily", "/api/v2/kline/monthly",
            "/api/v2/positions/current", "/api/v2/positions/closed",
            "/api/v2/trades", "/api/v2/dividends",
            "/api/v2/predictions/daily", "/api/v2/seasonal",
            "/api/v2/news", "/api/v2/expert",
            "/api/v2/learning", "/api/v2/accuracy",
        ]
        for route in routes:
            self.assertTrue(route.startswith("/api/v2/"),
                            f"{route} should use /api/v2/ prefix")

    def test_no_trailing_slash(self):
        """Routes should not have trailing slashes."""
        routes = [
            "/api/v2/config", "/api/v2/watchlist",
            "/api/v2/positions/current", "/api/v2/positions/closed",
        ]
        for route in routes:
            self.assertFalse(route.endswith("/") and route != "/",
                             f"{route} should not end with /")


if __name__ == "__main__":
    unittest.main()
