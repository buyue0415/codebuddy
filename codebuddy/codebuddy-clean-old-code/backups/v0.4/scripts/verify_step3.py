"""Verify Step 3: Run sync_all.py and check DB was updated"""
import subprocess, sqlite3, json, sys, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PYTHON = r'C:\Users\28312\.workbuddy\binaries\python\versions\3.13.12\python.exe'

print("Running sync_all.py...")
r = subprocess.run([PYTHON, os.path.join(ROOT, 'scripts', 'sync_all.py')],
    cwd=ROOT, capture_output=True, text=True, timeout=120)
print(r.stdout[-500:] if r.stdout else 'No output')
if r.stderr:
    print("STDERR:", r.stderr[-300:])

print("\n=== Verifying DB was updated ===")
db = sqlite3.connect(os.path.join(ROOT, 'data', 'stock.db'))
passed = 0; failed = 0

def check(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1; print("  [OK] {} {}".format(name, detail))
    else:
        failed += 1; print("  [FAIL] {} {}".format(name, detail))

# Kline must have data for watchlist stocks
for code in ['601166', '600036', '600919']:
    cnt = db.execute("SELECT COUNT(*) FROM kline_daily WHERE code=?", [code]).fetchone()[0]
    check("kline_daily " + code, cnt > 0, "{} bars".format(cnt))

# Monthly kline
cnt = db.execute("SELECT COUNT(*) FROM kline_monthly WHERE code='601166'").fetchone()[0]
check("kline_monthly 601166", cnt > 0, "{} bars".format(cnt))

# Predictions for today
import datetime
today = datetime.datetime.now().strftime("%Y-%m-%d")
cnt = db.execute("SELECT COUNT(*) FROM daily_predictions WHERE date=?", [today]).fetchone()[0]
check("daily_predictions today", cnt > 0, "{} rows".format(cnt))

# Learning params
cnt_lp = db.execute("SELECT COUNT(*) FROM learning_params").fetchone()[0]
check("learning_params", cnt_lp >= 3, "{} stocks".format(cnt_lp))

# Seasonal
cnt = db.execute("SELECT COUNT(*) FROM seasonal").fetchone()[0]
check("seasonal", cnt >= 3, "{} stocks".format(cnt))

# Quotes
cnt = db.execute("SELECT COUNT(*) FROM quotes").fetchone()[0]
check("quotes", cnt >= 3, "{} stocks".format(cnt))

db.close()

print("\n" + "="*60)
if failed == 0:
    print("ALL {} CHECKS PASSED - Step 3 complete".format(passed))
else:
    print("{} PASSED, {} FAILED".format(passed, failed))
    sys.exit(1)
