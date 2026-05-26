"""System audit - queries SQLite directly (migrated from legacy JSON)."""
import json, os, sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
from db_helper import get_watchlist, get_db

wl = get_watchlist()
today = datetime.now().strftime('%Y-%m-%d')

print('='*60)
print('系统审计 v0.3 (SQLite驱动)')
print('='*60)
print(f'监控股票: {[(s["code"], s["name"]) for s in wl]}')
print(f'审计日期: {today}')
print()

print('--- quotes ---')
for s in wl:
    db = get_db()
    r = db.execute("SELECT * FROM quotes WHERE code=?", [s['code']]).fetchone()
    db.close()
    if r:
        print(f'  {s["name"]}({s["code"]}): price={r["price"]} change={r["change"]}%')
    else:
        print(f'  {s["name"]}({s["code"]}): MISSING')

print('\n--- kline_daily ---')
for s in wl:
    db = get_db()
    rows = db.execute("SELECT date, open, close, high, low FROM kline_daily WHERE code=? ORDER BY date DESC", [s['code']]).fetchall()
    db.close()
    if rows:
        print(f'  {s["name"]}: {len(rows)} bars, {rows[-1][0]} -> {rows[0][0]}')
    else:
        print(f'  {s["name"]}: MISSING')

print('\n--- daily_predictions ---')
for s in wl:
    db = get_db()
    preds = db.execute(
        "SELECT date, direction, actual_close, dir_hit FROM daily_predictions WHERE code=? ORDER BY date DESC",
        [s['code']]
    ).fetchall()
    db.close()
    if preds:
        latest = preds[0]
        has_act = latest['actual_close'] is not None
        print(f'  {s["name"]}: {len(preds)} preds, latest={latest["date"]} dir={latest["direction"]} actual={"YES" if has_act else "pending"}')
    else:
        print(f'  {s["name"]}: NO predictions')

print('\n--- learning_params ---')
for s in wl:
    db = get_db()
    r = db.execute("SELECT update_count, mw_beta, learning_rate FROM learning_params WHERE code=?", [s['code']]).fetchone()
    db.close()
    if r:
        print(f'  {s["name"]}: update_count={r["update_count"]} mw_beta={r["mw_beta"]} lr={r["learning_rate"]}')
    else:
        print(f'  {s["name"]}: MISSING')

print('\n--- accuracy_stats ---')
for s in wl:
    db = get_db()
    r = db.execute("SELECT dir_correct, dir_total, dir_rate FROM accuracy_stats WHERE code=? AND period='last_20'", [s['code']]).fetchone()
    db.close()
    if r:
        print(f'  {s["name"]}: dir={r["dir_correct"]}/{r["dir_total"]} rate={r["dir_rate"]:.0f}%')
    else:
        print(f'  {s["name"]}: MISSING')

print('\n--- 其他 ---')
db = get_db()
pos_count = db.execute("SELECT COUNT(*) as c FROM positions").fetchone()['c']
closed_count = db.execute("SELECT COUNT(*) as c FROM closed_positions").fetchone()['c']
trade_count = db.execute("SELECT COUNT(*) as c FROM trades").fetchone()['c']
news_count = db.execute("SELECT COUNT(*) as c FROM news").fetchone()['c']
report_count = db.execute("SELECT COUNT(*) as c FROM expert_reports").fetchone()['c']
km_bars = db.execute("SELECT COUNT(*) as c FROM kline_monthly").fetchone()['c']
db.close()
print(f'  positions: {pos_count} current + {closed_count} closed')
print(f'  trades: {trade_count} total')
print(f'  news: {news_count} items')
print(f'  expert_reports: {report_count} reports')
print(f'  kline(月度): {km_bars} bars')
