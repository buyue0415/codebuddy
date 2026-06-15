"""
Scheduler: 定时任务调度引擎
执行周期：DAILY(每个交易日15:35) / WEEKLY(每周一09:00) / ON_UPLOAD(对账单上传后)

数据源与频率:
┌─────────────────────┬──────────────┬─────────────────────────┬─────────────────────┐
│ 数据模块            │ 更新频率     │ 数据源                  │ 脚本                │
├─────────────────────┼──────────────┼─────────────────────────┼─────────────────────┤
│ kline_daily (日K)   │ 每日 15:35   │ westock-data Node插件  │ sync_all.py Step1   │
│ daily_predictions   │ 每日 15:35   │ 计算(来自kline+信号)   │ sync_all.py Step2   │
│ learning_params     │ 每日 15:35   │ 自学习算法更新          │ daily_update.py     │
│ accuracy_stats      │ 每日 15:35   │ 准确率重算              │ daily_update.py     │
│ quotes (行情)       │ 实时/每日    │ 硬编码(需外部源)        │ daily_update.py     │
│ news (新闻)         │ 每日 09:00   │ 硬编码(需外部源)        │ daily_update.py     │
│ expert_reports      │ 每周一 09:00 │ WorkBuddy多Agent        │ 需手动触发          │
│ 持仓/交易/费用       │ ON_UPLOAD    │ 广发对账单.xlsx          │ update_from_statement│
│ seasonal (季节性)   │ 手动         │ 历史统计                │ 手动维护            │
│ watchlist           │ ON_ADD/DEL   │ Web管理页               │ server.py API       │
└─────────────────────┴──────────────┴─────────────────────────┴─────────────────────┘

触发链:
  addStock/removeStock → sync_all.py → reinject → location.reload()
  upload statement → update_from_statement.py → reinject → location.reload()
  定时 Daily → daily_update.py + sync_all.py → reinject
  定时 Weekly → 提醒运行专家分析
"""
import json, subprocess, os, sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PYTHON = r'C:\Users\28312\.workbuddy\binaries\python\versions\3.13.12\python.exe'

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
    return run('reinject_data.py', 10)

def task_sync_all():
    """Daily: sync kline + predictions + reinject for all stocks"""
    print(f"\n{'='*50}")
    print(f"TASK: sync_all — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*50}")
    ok = run('sync_all.py', 120)
    return ok

def task_daily_update():
    """Daily: update quotes, news, backfill predictions, self-learning"""
    print(f"\n{'='*50}")
    print(f"TASK: daily_update — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*50}")
    ok = run('daily_update.py', 60)
    return ok

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

# ===== CLI =====
if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('task', choices=['daily','sync','statement','all'], default='sync')
    args = ap.parse_args()

    if args.task == 'daily':
        task_daily_update()
    elif args.task == 'sync':
        task_sync_all()
    elif args.task == 'statement':
        task_statement_update()
    elif args.task == 'all':
        task_sync_all()
        task_daily_update()
