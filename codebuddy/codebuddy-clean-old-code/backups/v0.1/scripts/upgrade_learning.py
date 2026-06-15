"""
升级自学习系统：MWU 信号权重 + EG 偏移 + Beta-Binomial 信心度 + 滚动季节因子
从日K线重新生成预测，使用新参数结构
"""
import json, math, subprocess, re
from datetime import datetime

BASE = r'C:\Users\28312\.workbuddy\plugins\marketplaces\cb_teams_marketplace\plugins\finance-data\skills\westock-data'
NODE = r'C:\Users\28312\.workbuddy\binaries\node\versions\22.12.0\node.exe'
SCRIPT = 'scripts/index.js'

def fetch_kline(code, limit=200):
    result = subprocess.run(
        [NODE, SCRIPT, 'kline', code, '--period', 'day', '--limit', str(limit), '--fq', 'qfq'],
        cwd=BASE, capture_output=True, text=True, timeout=30
    )
    lines = result.stdout.strip().split('\n')
    data = []
    for line in lines:
        parts = [p.strip() for p in line.split('|') if p.strip()]
        if len(parts) >= 5 and re.match(r'\d{4}-\d{2}-\d{2}', parts[0]):
            date, op, cl, hi, lo = parts[0], float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4])
            data.append([date, op, cl, hi, lo])
    return data

# 拉取日K
print("Fetching daily K-lines...")
xy_kline = fetch_kline('sh601166')
zs_kline = fetch_kline('sh600036')
print(f"  兴业: {len(xy_kline)}条, 招行: {len(zs_kline)}条")

# ===== 信号计算 =====
def calc_signals(kdata):
    closes = [k[2] for k in kdata]
    highs = [k[3] for k in kdata]
    lows = [k[4] for k in kdata]
    close = closes[0]
    
    # ATR(14)
    n_atr = min(14, len(kdata)-1)
    trs = []
    for i in range(n_atr):
        trs.append(max(highs[i]-lows[i], abs(highs[i]-closes[i+1]), abs(lows[i]-closes[i+1])))
    atr = sum(trs)/len(trs)
    
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
                    'direction': 'bullish' if close > closes[5] else 'bearish' if close < closes[5] else 'neutral',
                    'raw': round(atr, 3)},
            'money_flow': {'direction': mf_dir, 'note': '近5日' + ('上涨' if chg_5d > 0 else '下跌')}
        }
    }

xy_info = calc_signals(xy_kline)
zs_info = calc_signals(zs_kline)

print(f"  兴业: close={xy_info['close']}, ATR={xy_info['atr']}, RSI={xy_info['signals']['rsi']['value']}")
print(f"  招行: close={zs_info['close']}, ATR={zs_info['atr']}, RSI={zs_info['signals']['rsi']['value']}")

# ===== 新学习参数结构 =====
BLOCKS_5 = ['09:30-10:30', '10:30-11:30', '13:00-14:00', '14:00-15:00', 'next_day']
SIGNAL_KEYS = ['macd', 'rsi', 'bollinger', 'kdj', 'seasonal', 'atr', 'money_flow']

def new_learning_params():
    """MWU + EG + Beta 初始化"""
    # MWU: 每个信号初始权重 = 1.0（均等）
    signal_weights = {
        s: {b: 1.0 for b in BLOCKS_5}
        for s in SIGNAL_KEYS
    }
    # EG: 时段偏移初始 = 0
    hourly_bias = {b: 0.0 for b in BLOCKS_5}
    # 滚动季节因子（从固定表初始化）
    seasonal_adj = {str(m): 0.0 for m in range(1, 13)}
    # Beta-Binomial 信心度（先验 Beta(1,1)）
    confidence_beta = {
        'bullish': {'alpha': 1, 'beta': 1},
        'bearish': {'alpha': 1, 'beta': 1},
        'neutral': {'alpha': 1, 'beta': 1}
    }
    return {
        'signal_weights': signal_weights,
        'hourly_bias': hourly_bias,
        'seasonal_adj': seasonal_adj,
        'confidence_beta': confidence_beta,
        'learning_rate': 0.01,
        'mw_beta': 0.7,  # MWU衰减因子
        'update_count': 0
    }

# ===== 加权预测生成（使用新参数） =====
def gen_weighted_prediction(code, info, lparams):
    close = info['close']
    atr = info['atr']
    sig = info['signals']
    weights = lparams['signal_weights']
    bias = lparams['hourly_bias']
    season_adj = lparams['seasonal_adj']
    conf_beta = lparams['confidence_beta']
    
    # 加权计算整体方向
    weighted_score = 0.0
    for sk in SIGNAL_KEYS:
        w = weights[sk]['next_day']
        d = sig[sk]['direction']
        score = 1 if d == 'bullish' else -1 if d == 'bearish' else 0
        weighted_score += w * score
    
    # 添加季节修正
    month = str(datetime.now().month)
    weighted_score += season_adj.get(month, 0.0) * 2
    
    day_dir = 'bullish' if weighted_score > 0.5 else 'bearish' if weighted_score < -0.5 else 'neutral'
    
    # Beta-Binomial 信心度
    beta_info = conf_beta.get(day_dir, {'alpha': 1, 'beta': 1})
    confidence = round(beta_info['alpha'] / (beta_info['alpha'] + beta_info['beta']), 2)
    if confidence < 0.4: confidence = 0.4  # 最低信心地板
    
    # 日区间
    daily_range = atr * 2.5
    next_high = round(close + daily_range * 0.6, 2)
    next_low = round(close - daily_range * 0.4, 2)
    
    # 逐小时预测（使用分时段权重和偏移）
    hw_defs = [
        ('09:30-10:30', 0.35, '开盘消化隔夜信息'),
        ('10:30-11:30', 0.20, '横盘整理，方向选择'),
        ('13:00-14:00', 0.20, '午后资金活跃'),
        ('14:00-15:00', 0.25, '尾盘主力动作')
    ]
    
    cum = close
    h_preds = []
    for block, pct, note in hw_defs:
        sd = daily_range * pct
        # 加权小时方向
        h_score = 0.0
        for sk in SIGNAL_KEYS:
            w = weights[sk][block]
            d = sig[sk]['direction']
            h_score += w * (1 if d == 'bullish' else -1 if d == 'bearish' else 0)
        h_score += bias.get(block, 0.0) * 2
        
        h_dir = 'bullish' if h_score > 0.3 else 'bearish' if h_score < -0.3 else 'neutral'
        
        off = close * bias.get(block, 0.0) * 2
        h_high = round(cum + sd*0.5 + off, 2)
        h_low = round(cum - sd*0.5 + off, 2)
        h_close = round(cum + off, 2)
        h_high, h_low = min(h_high, next_high), max(h_low, next_low)
        
        h_preds.append({
            'block': block,
            'pred_open': round(cum, 2) if not h_preds else round(h_preds[-1]['pred_close'], 2),
            'pred_high': h_high, 'pred_low': h_low, 'pred_close': h_close,
            'direction': h_dir,
            'strength': min(5, max(1, int(abs(h_score)))),
            'note': note
        })
        cum = h_close
    
    advice = '低吸为主' if day_dir == 'bullish' else '观望为主' if day_dir == 'neutral' else '逢高减仓'
    
    return {
        'date': datetime.now().strftime('%Y-%m-%d'),
        'code': code,
        'prev_close': close,
        'next_day': {
            'direction': day_dir, 'confidence': confidence,
            'high': next_high, 'low': next_low,
            'advice': advice,
            'entry_zone': next_low if day_dir == 'bullish' else next_high
        },
        'hourly': h_preds,
        'signals': sig,
        'actual': {'open': None, 'high': None, 'low': None, 'close': None,
                   'next_day_direction_hit': None, 'daily_range_hit': None,
                   'hourly_hits': [None, None, None, None]}
    }

# 加载数据
with open('data/system_data.json', 'r', encoding='utf-8') as f:
    d = json.load(f)

# 更新 kline_daily
d['kline_daily'] = {
    '601166': [[k[0], k[1], k[2], k[3], k[4]] for k in xy_kline],
    '600036': [[k[0], k[1], k[2], k[3], k[4]] for k in zs_kline]
}

# 新学习参数
lp_xy = new_learning_params()
lp_zs = new_learning_params()

# 生成预测
pred_xy = gen_weighted_prediction('601166', xy_info, lp_xy)
pred_zs = gen_weighted_prediction('600036', zs_info, lp_zs)

# 替换今天的预测
d['daily_predictions'] = [
    p for p in d.get('daily_predictions', [])
    if not (p['code'] in ('601166','600036') and p['date'] == pred_xy['date'])
]
d['daily_predictions'].extend([pred_xy, pred_zs])

# 新学习参数
d['learning_params'] = {'601166': lp_xy, '600036': lp_zs}

# 准确率统计（初始空）
empty_acc = {
    'last_20': {
        'direction': {'correct': 0, 'total': 0, 'rate': 0},
        'range': {'correct': 0, 'total': 0, 'rate': 0},
        'hourly': {'09:30-10:30': 0, '10:30-11:30': 0, '13:00-14:00': 0, '14:00-15:00': 0}
    },
    'last_60': {
        'direction': {'correct': 0, 'total': 0, 'rate': 0},
        'range': {'correct': 0, 'total': 0, 'rate': 0},
        'hourly': {'09:30-10:30': 0, '10:30-11:30': 0, '13:00-14:00': 0, '14:00-15:00': 0}
    }
}
if 'accuracy_stats' not in d:
    d['accuracy_stats'] = {'601166': dict(empty_acc), '600036': dict(empty_acc)}

with open('data/system_data.json', 'w', encoding='utf-8') as f:
    json.dump(d, f, ensure_ascii=False, indent=2)

print(f"\n=== 预测结果 ===")
print(f"兴业银行: {pred_xy['next_day']['direction']} confidence={pred_xy['next_day']['confidence']:.0%} (Beta校准)")
print(f"  区间: {pred_xy['next_day']['low']} ~ {pred_xy['next_day']['high']}")
for h in pred_xy['hourly']:
    print(f"  {h['block']}: {h['direction']} L{h['strength']}")
print(f"招商银行: {pred_zs['next_day']['direction']} confidence={pred_zs['next_day']['confidence']:.0%} (Beta校准)")
print(f"  区间: {pred_zs['next_day']['low']} ~ {pred_zs['next_day']['high']}")
for h in pred_zs['hourly']:
    print(f"  {h['block']}: {h['direction']} L{h['strength']}")
