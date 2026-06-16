"""每日预测同步运行器 — 带错误处理和日志"""
import subprocess, os, sys, time
from datetime import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
from env_paths import get_python
PYTHON = get_python()
LOG_PATH = os.path.join(ROOT, "data", "sync_log.txt")

def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except:
        pass

log("=== Daily Sync Runner START ===")
log("Running sync_all.py...")
start = time.time()
try:
    result = subprocess.run(
        [PYTHON, os.path.join(ROOT, "scripts", "sync_all.py")],
        cwd=ROOT, capture_output=True, text=True, timeout=300
    )
    elapsed = time.time() - start
    ok = result.returncode == 0
    if result.stdout:
        for line in result.stdout.strip().split("\n")[-20:]:
            print(f"  stdout: {line}")
    if result.stderr:
        for line in result.stderr.strip().split("\n")[-10:]:
            print(f"  stderr: {line}")
    log(f"sync_all.py {'OK' if ok else 'FAILED'} (exit={result.returncode}, {elapsed:.0f}s)")
except subprocess.TimeoutExpired:
    log("sync_all.py TIMEOUT after 300s")
    ok = False
except Exception as e:
    log(f"sync_all.py ERROR: {e}")
    ok = False

log("Checking for stale predictions...")
try:
    import sqlite3
    db = sqlite3.connect(os.path.join(ROOT, "data", "stock.db"))
    db.row_factory = sqlite3.Row
    today = datetime.now().strftime("%Y-%m-%d")
    stale = db.execute(
        "SELECT COUNT(*) as c FROM daily_predictions WHERE dir_hit IS NULL AND date < ?",
        [today]
    ).fetchone()
    sc = stale['c'] if stale else 0
    db.close()
    if sc > 0:
        log(f"Found {sc} stale predictions, running backfill...")
        result2 = subprocess.run(
            [PYTHON, os.path.join(ROOT, "_fix_backfill.py")],
            cwd=ROOT, capture_output=True, text=True, timeout=60
        )
        log(f"Backfill {'OK' if result2.returncode==0 else 'FAILED'}")
    else:
        log("No stale predictions found")
except Exception as e:
    log(f"Stale check error: {e}")

log("=== Daily Sync Runner DONE ===")
