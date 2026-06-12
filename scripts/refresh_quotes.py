"""
Lightweight real-time quotes refresh — fetches latest prices and calculates dividend yield.
Runs as a standalone script for the /api/v2/quotes/refresh endpoint.
Outputs JSON to stdout on success.
"""
import os, sys, json, subprocess, sqlite3
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from db_helper import upsert_quotes, get_db

NODE = r'C:\Users\28312\.workbuddy\binaries\node\versions\22.12.0\node.exe'
WESTOCK = r'C:\Users\28312\.workbuddy\plugins\marketplaces\experts\plugins\stock-partner-team\skills\westock-data'
SCRIPT = 'scripts/index.js'
DB_PATH = os.path.join(ROOT, 'data', 'stock.db')


def fetch_latest_kline(market_code: str, limit: int = 3) -> list:
    """Fetch a few daily K-line bars for latest price info."""
    try:
        result = subprocess.run(
            [NODE, SCRIPT, 'kline', market_code, '--period', 'day',
             '--limit', str(limit), '--fq', 'qfq'],
            cwd=WESTOCK, capture_output=True, timeout=20,
        )
        text = ''
        if result.stdout:
            try:
                text = result.stdout.decode('gbk')
            except (UnicodeDecodeError, LookupError):
                text = result.stdout.decode('utf-8', errors='replace')
        data = []
        for line in text.strip().split('\n'):
            parts = [p.strip() for p in line.split('|') if p.strip()]
            if len(parts) >= 5 and parts[0][:4].isdigit():
                volume = float(parts[5]) if len(parts) >= 6 else 0
                data.append([parts[0], float(parts[1]), float(parts[2]),
                             float(parts[3]), float(parts[4]), volume])
        # Sort newest first
        data.sort(key=lambda x: x[0], reverse=True)
        return data
    except subprocess.TimeoutExpired:
        print(f"  Timeout for {market_code}", file=sys.stderr)
        return []
    except Exception as e:
        print(f"  Error fetching {market_code}: {e}", file=sys.stderr)
        return []


def calc_dividend_yield(code: str, current_price: float) -> float:
    """Calculate trailing 12-month dividend yield (公式计算值 · TTM推算).

    TTM formula: (sum of per_share dividends in last 12 months / current_price) * 100

    Source-aware per_share calculation:
      - 'statement': per_share = amount / shares_held_before_record_date
      - 'web': price field stores actual per-share dividend, use directly
      - 'ttm_calculated' / 'kline_estimated': price field stores per_share
      - Estimated (K-line gaps): amount IS per_share directly

    Deduplication: Entries with ex_date within 5 days are treated as the same
    dividend event. Statement source preferred over web over estimated.

    TTM window: Rolling 365-day lookback from TODAY (current date).
    Uses ex_date (除权日) for window filtering to align with price adjustments.
    This ensures DY updates daily as the lookback window advances, rather than
    freezing after the most recent ex-date.

    Validation:
      - Per-share cap: 0.01 ~ 5.0 元 (sanity range for A-shares)
      - Total TTM per_share cap: 10.0 元 (prevents extreme anomalies)
      - current_price <= 0 → return 0.0
      - Returns percentage value (e.g. 5.2 means 5.2%)
    """
    if not current_price or current_price <= 0:
        return 0.0

    db = sqlite3.connect(DB_PATH, timeout=10)
    db.row_factory = sqlite3.Row

    # Query with price and source — CRITICAL for correct per_share by source type
    div_rows = db.execute(
        "SELECT date, amount, price, source, "
        "COALESCE(ex_date, date(date, '-3 days')) as ex_date "
        "FROM dividends WHERE code=? ORDER BY date DESC",
        [code]
    ).fetchall()

    # Step 1: Build normalized dividend events with correct per_share
    from db_helper import _get_dividend_per_share, _deduplicate_dividend_events

    events = []
    for r in div_rows:
        source = r['source'] if r['source'] else 'statement'
        amount = float(r['amount']) if r['amount'] else 0.0
        price = float(r['price']) if r['price'] else None
        ex_date = r['ex_date'] if r['ex_date'] else r['date']

        ps = _get_dividend_per_share(code, r['date'], amount, price, source)
        if ps <= 0:
            continue
        events.append({
            'date': r['date'],
            'ex_date': ex_date,
            'per_share': ps,
            'source': source,
            'amount': amount,
        })

    # Step 2: Fallback to K-line estimation if no recorded dividends
    if not events:
        try:
            from db_helper import _estimate_dividends_from_kline
            estimated = _estimate_dividends_from_kline(code)
            if estimated:
                events = [{
                    'date': e['date'],
                    'ex_date': e['date'],
                    'per_share': e['per_share'],
                    'source': 'ttm_calculated',
                    'amount': e['per_share'],
                } for e in estimated]
        except ImportError:
            pass

    if not events:
        db.close()
        return 0.0

    # Step 3: Deduplicate — same dividend event from multiple sources
    # TTM mode: prefer web data for accurate per_share (not affected by
    # record_date estimation errors in statement-based computation)
    events = _deduplicate_dividend_events(events, ttm_mode=True)

    # Step 4: TTM window filter — anchored at TODAY (rolling window)
    # FIXED: Previously anchored at latest_ex which caused DY to freeze
    # after the most recent ex-date. Now uses rolling 365-day lookback from
    # today, so the window advances every day.
    today = datetime.now()
    cutoff = today - timedelta(days=365)

    # Step 5: Sum per_share for events within TTM window
    total_per_share = 0.0
    for e in events:
        try:
            ex_dt = datetime.strptime(e['ex_date'][:10], '%Y-%m-%d')
        except (ValueError, TypeError):
            continue
        if ex_dt >= cutoff:
            total_per_share += e['per_share']

    db.close()

    # Step 6: Final validation
    if total_per_share <= 0:
        return 0.0

    # Hard cap: TTM per_share > 10 is unrealistic (even 10 means ~50% DY)
    MAX_TTM_PER_SHARE = 10.0
    if total_per_share > MAX_TTM_PER_SHARE:
        print(f"  [WARN] {code}: TTM per_share={total_per_share:.2f} exceeds cap "
              f"{MAX_TTM_PER_SHARE}, capping", file=sys.stderr)
        total_per_share = MAX_TTM_PER_SHARE

    # Return as percentage (e.g. 5.23 means 5.23%)
    return round(total_per_share / current_price * 100, 2)


def main():
    db = get_db()
    db.row_factory = sqlite3.Row

    # Collect all stocks we care about: positions + watchlist
    codes = set()
    name_map = {}

    for r in db.execute("SELECT code, name FROM positions").fetchall():
        codes.add(r['code'])
        name_map[r['code']] = r['name']

    for r in db.execute("SELECT code, name FROM watchlist").fetchall():
        codes.add(r['code'])
        name_map[r['code']] = r['name']

    db.close()

    if not codes:
        print(json.dumps({"success": False, "error": "No stocks to refresh"}, ensure_ascii=False))
        return

    print(f"[refresh_quotes] Refreshing {len(codes)} stocks...", file=sys.stderr)

    quotes = {}
    success_count = 0
    fail_count = 0

    for code in codes:
        # Determine market prefix
        if code.startswith('6'):
            market_code = f'sh{code}'
        elif code.startswith('0') or code.startswith('3'):
            market_code = f'sz{code}'
        elif code.startswith('4') or code.startswith('8'):
            market_code = f'bj{code}'
        else:
            market_code = f'sh{code}'

        bars = fetch_latest_kline(market_code, limit=3)
        if not bars:
            print(f"  {name_map.get(code, code)}({code}): FAILED", file=sys.stderr)
            fail_count += 1
            continue

        latest = bars[0]  # [date, open, close, high, low, volume]
        price = latest[2]  # close price
        prev_close = bars[1][2] if len(bars) > 1 else price
        change = round(price - prev_close, 2) if prev_close else 0
        dy = calc_dividend_yield(code, price)

        quotes[code] = {
            'price': price,
            'change': change,
            'open': latest[1],
            'high': latest[3],
            'low': latest[4],
            'volume': latest[5],   # 成交量（手）
            'pe': 0,   # Not available from K-line data alone
            'pb': 0,
            'dy': dy,
        }
        success_count += 1
        print(f"  {name_map.get(code, code)}({code}): ¥{price}  DY={dy}%", file=sys.stderr)

    # Persist to DB
    if quotes:
        try:
            upsert_quotes(quotes)
        except Exception as e:
            print(f"  DB write failed: {e}", file=sys.stderr)

    result = {
        "success": True,
        "data": quotes,
        "count": len(quotes),
        "refreshed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "stats": {"total": len(codes), "success": success_count, "failed": fail_count},
    }
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
