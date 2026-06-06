import json, math, sys

# Parse K-line data from args or hardcode (we already have it from stdout)
# Load existing data
with open('data/system_data.json', 'r', encoding='utf-8') as f:
    d = json.load(f)

# The K-line data - we'll build it from the command output
# For now let's use a file-based approach: save the raw table output and parse it

# Actually, let me just directly embed the data I saw in the output
# 兴业银行 日K 前复权 (200条, date, open, last(=prev close), high, low)
xy_raw = """2026-05-21,17.33,17.33,17.39,17.30
2026-05-20,17.52,17.33,17.52,17.33
2026-05-19,17.45,17.50,17.70,17.45
2026-05-18,17.66,17.45,17.66,17.38
2026-05-15,17.67,17.67,17.81,17.60
2026-05-14,17.68,17.69,17.74,17.58
2026-05-13,17.78,17.69,17.81,17.69
2026-05-12,17.73,17.75,17.82,17.71
2026-05-11,17.72,17.73,17.76,17.65
2026-05-08,17.76,17.73,17.84,17.72
2026-05-07,17.81,17.75,17.85,17.74
2026-05-06,17.94,17.79,17.97,17.74
2026-04-30,18.03,17.93,18.04,17.84
2026-04-29,18.09,18.18,18.18,18.05
2026-04-28,18.18,18.14,18.21,18.04
2026-04-27,18.23,18.17,18.41,18.16
2026-04-24,18.18,18.18,18.32,18.11
2026-04-23,18.22,18.20,18.28,18.13
2026-04-22,18.44,18.22,18.47,18.22
2026-04-21,18.37,18.42,18.68,18.36"""

# Actually, let's parse the raw tables more systematically.
# Read the data from a file that we'll write from the stdout output
print("Parsing K-line data...")
print(f"兴业银行 will get daily kline")
print(f"招商银行 will get daily kline")
print("")

# Let me just write the data directly - I know the format
# The key columns are: date, open, close(last), high, low

def calc_signals_daily(kdata):
    """Calculate technical signals from daily K-line data"""
    closes = [k[2] for k in kdata]  # 'last' = close
    highs = [k[3] for k in kdata]
    lows = [k[4] for k in kdata]
    opens = [k[1] for k in kdata]
    
    close = closes[0]  # Latest = first in list (most recent)
    
    # ATR(14) - True Range
    n_atr = min(14, len(kdata)-1)
    trs = []
    for i in range(n_atr):
        h, l, pc = highs[i], lows[i], closes[i+1]  # prev close = next in list
        tr = max(h - l, abs(h - pc), abs(l - pc))
        trs.append(tr)
    atr = sum(trs) / len(trs)
    atr_pct = (atr / close) * 100
    
    # RSI(14)
    n_rsi = min(14, len(closes)-1)
    gains, losses = [], []
    for i in range(n_rsi):
        chg = closes[i] - closes[i+1]
        gains.append(max(chg, 0))
        losses.append(max(-chg, 0))
    avg_gain = sum(gains) / n_rsi if n_rsi else 0
    avg_loss = sum(losses) / n_rsi if n_rsi else 0.001
    rs = avg_gain / avg_loss if avg_loss > 0 else 100
    rsi = 100 - 100 / (1 + rs)
    rsi_dir = 'bullish' if rsi > 55 else 'bearish' if rsi < 45 else 'neutral'
    
    # MACD
    n_ema = len(closes)
    ema12 = sum(closes[:12]) / 12 if n_ema >= 12 else sum(closes) / n_ema
    ema26 = sum(closes[:26]) / 26 if n_ema >= 26 else sum(closes) / n_ema
    macd_val = ema12 - ema26
    macd_pct = (macd_val / close) * 100
    macd_dir = 'bullish' if macd_val > 0 else 'bearish'
    
    # Bollinger (20)
    n_bb = min(20, len(closes))
    bb_data = closes[:n_bb]
    bb_ma = sum(bb_data) / n_bb
    bb_var = sum((x - bb_ma) ** 2 for x in bb_data) / n_bb
    bb_std = math.sqrt(bb_var)
    bb_upper = bb_ma + 2 * bb_std
    bb_lower = bb_ma - 2 * bb_std
    if close > bb_upper * 0.98:
        bb_dir, bb_pos = 'bearish', '上轨附近'
    elif close < bb_lower * 1.02:
        bb_dir, bb_pos = 'bullish', '下轨附近'
    else:
        bb_dir, bb_pos = 'neutral', '中轨附近'
    
    # KDJ (9,3,3)
    n_kdj = min(9, len(kdata))
    kd_h = max(highs[:n_kdj])
    kd_l = min(lows[:n_kdj])
    rsv = ((close - kd_l) / (kd_h - kd_l)) * 100 if kd_h != kd_l else 50
    k_val = 50 * 0.67 + rsv * 0.33
    d_val = 50 * 0.67 + k_val * 0.33
    j_val = 3 * k_val - 2 * d_val
    kdj_dir = 'bearish' if j_val > 80 else 'bullish' if j_val < 20 else 'neutral'
    
    # Seasonal
    from datetime import datetime
    month = datetime.now().month
    seasonal_factor = {1:0.95, 2:0.88, 3:0.97, 4:1.02, 5:0.92, 6:0.90,
                       7:1.08, 8:1.03, 9:0.98, 10:1.05, 11:0.93, 12:0.87}.get(month, 1.0)
    seasonal_dir = 'bullish' if seasonal_factor > 1.0 else 'bearish'
    
    # Money flow (5-day)
    chg_5d = ((closes[0] / closes[5]) - 1) * 100 if len(closes) > 5 else 0
    mf_dir = 'bullish' if chg_5d > 2 else 'bearish' if chg_5d < -2 else 'neutral'
    
    signals = {
        'macd': {'value': f'{macd_pct:+.2f}%', 'direction': macd_dir, 'raw': round(macd_pct, 2)},
        'rsi': {'value': round(rsi, 1), 'direction': rsi_dir, 'raw': round(rsi, 1)},
        'bollinger': {'position': bb_pos, 'direction': bb_dir, 'upper': round(bb_upper, 2), 'lower': round(bb_lower, 2)},
        'kdj': {'k': round(k_val, 0), 'd': round(d_val, 0), 'j': round(j_val, 0), 'direction': kdj_dir},
        'seasonal': {'note': f'{month}月季节性{"偏多" if seasonal_factor>1 else "偏弱"}',
                     'direction': seasonal_dir, 'factor': seasonal_factor},
        'atr': {'value': round(atr, 3), 'pct': round(atr_pct, 2)},
        'money_flow': {'direction': mf_dir, 'note': '近5日' + ('上涨' if chg_5d > 0 else '下跌')}
    }
    
    return {
        'close': close,
        'atr': atr,
        'atr_pct': atr_pct,
        'signals': signals
    }

print("Script ready. Need to save K-line data first.")
print("Run save_kline.py to save raw data, then gen_prediction_data_v2.py to regenerate.")
