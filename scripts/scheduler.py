import json, subprocess, os, sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
from env_paths import get_python
PYTHON = get_python()
LOCK_FILE = os.path.join(ROOT, 'data', '.sync_lock')

_TRADING_DAY_CHECK = None
def _is_trading_day():
    global _TRADING_DAY_CHECK
    if _TRADING_DAY_CHECK is None:
        try:
            sys.path.insert(0, os.path.join(ROOT, 'scripts'))
            from fetch_news import is_trading_day
            _TRADING_DAY_CHECK = is_trading_day
        except ImportError:
            _TRADING_DAY_CHECK = lambda: datetime.now().weekday() < 5
    return _TRADING_DAY_CHECK()

def run(name, timeout=60):
    script = os.path.join(ROOT, 'scripts', name)
    if not os.path.exists(script):
        print(f"[scheduler] Script not found: {script}")
        return
    print(f"[scheduler] Running {name}...")
    result = subprocess.run(
        [PYTHON, script], cwd=ROOT, capture_output=True, text=True, timeout=timeout
    )
    ok = result.returncode == 0
    print(f"[scheduler] {name}: {'OK' if ok else 'FAILED'}")
    return result


def sync_all():
    if not _is_trading_day():
        return
    run('sync_all.py', timeout=600)


def fetch_news():
    if not _is_trading_day():
        return
    run('fetch_news.py', timeout=300)


def intraday_collect():
    run('collect_intraday.py', timeout=120)


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('task', nargs='?', default='all',
                    choices=['all', 'sync', 'news', 'intraday'])
    args = ap.parse_args()
    if args.task in ('all', 'sync'):
        sync_all()
    if args.task in ('all', 'news'):
        fetch_news()
    if args.task in ('all', 'intraday'):
        intraday_collect()
