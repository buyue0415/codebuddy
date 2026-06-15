"""
Full data sync: refresh ALL modules for ALL watchlist stocks.
Runs: kline fetch → predictions → reinject HTML.
Called by: add/remove stock API, scheduler, manual trigger.
"""
import json, math, subprocess, re, os
from datetime import datetime
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NODE = r'C:\Users\28312\.workbuddy\binaries\node\versions\22.12.0\node.exe'
WESTOCK = r'C:\Users\28312\.workbuddy\plugins\marketplaces\cb_teams_marketplace\plugins\finance-data\skills\westock-data'
SCRIPT = 'scripts/index.js'

TODAY = datetime.now().strftime("%Y-%m-%d")

# Load data
with open(os.path.join(ROOT, 'data', 'system_data.json'), 'r', encoding='utf-8') as f:
    d = json.load(f)

watchlist = d.get('watchlist', [])
print(f"[sync_all] Watchlist: {len(watchlist)} stocks")

# ===== Step 1: Fetch daily K-line for all stocks =====
print("\n[Step 1] Fetching daily K-line...")
d['kline_daily'] = d.get('kline_daily', {})

def fetch_kline(market_code, limit=200):
    try:
        result = subprocess.run(
            [NODE, SCRIPT, 'kline', market_code, '--period', 'day', '--limit', str(limit), '--fq', 'qfq'],
            cwd=WESTOCK, capture_output=True, text=True, timeout=30
        )
        data = []
        for line in result.stdout.strip().split('\n'):
            parts = [p.strip() for p in line.split('|') if p.strip()]
            if len(parts) >= 5 and re.match(r'\d{4}-\d{2}-\d{2}', parts[0]):
                data.append([parts[0], float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4])])
        return data
    except Exception as e:
        print(f"  K-line fetch error: {e}")
        return []

for stock in watchlist:
    code, name, mkt = stock['code'], stock['name'], stock.get('market', 'sh')
    kdata = fetch_kline(f'{mkt}{code}')
    if kdata:
        d['kline_daily'][code] = [[k[0], k[1], k[2], k[3], k[4]] for k in kdata]
        print(f"  {name}({code}): {len(kdata)} bars")
    else:
        print(f"  {name}({code}): FAILED")

# ===== Step 2: Generate daily predictions =====
print("\n[Step 2] Generating predictions...")

def calc_signals(kdata):
    if len(kdata) < 14:
        return None
    closes = [k[2] for k in kdata]; highs = [k[3] for k in kdata]; lows = [k[4] for k in kdata]
    close = closes[0]

    n_atr = min(14, len(kdata)-1)
    atr = sum(max(highs[i]-lows[i], abs(highs[i]-closes[i+1]), abs(lows[i]-closes[i+1])) for i in range(n_atr))/n_atr

    n_rsi = min(14, len(closes)-1)
    gains = sum(max(closes[i]-closes[i+1],0) for i in range(n_rsi))
    losses = sum(max(closes[i+1]-closes[i],0) for i in range(n_rsi))
    rs = (gains/n_rsi)/(losses/n_rsi) if losses>0 else 100
    rsi = 100-100/(1+rs)

    ema12=sum(closes[:12])/12; ema26=sum(closes[:26])/26
    macd_val=ema12-ema26; macd_pct=(macd_val/close)*100

    n_bb=min(20,len(closes)); bb_ma=sum(closes[:n_bb])/n_bb
    bb_std=math.sqrt(sum((x-bb_ma)**2 for x in closes[:n_bb])/n_bb)
    bb_upper,bb_lower=bb_ma+2*bb_std,bb_ma-2*bb_std
    if close>bb_upper*0.98: bb_dir,bb_pos='bearish','上轨附近'
    elif close<bb_lower*1.02: bb_dir,bb_pos='bullish','下轨附近'
    else: bb_dir,bb_pos='neutral','中轨附近'

    n_kdj=min(9,len(kdata)); kd_h,kd_l=max(highs[:n_kdj]),min(lows[:n_kdj])
    rsv=((close-kd_l)/(kd_h-kd_l))*100 if kd_h!=kd_l else 50
    k_val=50*0.67+rsv*0.33; d_val=50*0.67+k_val*0.33; j_val=3*k_val-2*d_val

    month=datetime.now().month
    sf={1:0.95,2:0.88,3:0.97,4:1.02,5:0.92,6:0.90,7:1.08,8:1.03,9:0.98,10:1.05,11:0.93,12:0.87}.get(month,1.0)

    chg_5d=((closes[0]/closes[5])-1)*100 if len(closes)>5 else 0

    return {'close':close,'atr':round(atr,3),
        'signals':{'macd':{'value':f'{macd_pct:+.2f}%','direction':'bullish' if macd_val>0 else 'bearish','raw':round(macd_pct,2)},
                  'rsi':{'value':round(rsi,1),'direction':'bullish' if rsi>55 else 'bearish' if rsi<45 else 'neutral','raw':round(rsi,1)},
                  'bollinger':{'position':bb_pos,'direction':bb_dir,'upper':round(bb_upper,2),'lower':round(bb_lower,2)},
                  'kdj':{'k':round(k_val,0),'d':round(d_val,0),'j':round(j_val,0),'direction':'bearish' if j_val>80 else 'bullish' if j_val<20 else 'neutral'},
                  'seasonal':{'note':f'{month}月季节性{"偏多" if sf>1 else "偏弱"}','direction':'bullish' if sf>1 else 'bearish','factor':sf},
                  'atr':{'value':round(atr,3),'pct':round(atr/close*100,2),'direction':'neutral','raw':round(atr,3)},
                  'money_flow':{'direction':'bullish' if chg_5d>2 else 'bearish' if chg_5d<-2 else 'neutral','note':'近5日'+('上涨' if chg_5d>0 else '下跌')}}}

SIGNALS=['macd','rsi','bollinger','kdj','seasonal','atr','money_flow']
BLOCKS=['09:30-10:30','10:30-11:30','13:00-14:00','14:00-15:00','next_day']

def new_lp():
    return {'signal_weights':{s:{b:1.0 for b in BLOCKS} for s in SIGNALS},
            'hourly_bias':{b:0.0 for b in BLOCKS},'seasonal_adj':{str(m):0.0 for m in range(1,13)},
            'confidence_beta':{'bullish':{'alpha':1,'beta':1},'bearish':{'alpha':1,'beta':1},'neutral':{'alpha':1,'beta':1}},
            'learning_rate':0.01,'mw_beta':0.7,'update_count':0}

def gen_pred(code, info, lp):
    close=info['close'];atr=info['atr'];sig=info['signals']
    w=lp['signal_weights'];bias=lp['hourly_bias'];sa=lp['seasonal_adj']
    ws=sum(w[s]['next_day']*(1 if sig[s]['direction']=='bullish' else -1 if sig[s]['direction']=='bearish' else 0) for s in SIGNALS)
    ws+=sa.get(str(datetime.now().month),0)*2
    dd='bullish' if ws>0.5 else 'bearish' if ws<-0.5 else 'neutral'
    cb=lp['confidence_beta'].get(dd,{'alpha':1,'beta':1})
    conf=max(0.4,round(cb['alpha']/(cb['alpha']+cb['beta']),2))
    dr=atr*2.5;nh,nl=round(close+dr*0.6,2),round(close-dr*0.4,2)
    hws=[('09:30-10:30',0.35,'开盘消化隔夜信息'),('10:30-11:30',0.20,'横盘整理'),('13:00-14:00',0.20,'午后资金活跃'),('14:00-15:00',0.25,'尾盘主力动作')]
    cum=close;hp=[]
    for block,pct,note in hws:
        sd=dr*pct
        hs=sum(w[s][block]*(1 if sig[s]['direction']=='bullish' else -1 if sig[s]['direction']=='bearish' else 0) for s in SIGNALS)+bias.get(block,0)*2
        hd='bullish' if hs>0.3 else 'bearish' if hs<-0.3 else 'neutral'
        off=close*bias.get(block,0)*2
        hh,hl,hc=round(cum+sd*0.5+off,2),round(cum-sd*0.5+off,2),round(cum+off,2)
        hp.append({'block':block,'pred_open':round(cum,2) if not hp else round(hp[-1]['pred_close'],2),
                   'pred_high':min(hh,nh),'pred_low':max(hl,nl),'pred_close':hc,
                   'direction':hd,'strength':min(5,max(1,int(abs(hs)))),'note':note})
        cum=hc
    adv='低吸为主' if dd=='bullish' else '观望为主' if dd=='neutral' else '逢高减仓'
    return {'date':TODAY,'code':code,'prev_close':close,
            'next_day':{'direction':dd,'confidence':conf,'high':nh,'low':nl,'advice':adv,'entry_zone':nl if dd=='bullish' else nh},
            'hourly':hp,'signals':sig,
            'actual':{'open':None,'high':None,'low':None,'close':None,'next_day_direction_hit':None,'daily_range_hit':None,'hourly_hits':[None]*4}}

# Init learning params
d['learning_params'] = d.get('learning_params', {})
d['daily_predictions'] = [p for p in d.get('daily_predictions', []) if p['date'] != TODAY]
d['accuracy_stats'] = d.get('accuracy_stats', {})

empty_acc = {
    'last_20':{'direction':{'correct':0,'total':0,'rate':0},'range':{'correct':0,'total':0,'rate':0},
               'hourly':{b:0 for b in BLOCKS[:4]}},
    'last_60':{'direction':{'correct':0,'total':0,'rate':0},'range':{'correct':0,'total':0,'rate':0},
               'hourly':{b:0 for b in BLOCKS[:4]}}
}

for stock in watchlist:
    code = stock['code']
    kdata = d.get('kline_daily', {}).get(code, [])
    if not kdata:
        print(f"  {stock['name']}({code}): no kline data, skip")
        continue
    info = calc_signals(kdata)
    if not info:
        print(f"  {stock['name']}({code}): insufficient kline data")
        continue
    if code not in d['learning_params']:
        d['learning_params'][code] = new_lp()
    if code not in d['accuracy_stats']:
        d['accuracy_stats'][code] = dict(empty_acc)

    pred = gen_pred(code, info, d['learning_params'][code])
    d['daily_predictions'].append(pred)
    print(f"  {stock['name']}({code}): {pred['next_day']['direction']} conf={pred['next_day']['confidence']:.0%}")

d['daily_predictions'] = sorted(d['daily_predictions'], key=lambda p: p['date'])[-90 * len(watchlist):]
d['generated'] = TODAY

# ===== Step 2.5: Fill seasonal + monthly kline for new stocks =====
DEFAULT_SEASONAL = [0.8, -2.5, 1.2, 0.5, -1.0, 2.3, 3.5, -1.8, 1.5, 2.8, -1.2, 3.0]
d['seasonal'] = d.get('seasonal', {})
d['kline'] = d.get('kline', {})
d['quotes'] = d.get('quotes', {})

for stock in watchlist:
    code = stock['code']
    # Default seasonal if missing
    if code not in d['seasonal']:
        d['seasonal'][code] = DEFAULT_SEASONAL.copy()
        print(f"  {stock['name']}({code}): set default seasonal")
    # Generate monthly kline from daily
    if code not in d['kline'] and code in d.get('kline_daily', {}):
        daily = d['kline_daily'][code]
        monthly = {}
        for bar in daily:
            m = bar[0][:7]
            if m not in monthly:
                monthly[m] = {'open': bar[1], 'high': bar[3], 'low': bar[4], 'close': bar[2], 'vol': 0}
            monthly[m]['high'] = max(monthly[m]['high'], bar[3])
            monthly[m]['low'] = min(monthly[m]['low'], bar[4])
            monthly[m]['close'] = bar[2]
            monthly[m]['vol'] += 1
        d['kline'][code] = [[f"{m}-01", v['open'], v['high'], v['low'], v['close'], v['vol'], 0.0]
                              for m, v in sorted(monthly.items())]
        print(f"  {stock['name']}({code}): generated {len(d['kline'][code])} monthly bars")
    # Default quote from latest kline
    if code not in d['quotes'] and code in d.get('kline_daily', {}):
        kd = d['kline_daily'][code]
        if kd:
            latest = kd[0]
            d['quotes'][code] = {"price": latest[2], "change": 0, "open": latest[1],
                                  "high": latest[3], "low": latest[4], "pe": 0, "pb": 0, "dy": 0}
            print(f"  {stock['name']}({code}): set quote from kline")

# ===== Step 3: Save & reinject =====
with open(os.path.join(ROOT, 'data', 'system_data.json'), 'w', encoding='utf-8') as f:
    json.dump(d, f, ensure_ascii=False, indent=2)
print(f"\n[Step 3] system_data.json saved")

# Reinject into HTML
with open(os.path.join(ROOT, 'deliverables', 'bank-stock-system.html'), 'r', encoding='utf-8') as f:
    html = f.read()
data_json = json.dumps(d, ensure_ascii=False, separators=(',', ':'))
html = re.sub(r'const DATA = \{.*?\};\n', 'const DATA = ' + data_json + ';\n', html, flags=re.DOTALL)
with open(os.path.join(ROOT, 'deliverables', 'bank-stock-system.html'), 'w', encoding='utf-8') as f:
    f.write(html)
print(f"[Step 4] HTML reinjected")

print(f"\n[sync_all] Done. {len(watchlist)} stocks, {len(d['daily_predictions'])} predictions.")
