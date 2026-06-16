import json, os, sys, subprocess
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from db_helper import (
    get_db, get_watchlist_codes, get_paper_account,
    get_paper_positions, get_quotes, get_quotes_batch,
    get_daily_predictions_batch, reset_paper_account,
    upsert_paper_suggestion, init_backtest_tables,
)
from signals import TODAY
from market_utils import is_market_open
from env_paths import get_node, get_westock

_NODE = get_node()
_WESTOCK = get_westock()
_SCRIPT = 'scripts/index.js'

INITIAL_CAPITAL = 100000.0
COMMISSION_RATE = 0.0003
STAMP_TAX_RATE = 0.001
MIN_CONFIDENCE = 0.5
MAX_POSITION_WEIGHT = 0.3
LOT_SIZE = 100


def _market_code(stock_code: str) -> str:
    if stock_code.startswith('6'):
        return f'sh{stock_code}'
    elif stock_code.startswith('0') or stock_code.startswith('3'):
        return f'sz{stock_code}'
    elif stock_code.startswith('4') or stock_code.startswith('8'):
        return f'bj{stock_code}'
    return f'sh{stock_code}'


def fetch_live_price(code: str) -> float | None:
    mkt = _market_code(code)
    try:
        result = subprocess.run(
            [_NODE, _SCRIPT, 'kline', mkt, '--period', 'day', '--limit', '1', '--fq', 'qfq'],
            cwd=_WESTOCK, capture_output=True, timeout=10,
        )
        text = ''
        if result.stdout:
            try:
                text = result.stdout.decode('gbk')
            except (UnicodeDecodeError, LookupError):
                text = result.stdout.decode('utf-8', errors='replace')
        for line in text.strip().split('\n'):
            parts = [p.strip() for p in line.split('|') if p.strip()]
            if len(parts) >= 5 and parts[0][:4].isdigit():
                return float(parts[4])
        return None
    except Exception:
        return None
