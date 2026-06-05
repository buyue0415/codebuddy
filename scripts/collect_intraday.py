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

from db_helper import (
    get_db, get_watchlist_codes, insert_intraday_quotes, init_backtest_tables,
)
from market_utils import is_market_open

NODE = r'C:\Users\28312\.workbuddy\binaries\node\versions\22.12.0\node.exe'
WESTOCK = r'C:\Users\28312\.workbuddy\plugins\marketplaces\experts\plugins\stock-partner-team\skills\westock-data'
SCRIPT = 'scripts/index.js'

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


def fetch_minute_data(mkt_code: str) -> list:
    """Call westock-data minute to get full day's minute-level OHLC data.

    Returns:
        List of dicts: [{timestamp: 'YYYY-MM-DD HH:MM:00', price: float, volume: int}, ...]
    """
    try:
        result = subprocess.run(
            [NODE, SCRIPT, 'minute', mkt_code],
            cwd=WESTOCK, capture_output=True, timeout=30,
        )
        text = ''
        if result.stdout:
            try:
                text = result.stdout.decode('gbk')
            except (UnicodeDecodeError, LookupError):
                text = result.stdout.decode('utf-8', errors='replace')

        today = datetime.now().strftime('%Y-%m-%d')
        data = []
        for line in text.strip().split('\n'):
            parts = [p.strip() for p in line.split('|') if p.strip()]
            # Actual format: | code | time(HHMM) | price | volume | amount |
            # Example: | sh601166 | 0930 | 18.32 | 5972 | 10940703.56 |
            # Skip header and separator rows (contain '---' or non-numeric time)
            if len(parts) >= 4:
                time_str = parts[1].strip()
                # Skip header/separator rows
                if time_str in ('time', '---') or not time_str.isdigit():
                    continue
                try:
                    # Convert HHMM -> HH:MM
                    hm = f"{time_str[:2]}:{time_str[2:]}"
                    price = float(parts[2])
                    volume = int(float(parts[3])) if len(parts) > 3 and parts[3] else 0
                    timestamp = f"{today} {hm}:00"
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
        print(f"[Intraday] Timeout for {mkt_code}", file=sys.stderr)
        return []
    except Exception as e:
        print(f"[Intraday] Error fetching {mkt_code}: {e}", file=sys.stderr)
        return []


def collect_once():
    """Single collection run: fetch minute data for all watchlist stocks."""
    # Ensure tables exist
    init_backtest_tables()

    codes = get_watchlist_codes()
    if not codes:
        print("[Intraday] No watchlist stocks. Skipping.", file=sys.stderr)
        return

    total_points = 0
    for code in codes:
        mkt = market_code(code)
        bars = fetch_minute_data(mkt)
        if not bars:
            print(f"  {code}: no data", file=sys.stderr)
            continue

        # Add code to each bar
        for bar in bars:
            bar['code'] = code

        insert_intraday_quotes(bars)
        total_points += len(bars)
        print(f"  {code}: {len(bars)} points", file=sys.stderr)

    print(f"[Intraday] Collected {total_points} minute points from {len(codes)} stocks "
          f"at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", file=sys.stderr)


def collect_loop():
    """Continuously collect intraday data during market hours."""
    print(f"[Intraday] Starting continuous collector (interval={COLLECT_INTERVAL}s)", file=sys.stderr)

    while True:
        if is_market_open():
            print(f"\n[Intraday] Market open, collecting...", file=sys.stderr)
            try:
                collect_once()
            except Exception as e:
                print(f"[Intraday] Collect error: {e}", file=sys.stderr)
            print(f"[Intraday] Sleeping {COLLECT_INTERVAL}s...", file=sys.stderr)
            time.sleep(COLLECT_INTERVAL)
        else:
            # Not in market hours: check every 60 seconds for market open
            time.sleep(60)


# ── CLI ─────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser(description='Intraday data collector')
    ap.add_argument('action', nargs='?', default='loop', choices=['once', 'loop'],
                    help="'once' for single run, 'loop' for continuous (default)")
    args = ap.parse_args()

    if args.action == 'once':
        collect_once()
    else:
        collect_loop()
