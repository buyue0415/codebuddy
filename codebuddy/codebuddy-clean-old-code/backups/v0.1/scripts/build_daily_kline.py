import json, math, subprocess, re, sys
from datetime import datetime

BASE = r'C:\Users\28312\.workbuddy\plugins\marketplaces\cb_teams_marketplace\plugins\finance-data\skills\westock-data'
NODE = r'C:\Users\28312\.workbuddy\binaries\node\versions\22.12.0\node.exe'
SCRIPT = 'scripts/index.js'

# 1. Fetch daily K-line for both stocks
def fetch_kline(code, limit=200):
    result = subprocess.run(
        [NODE, SCRIPT, 'kline', code, '--period', 'day', '--limit', str(limit), '--fq', 'qfq'],
        cwd=BASE, capture_output=True, text=True, timeout=30
    )
    lines = result.stdout.strip().split('\n')
    # Parse markdown table: | date | open | last | high | low | ...
    data = []
    for line in lines:
        parts = [p.strip() for p in line.split('|') if p.strip()]
        if len(parts) >= 5 and re.match(r'\d{4}-\d{2}-\d{2}', parts[0]):
            date, open_p, close_p, high_p, low_p = parts[0], float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4])
            data.append([date, open_p, close_p, high_p, low_p])
    return data

print("Fetching 兴业银行 daily K-line...")
xy_kline = fetch_kline('sh601166')
print(f"  获取 {len(xy_kline)} 条日K")

print("Fetching 招商银行 daily K-line...")
zs_kline = fetch_kline('sh600036')
print(f"  获取 {len(zs_kline)} 条日K")

# 2. Calculate signals from daily data
def calc_signals(kdata):
    closes = [k[2] for k in kdata]
    highs = [k[3] for k in kdata]
    lows = [k[4] for k in kdata]
    close = closes[0]
    
    # ATR(14) using True Range
    n_atr = min(14, len(kdata)-1)
    trs = []
    for i in range(n_atr):
        h, l, pc = highs[i], lows[i], closes[i+1]
        trs.append(max(h-l, abs(h-pc), abs(l-pc)))
    atr = sum(trs)/len(trs)
    
    # RSI(14)
    n_rsi = min(14, len(closes)-1)
    gains = sum(max(closes[i]-closes[i+1], 0) for i in range(n_rsi))
    losses = sum(max(closes[i+1]-closes[i], 0) for i in range(n_rsi))
    rs = (gains/n_rsi) / (losses/n_rsi) if losses > 0 else 100
    rsi = 100 - 100/(1+rs)
    rsi_dir = 'bullish' if rsi > 55 else 'bearish' if rsi < 45 else 'neutral'
    
    # MACD
    ema12 = sum(closes[:12])/12
    ema26 = sum(closes[:26])/26
    macd_val = ema12 - ema26
    macd_pct = (macd_val/close)*100
    macd_dir = 'bullish' if macd_val > 0 else 'bearish'
    
    # Bollinger
    n_bb = min(20, len(closes))
    bb_ma = sum(closes[:n_bb])/n_bb
    bb_std = math.sqrt(sum((x-bb_ma)**2 for x in closes[:n_bb])/n_bb)
    bb_upper = bb_ma + 2*bb_std
    bb_lower = bb_ma - 2*bb_std
    if close > bb_upper*0.98: bb_dir, bb_pos = 'bearish', '上轨附近'
    elif close < bb_lower*1.02: bb_dir, bb_pos = 'bullish', '下轨附近'
    else: bb_dir, bb_pos = 'neutral', '中轨附近'
    
    # KDJ
    n_kdj = min(9, len(kdata))
    kd_h = max(highs[:n_kdj])
    kd_l = min(lows[:n_kdj])
    rsv = ((close-kd_l)/(kd_h-kd_l))*100 if kd_h!=kd_l else 50
    k_val, d_val = 50*0.67+rsv*0.33, 50*0.67+50*0.67*0.33+rsv*0.33*0.33
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
        'close': close, 'atr': round(atr,3), 'atr_pct': round(atr/close*100,2),
        'signals': {
            'macd': {'value': f'{macd_pct:+.2f}%', 'direction': macd_dir, 'raw': round(macd_pct,2)},
            'rsi': {'value': round(rsi,1), 'direction': rsi_dir, 'raw': round(rsi,1)},
            'bollinger': {'position': bb_pos, 'direction': bb_dir, 'upper': round(bb_upper,2), 'lower': round(bb_lower,2)},
            'kdj': {'k': round(k_val,0), 'd': round(d_val,0), 'j': round(j_val,0), 'direction': kdj_dir},
            'seasonal': {'note': f'{month}月季节性{"偏多" if sf>1 else "偏弱"}', 'direction': se_dir, 'factor': sf},
            'atr': {'value': round(atr,3), 'pct': round(atr/close*100,2)},
            'money_flow': {'direction': mf_dir, 'note': '近5日'+('上涨' if chg_5d>0 else '下跌')}
        }
    }

xy_info = calc_signals(xy_kline)
zs_info = calc_signals(zs_kline)

print(f"\n兴业银行: close={xy_info['close']}, ATR={xy_info['atr']}, RSI={xy_info['signals']['rsi']['value']}")
print(f"招商银行: close={zs_info['close']}, ATR={zs_info['atr']}, RSI={zs_info['signals']['rsi']['value']}")

# 3. Generate predictions
def gen_prediction(code, info):
    close = info['close']
    atr = info['atr']
    sig = info['signals']
    
    dirs = [sig[k]['direction'] for k in ['macd','rsi','bollinger','kdj','seasonal','money_flow']]
    bulls = dirs.count('bullish')
    bears = dirs.count('bearish')
    day_dir = 'bullish' if bulls>bears+1 else 'bearish' if bears>bulls+1 else 'neutral'
    
    daily_range = atr * 2.5  # Daily ATR-based range
    next_high = round(close + daily_range * 0.6, 2)
    next_low = round(close - daily_range * 0.4, 2)
    confidence = round(0.5 + abs(bulls-bears)*0.08, 2)
    
    # Hourly blocks
    hw_defs = [
        {'block':'09:30-10:30','pct':0.35,'offset':-0.003,'note':'开盘消化隔夜信息','dir':'bearish'},
        {'block':'10:30-11:30','pct':0.20,'offset':-0.001,'note':'横盘整理，方向选择','dir':'neutral'},
        {'block':'13:00-14:00','pct':0.20,'offset':0.002,'note':'午后资金活跃','dir':'bullish'},
        {'block':'14:00-15:00','pct':0.25,'offset':0.003,'note':'尾盘主力动作','dir':'bullish'}
    ]
    
    cum = close
    h_preds = []
    for hw in hw_defs:
        sd = daily_range * hw['pct']
        h_dir = hw['dir']
        if day_dir=='bearish' and h_dir=='bullish': h_dir='neutral'
        if day_dir=='bullish' and h_dir=='bearish': h_dir='neutral'
        off = close * hw['offset'] * (1 if h_dir=='bullish' else -1 if h_dir=='bearish' else 0)
        h_high = round(cum + sd*0.5 + off, 2)
        h_low = round(cum - sd*0.5 + off, 2)
        h_close = round(cum + off, 2)
        h_high, h_low = min(h_high, next_high), max(h_low, next_low)
        h_preds.append({
            'block': hw['block'],
            'pred_open': round(cum,2) if not h_preds else round(h_preds[-1]['pred_close'],2),
            'pred_high': h_high, 'pred_low': h_low, 'pred_close': h_close,
            'direction': h_dir, 'strength': min(5, max(1, abs(bulls-bears)+1)), 'note': hw['note']
        })
        cum = h_close
    
    advice = '低吸为主' if day_dir=='bullish' else '观望为主' if day_dir=='neutral' else '逢高减仓'
    return {
        'date': datetime.now().strftime('%Y-%m-%d'),
        'code': code,
        'prev_close': close,
        'next_day': {
            'direction': day_dir, 'confidence': confidence, 'high': next_high, 'low': next_low,
            'advice': advice, 'entry_zone': next_low if day_dir=='bullish' else next_high
        },
        'hourly': h_preds, 'signals': sig,
        'actual': {'open':None,'high':None,'low':None,'close':None,'next_day_direction_hit':None,'daily_range_hit':None,'hourly_hits':[None,None,None,None]}
    }

pred_xy = gen_prediction('601166', xy_info)
pred_zs = gen_prediction('600036', zs_info)

# 4. Save everything
with open('data/system_data.json', 'r', encoding='utf-8') as f:
    d = json.load(f)

# Save daily kline
d['kline_daily'] = {
    '601166': [[k[0], k[1], k[2], k[3], k[4]] for k in xy_kline],
    '600036': [[k[0], k[1], k[2], k[3], k[4]] for k in zs_kline]
}

# Replace today's predictions (or add new)
d['daily_predictions'] = [
    p for p in d.get('daily_predictions', [])
    if not (p['code'] in ('601166','600036') and p['date'] == pred_xy['date'])
]
d['daily_predictions'].extend([pred_xy, pred_zs])

# Init learning params if missing
if 'learning_params' not in d:
    d['learning_params'] = {
        '601166': {
            'signal_weights': {s: {b:0.65 for b in ['09:30-10:30','10:30-11:30','13:00-14:00','14:00-15:00','next_day']}
                              for s in ['macd','rsi','bollinger','kdj','seasonal','atr','money_flow']},
            'hourly_bias': {'09:30-10:30':-0.01,'10:30-11:30':0,'13:00-14:00':0.005,'14:00-15:00':0.01},
            'seasonal_adj': {str(m):0.0 for m in range(1,13)}, 'ema_alpha': 0.15
        },
        '600036': {
            'signal_weights': {s: {b:0.65 for b in ['09:30-10:30','10:30-11:30','13:00-14:00','14:00-15:00','next_day']}
                              for s in ['macd','rsi','bollinger','kdj','seasonal','atr','money_flow']},
            'hourly_bias': {'09:30-10:30':-0.01,'10:30-11:30':0,'13:00-14:00':0.005,'14:00-15:00':0.01},
            'seasonal_adj': {str(m):0.0 for m in range(1,13)}, 'ema_alpha': 0.15
        }
    }
if 'accuracy_stats' not in d:
    empty_acc = {
        'last_20': {'direction':{'correct':0,'total':0,'rate':0},'range':{'correct':0,'total':0,'rate':0},
                    'hourly':{'09:30-10:30':0,'10:30-11:30':0,'13:00-14:00':0,'14:00-15:00':0}},
        'last_60': {'direction':{'correct':0,'total':0,'rate':0},'range':{'correct':0,'total':0,'rate':0},
                    'hourly':{'09:30-10:30':0,'10:30-11:30':0,'13:00-14:00':0,'14:00-15:00':0}}
    }
    d['accuracy_stats'] = {'601166': empty_acc, '600036': empty_acc}

with open('data/system_data.json', 'w', encoding='utf-8') as f:
    json.dump(d, f, ensure_ascii=False, indent=2)

print(f"\nSaved: daily kline ({len(xy_kline)}/{len(zs_kline)}), predictions regenerated")
print(f"兴业银行: {pred_xy['next_day']['direction']} confidence={pred_xy['next_day']['confidence']:.0%} range={pred_xy['next_day']['low']}-{pred_xy['next_day']['high']}")
print(f"招商银行: {pred_zs['next_day']['direction']} confidence={pred_zs['next_day']['confidence']:.0%} range={pred_zs['next_day']['low']}-{pred_zs['next_day']['high']}")
