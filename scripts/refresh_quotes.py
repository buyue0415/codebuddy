import os, sys, json, subprocess, sqlite3
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from env_paths import get_node, get_westock
NODE = get_node()
WESTOCK = get_westock()
SCRIPT = 'scripts/index.js'

from db_helper import upsert_quotes, get_db
DB_PATH = os.path.join(ROOT, 'data', 'stock.db')


def fetch_latest_kline(market_code: str, limit: int = 3) -> list:
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
        if text:
            for line in text.strip().split('\n'):
                parts = [p.strip() for p in line.split('|') if p.strip()]
                if len(parts) >= 5 and parts[0][:4].isdigit():
                    data.append([parts[0], float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4])])
        return data
    except Exception as e:
        return []


def calc_dividend_yield(code: str, price: float) -> float:
    if price <= 0:
        return 0
    try:
        db = get_db()
        div_rows = db.execute(
            "SELECT date, amount, price, source, "
            "COALESCE(ex_date, date(date, '-3 days')) as ex_date "
            "FROM dividends WHERE code=? AND "
            "COALESCE(ex_date, date(date, '-3 days')) >= date('now', '-1 year') AND "
            "COALESCE(ex_date, date(date, '-3 days')) < date('now') "
            "ORDER BY date DESC",
            [code]
        ).fetchall()
        db.close()
        if not div_rows:
            return 0

        # Use the same per_share calculation as db_helper._calc_dy_at_date
        from db_helper import _get_dividend_per_share

        raw_events = []
        for r in div_rows:
            source = r['source'] if r['source'] else 'statement'
            amount_ = float(r['amount']) if r['amount'] else 0.0
            div_price_ = float(r['price']) if r['price'] else None
            ps = _get_dividend_per_share(code, r['date'], amount_, div_price_, source)
            if ps <= 0:
                continue
            ex_date_ = r['ex_date'] if r['ex_date'] else r['date']
            raw_events.append({'ex_date': ex_date_, 'per_share': ps})

        # Dedup: same event within same month
        dedup = set()
        total_per_share = 0.0
        for ev in raw_events:
            key = ev['ex_date'][:7]
            if key in dedup:
                continue
            dedup.add(key)
            total_per_share += ev['per_share']

        # Sanity cap (same as _calc_dy_at_date)
        MAX_TTM = 10.0
        if total_per_share > MAX_TTM:
            total_per_share = MAX_TTM

        if total_per_share <= 0:
            return 0
        return round(total_per_share / price * 100, 2)
    except Exception:
        pass
    return 0


def refresh_all() -> dict:
    from db_helper import get_watchlist
    watchlist = get_watchlist()
    results = {}
    for stock in watchlist:
        code, mkt = stock['code'], stock.get('market', 'sh')
        kdata = fetch_latest_kline(f'{mkt}{code}')
        if kdata:
            latest = kdata[-1]
            price = latest[4]
            dy = calc_dividend_yield(code, price)
            results[code] = {
                'price': price, 'change': 0, 'open': latest[1],
                'high': latest[2], 'low': latest[3], 'pe': 0, 'pb': 0, 'dy': dy,
            }
    if results:
        upsert_quotes(results)
    return results


if __name__ == '__main__':
    result = refresh_all()
    print(json.dumps({'success': True, 'count': len(result)}, ensure_ascii=False))
