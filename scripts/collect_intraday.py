"""
Intraday data collector: fetches minute-level OHLC data and stores in intraday_quotes.

Runs every 60 minutes during market hours. Uses westock-data minute command
which returns the full day's minute data in a single call. INSERT OR REPLACE
ensures deduplication on (code, timestamp).

Usage:
    python collect_intraday.py once    # Single collection run
    python collect_intraday.py         # Continuous mode (loop every 60 min)
"""
import os, sys, subprocess, json, time
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from env_paths import get_node, get_westock
NODE = get_node()
WESTOCK = get_westock()
SCRIPT = 'scripts/index.js'

from db_helper import (
    get_db, get_watchlist_codes, insert_intraday_quotes, init_backtest_tables,
)
from market_utils import is_market_open

COLLECT_INTERVAL = 3600  # 1 hour in seconds


def market_code(stock_code: str) -> str:
    """Convert stock code to westock-data market_code format."""
    if stock_code.startswith('6'):
        return f'sh{stock_code}'
    elif stock_code.startswith('0') or stock_code.startswith('3'):
        return f'sz{stock_code}'
    elif stock_code.startswith('4') or stock_code.startswith('8'):
        return f'bj{stock_code}'
    return f'sh{stock_code}'


def fetch_minute_data(mkt_code: str, days: int = None) -> list:
    """Call westock-data minute to get minute-level OHLC data."""
    try:
        cmd = [NODE, SCRIPT, 'minute', mkt_code]
        if days:
            cmd.extend(['--days', str(days)])
        result = subprocess.run(cmd, cwd=WESTOCK, capture_output=True, timeout=30)
        text = ''
        if result.stdout:
            try:
                text = result.stdout.decode('gbk')
            except (UnicodeDecodeError, LookupError):
                text = result.stdout.decode('utf-8', errors='replace')

        data = []
        for line in text.strip().split('\n'):
            parts = [p.strip() for p in line.split('|') if p.strip()]
            if len(parts) < 4:
                continue
            time_str = parts[1].strip() if not days else parts[2].strip()
            if time_str in ('time', '---') or not time_str.isdigit():
                continue
            try:
                hm = f"{time_str[:2]}:{time_str[2:]}"
                if days:
                    date_str = parts[1].strip()
                    date_fmt = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
                    price = float(parts[3])
                    volume = int(float(parts[4])) if len(parts) > 4 and parts[4] else 0
                else:
                    date_fmt = datetime.now().strftime('%Y-%m-%d')
                    price = float(parts[2])
                    volume = int(float(parts[3])) if len(parts) > 3 and parts[3] else 0
                timestamp = f"{date_fmt} {hm}:00"
                data.append({
                    'timestamp': timestamp,
                    'price': price,
                    'change_pct': 0,
                    'volume': volume,
                })
            except (ValueError, IndexError):
                continue
        return data
    except subprocess.TimeoutExpired:
        return []
    except Exception as e:
        return []


def collect_once():
    """Single collection run."""
    init_backtest_tables()
    codes = get_watchlist_codes()
    if not codes:
        return
    total_points = 0
    for code in codes:
        mkt = market_code(code)
        bars = fetch_minute_data(mkt)
        if not bars:
            continue
        for bar in bars:
            bar['code'] = code
        insert_intraday_quotes(bars)
        total_points += len(bars)


def collect_backfill(days: int = 30):
    """Backfill historical intraday data."""
    init_backtest_tables()
    codes = get_watchlist_codes()
    if not codes:
        return
    for code in codes:
        mkt = market_code(code)
        bars = fetch_minute_data(mkt, days=days)
        if not bars:
            continue
        for bar in bars:
            bar['code'] = code
        insert_intraday_quotes(bars)


def collect_loop():
    """Continuous collection loop."""
    while True:
        if is_market_open():
            try:
                collect_once()
            except Exception:
                pass
            time.sleep(COLLECT_INTERVAL)
        else:
            time.sleep(60)


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser(description='Intraday data collector')
    ap.add_argument('action', nargs='?', default='loop',
                    choices=['once', 'loop', 'backfill'])
    ap.add_argument('--days', type=int, default=30)
    args = ap.parse_args()
    if args.action == 'once':
        collect_once()
    elif args.action == 'backfill':
        collect_backfill(days=args.days)
    else:
        collect_loop()
