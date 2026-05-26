"""Shared test configuration and utilities."""
import os, sys, json, sqlite3, unittest

# Project root detection
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'scripts'))

DB_PATH = os.path.join(ROOT, 'data', 'stock.db')
CONFIG_PATH = os.path.join(ROOT, 'data', 'config.json')

# Test constants
SAMPLE_CODES = ['601166', '600036']
SAMPLE_NAMES = {'601166': '兴业银行', '600036': '招商银行'}
WATCHLIST_PATH = os.path.join(ROOT, 'data', 'a_stocks.json')


def load_config():
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_test_db():
    """Return a database connection with row_factory set."""
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(f"Test DB not found: {DB_PATH}")
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    return db


def require_db(func):
    """Decorator: skip test if DB file is missing."""
    def wrapper(*args, **kwargs):
        if not os.path.exists(DB_PATH):
            raise unittest.SkipTest(f"Database not found: {DB_PATH}")
        return func(*args, **kwargs)
    return wrapper


class StockTestBase(unittest.TestCase):
    """Base class for all stock system tests."""

    maxDiff = None

    def setUp(self):
        self.root = ROOT

    def assertSuccess(self, resp_dict, msg="Response should have success=True"):
        self.assertTrue(resp_dict.get('success', False), msg)

    def assertApiShape(self, data, required_keys, container_name="response"):
        """Assert that data dict contains all required keys."""
        missing = [k for k in required_keys if k not in data]
        self.assertEqual(
            [], missing,
            f"{container_name} missing keys: {missing}"
        )


def print_header(title: str):
    """Print a section header for test output."""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")
