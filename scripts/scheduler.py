"""
Scheduler: 定时任务调度引擎
执行周期：DAILY(每个交易日15:35) / WEEKLY(每周一09:00) / ON_UPLOAD(对账单上传后)

数据源与频率:
┌─────────────────────┬──────────────┬─────────────────────────┬─────────────────────┐
│ 数据模块            │ 更新频率     │ 数据源                  │ 脚本                │
├─────────────────────┼──────────────┼─────────────────────────┼─────────────────────┤
│ kline_daily (日K)   │ 每日 15:35   │ westock-data Node插件  │ sync_all.py Step2   │
│ daily_predictions   │ 每日 15:35   │ 计算(来自kline+信号)   │ sync_all.py Step6   │
│ learning_params     │ 每日 15:35   │ 自学习算法(MWU/EG)     │ sync_all.py Step5   │
│ accuracy_stats      │ 每日 15:35   │ 准确率重算              │ sync_all.py Step4   │
│ quotes (行情)       │ 每日 15:35   │ 从K线最新价获取         │ sync_all.py Step7   │
│ news (新闻)         │ 每日 09:00   │ NeoData (westock-data) │ fetch_news.py       │
│ expert_reports      │ 每周一 09:00 │ WorkBuddy多Agent        │ 需手动触发          │
│ 持仓/交易/费用       │ ON_UPLOAD    │ 广发对账单.xlsx          │ update_from_statement│
│ seasonal (季节性)   │ 每日 15:35   │ 同月K线同步生成         │ sync_all.py Step7   │
│ watchlist           │ ON_ADD/DEL   │ Web管理页               │ server.py API       │
└─────────────────────┴──────────────┴─────────────────────────┴─────────────────────┘

触发链:
  addStock/removeStock → sync_all.py → reinject → location.reload()
  upload statement → update_from_statement.py → reinject → location.reload()
  定时 Daily → sync_all.py (7步骤全量同步含自学习) → reinject
  定时 Weekly → 提醒运行专家分析
"""
import json, subprocess, os, sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PYTHON = r'C:\Users\28312\.workbuddy\binaries\python\versions\3.12.6\python.exe'

def run(name, timeout=60):
    script = os.path.join(ROOT, 'scripts', name)
    if not os.path.exists(script):
        print(f"  [SKIP] {name} not found")
        return False
    try:
        r = subprocess.run([PYTHON, script], cwd=ROOT, capture_output=True, text=True, timeout=timeout)
        ok = r.returncode == 0
        status = 'OK' if ok else 'FAIL'
        print(f"  [{status}] {name}")
        if r.stdout: print(f"    stdout: {r.stdout.strip()[-200:]}")
        if r.stderr: print(f"    stderr: {r.stderr.strip()[-200:]}")
        return ok
    except subprocess.TimeoutExpired:
        print(f"  [TIMEOUT] {name}")
        return False

def rebuild_html():
    """Always reinject data into HTML after any data change"""
    return run('reinject_from_db.py', 15)

def task_sync_all():
    """Daily: sync kline + predictions + reinject for all stocks"""
    print(f"\n{'='*50}")
    print(f"TASK: sync_all — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*50}")
    ok = run('sync_all.py', 180)
    if ok:
        # Step 2: Auto-execute paper trading (independent script)
        print(f"\n  → Running paper_trading auto (independent step)")
        task_paper_trading()
    return ok

def task_paper_trading():
    """Run paper trading auto-execute as an independent step."""
    print(f"\n{'='*50}")
    print(f"TASK: paper_trading — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*50}")

    # Market time check — skip if market is closed
    try:
        from market_utils import is_market_open as _open
        if not _open():
            print(f"  [SKIP] Market closed. Skipping paper trading auto-execute.")
            return True
    except ImportError:
        pass  # market_utils not available, proceed anyway

    return run('paper_trading.py auto', 30)

def task_statement_update():
    """On upload: parse broker statement"""
    print(f"\n{'='*50}")
    print(f"TASK: update_statement — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*50}")
    ok = run('update_from_statement.py', 30)
    if ok:
        ok2 = rebuild_html()
        return ok2
    return False

def task_intraday_collect():
    """Run intraday data collection (single pass)."""
    print(f"\n{'='*50}")
    print(f"TASK: intraday_collect — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*50}")
    script = os.path.join(ROOT, 'scripts', 'collect_intraday.py')
    try:
        r = subprocess.run([PYTHON, script, 'once'], cwd=ROOT, capture_output=True, text=True, timeout=60)
        ok = r.returncode == 0
        print(f"  {'OK' if ok else 'FAIL'} intraday_collect")
        if r.stderr.strip(): print(f"  stderr: {r.stderr.strip()[-400:]}")
        return ok
    except subprocess.TimeoutExpired:
        print(f"  [TIMEOUT] intraday_collect")
        return False


# ===== CLI =====
if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('task', choices=['sync','statement','paper','intraday'], default='sync')
    args = ap.parse_args()

    if args.task == 'sync':
        task_sync_all()
    elif args.task == 'statement':
        task_statement_update()
    elif args.task == 'paper':
        task_paper_trading()
    elif args.task == 'intraday':
        task_intraday_collect()
