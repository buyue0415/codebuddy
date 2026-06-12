"""
Refactored: iterate over watchlist instead of hardcoding stock codes.
"""
import json, math, subprocess, re
from datetime import datetime

BASE = r'C:\Users\28312\.workbuddy\plugins\marketplaces\cb_teams_marketplace\plugins\finance-data\skills\westock-data'
NODE = r'C:\Users\28312\.workbuddy\binaries\node\versions\22.12.0\node.exe'
SCRIPT = 'scripts/index.js'

# Load watchlist
with open('data/system_data.json', 'r', encoding='utf-8') as f:
    d = json.load(f)

watchlist = d.get('watchlist', [{'code': '601166', 'name': '兴业银行', 'market': 'sh'}])
print(f"Watchlist: {[(s['code'], s['name']) for s in watchlist]}")

def fetch_kline(market_code, limit=200):
    """Fetch daily K-line for a stock"""
    result = subprocess.run(
        [NODE, SCRIPT, 'kline', market_code, '--period', 'day', '--limit', str(limit), '--fq', 'qfq'],
        cwd=BASE, capture_output=True, text=True, timeout=30
    )
    lines = result.stdout.strip().split('\n')
    data = []
    for line in lines:
        parts = [p.strip() for p in line.split('|') if p.strip()]
        if len(parts) >= 5 and re.match(r'\d{4}-\d{2}-\d{2}', parts[0]):
            # parts: date, open, close, high, low, volume (optional)
            volume = float(parts[5]) if len(parts) >= 6 else 0
            data.append([parts[0], float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4]), volume])
    return data

def calc_signals(kdata):
    """Calculate all technical signals from daily K-line data"""
    closes = [k[2] for k in kdata]
    highs = [k[3] for k in kdata]
    lows = [k[4] for k in kdata]
    close = closes[0]
    
    # ATR(14)
    n_atr = min(14, len(kdata)-1)
    trs = [max(highs[i]-lows[i], abs(highs[i]-closes[i+1]), abs(lows[i]-closes[i+1])) for i in range(n_atr)]
    atr = sum(trs)/len(trs) if trs else close*0.01
    
    # RSI(14)
    n_rsi = min(14, len(closes)-1)
    gains = sum(max(closes[i]-closes[i+1], 0) for i in range(n_rsi))
    losses = sum(max(closes[i+1]-closes[i], 0) for i in range(n_rsi))
    rs = (gains/n_rsi)/(losses/n_rsi) if losses > 0 else 100
    rsi = 100 - 100/(1+rs)
    rsi_dir = 'bullish' if rsi > 55 else 'bearish' if rsi < 45 else 'neutral'
    
    # MACD
    ema12 = sum(closes[:12])/12; ema26 = sum(closes[:26])/26
    macd_val = ema12 - ema26
    macd_pct = (macd_val/close)*100
    macd_dir = 'bullish' if macd_val > 0 else 'bearish'
    
    # Bollinger
    n_bb = min(20, len(closes))
    bb_ma = sum(closes[:n_bb])/n_bb
    bb_std = math.sqrt(sum((x-bb_ma)**2 for x in closes[:n_bb])/n_bb)
    bb_upper, bb_lower = bb_ma+2*bb_std, bb_ma-2*bb_std
    if close > bb_upper*0.98: bb_dir, bb_pos = 'bearish', '上轨附近'
    elif close < bb_lower*1.02: bb_dir, bb_pos = 'bullish', '下轨附近'
    else: bb_dir, bb_pos = 'neutral', '中轨附近'
    
    # KDJ
    n_kdj = min(9, len(kdata))
    kd_h, kd_l = max(highs[:n_kdj]), min(lows[:n_kdj])
    rsv = ((close-kd_l)/(kd_h-kd_l))*100 if kd_h!=kd_l else 50
    k_val = 50*0.67+rsv*0.33
    d_val = 50*0.67+k_val*0.33
    j_val = 3*k_val-2*d_val
    kdj_dir = 'bearish' if j_val>80 else 'bullish' if j_val<20 else 'neutral'
    
    # Seasonal
    month = datetime.now().month
    sf = {1:0.95,2:0.88,3:0.97,4:1.02,5:0.92,6:0.90,7:1.08,8:1.03,9:0.98,10:1.05,11:0.93,12:0.87}.get(month,1.0)
    se_dir = 'bullish' if sf>1.0 else 'bearish'
    
    # Money flow
    chg_5d = ((closes[0]/closes[5])-1)*100 if len(closes)>5 else 0
    mf_dir = 'bullish' if chg_5d>2 else 'bearish' if chg_5d<-2 else 'neutral'
    
    return {
        'close': close, 'atr': round(atr, 3),
        'signals': {
            'macd': {'value': f'{macd_pct:+.2f}%', 'direction': macd_dir, 'raw': round(macd_pct, 2)},
            'rsi': {'value': round(rsi, 1), 'direction': rsi_dir, 'raw': round(rsi, 1)},
            'bollinger': {'position': bb_pos, 'direction': bb_dir, 'upper': round(bb_upper, 2), 'lower': round(bb_lower, 2)},
            'kdj': {'k': round(k_val, 0), 'd': round(d_val, 0), 'j': round(j_val, 0), 'direction': kdj_dir},
            'seasonal': {'note': f'{month}月季节性{"偏多" if sf>1 else "偏弱"}', 'direction': se_dir, 'factor': sf},
            'atr': {'value': round(atr, 3), 'pct': round(atr/close*100, 2),
                    'direction': 'bullish' if close>closes[5] else 'bearish' if close<closes[5] else 'neutral', 'raw': round(atr, 3)},
            'money_flow': {'direction': mf_dir, 'note': '近5日'+('上涨' if chg_5d>0 else '下跌')}
        }
    }

SIGNALS = ['macd', 'rsi', 'bollinger', 'kdj', 'seasonal', 'atr', 'money_flow']
BLOCKS = ['09:30-10:30', '10:30-11:30', '13:00-14:00', '14:00-15:00', 'next_day']

def new_learning_params():
    return {
        'signal_weights': {s: {b: 1.0 for b in BLOCKS} for s in SIGNALS},
        'hourly_bias': {b: 0.0 for b in BLOCKS},
        'seasonal_adj': {str(m): 0.0 for m in range(1, 13)},
        'confidence_beta': {
            'bullish': {'alpha': 1, 'beta': 1},
            'bearish': {'alpha': 1, 'beta': 1},
            'neutral': {'alpha': 1, 'beta': 1}
        },
        'learning_rate': 0.01,
        'mw_beta': 0.7,
        'update_count': 0
    }

def gen_prediction(code, info, lp):
    close = info['close']
    atr = info['atr']
    sig = info['signals']
    weights = lp['signal_weights']
    bias = lp['hourly_bias']
    season_adj = lp['seasonal_adj']
    conf_beta = lp['confidence_beta']
    
    weighted_score = sum(weights[s]['next_day'] * (1 if sig[s]['direction']=='bullish' else -1 if sig[s]['direction']=='bearish' else 0) for s in SIGNALS)
    month = str(datetime.now().month)
    weighted_score += season_adj.get(month, 0.0) * 2
    
    day_dir = 'bullish' if weighted_score > 0.5 else 'bearish' if weighted_score < -0.5 else 'neutral'
    beta_info = conf_beta.get(day_dir, {'alpha': 1, 'beta': 1})
    confidence = max(0.4, round(beta_info['alpha']/(beta_info['alpha']+beta_info['beta']), 2))
    
    daily_range = atr * 2.5
    nh, nl = round(close+daily_range*0.6, 2), round(close-daily_range*0.4, 2)
    
    hw_defs = [('09:30-10:30',0.35,'开盘消化隔夜信息'),('10:30-11:30',0.20,'横盘整理'),('13:00-14:00',0.20,'午后资金活跃'),('14:00-15:00',0.25,'尾盘主力动作')]
    
    cum = close
    h_preds = []
    for block, pct, note in hw_defs:
        sd = daily_range * pct
        h_score = sum(weights[s][block]*(1 if sig[s]['direction']=='bullish' else -1 if sig[s]['direction']=='bearish' else 0) for s in SIGNALS)
        h_score += bias.get(block, 0) * 2
        h_dir = 'bullish' if h_score>0.3 else 'bearish' if h_score<-0.3 else 'neutral'
        off = close * bias.get(block, 0) * 2
        hh, hl, hc = round(cum+sd*0.5+off,2), round(cum-sd*0.5+off,2), round(cum+off,2)
        h_preds.append({'block':block,'pred_open':round(cum,2) if not h_preds else round(h_preds[-1]['pred_close'],2),
                       'pred_high':min(hh,nh),'pred_low':max(hl,nl),'pred_close':hc,
                       'direction':h_dir,'strength':min(5,max(1,int(abs(h_score)))),'note':note})
        cum = hc
    
    advice = '低吸为主' if day_dir=='bullish' else '观望为主' if day_dir=='neutral' else '逢高减仓'
    return {'date':datetime.now().strftime('%Y-%m-%d'),'code':code,'prev_close':close,
            'next_day':{'direction':day_dir,'confidence':confidence,'high':nh,'low':nl,'advice':advice,'entry_zone':nl if day_dir=='bullish' else nh},
            'hourly':h_preds,'signals':sig,
            'actual':{'open':None,'high':None,'low':None,'close':None,'next_day_direction_hit':None,'daily_range_hit':None,'hourly_hits':[None]*4}}

# === MAIN: iterate watchlist ===
today = datetime.now().strftime('%Y-%m-%d')
d['kline_daily'] = d.get('kline_daily', {})
d['daily_predictions'] = [p for p in d.get('daily_predictions', []) if p['date'] != today]
d['learning_params'] = d.get('learning_params', {})
d['accuracy_stats'] = d.get('accuracy_stats', {})

for stock in watchlist:
    code = stock['code']
    name = stock['name']
    market_code = f"{stock['market']}{code}"
    
    print(f"\n--- {name}({code}) ---")
    kdata = fetch_kline(market_code)
    print(f"  K-line: {len(kdata)} bars")
    
    info = calc_signals(kdata)
    print(f"  close={info['close']} ATR={info['atr']} RSI={info['signals']['rsi']['value']}")
    
    d['kline_daily'][code] = [[k[0],k[1],k[2],k[3],k[4]] for k in kdata]
    
    if code not in d['learning_params']:
        d['learning_params'][code] = new_learning_params()
    
    pred = gen_prediction(code, info, d['learning_params'][code])
    d['daily_predictions'].append(pred)
    print(f"  prediction: {pred['next_day']['direction']} conf={pred['next_day']['confidence']:.0%}")

# Init accuracy_stats for any new stocks
empty_acc = {'last_20':{'direction':{'correct':0,'total':0,'rate':0},'range':{'correct':0,'total':0,'rate':0},'hourly':{b:0 for b in BLOCKS[:4]}},
             'last_60':{'direction':{'correct':0,'total':0,'rate':0},'range':{'correct':0,'total':0,'rate':0},'hourly':{b:0 for b in BLOCKS[:4]}}}
for stock in watchlist:
    if stock['code'] not in d['accuracy_stats']:
        d['accuracy_stats'][stock['code']] = dict(empty_acc)

d['generated'] = today
d['daily_predictions'] = sorted(d['daily_predictions'], key=lambda p: p['date'])[-90*len(watchlist):]

with open('data/system_data.json', 'w', encoding='utf-8') as f:
    json.dump(d, f, ensure_ascii=False, indent=2)

print(f"\nDone. {len(watchlist)} stocks processed, {len(d['daily_predictions'])} predictions total.")
