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


def fetch_minute_data(mkt_code: str, days: int = None) -> list:
    """Call westock-data minute to get minute-level OHLC data.

    Supports two modes:
    - Without days (default): returns today's data only
      Format: | code | time(HHMM) | price | volume | amount |
    - With --days N: returns data for last N trading days
      Format: | code | date(YYYYMMDD) | time(HHMM) | price | volume | amount |

    Returns:
        List of dicts: [{timestamp: 'YYYY-MM-DD HH:MM:00', price: float, volume: int}, ...]
    """
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
            # Skip header and separator rows (contain '---' or non-numeric time/date)
            if len(parts) < 4:
                continue
            time_str = parts[1].strip() if not days else parts[2].strip()
            if time_str in ('time', '---') or not time_str.isdigit():
                continue
            try:
                hm = f"{time_str[:2]}:{time_str[2:]}"
                # With --days N: parts = [code, date(YYYYMMDD), time(HHMM), price, volume, amount]
                # Without --days: parts = [code, time(HHMM), price, volume, amount]
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


def collect_backfill(days: int = 30):
    """Backfill historical intraday data for the last N trading days.

    Uses `westock-data minute --days N` which returns minute data with
    actual date information embedded in the response.
    """
    init_backtest_tables()
    codes = get_watchlist_codes()
    if not codes:
        print("[Intraday] No watchlist stocks. Skipping backfill.", file=sys.stderr)
        return

    total_new = 0
    for code in codes:
        mkt = market_code(code)
        bars = fetch_minute_data(mkt, days=days)
        if not bars:
            print(f"  {code}: no data", file=sys.stderr)
            continue

        # Assign code to each bar
        for bar in bars:
            bar['code'] = code
        insert_intraday_quotes(bars)
        total_new += len(bars)
        print(f"  {code}: {len(bars)} points", file=sys.stderr)

    print(f"[Intraday] Backfill complete: {total_new} points from {len(codes)} stocks "
          f"(past {days} days)", file=sys.stderr)


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
    ap.add_argument('action', nargs='?', default='loop',
                    choices=['once', 'loop', 'backfill'],
                    help="'once' for single run, 'loop' for continuous, 'backfill' for historical backfill")
    ap.add_argument('--days', type=int, default=30,
                    help="Number of days to backfill (default: 30, only used with 'backfill' action)")
    args = ap.parse_args()

    if args.action == 'once':
        collect_once()
    elif args.action == 'backfill':
        collect_backfill(days=args.days)
    else:
        collect_loop()
