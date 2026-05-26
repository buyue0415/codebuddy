"""
Full data sync: refresh ALL modules for ALL watchlist stocks (V0.6 optimized).

V0.6 optimizations:
  - Reads watchlist from SQLite directly (not JSON file)
  - Parallel Node.js subprocess for K-line fetching (ThreadPoolExecutor)
  - Removes HTML reinjection (V0.6 no longer uses inline DATA)
  - Conditional monthly kline generation (skips if already in DB)
  - Eliminates redundant in-memory JSON dictionary building
  - kline data normalized to newest-first order
  - Learning params loaded from DB (preserves self-learning progress)

Execution flow (7 steps, aligned with specs/03-sync-engine.md):
  Step 1: Fetch news          Step 2: Parallel K-line fetch
  Step 3: Backfill predictions Step 4: Recalculate accuracy
  Step 5: Generate predictions Step 6: Seasonal + monthly + quotes
  Step 7: Write legacy JSON

External data source: NeoData (via westock-data Node.js package)
Target: SQLite stock.db (17 tables)
"""

import json, math, subprocess, os, sys
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict

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
WESTOCK = r'C:\Users\28312\.workbuddy\plugins\marketplaces\cb_teams_marketplace\plugins\finance-data\skills\westock-data'
SCRIPT = 'scripts/index.js'
TODAY = datetime.now().strftime("%Y-%m-%d")

# =====================================================================
# Prerequisite: Read watchlist from SQLite
# =====================================================================
watchlist = get_watchlist()
print(f"[sync_all] Watchlist: {len(watchlist)} stocks")

# =====================================================================
# Step 1: Fetch news for all watchlist stocks
# =====================================================================
print("[Step 1] Fetching news for all watchlist stocks ...")
try:
    from fetch_news import fetch_news_node, _parse_news_table
    from db_helper import upsert_news

    all_news = []
    for stock in watchlist:
        code, name, mkt = stock['code'], stock['name'], stock.get('market', 'sh')
        market_code = f'{mkt}{code}'
        items = fetch_news_node(market_code)
        if items:
            print(f"  News for {name}({code}): {len(items)} items")
            all_news.extend(items)
        else:
            print(f"  News for {name}({code}): no data")

    if all_news:
        upsert_news(all_news, TODAY)
        print(f"  Saved {len(all_news)} news items to DB")
except Exception as e:
    print(f"  News fetch skipped: {e}")

# =====================================================================
# Step 2: Fetch daily K-line in parallel
# =====================================================================
print("\n[Step 2] Fetching daily K-line in parallel ...")

def fetch_kline(market_code: str, limit: int = 200) -> list:
    """Fetch daily K-line from NeoData via Node.js subprocess."""
    try:
        result = subprocess.run(
            [NODE, SCRIPT, 'kline', market_code, '--period', 'day',
             '--limit', str(limit), '--fq', 'qfq'],
            cwd=WESTOCK, capture_output=True, timeout=30,
        )
        # Decode stdout: try gbk first (Windows), fall back to utf-8
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
        # Normalize: sort newest-first so [0] is always the latest bar
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

# Parallel fetch — max 4 concurrent subprocess calls
kline_results: dict[str, list] = {}
if watchlist:
    max_workers = min(len(watchlist), 4)
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(sync_one_stock, s): s for s in watchlist}
        for future in as_completed(futures):
            code, bars = future.result()
            kline_results[code] = bars

SIGNALS = ['macd', 'rsi', 'bollinger', 'kdj', 'seasonal', 'atr', 'money_flow']
BLOCKS = ['09:30-10:30', '10:30-11:30', '13:00-14:00', '14:00-15:00', 'next_day']

def _ema(data: list, n: int) -> float:
    """True Exponential Moving Average (EMA), not SMA."""
    k = 2.0 / (n + 1)
    result = sum(data[:n]) / n  # start with SMA
    for price in data[n:]:
        result = price * k + result * (1 - k)
    return result

def _calc_seasonal_from_db(code: str) -> list | None:
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
        m = int(r[0][5:7])  # extract month from date string "2026-01-01"
        month_stats[m].append(r[1])
    factors = []
    for m in range(1, 13):
        values = month_stats.get(m, [])
        avg = round(sum(values) / len(values), 2) if values else 0
        # Scale to 0.8-1.2 range around 1.0 with 3x multiplier for more signal impact
        scaled = 1.0 + avg * 3 / 100.0  # 3x multiplier: 3.5% → 1.105, not 1.035
        factors.append(max(0.80, min(1.20, round(scaled, 2))))
    return factors

def new_lp() -> dict:
    """Initialize fresh learning parameters."""
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
    """Compute 7 technical signals from daily K-line data.
    
    Args:
        kdata: Daily K-line bars [[date, open, close, high, low], ...]
        seasonal_factor: Seasonality multiplier (>1 bullish, <1 bearish)
    """
    if len(kdata) < 14:
        return None
    closes = [k[2] for k in kdata]
    highs  = [k[3] for k in kdata]
    lows   = [k[4] for k in kdata]
    close  = closes[0]

    # ATR
    n = min(14, len(kdata) - 1)
    atr = sum(
        max(highs[i] - lows[i], abs(highs[i] - closes[i + 1]),
            abs(lows[i] - closes[i + 1]))
        for i in range(n)
    ) / n

    # RSI
    n = min(14, len(closes) - 1)
    gains  = sum(max(closes[i] - closes[i + 1], 0) for i in range(n))
    losses = sum(max(closes[i + 1] - closes[i], 0) for i in range(n))
    rs  = (gains / n) / (losses / n) if losses > 0 else 100
    rsi = 100 - 100 / (1 + rs)

    # MACD — true EMA with signal line cross detection
    ema12 = _ema(closes, 12)
    ema26 = _ema(closes, 26)
    # Also compute 9-day EMA of MACD (signal line)
    macd_vals = [_ema(closes[:i+1], 12) - _ema(closes[:i+1], 26)
                 for i in range(8, min(33, len(closes)))]
    macd_val = ema12 - ema26
    signal_val = _ema(list(reversed(macd_vals)) + [macd_val], 9) if macd_vals else macd_val
    macd_pct = (macd_val / close) * 100
    macd_dir = 'bullish' if macd_val > signal_val else 'bearish'

    # Bollinger
    n = min(20, len(closes))
    bb_ma  = sum(closes[:n]) / n
    bb_std = math.sqrt(sum((x - bb_ma) ** 2 for x in closes[:n]) / n)
    bb_upper, bb_lower = bb_ma + 2 * bb_std, bb_ma - 2 * bb_std
    if close > bb_upper * 0.98:
        bb_dir = 'bearish'
    elif close < bb_lower * 1.02:
        bb_dir = 'bullish'
    else:
        bb_dir = 'neutral'

    # KDJ
    n = min(9, len(kdata))
    kd_h, kd_l = max(highs[:n]), min(lows[:n])
    rsv = ((close - kd_l) / (kd_h - kd_l)) * 100 if kd_h != kd_l else 50
    k_val = 50 * 0.67 + rsv * 0.33
    d_val = 50 * 0.67 + k_val * 0.33
    j_val = 3 * k_val - 2 * d_val

    # Seasonal factor — from historical data via caller
    sf = seasonal_factor

    # Money flow proxy — multi-period momentum (3d + 10d divergence)
    chg_3d = ((closes[0] - closes[3]) / closes[3]) * 100 if len(closes) > 3 else 0
    chg_10d = ((closes[0] - closes[10]) / closes[10]) * 100 if len(closes) > 10 else chg_3d

    return {
        'close': close, 'atr': round(atr, 3),
        'signals': {
            'macd': {
                'value': f'{macd_pct:+.2f}%',
                'direction': macd_dir,
                'diff': round(macd_val, 4),
                'signal': round(signal_val, 4),
                'raw': round(macd_pct, 2),
            },
            'rsi': {
                'value': round(rsi, 1),
                'direction': 'bullish' if rsi > 55 else 'bearish' if rsi < 45 else 'neutral',
                'raw': round(rsi, 1),
            },
            'bollinger': {
                'direction': bb_dir,
                'value': f'{round((close - bb_ma) / bb_std, 2)}σ',
                'raw': round((close - bb_ma) / bb_std, 2),
                'upper': round(bb_upper, 2),
                'lower': round(bb_lower, 2),
            },
            'kdj': {
                'value': f'K{round(k_val,0)} D{round(d_val,0)} J{round(j_val,0)}',
                'raw': round(j_val, 0),
                'direction': ('bearish' if j_val > 80
                              else 'bullish' if j_val < 20 else 'neutral'),
            },
            'seasonal': {
                'direction': 'bullish' if sf > 1 else 'bearish',
                'factor': sf,
            },
            'atr': {
                'value': round(atr, 3),
                'pct': round(atr / close * 100, 2),
                'direction': 'neutral',
                'raw': round(atr, 3),
            },
            'money_flow': {
                'direction': ('bullish' if chg_3d > 1 and chg_10d > 0
                              else 'bearish' if chg_3d < -1 and chg_10d < 0
                              else 'bullish' if chg_3d > 2.5
                              else 'bearish' if chg_3d < -2.5 else 'neutral'),
                'value': f'{chg_3d:+.1f}%',
                'raw': round(chg_3d, 2),
            },
        },
    }

def gen_pred(code: str, info: dict, lp: dict) -> dict:
    """Generate a daily prediction from signals and learning params."""
    close = info['close']
    atr   = info['atr']
    sig   = info['signals']
    w     = lp['signal_weights']
    bias  = lp['hourly_bias']
    sa    = lp['seasonal_adj']

    # Overall direction
    # Weighted sum with signal participation count
    bullish_count = sum(1 for s in SIGNALS if sig[s]['direction'] == 'bullish')
    bearish_count = sum(1 for s in SIGNALS if sig[s]['direction'] == 'bearish')
    neutral_count = sum(1 for s in SIGNALS if sig[s]['direction'] == 'neutral')
    ws = sum(
        w[s]['next_day']
        * (1 if sig[s]['direction'] == 'bullish'
           else -1 if sig[s]['direction'] == 'bearish'
           else 0)
        for s in SIGNALS
    )
    ws += sa.get(str(datetime.now().month), 0) * 2
    dd = 'bullish' if ws > 0.5 else 'bearish' if ws < -0.5 else 'neutral'

    # Confidence: combine Beta-Binomial history + signal consensus
    cb = lp['confidence_beta'].get(dd, {'alpha': 1, 'beta': 1})
    beta_conf = cb['alpha'] / (cb['alpha'] + cb['beta'])
    # Signal consensus: proportion of non-neutral signals agreeing with direction
    if dd == 'bullish':
        consensus = bullish_count / (bullish_count + bearish_count) if (bullish_count + bearish_count) > 0 else 0.5
    elif dd == 'bearish':
        consensus = bearish_count / (bullish_count + bearish_count) if (bullish_count + bearish_count) > 0 else 0.5
    else:
        consensus = 0.5  # neutral: default 50%
    # Blend: 60% consensus + 40% historical
    conf = max(0.4, round(0.6 * consensus + 0.4 * beta_conf, 2))

    # Price range
    dr = atr * 2.5
    nh, nl = round(close + dr * 0.6, 2), round(close - dr * 0.4, 2)

    # Hourly blocks
    hws = [
        ('09:30-10:30', 0.35, '开盘消化隔夜信息'),
        ('10:30-11:30', 0.20, '横盘整理'),
        ('13:00-14:00', 0.20, '午后资金活跃'),
        ('14:00-15:00', 0.25, '尾盘主力动作'),
    ]
    cum = close
    hp = []
    for block, pct, note in hws:
        sd = dr * pct
        hs = sum(
            w[s][block]
            * (1 if sig[s]['direction'] == 'bullish'
               else -1 if sig[s]['direction'] == 'bearish'
               else 0)
            for s in SIGNALS
        ) + bias.get(block, 0) * 2
        hd = 'bullish' if hs > 0.3 else 'bearish' if hs < -0.3 else 'neutral'
        off = close * bias.get(block, 0) * 2
        hh = round(cum + sd * 0.5 + off, 2)
        hl = round(cum - sd * 0.5 + off, 2)
        hc = round(cum + off, 2)
        hp.append({
            'block': block,
            'pred_open': round(cum, 2) if not hp else round(hp[-1]['pred_close'], 2),
            'pred_high': min(hh, nh),
            'pred_low': max(hl, nl),
            'pred_close': hc,
            'direction': hd,
            'strength': min(5, max(1, int(abs(hs)))),
            'note': note,
        })
        cum = hc

    advice = '低吸为主' if dd == 'bullish' else '观望为主' if dd == 'neutral' else '逢高减仓'
    return {
        'date': TODAY, 'code': code, 'prev_close': close,
        'next_day': {
            'direction': dd, 'confidence': conf,
            'high': nh, 'low': nl, 'advice': advice,
            'entry_zone': nl if dd == 'bullish' else nh,
        },
        'hourly': hp,
        'signals': sig,
        'actual': {
            'open': None, 'high': None, 'low': None, 'close': None,
            'next_day_direction_hit': None, 'daily_range_hit': None,
            'hourly_hits': [None] * 4,
        },
    }


# =====================================================================
# Step 3: Backfill ALL unverified predictions with actual K-line data
# =====================================================================
print("\n[Step 3] Backfilling predictions with actual data ...")
for stock in watchlist:
    code = stock['code']
    kdata = kline_results.get(code, [])
    if not kdata or len(kdata) < 2:
        continue

    # Build date→bar lookup from kline data (most recent bars)
    kline_by_date = {b[0]: b for b in kdata if b[0] <= TODAY}

    # Find all unverified predictions for this stock
    db = get_db()
    unverified = db.execute(
        "SELECT id, date, direction, high, low, prev_close FROM daily_predictions WHERE code=? AND dir_hit IS NULL ORDER BY date DESC",
        [code]
    ).fetchall()
    db.close()

    backfilled = 0
    for pred in unverified:
        pred_date = pred['date']
        if pred_date == TODAY:
            continue  # Skip today's prediction (not yet verifiable)
        bar = kline_by_date.get(pred_date)
        if not bar:
            continue  # No K-line data for this prediction date

        y_open, y_high, y_low, y_close = bar[1], bar[3], bar[4], bar[2]
        pred_dir = pred['direction']
        prev_close = pred['prev_close']

        # Direction hit
        actual_dir = 'bullish' if y_close > prev_close else ('bearish' if y_close < prev_close else 'neutral')
        dir_hit = 0
        if pred_dir != 'neutral' and actual_dir != 'neutral':
            dir_hit = 1 if pred_dir == actual_dir else 0

        # Range hit
        pred_high, pred_low = pred['high'], pred['low']
        range_hit = 1 if (y_low >= pred_low and y_high <= pred_high) else 0

        # Update prediction record
        db2 = get_db()
        db2.execute(
            "UPDATE daily_predictions SET actual_open=?, actual_high=?, actual_low=?, actual_close=?, dir_hit=?, range_hit=? WHERE id=?",
            [y_open, y_high, y_low, y_close, dir_hit, range_hit, pred['id']]
        )
        db2.commit()
        db2.close()
        backfilled += 1
        print(f"  {stock['name']}({code}) {pred_date}: dir={'HIT' if dir_hit else 'MISS'}, range={'HIT' if range_hit else 'MISS'}")

    if backfilled == 0:
        print(f"  {stock['name']}({code}): no unverified past predictions to backfill")

# Recalculate accuracy stats from actual backfilled data
print("[Step 4] Recalculating accuracy stats ...")
for stock in watchlist:
    code = stock['code']
    db = get_db()
    all_preds = db.execute(
        "SELECT date, dir_hit, range_hit FROM daily_predictions WHERE code=? AND dir_hit IS NOT NULL ORDER BY date DESC",
        [code]
    ).fetchall()
    db.close()

    if not all_preds:
        continue

    # Compute window stats
    last_20 = all_preds[:20]
    last_60 = all_preds[:60]

    for period_label, period_preds in [('last_20', last_20), ('last_60', last_60)]:
        if not period_preds:
            continue
        dir_correct = sum(1 for p in period_preds if p['dir_hit'])
        range_correct = sum(1 for p in period_preds if p['range_hit'])
        dir_total = len(period_preds)
        range_total = len(period_preds)
        dir_rate = round(dir_correct / dir_total * 100, 1) if dir_total > 0 else 0
        range_rate = round(range_correct / range_total * 100, 1) if range_total > 0 else 0

        try:
            upsert_accuracy_stats(code, period_label, {
                'direction': {'correct': dir_correct, 'total': dir_total, 'rate': dir_rate},
                'range': {'correct': range_correct, 'total': range_total, 'rate': range_rate},
                'hourly': {},  # Hourly accuracy not available from daily kline
            })
        except Exception as e:
            print(f"  DB write accuracy {code}/{period_label} failed: {e}")

    print(f"  {stock['name']}({code}): dir_acc={dir_rate}% ({dir_correct}/{dir_total}), range_acc={range_rate}%")

# =====================================================================
# Step 5: Generate daily predictions
# =====================================================================
print("\n[Step 5] Generating predictions ...")

# Clear today's old predictions before regenerating
try:
    clear_today_predictions(TODAY)
    print("  Cleared today's old predictions")
except Exception as e:
    print(f"  DB clear predictions failed: {e}")

# Pre-compute seasonal factors from historical monthly data
seasonal_factors = {}
for stock in watchlist:
    sf = _calc_seasonal_from_db(stock['code'])
    if sf is not None:
        seasonal_factors[stock['code']] = sf[datetime.now().month - 1]

new_preds = []
for stock in watchlist:
    code = stock['code']
    kdata = kline_results.get(code, [])
    if not kdata:
        print(f"  {stock['name']}({code}): no kline data, skip")
        continue

    info = calc_signals(kdata, seasonal_factor=seasonal_factors.get(code, 1.0))
    if not info:
        print(f"  {stock['name']}({code}): insufficient kline data")
        continue

    # Use existing learning params if available (preserves self-learning progress)
    lp = get_learning_params(code) or new_lp()
    pred = gen_pred(code, info, lp)
    new_preds.append(pred)

    try:
        insert_daily_prediction(code, pred['date'], pred['prev_close'],
                                 pred['next_day'], pred['hourly'], pred['signals'])
    except Exception as e:
        print(f"  DB write pred {code} failed: {e}")

    try:
        upsert_learning_params(code, lp)
    except Exception as e:
        print(f"  DB write learning {code} failed: {e}")

    print(f"  {stock['name']}({code}): {pred['next_day']['direction']} "
          f"conf={pred['next_day']['confidence']:.0%}")

# =====================================================================
# Step 6: Seasonal + monthly kline (conditionally for new stocks)
# =====================================================================
DEFAULT_SEASONAL = [0.8, -2.5, 1.2, 0.5, -1.0, 2.3, 3.5, -1.8, 1.5, 2.8, -1.2, 3.0]

for stock in watchlist:
    code = stock['code']

    # Seasonal — idempotent upsert
    try:
        upsert_seasonal(code, DEFAULT_SEASONAL)
    except Exception:
        pass

    # Monthly kline — only generate if not yet in DB
    db = get_db()
    has_monthly = (
        db.execute("SELECT COUNT(*) FROM kline_monthly WHERE code=?",
                   [code]).fetchone()[0] > 0
    )
    db.close()

    if not has_monthly and code in kline_results and kline_results[code]:
        daily = kline_results[code]
        monthly = {}
        for bar in daily:
            m = bar[0][:7]
            if m not in monthly:
                monthly[m] = {'open': bar[1], 'high': bar[3],
                              'low': bar[4], 'close': bar[2], 'vol': 0}
            monthly[m]['high'] = max(monthly[m]['high'], bar[3])
            monthly[m]['low']  = min(monthly[m]['low'],  bar[4])
            monthly[m]['close'] = bar[2]
            monthly[m]['vol'] += 1
        bars_m = [
            [f"{m}-01", v['open'], v['high'], v['low'], v['close'], v['vol'], 0.0]
            for m, v in sorted(monthly.items())
        ]
        try:
            upsert_kline_monthly(code, bars_m)
            print(f"  {stock['name']}({code}): generated {len(bars_m)} monthly bars")
        except Exception as e:
            print(f"  DB write monthly kline {code} failed: {e}")

    # Quote from latest daily kline
    if code in kline_results and kline_results[code]:
        latest = kline_results[code][0]
        try:
            upsert_quotes({
                code: {
                    'price': latest[2], 'change': 0, 'open': latest[1],
                    'high': latest[3], 'low':  latest[4],
                    'pe': 0, 'pb': 0, 'dy': 0,
                }
            })
        except Exception as e:
            print(f"  DB write quote {code} failed: {e}")

# =====================================================================
# Step 7: Write legacy system_data.json (for deprecated /api/system-data)
# =====================================================================
legacy = {
    'generated':  TODAY,
    'watchlist':  [dict(s) for s in watchlist],
    'kline_daily': kline_results,
    'daily_predictions': new_preds,
    'seasonal':  {},
    'kline':     {},
    'quotes':    {},
}
for stock in watchlist:
    code = stock['code']
    db = get_db()
    r = db.execute("SELECT factors FROM seasonal WHERE code=?", [code]).fetchone()
    if r:
        legacy['seasonal'][code] = json.loads(r[0])
    rows = db.execute("SELECT date, open, high, low, close, volume, change_pct "
                       "FROM kline_monthly WHERE code=? ORDER BY date DESC",
                       [code]).fetchall()
    if rows:
        legacy['kline'][code] = [[r[0], r[1], r[2], r[3], r[4], r[5], r[6]] for r in rows]
    r2 = db.execute("SELECT * FROM quotes WHERE code=?", [code]).fetchone()
    if r2:
        legacy['quotes'][code] = {
            'price': r2['price'], 'change': r2['change'], 'open': r2['open'],
            'high': r2['high'], 'low': r2['low'], 'pe': r2['pe'], 'pb': r2['pb'], 'dy': r2['dy'],
        }
    db.close()

try:
    with open(os.path.join(ROOT, 'data', 'system_data.json'), 'w',
              encoding='utf-8') as f:
        json.dump(legacy, f, ensure_ascii=False, indent=2)
    print(f"\n[Step 7] system_data.json saved (legacy)")
except Exception as e:
    print(f"\n[Step 7] system_data.json write failed: {e}")

print(f"\n[sync_all] Done. {len(watchlist)} stocks, {len(new_preds)} predictions.")
