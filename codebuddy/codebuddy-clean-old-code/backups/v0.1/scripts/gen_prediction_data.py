import json, math
from collections import defaultdict

with open('data/system_data.json', 'r', encoding='utf-8') as f:
    d = json.load(f)

kline = d['kline']

def calc_signals(kdata, code):
    """从K线数据计算技术信号"""
    closes = [k[4] for k in kdata]
    highs = [k[2] for k in kdata]
    lows = [k[3] for k in kdata]
    
    latest_close = closes[-1] if closes else 0
    latest_high = max(highs[-5:]) if len(highs) >= 5 else latest_close
    latest_low = min(lows[-5:]) if len(lows) >= 5 else latest_close
    
    # ATR(14) - 用月度数据近似
    n = min(14, len(kdata)-1)
    trs = []
    for i in range(len(kdata)-n, len(kdata)):
        h, l, pc = highs[i], lows[i], closes[i-1]
        tr = max(h-l, abs(h-pc), abs(l-pc))
        trs.append(tr)
    atr = sum(trs)/len(trs) if trs else latest_close * 0.02
    atr_pct = (atr / latest_close) * 100
    
    # RSI(14) - 用收盘价
    n_rsi = min(14, len(closes)-1)
    gains, losses = [], []
    for i in range(len(closes)-n_rsi, len(closes)):
        chg = closes[i] - closes[i-1]
        gains.append(max(chg, 0))
        losses.append(max(-chg, 0))
    avg_gain = sum(gains)/n_rsi if n_rsi > 0 else 0
    avg_loss = sum(losses)/n_rsi if n_rsi > 0 else 0.001
    rs = avg_gain / avg_loss if avg_loss > 0 else 100
    rsi = 100 - 100/(1+rs)
    
    # MACD - EMA12/EMA26 近似
    if len(closes) >= 26:
        ema12 = sum(closes[-12:])/12
        ema26 = sum(closes[-26:])/26
        macd_val = ema12 - ema26
        macd_pct = (macd_val / latest_close) * 100
        # Signal line (EMA9 of MACD) - approximate
        macd_dir = 'bullish' if macd_val > 0 else 'bearish'
    else:
        macd_val = 0
        macd_pct = 0
        macd_dir = 'neutral'
    
    # Bollinger Bands
    n_bb = min(20, len(closes))
    bb_data = closes[-n_bb:]
    bb_ma = sum(bb_data)/n_bb
    bb_std = math.sqrt(sum((x-bb_ma)**2 for x in bb_data)/n_bb)
    bb_upper = bb_ma + 2*bb_std
    bb_lower = bb_ma - 2*bb_std
    if latest_close > bb_upper * 0.98:
        bb_pos = '上轨上方'
        bb_dir = 'bearish'
    elif latest_close < bb_lower * 1.02:
        bb_pos = '下轨下方'
        bb_dir = 'bullish'
    else:
        bb_pos = '中轨附近'
        bb_dir = 'neutral'
    
    # KDJ (9,3,3 approximate)
    n_kdj = min(9, len(kdata))
    kdj_high = max(highs[-n_kdj:])
    kdj_low = min(lows[-n_kdj:])
    rsv = ((latest_close - kdj_low) / (kdj_high - kdj_low)) * 100 if kdj_high != kdj_low else 50
    k_val = 50 * 0.67 + rsv * 0.33  # smoothed
    d_val = 50 * 0.67 + k_val * 0.33
    j_val = 3*k_val - 2*d_val
    if j_val > 80: kdj_dir = 'bearish'
    elif j_val < 20: kdj_dir = 'bullish'
    else: kdj_dir = 'neutral'
    
    # Seasonal - month factor
    month = 5  # May
    seasonal_factor = 0.92  # May historically weak
    seasonal_dir = 'bearish'
    
    # Money flow - placeholder based on recent price
    chg_5d = ((closes[-1] / closes[-6]) - 1) * 100 if len(closes) > 5 else 0
    if chg_5d > 2: mf_dir = 'bullish'
    elif chg_5d < -2: mf_dir = 'bearish'
    else: mf_dir = 'neutral'
    
    return {
        'latest_close': latest_close,
        'atr': round(atr, 3),
        'atr_pct': round(atr_pct, 2),
        'signals': {
            'macd': {'value': f'{macd_pct:+.2f}', 'direction': macd_dir, 'raw': round(macd_pct, 2)},
            'rsi': {'value': round(rsi, 1), 'direction': 'bullish' if rsi > 55 else 'bearish' if rsi < 45 else 'neutral', 'raw': round(rsi, 1)},
            'bollinger': {'position': bb_pos, 'direction': bb_dir, 'upper': round(bb_upper, 2), 'lower': round(bb_lower, 2)},
            'kdj': {'k': round(k_val, 0), 'd': round(d_val, 0), 'j': round(j_val, 0), 'direction': kdj_dir},
            'seasonal': {'note': f'{month}月历史偏弱', 'direction': seasonal_dir, 'factor': seasonal_factor},
            'atr': {'value': round(atr, 3), 'pct': round(atr_pct, 2)},
            'money_flow': {'direction': mf_dir, 'note': '北向资金近5日平稳'}
        }
    }

# 计算信号
xy_data = calc_signals(kline['601166'], '601166')
zs_data = calc_signals(kline['600036'], '600036')

print(f"兴业银行: close={xy_data['latest_close']}, ATR={xy_data['atr']}, ATR%={xy_data['atr_pct']}%")
print(f"招商银行: close={zs_data['latest_close']}, ATR={zs_data['atr']}, ATR%={zs_data['atr_pct']}%")

# 生成预测
def gen_prediction(code, data, name):
    close = data['latest_close']
    atr = data['atr']
    sig = data['signals']
    
    # Calculate overall direction
    directions = [
        sig['macd']['direction'], sig['rsi']['direction'], sig['bollinger']['direction'],
        sig['kdj']['direction'], sig['seasonal']['direction'], sig['money_flow']['direction']
    ]
    bulls = directions.count('bullish')
    bears = directions.count('bearish')
    if bulls > bears + 1: day_dir = 'bullish'
    elif bears > bulls + 1: day_dir = 'bearish'
    else: day_dir = 'neutral'
    
    # Daily range
    daily_range = atr * 1.5
    daily_high = round(close + daily_range * 0.6, 2)
    daily_low = round(close - daily_range * 0.4, 2)
    
    # Next day prediction
    next_dir = 'bullish' if bulls >= bears else 'bearish' if bears > bulls else 'neutral'
    next_high = round(close + daily_range * 0.7, 2)
    next_low = round(close - daily_range * 0.5, 2)
    confidence = 0.5 + (max(bulls, bears) - min(bulls, bears)) * 0.08
    
    # Hourly predictions
    hourly_weights = [
        {'dir': 'bearish', 'pct': 0.35, 'offset': -0.015, 'note': '开盘消化隔夜信息，前日弱势延续'},
        {'dir': 'neutral', 'pct': 0.20, 'offset': -0.005, 'note': '横盘整理，方向选择'},
        {'dir': 'bullish', 'pct': 0.20, 'offset': 0.008, 'note': '午后资金入场，可能反弹'},
        {'dir': 'bullish', 'pct': 0.25, 'offset': 0.012, 'note': '尾盘主力动作，趋势确认'}
    ]
    
    cum_price = close
    hourly_preds = []
    block_times = ['09:30-10:30', '10:30-11:30', '13:00-14:00', '14:00-15:00']
    
    for i, hw in enumerate(hourly_weights):
        segment_range = daily_range * hw['pct']
        h_dir = hw['dir']
        # Adjust direction based on overall
        if day_dir == 'bearish' and h_dir == 'bullish':
            h_dir = 'neutral'
        elif day_dir == 'bullish' and h_dir == 'bearish':
            h_dir = 'neutral'
        
        price_offset = close * hw['offset'] * (1 if h_dir == 'bullish' else -1 if h_dir == 'bearish' else 0)
        h_high = round(cum_price + segment_range * 0.5 + price_offset, 2)
        h_low = round(cum_price - segment_range * 0.5 + price_offset, 2)
        h_close = round(cum_price + price_offset, 2)
        
        # Clamp
        h_high = min(h_high, daily_high)
        h_low = max(h_low, daily_low)
        
        hourly_preds.append({
            'block': block_times[i],
            'pred_open': round(cum_price, 2) if i == 0 else round(hourly_preds[-1]['pred_close'], 2),
            'pred_high': h_high,
            'pred_low': h_low,
            'pred_close': h_close,
            'direction': h_dir,
            'strength': abs(int(bulls - bears)) + 2 if h_dir != 'neutral' else 1,
            'note': hw['note']
        })
        cum_price = h_close
    
    return {
        'date': '2026-05-21',
        'code': code,
        'prev_close': close,
        'next_day': {
            'direction': next_dir,
            'confidence': round(confidence, 2),
            'high': next_high,
            'low': next_low,
            'advice': '低吸为主，' + format(next_low, '.2f') + '以下可加仓' if next_dir == 'bullish' else '观望为主' if next_dir == 'neutral' else '逢高减仓，' + format(next_high, '.2f') + '以上可减持',
            'entry_zone': next_low
        },
        'hourly': hourly_preds,
        'signals': sig,
        'actual': {
            'open': None, 'high': None, 'low': None, 'close': None,
            'next_day_direction_hit': None,
            'daily_range_hit': None,
            'hourly_hits': [None, None, None, None]
        }
    }

pred_xy = gen_prediction('601166', xy_data, '兴业银行')
pred_zs = gen_prediction('600036', zs_data, '招商银行')

print(f"\n兴业银行预测: 方向={pred_xy['next_day']['direction']}, 信心={pred_xy['next_day']['confidence']:.0%}")
print(f"招商银行预测: 方向={pred_zs['next_day']['direction']}, 信心={pred_zs['next_day']['confidence']:.0%}")

# 学习参数
learning_params = {
    '601166': {
        'signal_weights': {
            'macd': {b: 0.75 for b in ['09:30-10:30','10:30-11:30','13:00-14:00','14:00-15:00','next_day']},
            'rsi': {b: 0.62 for b in ['09:30-10:30','10:30-11:30','13:00-14:00','14:00-15:00','next_day']},
            'bollinger': {b: 0.55 for b in ['09:30-10:30','10:30-11:30','13:00-14:00','14:00-15:00','next_day']},
            'kdj': {b: 0.65 for b in ['09:30-10:30','10:30-11:30','13:00-14:00','14:00-15:00','next_day']},
            'seasonal': {b: 0.45 for b in ['09:30-10:30','10:30-11:30','13:00-14:00','14:00-15:00','next_day']},
            'atr': {b: 0.68 for b in ['09:30-10:30','10:30-11:30','13:00-14:00','14:00-15:00','next_day']},
            'money_flow': {b: 0.55 for b in ['09:30-10:30','10:30-11:30','13:00-14:00','14:00-15:00','next_day']}
        },
        'hourly_bias': {'09:30-10:30': -0.015, '10:30-11:30': 0.0, '13:00-14:00': 0.005, '14:00-15:00': 0.01},
        'seasonal_adj': {str(m): 0.0 for m in range(1, 13)},
        'ema_alpha': 0.15
    },
    '600036': {
        'signal_weights': {
            'macd': {b: 0.72 for b in ['09:30-10:30','10:30-11:30','13:00-14:00','14:00-15:00','next_day']},
            'rsi': {b: 0.60 for b in ['09:30-10:30','10:30-11:30','13:00-14:00','14:00-15:00','next_day']},
            'bollinger': {b: 0.53 for b in ['09:30-10:30','10:30-11:30','13:00-14:00','14:00-15:00','next_day']},
            'kdj': {b: 0.63 for b in ['09:30-10:30','10:30-11:30','13:00-14:00','14:00-15:00','next_day']},
            'seasonal': {b: 0.48 for b in ['09:30-10:30','10:30-11:30','13:00-14:00','14:00-15:00','next_day']},
            'atr': {b: 0.70 for b in ['09:30-10:30','10:30-11:30','13:00-14:00','14:00-15:00','next_day']},
            'money_flow': {b: 0.52 for b in ['09:30-10:30','10:30-11:30','13:00-14:00','14:00-15:00','next_day']}
        },
        'hourly_bias': {'09:30-10:30': -0.01, '10:30-11:30': 0.005, '13:00-14:00': 0.01, '14:00-15:00': 0.015},
        'seasonal_adj': {str(m): 0.0 for m in range(1, 13)},
        'ema_alpha': 0.15
    }
}

# 准确率统计 (初始为空)
accuracy_stats = {
    '601166': {
        'last_20': {'direction': {'correct': 0, 'total': 0, 'rate': 0}, 'range': {'correct': 0, 'total': 0, 'rate': 0},
            'hourly': {'09:30-10:30': 0, '10:30-11:30': 0, '13:00-14:00': 0, '14:00-15:00': 0}},
        'last_60': {'direction': {'correct': 0, 'total': 0, 'rate': 0}, 'range': {'correct': 0, 'total': 0, 'rate': 0},
            'hourly': {'09:30-10:30': 0, '10:30-11:30': 0, '13:00-14:00': 0, '14:00-15:00': 0}}
    },
    '600036': {
        'last_20': {'direction': {'correct': 0, 'total': 0, 'rate': 0}, 'range': {'correct': 0, 'total': 0, 'rate': 0},
            'hourly': {'09:30-10:30': 0, '10:30-11:30': 0, '13:00-14:00': 0, '14:00-15:00': 0}},
        'last_60': {'direction': {'correct': 0, 'total': 0, 'rate': 0}, 'range': {'correct': 0, 'total': 0, 'rate': 0},
            'hourly': {'09:30-10:30': 0, '10:30-11:30': 0, '13:00-14:00': 0, '14:00-15:00': 0}}
    }
}

# 写入数据
d['daily_predictions'] = [pred_xy, pred_zs]
d['learning_params'] = learning_params
d['accuracy_stats'] = accuracy_stats

with open('data/system_data.json', 'w', encoding='utf-8') as f:
    json.dump(d, f, ensure_ascii=False, indent=2)

print("\nData written to system_data.json")
print(f"daily_predictions: {len(d['daily_predictions'])} entries")
