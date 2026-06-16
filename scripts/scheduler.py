import json, subprocess, os, sys, math
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
from env_paths import get_python, get_node, get_westock
PYTHON = get_python()
NODE = get_node()
WESTOCK = get_westock()

_TRADING_DAY_CHECK = None
def _is_trading_day():
    global _TRADING_DAY_CHECK
    if _TRADING_DAY_CHECK is None:
        try:
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
    if not _is_trading_day(): return
    from db_helper import (get_watchlist, upsert_kline_daily, upsert_kline_monthly,
                           upsert_quotes, upsert_seasonal, clear_stock_predictions,
                           insert_daily_predictions_batch, upsert_learning_params,
                           upsert_accuracy_stats)
    from db_helper import get_db
    from signals import calc_signals, gen_multi_day_pred, new_lp, SIGNALS, BLOCKS
    SCRIPT = 'scripts/index.js'
    TODAY = datetime.now().strftime("%Y-%m-%d")

    def fetch_kline(market_code, limit=2000):
        try:
            result = subprocess.run([NODE,SCRIPT,'kline',market_code,'--period','day','--limit',str(limit),'--fq','qfq'],
                                    cwd=WESTOCK,capture_output=True,timeout=30)
            stdout = result.stdout
            if stdout:
                try: text = stdout.decode('gbk')
                except: text = stdout.decode('utf-8',errors='replace')
            else: text = ''
            data = []
            for line in text.strip().split('\n'):
                parts = [p.strip() for p in line.split('|') if p.strip()]
                if len(parts) >= 5 and parts[0][:4].isdigit():
                    data.append([parts[0],float(parts[1]),float(parts[2]),float(parts[3]),float(parts[4])])
            return data
        except: return []

    watchlist = get_watchlist()
    print(f"[scheduler] Sync all: {len(watchlist)} stocks")

    # Step 1: Fetch K-line in parallel (2000 bars each)
    print("[scheduler] Fetching K-line (limit=2000)...")
    kline_results = {}
    if watchlist:
        def sync_one(stock):
            code,mkt=stock['code'],stock.get('market','sh')
            kdata=fetch_kline(f'{mkt}{code}')
            if kdata:
                bars=[[k[0],k[1],k[2],k[3],k[4]] for k in kdata]
                upsert_kline_daily(code,bars)
                print(f"  {stock['name']}({code}): {len(kdata)} bars")
            else:
                bars=[]
                print(f"  {stock['name']}({code}): FAILED")
            return code,bars
        max_w=min(len(watchlist),4)
        with ThreadPoolExecutor(max_workers=max_w) as pool:
            for fut in as_completed({pool.submit(sync_one,s):s for s in watchlist}):
                code,bars=fut.result();kline_results[code]=bars

    # Step 2: Generate multi-day predictions (10 days each)
    print("[scheduler] Generating 10-day predictions (signals.py)...")
    empty_acc={'last_20':{'direction':{'correct':0,'total':0,'rate':0},'range':{'correct':0,'total':0,'rate':0},'hourly':{b:0 for b in BLOCKS[:4]}},'last_60':{'direction':{'correct':0,'total':0,'rate':0},'range':{'correct':0,'total':0,'rate':0},'hourly':{b:0 for b in BLOCKS[:4]}}}
    new_preds = []       # flat list of pred dicts for batch insert
    new_learn = []       # (code, lp) pairs for learning params
    for stock in watchlist:
        code=stock['code'];kdata=kline_results.get(code,[])
        if not kdata:
            print(f"  {stock['name']}({code}): skip - no kline data")
            continue
        info=calc_signals(kdata)
        if not info:
            print(f"  {stock['name']}({code}): skip - insufficient data")
            continue
        lp=new_lp()
        preds=gen_multi_day_pred(code,kdata,info,lp,num_days=10)
        if preds:
            new_preds.extend(preds)
            new_learn.append((code,lp))
            print(f"  {stock['name']}({code}): {len(preds)} days ({preds[0]['next_day']['direction']}→{preds[-1]['next_day']['direction']})")
        else:
            print(f"  {stock['name']}({code}): prediction generation failed")

    # Only clear old predictions for stocks that successfully regenerated
    if new_preds:
        success_codes = set(p['code'] for p in new_preds)
        for code in success_codes:
            try:
                clear_stock_predictions(code, TODAY)
                print(f"  Cleared old predictions for {code}")
            except Exception as e:
                print(f"  Clear predictions for {code} failed: {e}")
        insert_daily_predictions_batch(new_preds)
        for code,lp in new_learn:
            try: upsert_learning_params(code,lp)
            except: pass
            for period in ('last_20','last_60'):
                try: upsert_accuracy_stats(code,period,empty_acc[period])
                except: pass
        print(f"  Written {len(new_preds)} predictions across {len(new_learn)} stocks")
    else:
        print("  No predictions generated - keeping old predictions intact")

    # Step 3: Monthly + seasonal + quotes
    DEFAULT_SEASONAL=[0.8,-2.5,1.2,0.5,-1.0,2.3,3.5,-1.8,1.5,2.8,-1.2,3.0]
    for stock in watchlist:
        code=stock['code']
        db=get_db()
        has_monthly=db.execute("SELECT COUNT(*) FROM kline_monthly WHERE code=?",[code]).fetchone()[0]>0
        db.close()
        if not has_monthly and code in kline_results and kline_results[code]:
            daily=kline_results[code];monthly={}
            for bar in daily:
                m=bar[0][:7]
                if m not in monthly: monthly[m]={'open':bar[1],'high':bar[3],'low':bar[4],'close':bar[2],'vol':0}
                monthly[m]['high']=max(monthly[m]['high'],bar[3]);monthly[m]['low']=min(monthly[m]['low'],bar[4])
                monthly[m]['close']=bar[2];monthly[m]['vol']+=1
            sorted_months=sorted(monthly.items())
            bars_m=[]
            for i,(m,v) in enumerate(sorted_months):
                prev_close=sorted_months[i-1][1]['close'] if i>0 else v['close']
                cp=round((v['close']-prev_close)/prev_close*100,2) if prev_close else 0.0
                bars_m.append([f"{m}-01",v['open'],v['high'],v['low'],v['close'],v['vol'],cp])
            try: upsert_kline_monthly(code,bars_m)
            except Exception as e: print(f"  monthly write {code}: {e}")
        # 从该股票的实际月K线计算各月份平均涨跌幅（替代硬编码默认值）
        db=get_db()
        rows=db.execute("SELECT date,change_pct FROM kline_monthly WHERE code=? ORDER BY date",[code]).fetchall()
        db.close()
        if rows:
            mg={m:[] for m in range(1,13)}
            for r in rows:
                try: mg[int(r['date'][5:7])].append(r['change_pct'])
                except: pass
            seasonal=[]
            for m in range(1,13):
                vals=[v for v in mg[m] if v is not None]
                seasonal.append(round(sum(vals)/len(vals),2) if vals else 0.0)
        else:
            seasonal=DEFAULT_SEASONAL
        try: upsert_seasonal(code,seasonal)
        except: pass
        if code in kline_results and kline_results[code]:
            latest=kline_results[code][0]
            try: upsert_quotes({code:{'price':latest[2],'change':0,'open':latest[1],'high':latest[3],'low':latest[4],'pe':0,'pb':0,'dy':0}})
            except: pass

    # Step 4: Lightweight scripts
    run('refresh_quotes.py',timeout=120)
    run('fetch_news.py',timeout=120)
    run('fetch_dividends.py',timeout=120)
    print(f"[scheduler] Sync all done. {len(watchlist)} stocks.")

def fetch_news():
    if not _is_trading_day(): return
    run('fetch_news.py', timeout=300)

def intraday_collect():
    run('collect_intraday.py', timeout=120)

if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('task', nargs='?', default='all', choices=['all','sync','news','intraday'])
    args = ap.parse_args()
    if args.task in ('all','sync'): sync_all()
    if args.task in ('all','news'): fetch_news()
    if args.task in ('all','intraday'): intraday_collect()
