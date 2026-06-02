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
                data.append([parts[0], float(parts[1]), float(parts[2]),
                             float(parts[3]), float(parts[4])])
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
    """Calculate trailing 12-month dividend yield.

    Formula: (sum of per_share dividends in last 12 months / current_price) * 100

    per_share = dividend.amount / shares_held_before_dividend_date

    IMPORTANT: The dividends table's `price` column stores the stock market
    price on the ex-dividend date, NOT the per-share dividend amount.
    We MUST use `amount / shares` to compute the actual per-share dividend.

    Boundary conditions & validation:
      - current_price <= 0 → return 0.0
      - No dividends recorded → return 0.0
      - dividend amount <= 0 → skip (data error / corrupted entry)
      - shares held <= 0 at dividend date → skip (can't compute per_share)
      - TTM window: today - 365 days (not latest dividend date as anchor)
      - Returns percentage value (e.g. 5.2 means 5.2%)
    """
    if not current_price or current_price <= 0:
        return 0.0

    db = sqlite3.connect(DB_PATH, timeout=10)
    db.row_factory = sqlite3.Row

    # Get all dividends for this stock, newest first
    div_rows = db.execute(
        "SELECT date, amount FROM dividends WHERE code=? ORDER BY date DESC",
        [code]
    ).fetchall()

    if not div_rows:
        db.close()
        return 0.0

    # TTM window anchors on TODAY (not latest dividend date)
    today = datetime.now()
    cutoff = today - timedelta(days=365)

    total_per_share = 0.0

    for r in div_rows:
        # Parse dividend date
        try:
            div_date_str = r['date']
            if len(div_date_str) > 10:
                div_date_str = div_date_str[:10]
            div_date = datetime.strptime(div_date_str, '%Y-%m-%d')
        except (ValueError, IndexError, TypeError):
            continue

        # Only count dividends within the trailing 12-month window
        if div_date < cutoff:
            continue

        # Validate dividend amount
        try:
            amount = float(r['amount'])
        except (ValueError, TypeError):
            continue
        if amount <= 0:
            continue  # Skip zero/negative (data corruption)

        # Calculate shares held at RECORD DATE (股权登记日), NOT payment date.
        # In China A-shares, dividend eligibility is based on the record date,
        # which is typically 2-5 trading days BEFORE the payment date in the
        # broker statement. Using the payment date directly would overcount
        # shares bought between record date and payment date.
        # We subtract 2 calendar days as a conservative approximation.
        record_date_str = (div_date - timedelta(days=2)).strftime('%Y-%m-%d')
        buys = db.execute(
            "SELECT COALESCE(SUM(qty), 0) FROM trades "
            "WHERE code=? AND date<? AND type='证券买入'",
            [code, record_date_str]
        ).fetchone()[0]
        sells = db.execute(
            "SELECT COALESCE(SUM(ABS(qty)), 0) FROM trades "
            "WHERE code=? AND date<? AND type='证券卖出'",
            [code, record_date_str]
        ).fetchone()[0]
        shares = int(buys - sells)

        if shares <= 0:
            continue  # No shares held → can't compute per_share

        per_share = amount / shares
        total_per_share += per_share

    db.close()

    if total_per_share <= 0:
        return 0.0

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

        latest = bars[0]  # [date, open, close, high, low]
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
