"""Verify Step 1: Compare SQLite DB with source JSON data"""
import sqlite3, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, 'data', 'stock.db')

if not os.path.exists(DB):
    print("ERROR: stock.db not found. Run migrate_to_sqlite.py first.")
    sys.exit(1)

with open(os.path.join(ROOT, 'data', 'system_data.json'), 'r', encoding='utf-8') as f:
    sd = json.load(f)
with open(os.path.join(ROOT, 'data', 'a_stocks.json'), 'r', encoding='utf-8') as f:
    stocks_list = json.load(f)
with open(os.path.join(ROOT, 'data', 'watchlist.json'), 'r', encoding='utf-8') as f:
    wl = json.load(f)

db = sqlite3.connect(DB)
db.row_factory = sqlite3.Row

passed = 0; failed = 0

def check(name, actual, expected, detail=""):
    global passed, failed
    if actual == expected:
        passed += 1
        print("  [OK] {}: {} {} {}".format(name, actual, "(expected: {})".format(expected) if detail else "", detail))
    else:
        failed += 1
        print("  [FAIL] {}: got {}, expected {}".format(name, actual, expected))

print("="*60)
print("VERIFICATION: SQLite vs JSON")
print("="*60)

# 1. Stocks count
json_count = len(stocks_list)
db_count = db.execute("SELECT COUNT(*) as c FROM stocks").fetchone()['c']
check("stocks count", db_count, json_count)

# Watchlist
json_wl = len(wl['stocks'])
db_wl = db.execute("SELECT COUNT(*) as c FROM watchlist").fetchone()['c']
check("watchlist count", db_wl, json_wl)

# Kline daily
json_kd = sum(len(v) for v in sd.get('kline_daily', {}).values())
db_kd = db.execute("SELECT COUNT(*) as c FROM kline_daily").fetchone()['c']
check("kline_daily rows", db_kd, json_kd)

# Kline monthly
json_km = sum(len(v) for v in sd.get('kline', {}).values())
db_km = db.execute("SELECT COUNT(*) as c FROM kline_monthly").fetchone()['c']
check("kline_monthly rows", db_km, json_km)

# Quotes
json_q = len(sd.get('quotes', {}))
db_q = db.execute("SELECT COUNT(*) as c FROM quotes").fetchone()['c']
check("quotes count", db_q, json_q)

# Daily predictions
json_dp = len(sd.get('daily_predictions', []))
db_dp = db.execute("SELECT COUNT(*) as c FROM daily_predictions").fetchone()['c']
check("daily_predictions count", db_dp, json_dp)

# Trades
json_tr = len(sd.get('all_trades', []))
db_tr = db.execute("SELECT COUNT(*) as c FROM trades").fetchone()['c']
check("trades count", db_tr, json_tr)

# Positions
json_pos = len(sd.get('current_positions', {}))
db_pos = db.execute("SELECT COUNT(*) as c FROM positions").fetchone()['c']
check("current_positions count", db_pos, json_pos)

# Closed positions
json_cp = len(sd.get('closed_positions', {}))
db_cp = db.execute("SELECT COUNT(*) as c FROM closed_positions").fetchone()['c']
check("closed_positions count", db_cp, json_cp)

# News
json_nw = len(sd.get('news', []))
db_nw = db.execute("SELECT COUNT(*) as c FROM news").fetchone()['c']
check("news count", db_nw, json_nw)

# Expert reports
json_er = len(sd.get('expert_reports', []))
db_er = db.execute("SELECT COUNT(*) as c FROM expert_reports").fetchone()['c']
check("expert_reports count", db_er, json_er)

# Seasonal
json_se = len(sd.get('seasonal', {}))
db_se = db.execute("SELECT COUNT(*) as c FROM seasonal").fetchone()['c']
check("seasonal count", db_se, json_se)

# Learning params
json_lp = len(sd.get('learning_params', {}))
db_lp = db.execute("SELECT COUNT(*) as c FROM learning_params").fetchone()['c']
check("learning_params count", db_lp, json_lp)

# Accuracy stats
json_ac = len(sd.get('accuracy_stats', {}))
db_ac = db.execute("SELECT COUNT(DISTINCT code) as c FROM accuracy_stats").fetchone()['c']
check("accuracy_stats stocks", db_ac, json_ac)

# Sample data check
print("\n--- Sample data checks ---")

# Check first stock
first = stocks_list[0]
row = db.execute("SELECT * FROM stocks WHERE code=?", [first['code']]).fetchone()
check("stock sample: " + first['code'], row['name'], first['name'])

# Check first kline entry
for code in sd.get('kline_daily', {}):
    bars = sd['kline_daily'][code]
    if bars:
        row = db.execute("SELECT * FROM kline_daily WHERE code=? AND date=?", [code, bars[0][0]]).fetchone()
        check("kline daily sample close: " + code, row['close'], bars[0][2])
        break

# Check first trade
if sd.get('all_trades'):
    t = sd['all_trades'][0]
    row = db.execute("SELECT * FROM trades WHERE date=? AND code=? AND settlement=?", [t['date'], t['code'], t['settlement']]).fetchone()
    check("trade sample: " + t['code'], row['name'], t['name'])

# Check quotes
for code, q in sd.get('quotes', {}).items():
    row = db.execute("SELECT * FROM quotes WHERE code=?", [code]).fetchone()
    check("quote price: " + code, row['price'], q.get('price'))
    break

# ===== Summary =====
print("\n" + "="*60)
if failed == 0:
    print("ALL {} CHECKS PASSED - Step 1 complete".format(passed))
else:
    print("{} PASSED, {} FAILED - Please fix before proceeding".format(passed, failed))
    sys.exit(1)

db.close()
