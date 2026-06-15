"""
Shared signal computation & prediction generation module.

This module is the single source of truth for:
  - Technical signal calculation (calc_signals)
  - Prediction generation (gen_pred, gen_multi_day_pred)
  - Learning parameter initialization (new_lp)

Usage:
    from signals import calc_signals, gen_pred, new_lp
    # Used by: sync_all.py, backtest_engine.py

Architecture constraint: 🔴 MUST be imported by both modules.
No re-implementation of calc_signals/gen_pred is allowed elsewhere.
"""
import json, math
from datetime import datetime, timedelta
from collections import defaultdict

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

# ─── Constants ──────────────────────────────────────────────────────────
SIGNALS = ['macd', 'rsi', 'bollinger', 'kdj', 'seasonal', 'atr', 'money_flow',
           'adx_trend', 'obv_divergence', 'vol_convergence']
BLOCKS = ['09:30-10:30', '10:30-11:30', '13:00-14:00', '14:00-15:00', 'next_day']
TODAY = datetime.now().strftime("%Y-%m-%d")


# ─── Market Regime Detection ────────────────────────────────────────────

def detect_market_regime(kdata: list) -> str:
    """Classify market state: trending / ranging / volatile."""
    if len(kdata) < 30:
        return 'ranging'
    if HAS_NUMPY:
        closes_arr = np.array([k[2] for k in kdata])
        highs_arr = np.array([k[3] for k in kdata])
        lows_arr = np.array([k[4] for k in kdata])
        n = min(14, len(kdata)-1)
        tr = np.maximum(highs_arr[:n]-lows_arr[:n],
                        np.abs(highs_arr[:n]-closes_arr[1:n+1]),
                        np.abs(lows_arr[:n]-closes_arr[1:n+1]))
        atr = np.mean(tr)
        if atr < 1e-6:
            return 'ranging'
        plus_dm = np.maximum(0, highs_arr[:n]-highs_arr[1:n+1])
        minus_dm = np.maximum(0, lows_arr[1:n+1]-lows_arr[:n])
        dm_mask = plus_dm > minus_dm
        plus_dm[~dm_mask] = 0; minus_dm[dm_mask] = 0
        plus_di = np.mean(plus_dm)/atr*100
        minus_di = np.mean(minus_dm)/atr*100
        denom = plus_di + minus_di
        adx = abs(plus_di-minus_di)/denom*100 if denom > 0 else 0
        rets = np.diff(closes_arr[:60]) / closes_arr[1:60] if len(closes_arr) > 60 else np.array([0])
        vol = np.std(rets) / (np.mean(np.abs(rets)) + 1e-6) if len(rets) > 1 else 1
        if adx > 25 and vol < 2.0:
            return 'trending'
        elif adx < 20 and vol < 1.5:
            return 'ranging'
        else:
            return 'volatile'
    return 'ranging'


# ─── Helpers ────────────────────────────────────────────────────────────

def _ema(data: list, n: int) -> float:
    """True Exponential Moving Average (EMA), not SMA."""
    k = 2.0 / (n + 1)
    result = sum(data[:n]) / n
    for price in data[n:]:
        result = price * k + result * (1 - k)
    return result


def _ema_series(data: 'np.ndarray', n: int) -> 'np.ndarray':
    """Compute prefix EMAs efficiently: result[i] = _ema(data[:i+1], n), in O(N).
    
    Replaces the O(N²) approach of calling _ema() for each prefix individually.
    Only used when HAS_NUMPY=True.
    """
    k = 2.0 / (n + 1)
    length = len(data)
    result = np.empty(length, dtype=np.float64)

    init_len = min(n, length)
    result[init_len - 1] = np.mean(data[:init_len])
    result[:init_len - 1] = 0.0

    for i in range(init_len, length):
        result[i] = data[i] * k + result[i - 1] * (1 - k)

    return result


def _calc_seasonal_from_db(code: str, get_db_func) -> list | None:
    """Compute seasonal factors from kline_monthly change_pct history.
    
    Requires a callable get_db_func that returns an sqlite3 connection
    with row_factory = Row.
    """
    db = get_db_func()
    rows = db.execute(
        "SELECT date, change_pct FROM kline_monthly WHERE code=? AND change_pct != 0 ORDER BY date",
        [code]
    ).fetchall()
    db.close()
    if not rows:
        return None
    month_stats = defaultdict(list)
    for r in rows:
        m = int(r[0][5:7])
        month_stats[m].append(r[1])
    factors = []
    for m in range(1, 13):
        values = month_stats.get(m, [])
        avg = round(sum(values) / len(values), 2) if values else 0
        scaled = 1.0 + avg * 3 / 100.0
        factors.append(max(0.80, min(1.20, round(scaled, 2))))
    return factors


def new_lp() -> dict:
    """Initialize fresh learning parameters (V3 with 10 signals)."""
    return {
        'signal_weights': {s: {b: 1.0 for b in BLOCKS} for s in SIGNALS},
        'hourly_bias': {b: 0.0 for b in BLOCKS},
        'seasonal_adj': {str(m): 0.0 for m in range(1, 13)},
        'confidence_beta': {
            'bullish': {'alpha': 1, 'beta': 1},
            'bearish':  {'alpha': 1, 'beta': 1},
            'neutral':  {'alpha': 1, 'beta': 1},
        },
        'learning_rate': 0.01, 'mw_beta': 0.7, 'update_count': 0,
    }


# ─── Signal Computation ─────────────────────────────────────────────────

def calc_signals(kdata: list, seasonal_factor: float = 1.0) -> dict | None:
    """
    Compute **10** technical signals from daily K-line data (V3 Enhanced).
    
    V3 adds 3 new signals (beyond original 7):
      - adx_trend: ADX > 25 with +DI/-DI direction
      - obv_divergence: OBV 5-day vs 20-day MA
      - vol_convergence: short-term / long-term volatility ratio
    
    Falls back to V2 (7 signals) if kdata < 20 bars.
    """
    if len(kdata) < 14:
        return None
    closes = [k[2] for k in kdata]
    highs  = [k[3] for k in kdata]
    lows   = [k[4] for k in kdata]
    close  = closes[0]

    n = min(14, len(kdata) - 1)
    atr = sum(max(highs[i] - lows[i], abs(highs[i] - closes[i + 1]),
                  abs(lows[i] - closes[i + 1])) for i in range(n)) / n

    n = min(14, len(closes) - 1)
    if HAS_NUMPY and n >= 2:
        closes_arr_np = np.array(closes[:n+1], dtype=np.float64)
        diffs = closes_arr_np[:-1] - closes_arr_np[1:]
        gains = float(np.sum(np.maximum(diffs, 0)))
        losses = float(np.sum(np.maximum(-diffs, 0)))
        rs = (gains / n) / (losses / n) if losses > 0 else 100
        rsi = 100 - 100 / (1 + rs)
    else:
        gains  = sum(max(closes[i] - closes[i + 1], 0) for i in range(n))
        losses = sum(max(closes[i + 1] - closes[i], 0) for i in range(n))
        rs = (gains / n) / (losses / n) if losses > 0 else 100
        rsi = 100 - 100 / (1 + rs)

    if HAS_NUMPY and len(closes) >= 33:
        # ── Vectorized MACD (O(N) instead of O(N²)) ──
        closes_arr = np.array(closes, dtype=np.float64)
        ema12s = _ema_series(closes_arr, 12)
        ema26s = _ema_series(closes_arr, 26)
        macd_series = ema12s - ema26s
        ema12 = float(ema12s[-1])
        ema26 = float(ema26s[-1])
        macd_val = ema12 - ema26
        end_idx = min(33, len(closes))
        if end_idx > 8:
            macd_vals_list = macd_series[8:end_idx].tolist()
            signal_val = _ema(list(reversed(macd_vals_list)) + [macd_val], 9)
        else:
            signal_val = macd_val
    else:
        ema12 = _ema(closes, 12)
        ema26 = _ema(closes, 26)
        macd_vals = [_ema(closes[:i+1], 12) - _ema(closes[:i+1], 26)
                     for i in range(8, min(33, len(closes)))]
        macd_val = ema12 - ema26
        signal_val = _ema(list(reversed(macd_vals)) + [macd_val], 9) if macd_vals else macd_val
    macd_pct = (macd_val / close) * 100
    macd_dir = 'bullish' if macd_val > signal_val else 'bearish'

    n = min(20, len(closes))
    if HAS_NUMPY and n >= 2:
        closes_slice = np.array(closes[:n], dtype=np.float64)
        bb_ma = float(np.mean(closes_slice))
        bb_std = float(np.std(closes_slice, ddof=0))
    else:
        bb_ma = sum(closes[:n]) / n
        bb_std = math.sqrt(sum((x - bb_ma) ** 2 for x in closes[:n]) / n)
    if close > bb_ma + 2 * bb_std * 0.98:
        bb_dir = 'bearish'
    elif close < bb_ma - 2 * bb_std * 1.02:
        bb_dir = 'bullish'
    else:
        bb_dir = 'neutral'

    n = min(9, len(kdata))
    kd_h, kd_l = max(highs[:n]), min(lows[:n])
    rsv = ((close - kd_l) / (kd_h - kd_l)) * 100 if kd_h != kd_l else 50
    k_val = 50 * 0.67 + rsv * 0.33
    d_val = 50 * 0.67 + k_val * 0.33
    j_val = 3 * k_val - 2 * d_val

    sf = seasonal_factor
    chg_3d = ((closes[0] - closes[3]) / closes[3]) * 100 if len(closes) > 3 else 0
    chg_10d = ((closes[0] - closes[10]) / closes[10]) * 100 if len(closes) > 10 else chg_3d

    # V3 NEW: ADX Trend (14-day)
    if HAS_NUMPY and len(kdata) >= 20:
        n_adx = min(14, len(kdata)-1)
        tr_adx = [max(highs[i]-lows[i], abs(highs[i]-closes[i+1]), abs(lows[i]-closes[i+1]))
                  for i in range(n_adx)]
        atr_adx = sum(tr_adx)/n_adx
        plus_dm = [max(0, highs[i]-highs[i+1]) if highs[i]-highs[i+1] > lows[i+1]-lows[i] else 0
                   for i in range(n_adx)]
        minus_dm = [max(0, lows[i+1]-lows[i]) if lows[i+1]-lows[i] > highs[i]-highs[i+1] else 0
                    for i in range(n_adx)]
        plus_di = sum(plus_dm)/n_adx/atr_adx*100 if atr_adx>0 else 0
        minus_di = sum(minus_dm)/n_adx/atr_adx*100 if atr_adx>0 else 0
        dx = abs(plus_di-minus_di)/(plus_di+minus_di)*100 if (plus_di+minus_di)>0 else 0
        adx = dx
        if adx > 25:
            adx_dir = 'bullish' if plus_di > minus_di else 'bearish'
        else:
            adx_dir = 'neutral'
        adx_raw = round(adx - 20, 0)
    else:
        adx_dir = 'neutral'
        plus_di, minus_di, adx = 0, 0, 20
        adx_raw = 0

    # V3 NEW: OBV Divergence
    if len(kdata) >= 20:
        obv_vals = [0]
        for i in range(1, min(25, len(kdata))):
            prev_close = closes[i-1]
            curr_close = closes[i]
            if curr_close > prev_close:
                obv_vals.append(obv_vals[-1] + (highs[i-1] - lows[i-1]))
            elif curr_close < prev_close:
                obv_vals.append(obv_vals[-1] - (highs[i-1] - lows[i-1]))
            else:
                obv_vals.append(obv_vals[-1])
        obv_list = list(reversed(obv_vals))
        obv_ma5 = sum(obv_list[:5])/5 if len(obv_list)>=5 else obv_list[-1]
        obv_ma20 = sum(obv_list[:20])/20 if len(obv_list)>=20 else obv_ma5
        obv_dir = 'bullish' if obv_ma5 > obv_ma20 else 'bearish' if obv_ma5 < obv_ma20 else 'neutral'
        obv_raw = round((obv_ma5-obv_ma20)/max(abs(obv_ma20),1), 2)
    else:
        obv_dir = 'neutral'
        obv_raw = 0

    # V3 NEW: Volatility Convergence
    if HAS_NUMPY and len(kdata) >= 22:
        rets = [(closes[i]-closes[i+1])/closes[i+1]*100 for i in range(min(20, len(kdata)-1))]
        vol_s = np.std(rets[:10]) if len(rets)>=10 else np.std(rets)
        vol_l = np.std(rets[:20]) if len(rets)>=20 else vol_s
        vol_ratio = vol_s/vol_l if vol_l>0 else 1
        if vol_ratio < 0.8:
            vol_dir = 'bullish'
        elif vol_ratio > 1.5:
            vol_dir = 'bearish'
        else:
            vol_dir = 'neutral'
        vol_raw = round(vol_ratio, 2)
    else:
        vol_dir = 'neutral'
        vol_raw = 1.0

    return {
        'close': close, 'atr': round(atr, 3),
        'signals': {
            'macd': {'value': f'{macd_pct:+.2f}%', 'direction': macd_dir,
                     'raw': round(macd_pct, 2)},
            'rsi': {'value': round(rsi, 1),
                    'direction': 'bullish' if rsi > 55 else 'bearish' if rsi < 45 else 'neutral',
                    'raw': round(rsi, 1)},
            'bollinger': {'direction': bb_dir, 'value': f'{round((close-bb_ma)/bb_std,2)}σ',
                          'raw': round((close-bb_ma)/bb_std, 2)},
            'kdj': {'value': f'K{round(k_val,0)} D{round(d_val,0)} J{round(j_val,0)}',
                    'raw': round(j_val, 0),
                    'direction': 'bearish' if j_val > 80 else 'bullish' if j_val < 20 else 'neutral'},
            'seasonal': {'direction': 'bullish' if sf > 1 else 'bearish',
                        'raw': round(sf, 2), 'value': f'{sf:.2f}x', 'factor': sf},
            'atr': {'value': round(atr, 3), 'pct': round(atr/close*100, 2),
                    'direction': 'neutral', 'raw': round(atr, 3)},
            'money_flow': {'direction': 'bullish' if chg_3d>1 and chg_10d>0
                           else 'bearish' if chg_3d<-1 and chg_10d<0
                           else 'bullish' if chg_3d>2.5 else 'bearish' if chg_3d<-2.5 else 'neutral',
                           'value': f'{chg_3d:+.1f}%', 'raw': round(chg_3d, 2)},
            'adx_trend': {'direction': adx_dir,
                          'value': f'ADX{round(adx,0)}+DI{round(plus_di,0)}-DI{round(minus_di,0)}',
                          'raw': adx_raw},
            'obv_divergence': {'direction': obv_dir,
                               'value': 'OBV5/20',
                               'raw': obv_raw},
            'vol_convergence': {'direction': vol_dir,
                                'value': f'{vol_raw:.2f}x',
                                'raw': vol_raw},
        },
    }


# ─── Prediction Generation ──────────────────────────────────────────────

def gen_pred(code: str, info: dict, lp: dict) -> dict:
    """Generate a daily prediction from signals and learning params (V3 Enhanced).
    
    V3 improvements:
    - 10-signal weighted voting (includes ADX, OBV, Vol convergence)
    - Adaptive confidence: floor starts higher, adjusts with experience
    - Consensus: uses signal count ratio for robustness
    """
    close = info['close']
    atr = info['atr']
    sig = info['signals']
    w = lp['signal_weights']
    # Ensure V3 weights exist
    for sn in SIGNALS:
        if sn not in w:
            w[sn] = {b: 1.0 for b in BLOCKS}

    bias = lp['hourly_bias']
    sa = lp['seasonal_adj']

    bullish_count = sum(1 for s in SIGNALS if sig[s]['direction'] == 'bullish')
    bearish_count = sum(1 for s in SIGNALS if sig[s]['direction'] == 'bearish')
    ws = sum(w[s]['next_day'] * (1 if sig[s]['direction'] == 'bullish'
              else -1 if sig[s]['direction'] == 'bearish' else 0) for s in SIGNALS)
    ws += sa.get(str(datetime.now().month), 0) * 2
    dd = 'bullish' if ws > 0.5 else 'bearish' if ws < -0.5 else 'neutral'

    cb = lp['confidence_beta'].get(dd, {'alpha': 1, 'beta': 1})
    beta_conf = cb['alpha'] / (cb['alpha'] + cb['beta']) if (cb['alpha']+cb['beta']) > 0 else 0.5
    if dd == 'bullish':
        consensus = bullish_count/(bullish_count+bearish_count) if (bullish_count+bearish_count) > 0 else 0.5
    elif dd == 'bearish':
        consensus = bearish_count/(bullish_count+bearish_count) if (bullish_count+bearish_count) > 0 else 0.5
    else:
        consensus = 0.5

    n = lp.get('update_count', 0)
    conf_floor = max(0.30, 0.40 - n * 0.001)
    conf = round(0.5 * consensus + 0.3 * beta_conf + 0.2 * (abs(ws)/5), 2)
    conf = max(conf_floor, min(0.85, conf))

    dr = atr * 2.5
    nh, nl = round(close + dr * 0.55, 2), round(close - dr * 0.45, 2)

    hws = [('09:30-10:30', 0.35, '开盘消化隔夜信息'), ('10:30-11:30', 0.20, '横盘整理'),
           ('13:00-14:00', 0.20, '午后资金活跃'), ('14:00-15:00', 0.25, '尾盘主力动作')]
    cum = close
    hp = []
    for block, pct, note in hws:
        sd = dr * pct
        hs = sum(w[s][block] * (1 if sig[s]['direction'] == 'bullish'
                  else -1 if sig[s]['direction'] == 'bearish' else 0) for s in SIGNALS)
        hs += bias.get(block, 0) * 2
        hd = 'bullish' if hs > 0.3 else 'bearish' if hs < -0.3 else 'neutral'
        off = close * bias.get(block, 0) * 2
        hh = round(cum + sd * 0.5 + off, 2)
        hl = round(cum - sd * 0.5 + off, 2)
        hc = round(cum + off, 2)
        hp.append({'block': block, 'pred_open': round(cum, 2) if not hp else round(hp[-1]['pred_close'], 2),
                   'pred_high': min(hh, nh), 'pred_low': max(hl, nl), 'pred_close': hc,
                   'direction': hd, 'strength': min(5, max(1, int(abs(hs)))), 'note': note})
        cum = hc

    advice = ('低吸为主' if conf > 0.6 else '谨慎看多') if dd == 'bullish' else \
             ('观望为主' if dd == 'neutral' else 
              ('逢高减仓' if conf > 0.6 else '谨慎看空'))
    return {
        'date': TODAY, 'code': code, 'prev_close': close,
        'next_day': {'direction': dd, 'confidence': conf, 'high': nh, 'low': nl,
                     'advice': advice, 'entry_zone': nl if dd == 'bullish' else nh,
                     'weighted_score': round(float(ws), 2),
                     'signals_bullish': bullish_count, 'signals_bearish': bearish_count},
        'hourly': hp, 'signals': sig,
        'actual': {'open': None, 'high': None, 'low': None, 'close': None,
                   'next_day_direction_hit': None, 'daily_range_hit': None,
                   'hourly_hits': [None] * 4},
    }


def _next_trading_dates(start_date: str, count: int) -> list:
    """Generate count future trading dates (skip Sat/Sun) starting from start_date."""
    dates = []
    base = datetime.strptime(start_date, '%Y-%m-%d')
    d = base
    while len(dates) < count:
        d = d + timedelta(days=1)
        if d.weekday() < 5:
            dates.append(d.strftime('%Y-%m-%d'))
    return dates


def gen_multi_day_pred(code: str, kdata: list, info: dict, lp: dict,
                       num_days: int = 10, start_date: str = None,
                       sf_cache: list = None) -> list:
    """Generate num_days of daily predictions using iterative V3 forecasting."""
    close = info['close']
    atr = info['atr']
    sig = info['signals']
    w = lp['signal_weights']
    for sn in SIGNALS:
        if sn not in w:
            w[sn] = {b: 1.0 for b in BLOCKS}

    day1 = gen_pred(code, info, lp)
    preds = [day1]

    if num_days <= 1:
        return preds

    closes = [k[2] for k in kdata]
    daily_returns = [abs(closes[i] / closes[i + 1] - 1) for i in range(min(len(closes) - 1, 120))]
    avg_daily_move = sum(daily_returns) / len(daily_returns) if daily_returns else atr / close

    dd = day1['next_day']['direction']
    dir_sign = 1 if dd == 'bullish' else -1 if dd == 'bearish' else 0
    base_conf = day1['next_day']['confidence']
    if dd == 'bullish':
        base_close = close * (1 + avg_daily_move * 0.5)
    elif dd == 'bearish':
        base_close = close * (1 - avg_daily_move * 0.5)
    else:
        base_close = close

    trading_dates = _next_trading_dates(start_date or TODAY, num_days)
    if len(trading_dates) < num_days:
        base_dt = datetime.strptime(start_date or TODAY, '%Y-%m-%d')
        trading_dates = [(base_dt + timedelta(days=i + 1)).strftime('%Y-%m-%d') for i in range(num_days)]

    prev_close = base_close
    sf = sf_cache or [1.0] * 12

    for i in range(1, num_days):
        day_num = i + 1
        pred_date = trading_dates[i-1] if i-1 < len(trading_dates) else trading_dates[-1]

        momentum_decay = 0.90 ** day_num
        effective_dir_sign = dir_sign * momentum_decay
        if abs(effective_dir_sign) < 0.15:
            effective_dir_sign = 0

        vol_scale = min(3.0, 1.0 + 0.25 * (day_num ** 0.5))
        daily_drift = avg_daily_move * effective_dir_sign

        try:
            pred_month = datetime.strptime(pred_date, '%Y-%m-%d').month
        except ValueError:
            pred_month = (datetime.now().month + day_num - 1) % 12 + 1
        seasonal_bias = (sf[pred_month - 1] - 1.0) * 0.3 / 22.0 if sf else 0

        predicted_close = prev_close * (1 + daily_drift + seasonal_bias)
        day_range = atr * vol_scale * 2.0
        predicted_high = round(predicted_close + day_range * 0.55, 2)
        predicted_low = round(predicted_close - day_range * 0.45, 2)
        predicted_close = round(predicted_close, 2)

        conf_decay = 0.93 ** day_num
        predicted_conf = round(max(0.15, base_conf * conf_decay), 2)

        if effective_dir_sign > 0.05:
            day_dir = 'bullish'
        elif effective_dir_sign < -0.05:
            day_dir = 'bearish'
        else:
            day_dir = 'neutral'

        advice = '低吸为主' if predicted_conf > 0.5 else '谨慎看多' if day_dir == 'bullish' else \
                 '逢高减仓' if predicted_conf > 0.5 else '谨慎看空' if day_dir == 'bearish' else '观望为主'

        preds.append({
            'date': pred_date, 'code': code, 'prev_close': round(prev_close, 2),
            'next_day': {
                'direction': day_dir, 'confidence': predicted_conf,
                'high': predicted_high, 'low': predicted_low,
                'advice': advice,
                'entry_zone': predicted_low if day_dir == 'bullish' else predicted_high,
                'weighted_score': round(effective_dir_sign * 5, 2),
                'signals_bullish': 0, 'signals_bearish': 0,
            },
            'hourly': [], 'signals': sig,
            'actual': {'open': None, 'high': None, 'low': None, 'close': None,
                       'next_day_direction_hit': None, 'daily_range_hit': None,
                       'hourly_hits': [None] * 4},
        })
        prev_close = predicted_close

    return preds
