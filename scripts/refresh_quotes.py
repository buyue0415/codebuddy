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
        rows = db.execute(
            "SELECT sum(amount) as total FROM dividends WHERE code=? AND date >= date('now', '-1 year')",
            [code]
        ).fetchall()
        db.close()
        if rows and rows[0][0]:
            return round(rows[0][0] / price * 100, 2)
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
