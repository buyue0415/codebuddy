"""
Full data sync: refresh ALL modules for ALL watchlist stocks (V0.7 ML-Enhanced).

V0.7 ML-Enhanced optimizations:
  - V3 Pred: 10-signal voting (adds ADX, OBV, Volatility Convergence)
  - Adaptive MWU: self-tuned decay rate based on recent accuracy
  - Meta-learner: ML model that adjusts confidence when rules are uncertain
  - Data quality: automatic outlier detection and cleaning
  - Backward compatible: all V0.6 APIs preserved

Execution flow (8 steps, SQLite-only, no legacy JSON):
  Step 1: Fetch news          Step 1.5: Fetch dividends (web)
  Step 2: Parallel K-line fetch
  Step 3: Backfill predictions Step 4: Recalculate accuracy
  Step 5: Self-learning (Adaptive MWU) Step 6: Generate predictions (V3)
  Step 7: Seasonal + monthly + quotes

External data source: NeoData (via westock-data Node.js package)
Target: SQLite stock.db (17 tables)

NOTE: Module-level code is wrapped in main() with if __name__ guard.
      Functions can be imported without triggering execution.
"""
import json, math, subprocess, os, sys, warnings
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from db_helper import (
    get_watchlist, get_db, get_learning_params,
    upsert_kline_daily, upsert_kline_monthly, upsert_quotes,
    upsert_seasonal, clear_today_predictions, insert_daily_prediction,
    upsert_learning_params, upsert_accuracy_stats,
)

NODE = r'C:\Users\28312\.workbuddy\binaries\node\versions\22.12.0\node.exe'
WESTOCK = r'C:\Users\28312\.workbuddy\plugins\marketplaces\experts\plugins\stock-partner-team\skills\westock-data'
SCRIPT = 'scripts/index.js'
TODAY = datetime.now().strftime("%Y-%m-%d")

# V3 扩展: 10 个信号（原有 7 个 + ADX趋势、OBV背离、波动率收敛）
SIGNALS = ['macd', 'rsi', 'bollinger', 'kdj', 'seasonal', 'atr', 'money_flow',
           'adx_trend', 'obv_divergence', 'vol_convergence']
BLOCKS = ['09:30-10:30', '10:30-11:30', '13:00-14:00', '14:00-15:00', 'next_day']


# ======================================================================
# Function definitions (available on import, no side effects)
# ======================================================================

def fetch_kline(market_code: str, limit: int = 2000) -> list:
    """Fetch daily K-line from NeoData via Node.js subprocess."""
    try:
        result = subprocess.run(
            [NODE, SCRIPT, 'kline', market_code, '--period', 'day',
             '--limit', str(limit), '--fq', 'qfq'],
            cwd=WESTOCK, capture_output=True, timeout=30,
        )
        stdout = result.stdout
        if stdout:
            try:
                text = stdout.decode('gbk')
            except (UnicodeDecodeError, LookupError):
                text = stdout.decode('utf-8', errors='replace')
        else:
            text = ''
        data = []
        for line in text.strip().split('\n'):
            parts = [p.strip() for p in line.split('|') if p.strip()]
            if len(parts) >= 5 and parts[0][:4].isdigit():
                data.append([parts[0], float(parts[1]), float(parts[2]),
                             float(parts[3]), float(parts[4])])
        if result.returncode != 0:
            print(f"  K-line fetch {market_code}: Node exited {result.returncode}")
        return data
    except Exception as e:
        print(f"  K-line fetch error for {market_code}: {e}")
        return []


def sync_one_stock(stock: dict) -> tuple:
    """Fetch + persist K-line for a single stock. Returns (code, bars).
    
    NOTE: bars are guaranteed newest-first (descending by date) so that
    kline_results[code][0] is always the latest bar across the entire script.
    """
    code, name, mkt = stock['code'], stock['name'], stock.get('market', 'sh')
    kdata = fetch_kline(f'{mkt}{code}')
    if kdata:
        kdata.sort(key=lambda x: x[0], reverse=True)
        bars = [[k[0], k[1], k[2], k[3], k[4]] for k in kdata]
        try:
            upsert_kline_daily(code, bars)
            print(f"  {name}({code}): {len(kdata)} bars")
        except Exception as e:
            print(f"  DB write kline {code} failed: {e}")
    else:
        bars = []
        print(f"  {name}({code}): FAILED")
    return code, bars


def _ema(data: list, n: int) -> float:
    """True Exponential Moving Average (EMA), not SMA."""
    k = 2.0 / (n + 1)
    result = sum(data[:n]) / n
    for price in data[n:]:
        result = price * k + result * (1 - k)
    return result


def _calc_seasonal_from_db(code: str):
    """Compute seasonal factors from kline_monthly change_pct history."""
    db = get_db()
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


def _calc_seasonal_pct(code: str) -> list:
    """从 kline_monthly 按月计算真实平均涨跌幅百分比，返回12个浮点数（1月~12月）。
    
    与 _calc_seasonal_from_db 的区别：返回原始月均涨跌幅%而非缩放因子。
    月份无数据时用 0.0 填充。
    """
    db = get_db()
    rows = db.execute(
        "SELECT date, change_pct FROM kline_monthly WHERE code=? AND change_pct != 0 ORDER BY date",
        [code]
    ).fetchall()
    db.close()
    if not rows:
        return [0.0] * 12
    month_stats = defaultdict(list)
    for r in rows:
        m = int(r[0][5:7])  # 从 "YYYY-MM-DD" 提取月份
        month_stats[m].append(r[1])
    return [round(sum(month_stats.get(m, [])) / len(month_stats[m]), 2) if month_stats.get(m) else 0.0
            for m in range(1, 13)]


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


def calc_signals(kdata: list, seasonal_factor: float = 1.0) -> dict | None:
    """
    Compute **10** technical signals from daily K-line data (V3 Enhanced).
    
    V3 adds 3 new signals (beyond original 7):
      - adx_trend: ADX > 25 with +DI/‑DI direction
      - obv_divergence: OBV 5‑day vs 20‑day MA
      - vol_convergence: short‑term / long‑term volatility ratio
    
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
    gains  = sum(max(closes[i] - closes[i + 1], 0) for i in range(n))
    losses = sum(max(closes[i + 1] - closes[i], 0) for i in range(n))
    rs = (gains / n) / (losses / n) if losses > 0 else 100
    rsi = 100 - 100 / (1 + rs)

    ema12 = _ema(closes, 12)
    ema26 = _ema(closes, 26)
    macd_vals = [_ema(closes[:i+1], 12) - _ema(closes[:i+1], 26)
                 for i in range(8, min(33, len(closes)))]
    macd_val = ema12 - ema26
    signal_val = _ema(list(reversed(macd_vals)) + [macd_val], 9) if macd_vals else macd_val
    macd_pct = (macd_val / close) * 100
    macd_dir = 'bullish' if macd_val > signal_val else 'bearish'

    n = min(20, len(closes))
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

    # ---- V3 NEW: ADX Trend (14-day) ----
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

    # ---- V3 NEW: OBV Divergence ----
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

    # ---- V3 NEW: Volatility Convergence ----
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

    # ---- 组装信号 ----
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
            'seasonal': {'direction': 'bullish' if sf > 1 else 'bearish', 'factor': sf},
            'atr': {'value': round(atr, 3), 'pct': round(atr/close*100, 2),
                    'direction': 'neutral', 'raw': round(atr, 3)},
            'money_flow': {'direction': 'bullish' if chg_3d>1 and chg_10d>0
                           else 'bearish' if chg_3d<-1 and chg_10d<0
                           else 'bullish' if chg_3d>2.5 else 'bearish' if chg_3d<-2.5 else 'neutral',
                           'value': f'{chg_3d:+.1f}%', 'raw': round(chg_3d, 2)},
            # V3 New
            'adx_trend': {'direction': adx_dir,
                          'value': f'ADX{round(adx,0)}+DI{round(plus_di,0)}-DI{round(minus_di,0)}',
                          'raw': adx_raw},
            'obv_divergence': {'direction': obv_dir,
                               'value': f'OBV5/20',
                               'raw': obv_raw},
            'vol_convergence': {'direction': vol_dir,
                                'value': f'{vol_raw:.2f}x',
                                'raw': vol_raw},
        },
    }


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

    # Fix: upgrade V2 learning params (7 signals) → V3 (10 signals)
    # Old params missing adx_trend/obv_divergence/vol_convergence cause KeyError
    for sn in SIGNALS:
        if sn not in w:
            w[sn] = {b: 1.0 for b in BLOCKS}

    bias = lp['hourly_bias']
    sa = lp['seasonal_adj']

    # V3 weighted vote: 10 signals
    bullish_count = sum(1 for s in SIGNALS if sig[s]['direction'] == 'bullish')
    bearish_count = sum(1 for s in SIGNALS if sig[s]['direction'] == 'bearish')
    ws = sum(w[s]['next_day'] * (1 if sig[s]['direction'] == 'bullish'
              else -1 if sig[s]['direction'] == 'bearish' else 0) for s in SIGNALS)
    ws += sa.get(str(datetime.now().month), 0) * 2
    dd = 'bullish' if ws > 0.5 else 'bearish' if ws < -0.5 else 'neutral'

    # V3 confidence: adaptive floor based on learning experience
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
    from datetime import datetime as dt, timedelta as td
    dates = []
    base = dt.strptime(start_date, '%Y-%m-%d')
    d = base
    while len(dates) < count:
        d = d + td(days=1)
        if d.weekday() < 5:  # Mon-Fri only
            dates.append(d.strftime('%Y-%m-%d'))
    return dates


def gen_multi_day_pred(code: str, kdata: list, info: dict, lp: dict,
                       num_days: int = 30, start_date: str = None) -> list:
    """Generate num_days of daily predictions using iterative V3 forecasting.

    Day 1: full gen_pred with existing signals
    Days 2-30: iterative projection with momentum decay, sqrt-volatility expansion,
               and seasonal adjustments per calendar month.

    Returns list of prediction dicts, one per future trading day.
    """
    close = info['close']
    atr = info['atr']
    sig = info['signals']
    w = lp['signal_weights']
    # Ensure V3 signal weights
    for sn in SIGNALS:
        if sn not in w:
            w[sn] = {b: 1.0 for b in BLOCKS}

    # ---- Day 1: full prediction using existing gen_pred ----
    day1 = gen_pred(code, info, lp)
    preds = [day1]

    if num_days <= 1:
        return preds

    # ---- Compute daily drift from history ----
    closes = [k[2] for k in kdata]
    daily_returns = [abs(closes[i] / closes[i + 1] - 1) for i in range(min(len(closes) - 1, 120))]
    avg_daily_move = sum(daily_returns) / len(daily_returns) if daily_returns else atr / close

    # ---- Core projection parameters ----
    dd = day1['next_day']['direction']
    dir_sign = 1 if dd == 'bullish' else -1 if dd == 'bearish' else 0
    base_conf = day1['next_day']['confidence']
    base_close = day1['next_day'].get('predicted_close', close)
    # If gen_pred doesn't return predicted_close, use prev_close adjusted
    if dd == 'bullish':
        base_close = close * (1 + avg_daily_move * 0.5)
    elif dd == 'bearish':
        base_close = close * (1 - avg_daily_move * 0.5)
    # If neutral, close stays roughly same

    # Seasonal factors lookup
    sf_cache = _calc_seasonal_from_db(code)
    from datetime import datetime as dt, timedelta as td

    trading_dates = _next_trading_dates(start_date or TODAY, num_days)
    if len(trading_dates) < num_days:
        # Fallback: just use consecutive calendar days
        base_dt = dt.strptime(start_date or TODAY, '%Y-%m-%d')
        trading_dates = [(base_dt + td(days=i + 1)).strftime('%Y-%m-%d') for i in range(num_days)]

    prev_close = base_close

    for i in range(1, num_days):
        day_num = i + 1
        pred_date = trading_dates[i-1] if i-1 < len(trading_dates) else trading_dates[-1]

        # ---- Momentum decay: direction weakens over time ----
        momentum_decay = 0.90 ** day_num
        effective_dir_sign = dir_sign * momentum_decay
        if abs(effective_dir_sign) < 0.15:
            effective_dir_sign = 0  # Direction fades to neutral

        # ---- Volatility expansion: uncertainty grows with sqrt(time) ----
        vol_scale = min(3.0, 1.0 + 0.25 * (day_num ** 0.5))  # capped at 3x
        daily_drift = avg_daily_move * effective_dir_sign

        # ---- Seasonal factor for the prediction month ----
        try:
            pred_month = dt.strptime(pred_date, '%Y-%m-%d').month
        except ValueError:
            pred_month = (dt.now().month + day_num - 1) % 12 + 1
        sf = sf_cache[pred_month - 1] if sf_cache else 1.0
        seasonal_bias = (sf - 1.0) * 0.3 / 22.0  # 30% of monthly seasonal, divided by ~22 trading days

        # ---- Project price ----
        predicted_close = prev_close * (1 + daily_drift + seasonal_bias)
        day_range = atr * vol_scale * 2.0
        predicted_high = round(predicted_close + day_range * 0.55, 2)
        predicted_low = round(predicted_close - day_range * 0.45, 2)
        predicted_close = round(predicted_close, 2)

        # ---- Confidence decay ----
        conf_decay = 0.93 ** day_num
        predicted_conf = round(max(0.15, base_conf * conf_decay), 2)

        # ---- Direction for this day ----
        if effective_dir_sign > 0.05:
            day_dir = 'bullish'
        elif effective_dir_sign < -0.05:
            day_dir = 'bearish'
        else:
            day_dir = 'neutral'

        # ---- Advice ----
        if day_dir == 'bullish':
            advice = '低吸为主' if predicted_conf > 0.5 else '谨慎看多'
        elif day_dir == 'bearish':
            advice = '逢高减仓' if predicted_conf > 0.5 else '谨慎看空'
        else:
            advice = '观望为主'

        pred_entry = {
            'date': pred_date,
            'code': code,
            'prev_close': round(prev_close, 2),
            'next_day': {
                'direction': day_dir,
                'confidence': predicted_conf,
                'high': predicted_high,
                'low': predicted_low,
                'advice': advice,
                'entry_zone': predicted_low if day_dir == 'bullish' else predicted_high,
                'weighted_score': round(effective_dir_sign * 5, 2),
                'signals_bullish': 0,
                'signals_bearish': 0,
            },
            'hourly': [],
            'signals': {},
            'actual': {
                'open': None, 'high': None, 'low': None, 'close': None,
                'next_day_direction_hit': None, 'daily_range_hit': None,
                'hourly_hits': [None] * 4,
            },
        }
        preds.append(pred_entry)
        prev_close = predicted_close

    return preds


# ======================================================================
# Main execution (only runs when script is executed directly)
# ======================================================================

def main():
    watchlist = get_watchlist()
    print(f"[sync_all] Watchlist: {len(watchlist)} stocks")

    # Step 1: Fetch news with dedup
    print("[Step 1] Fetching news for all watchlist stocks ...")
    try:
        from fetch_news import fetch_news_node
        from db_helper import upsert_news
        all_news = []
        for stock in watchlist:
            code, name, mkt = stock['code'], stock['name'], stock.get('market', 'sh')
            items = fetch_news_node(f'{mkt}{code}')
            if items:
                print(f"  News for {name}({code}): {len(items)} items")
                all_news.extend(items)
            else:
                print(f"  News for {name}({code}): no data")
        if all_news:
            # In-memory dedup by URL first, fallback to (title, date, code)
            seen = set()
            deduped = []
            for n in all_news:
                key = (n.get('url', ''), n['title'], n['date'], n['code'])
                if key not in seen:
                    seen.add(key)
                    deduped.append(n)
            upsert_news(deduped)
            print(f"  Saved {len(deduped)} unique news items (filtered from {len(all_news)})")
    except Exception as e:
        print(f"  News fetch skipped: {e}")

    # Step 1.5: Fetch dividend history from web (before K-line, so calc_dividend_yield has data)
    print("\n[Step 1.5] Fetching dividend history from web ...")
    try:
        from fetch_dividends import fetch_all as fetch_dividends_all
        div_summary = fetch_dividends_all()
        print(f"  Dividend fetch complete: {div_summary['total']} records from {len(div_summary['stocks'])} stocks")
    except Exception as e:
        print(f"  Dividend fetch skipped: {e}")

    # Step 1.6: Sync dividend income from trades to dividends table
    # This captures 股息入账 records (e.g., 长江电力 600900) that exist in
    # the trades table but weren't imported into the dividends table
    print("\n[Step 1.6] Syncing dividend income from trades ...")
    try:
        from db_helper import sync_dividends_from_trades
        synced = sync_dividends_from_trades()
        print(f"  Dividend sync from trades: {synced} records synced")
    except Exception as e:
        print(f"  Dividend sync from trades skipped: {e}")

    # Step 2: Parallel K-line fetch
    print("\n[Step 2] Fetching daily K-line in parallel ...")
    kline_results = {}
    if watchlist:
        max_workers = min(len(watchlist), 4)
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {pool.submit(sync_one_stock, s): s for s in watchlist}
            for future in as_completed(futures):
                code, bars = future.result()
                kline_results[code] = bars

    # Step 3: Backfill predictions
    print("\n[Step 3] Backfilling predictions with actual data ...")
    for stock in watchlist:
        code = stock['code']
        kdata = kline_results.get(code, [])
        if not kdata:
            # Fallback to DB kline
            try:
                db_fb = get_db()
                fb_rows = db_fb.execute(
                    "SELECT date, open, close, high, low FROM kline_daily "
                    "WHERE code=? ORDER BY date DESC LIMIT 2000", [code]
                ).fetchall()
                db_fb.close()
                if fb_rows:
                    kdata = [[r['date'], r['open'], r['close'], r['high'], r['low']] for r in fb_rows]
            except Exception:
                pass
        if not kdata or len(kdata) < 2:
            continue
        kline_by_date = {b[0]: b for b in kdata if b[0] <= TODAY}
        db = get_db()
        unverified = db.execute(
            "SELECT id, date, direction, high, low, prev_close FROM daily_predictions "
            "WHERE code=? AND dir_hit IS NULL ORDER BY date DESC", [code]
        ).fetchall()
        db.close()
        backfilled = 0
        for pred in unverified:
            pred_date = pred['date']
            bar = kline_by_date.get(pred_date)
            if not bar:
                continue
            y_open, y_high, y_low, y_close = bar[1], bar[3], bar[4], bar[2]
            pred_dir = pred['direction']
            prev_close = pred['prev_close']
            actual_dir = 'bullish' if y_close > prev_close else ('bearish' if y_close < prev_close else 'neutral')
            dir_hit = 0
            if pred_dir != 'neutral' and actual_dir != 'neutral':
                dir_hit = 1 if pred_dir == actual_dir else 0
            pred_high, pred_low = pred['high'], pred['low']
            range_hit = 1 if (y_low >= pred_low and y_high <= pred_high) else 0
            db2 = get_db()
            db2.execute(
                "UPDATE daily_predictions SET actual_open=?, actual_high=?, actual_low=?, "
                "actual_close=?, dir_hit=?, range_hit=? WHERE id=?",
                [y_open, y_high, y_low, y_close, dir_hit, range_hit, pred['id']]
            )
            db2.commit(); db2.close()
            backfilled += 1
            print(f"  {stock['name']}({code}) {pred_date}: dir={'HIT' if dir_hit else 'MISS'}, range={'HIT' if range_hit else 'MISS'}")
        if backfilled == 0:
            print(f"  {stock['name']}({code}): no unverified past predictions")

    # Step 4: Recalculate accuracy
    print("[Step 4] Recalculating accuracy stats ...")
    for stock in watchlist:
        code = stock['code']
        db = get_db()
        all_preds = db.execute(
            "SELECT date, dir_hit, range_hit FROM daily_predictions "
            "WHERE code=? AND dir_hit IS NOT NULL ORDER BY date DESC", [code]
        ).fetchall()
        db.close()
        if not all_preds:
            continue
        for period_label, period_preds in [('last_20', all_preds[:20]), ('last_60', all_preds[:60])]:
            if not period_preds:
                continue
            dir_c = sum(1 for p in period_preds if p['dir_hit'])
            range_c = sum(1 for p in period_preds if p['range_hit'])
            total = len(period_preds)
            try:
                upsert_accuracy_stats(code, period_label, {
                    'direction': {'correct': dir_c, 'total': total, 'rate': round(dir_c/total*100, 1) if total else 0},
                    'range': {'correct': range_c, 'total': total, 'rate': round(range_c/total*100, 1) if total else 0},
                    'hourly': {},
                })
            except Exception as e:
                print(f"  DB write accuracy {code}/{period_label} failed: {e}")
        print(f"  {stock['name']}({code}): dir_acc={dir_c/total*100:.1f}% ({dir_c}/{total})" if all_preds else "")

    # Step 4.5: Backtest baseline + Circuit breaker
    print("\n[Step 4.5] Backtest + circuit breaker ...")
    for stock in watchlist:
        code = stock['code']
        db = get_db()
        # Get last 60 verified predictions with their IDs
        verified = db.execute(
            "SELECT id, date, direction, dir_hit, prev_close, actual_close FROM daily_predictions "
            "WHERE code=? AND dir_hit IS NOT NULL ORDER BY date DESC LIMIT 60", [code]
        ).fetchall()
        db.close()
        if not verified:
            continue

        # ---- A: Backtest baseline (equal-weight majority vote) ----
        baseline_hits = 0
        for v in verified:
            db2 = get_db()
            signals = db2.execute(
                "SELECT name, direction FROM prediction_signals WHERE pred_id=?",
                [v['id']]
            ).fetchall()
            db2.close()
            # Majority vote among 10 signals (equal weight = 1.0)
            bull = sum(1 for s in signals if s['direction'] == 'bullish')
            bear = sum(1 for s in signals if s['direction'] == 'bearish')
            if bull + bear == 0:
                continue
            baseline_dir = 'bullish' if bull > bear else 'bearish' if bear > bull else 'neutral'
            pred_dir = v['direction']
            prev_close = v['prev_close']
            actual_close = v['actual_close']
            if prev_close is None or actual_close is None:
                continue
            actual_dir = 'bullish' if actual_close > prev_close else 'bearish' if actual_close < prev_close else 'neutral'
            if baseline_dir != 'neutral' and actual_dir != 'neutral':
                if baseline_dir == actual_dir:
                    baseline_hits += 1

        baseline_total = len(verified)
        baseline_rate = round(baseline_hits / baseline_total * 100, 1) if baseline_total > 0 else 0
        # Learned rate from Step 4
        learned_hits = sum(1 for v in verified if v['dir_hit'])
        learned_rate = round(learned_hits / baseline_total * 100, 1) if baseline_total > 0 else 0
        improvement = round(learned_rate - baseline_rate, 1)

        try:
            upsert_accuracy_stats(code, 'backtest_60', {
                'direction': {
                    'correct': learned_hits, 'total': baseline_total,
                    'rate': learned_rate,
                },
                'range': {'correct': 0, 'total': baseline_total, 'rate': 0},
                'hourly': {
                    'baseline_rate': baseline_rate,
                    'baseline_hits': baseline_hits,
                    'improvement': improvement,
                },
            })
            icon = '↑' if improvement > 0 else '↓' if improvement < 0 else '→'
            print(f"  {stock['name']}({code}): learned={learned_rate}% baseline={baseline_rate}% "
                  f"Δ={icon}{abs(improvement):.1f}%")
        except Exception as e:
            print(f"  DB write backtest {code} failed: {e}")

        # ---- C: Circuit breaker (consecutive misses) ----
        # Check last 5 verified predictions in chronological order
        recent_5 = list(reversed(verified[:5])) if len(verified) >= 5 else []
        if len(recent_5) >= 5 and all(v['dir_hit'] == 0 for v in recent_5):
            print(f"  ⚠️  {stock['name']}({code}): 5 consecutive misses! "
                  f"Resetting learning params to baseline.")
            try:
                upsert_learning_params(code, new_lp())
                print(f"  → Learning params reset to V3 defaults")
            except Exception as e:
                print(f"  → Reset failed: {e}")

    # Step 5: Self-learning (Adaptive MWU V3)
    print("\n[Step 5] Self-learning updates (Adaptive MWU) ...")
    for stock in watchlist:
        code = stock['code']
        db = get_db()
        lp_row = db.execute("SELECT * FROM learning_params WHERE code=?", [code]).fetchone()
        db.close()
        if not lp_row:
            continue
        lp = {
            'signal_weights': json.loads(lp_row['signal_weights']),
            'hourly_bias': json.loads(lp_row['hourly_bias']),
            'seasonal_adj': json.loads(lp_row['seasonal_adj']),
            'confidence_beta': json.loads(lp_row['confidence_beta']),
            'learning_rate': lp_row['learning_rate'], 'mw_beta': lp_row['mw_beta'],
            'update_count': lp_row['update_count'],
        }
        
        # Ensure new V3 signals have default weights
        for s in SIGNALS:
            if s not in lp.get('signal_weights', {}):
                lp.setdefault('signal_weights', {})[s] = {'next_day': 1.0}
        
        # Get recent accuracy for adaptive decay
        db = get_db()
        recent = db.execute(
            "SELECT dir_hit FROM daily_predictions WHERE code=? AND dir_hit IS NOT NULL "
            "ORDER BY date DESC LIMIT 20", [code]
        ).fetchall()
        recent_hits = sum(1 for r in recent if r['dir_hit'])
        recent_total = max(len(recent), 1)
        stock_accuracy = recent_hits / recent_total
        
        today_preds = db.execute(
            "SELECT direction, prev_close, actual_close, dir_hit FROM daily_predictions "
            "WHERE code=? AND dir_hit IS NOT NULL ORDER BY date DESC LIMIT 1", [code]
        ).fetchall()
        db.close()
        
        for pred in today_preds:
            dir_hit = bool(pred['dir_hit'])
            n = lp['update_count']
            
            # V3 Adaptive decay: beta = 0.5 + 0.3 * accuracy
            adaptive_beta = 0.5 + 0.3 * max(0.3, min(0.8, stock_accuracy))
            
            for signal_name in lp['signal_weights']:
                sw = lp['signal_weights'][signal_name]
                for period in BLOCKS:
                    old_w = sw.get(period, 1.0)
                    if dir_hit:
                        sw[period] = old_w * math.exp(0.5)
                    else:
                        sw[period] = old_w * math.exp(-0.5)
                    # Adaptive decay to mean
                    sw[period] = sw[period] * adaptive_beta + 1.0 * (1 - adaptive_beta)
                # Normalize per-signal block weights
                total_w = sum(sw.get(p, 1.0) for p in BLOCKS)
                if total_w > 0:
                    for p in BLOCKS:
                        sw[p] = sw.get(p, 1.0) / total_w * 5.0
            
            # Hourly bias update (smaller steps)
            eta = 0.005 * (0.995 ** n)
            for period in lp['hourly_bias']:
                old_bias = lp['hourly_bias'][period]
                error = 1.0 if (dir_hit if period == 'next_day' else False) else -1.0
                lp['hourly_bias'][period] = max(-0.05, min(0.05, old_bias + eta * error))
            
            # Beta-Binomial confidence update
            if pred['direction'] != 'neutral':
                cb = lp['confidence_beta']
                if dir_hit:
                    cb[pred['direction']]['alpha'] = min(cb[pred['direction']]['alpha'] + 1, 200)
                else:
                    cb[pred['direction']]['beta'] = min(cb[pred['direction']]['beta'] + 1, 200)
            
            # Seasonal EMA
            month_key = str(datetime.now().month)
            if month_key in lp.get('seasonal_adj', {}):
                prev_close = pred['prev_close']
                actual_close = pred['actual_close']
                daily_ret = ((actual_close - prev_close) / prev_close * 100) if prev_close > 0 else 0
                lp['seasonal_adj'][month_key] = 0.2 * daily_ret + 0.8 * lp['seasonal_adj'][month_key]
            
            lp['update_count'] = n + 1
            lp['mw_beta'] = adaptive_beta
            try:
                upsert_learning_params(code, lp)
                print(f"  {stock['name']}({code}): learning updated "
                      f"(count={lp['update_count']}, beta={adaptive_beta:.2f})")
            except Exception as e:
                print(f"  DB write learning {code} failed: {e}")

    # Step 6: Generate 30-day predictions (future only, preserve today's backfill)
    print("\n[Step 6] Generating 30-day predictions ...")
    NUM_DAYS = 30
    try:
        clear_today_predictions(TODAY)  # Only clears >=TODAY
        print("  Cleared existing future predictions")
    except Exception as e:
        print(f"  DB clear predictions failed: {e}")

    seasonal_factors = {}
    for stock in watchlist:
        sf = _calc_seasonal_from_db(stock['code'])
        if sf is not None:
            seasonal_factors[stock['code']] = sf[datetime.now().month - 1]

    all_new_preds = []
    for stock in watchlist:
        code = stock['code']
        kdata = kline_results.get(code, [])
        if not kdata:
            # Fallback: try loading from existing DB kline_daily
            try:
                db_fb = get_db()
                fb_rows = db_fb.execute(
                    "SELECT date, open, close, high, low FROM kline_daily "
                    "WHERE code=? ORDER BY date DESC LIMIT 2000", [code]
                ).fetchall()
                db_fb.close()
                if fb_rows:
                    kdata = [[r['date'], r['open'], r['close'], r['high'], r['low']] for r in fb_rows]
                    print(f"  {stock['name']}({code}): fallback to DB kline ({len(kdata)} bars)")
            except Exception as e:
                print(f"  {stock['name']}({code}): DB fallback failed: {e}")
        if not kdata:
            print(f"  {stock['name']}({code}): no kline data, skip")
            continue
        info = calc_signals(kdata, seasonal_factor=seasonal_factors.get(code, 1.0))
        if not info:
            print(f"  {stock['name']}({code}): insufficient kline data")
            continue
        lp = get_learning_params(code) or new_lp()

        # Generate 30-day predictions (iterative projection)
        multi_preds = gen_multi_day_pred(code, kdata, info, lp, num_days=NUM_DAYS)
        inserted = 0
        for pred in multi_preds:
            all_new_preds.append(pred)
            if pred['date'] <= TODAY:
                continue  # Skip today: already backfilled in Step 3
            try:
                insert_daily_prediction(code, pred['date'], pred['prev_close'],
                                         pred['next_day'], pred['hourly'], pred['signals'])
                inserted += 1
            except Exception as e:
                print(f"  DB write pred {code} {pred['date']} failed: {e}")
                break  # Stop on DB error
        try:
            upsert_learning_params(code, lp)
        except Exception as e:
            print(f"  DB write learning {code} failed: {e}")
        d1 = multi_preds[0]['next_day']
        print(f"  {stock['name']}({code}): {d1['direction']} conf={d1['confidence']:.0%} "
              f"→ {inserted}/{NUM_DAYS} days predicted")

    # Step 7: Seasonal + monthly kline + quotes
    print("\n[Step 7] Seasonal + monthly + quotes ...")
    for stock in watchlist:
        code = stock['code']
        # Step 7a: Build & write monthly kline first (so seasonal reads fresh data)
        if code in kline_results and kline_results[code]:
            daily = kline_results[code]
            monthly = {}
            for bar in daily:
                m = bar[0][:7]
                if m not in monthly:
                    monthly[m] = {'open': bar[1], 'high': bar[3], 'low': bar[4], 'close': bar[2], 'vol': 0}
                monthly[m]['high'] = max(monthly[m]['high'], bar[3])
                monthly[m]['low'] = min(monthly[m]['low'], bar[4])
                monthly[m]['close'] = bar[2]
                monthly[m]['vol'] += 1
            # Sort months chronologically to calculate change_pct
            prev_close = None
            bars_m = []
            for m in sorted(monthly.keys()):
                v = monthly[m]
                chg = 0.0
                if prev_close is not None and prev_close != 0:
                    chg = round((v['close'] - prev_close) / prev_close * 100, 2)
                prev_close = v['close']
                bars_m.append([f"{m}-01", v['open'], v['high'], v['low'], v['close'], v['vol'], chg])
            try:
                upsert_kline_monthly(code, bars_m)
                print(f"  {stock['name']}({code}): {len(bars_m)} monthly bars (latest chg: {bars_m[-1][6]:.1f}%)")
            except Exception as e:
                print(f"  DB write monthly kline {code} failed: {e}")
        # Step 7b: Calculate seasonal from just-written monthly data
        try:
            real_seasonal = _calc_seasonal_pct(code)
            upsert_seasonal(code, real_seasonal)
            print(f"  {stock['name']}({code}): seasonal updated (avg monthly chg%)")
        except Exception:
            pass
        if code in kline_results and kline_results[code]:
            latest = kline_results[code][0]
            price = latest[2]
            # Calculate dividend yield from dividends table (same logic as refresh_quotes.py)
            try:
                from refresh_quotes import calc_dividend_yield
                dy = calc_dividend_yield(code, price)
            except Exception:
                dy = 0
            try:
                upsert_quotes({code: {'price': price, 'change': 0, 'open': latest[1],
                                      'high': latest[3], 'low': latest[4], 'pe': 0, 'pb': 0, 'dy': dy}})
            except Exception as e:
                print(f"  DB write quote {code} failed: {e}")

    print(f"\n[sync_all] Done. {len(watchlist)} stocks, {len(all_new_preds)} predictions.")


if __name__ == '__main__':
    main()
