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
from signals import (
    calc_signals, gen_pred, gen_multi_day_pred, new_lp, HAS_NUMPY,
    SIGNALS, BLOCKS,
)

NODE = r'C:\Users\28312\.workbuddy\binaries\node\versions\22.12.0\node.exe'
WESTOCK = r'C:\Users\28312\.workbuddy\plugins\marketplaces\experts\plugins\stock-partner-team\skills\westock-data'
SCRIPT = 'scripts/index.js'
TODAY = datetime.now().strftime("%Y-%m-%d")


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
    """从 kline_monthly 按月计算真实平均涨跌幅百分比，返回12个浮点数（1月~12月）。"""
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
        m = int(r[0][5:7])
        month_stats[m].append(r[1])
    return [round(sum(month_stats.get(m, [])) / len(month_stats[m]), 2) if month_stats.get(m) else 0.0
            for m in range(1, 13)]


# ======================================================================
# Logging setup
# ======================================================================

LOG_PATH = os.path.join(ROOT, "data", "sync_log.txt")

def _log(msg: str):
    """Append timestamped message to sync log file."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass
    print(line)


# ======================================================================
# Main execution (only runs when script is executed directly)
# ======================================================================

def main():
    watchlist = get_watchlist()
    _log(f"sync_all START: {len(watchlist)} stocks")

    # Step 1: Fetch news with dedup
    _log("Step 1: Fetching news...")
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
    _log("Step 1.5: Fetching dividends...")
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
    _log("Step 2: Fetching K-line parallel...")
    kline_results = {}
    if watchlist:
        max_workers = min(len(watchlist), 4)
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {pool.submit(sync_one_stock, s): s for s in watchlist}
            for future in as_completed(futures):
                code, bars = future.result()
                kline_results[code] = bars

    # Step 3: Backfill predictions
    _log("Step 3: Backfilling predictions...")
    total_backfilled = 0
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
        total_backfilled += backfilled
    _log(f"Step 3 DONE: {total_backfilled} predictions backfilled")

    # Step 4: Recalculate accuracy
    _log("Step 4: Recalculating accuracy stats...")
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
    _log("Step 5: Self-learning updates...")
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

        # ── V0.9: Backtest cold-start & regime weights ──
        backtest_weights = lp_row['backtest_weights'] if 'backtest_weights' in lp_row.keys() else None
        if lp['update_count'] == 0 and backtest_weights:
            try:
                bt = json.loads(backtest_weights)
                lp['signal_weights'] = bt
                print(f"  {stock['name']}({code}): cold-start from backtest weights")
            except (json.JSONDecodeError, TypeError):
                pass
        elif 'regime_weights' in lp_row.keys() and lp_row['regime_weights']:
            try:
                rw = json.loads(lp_row['regime_weights'])
                # Get kline for regime detection
                db2 = get_db()
                krows = db2.execute(
                    "SELECT date, open, close, high, low FROM kline_daily WHERE code=? ORDER BY date DESC LIMIT 200",
                    [code]
                ).fetchall()
                db2.close()
                kdata = [[r['date'], r['open'], r['close'], r['high'], r['low']] for r in krows]
                from signals import detect_market_regime
                regime = detect_market_regime(kdata) if len(kdata) >= 30 else 'ranging'
                if regime in rw:
                    # Blend: 70% current MWU + 30% regime-specific
                    for sn in SIGNALS:
                        if sn in rw[regime]:
                            for b in BLOCKS:
                                lp['signal_weights'][sn][b] = (
                                    lp['signal_weights'][sn][b] * 0.7 +
                                    rw[regime][sn].get(b, 1.0) * 0.3
                                )
                    print(f"  {stock['name']}({code}): regime blend ({regime}, 30%)")
            except (json.JSONDecodeError, TypeError, Exception):
                pass

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

    # Step 6: Generate 10-day predictions (future only, preserve today's backfill)
    _log("Step 6: Generating 10-day predictions...")
    NUM_DAYS = 10
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

    # Also build full sf_cache for multi-day projections
    seasonal_cache = {stock['code']: _calc_seasonal_from_db(stock['code']) for stock in watchlist}

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
        sf_full = seasonal_cache.get(code)

        # Generate 10-day predictions (iterative projection)
        multi_preds = gen_multi_day_pred(code, kdata, info, lp, num_days=NUM_DAYS, sf_cache=sf_full)
        inserted = 0
        for pred in multi_preds:
            all_new_preds.append(pred)
            if pred['date'] < TODAY:
                continue  # Skip past dates: already backfilled in Step 3
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
    _log("Step 7: Seasonal + monthly + quotes...")
    for stock in watchlist:
        code = stock['code']
        # Step 7a: Build & write monthly kline first (so seasonal reads fresh data)
        daily = kline_results.get(code, [])
        if not daily:
            # Fallback: try loading from existing DB kline_daily
            try:
                db_fb = get_db()
                fb_rows = db_fb.execute(
                    "SELECT date, open, close, high, low FROM kline_daily "
                    "WHERE code=? ORDER BY date DESC", [code]
                ).fetchall()
                db_fb.close()
                if fb_rows:
                    daily = [[r['date'], r['open'], r['close'], r['high'], r['low']] for r in fb_rows]
                    print(f"  {stock['name']}({code}): fallback to DB daily kline ({len(daily)} bars)")
            except Exception as e:
                print(f"  {stock['name']}({code}): DB fallback failed: {e}")
        if daily:
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
        if daily:
            latest = daily[0]
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

    _log(f"sync_all DONE: {len(watchlist)} stocks, {len(all_new_preds)} predictions, {total_backfilled} backfilled")

    # Post-sync audit: check for any remaining stale unverified predictions
    stale_count = 0
    try:
        db_audit = get_db()
        stale = db_audit.execute(
            "SELECT COUNT(*) as c FROM daily_predictions WHERE dir_hit IS NULL AND date < ?",
            [TODAY]
        ).fetchone()
        stale_count = stale['c'] if stale else 0
        db_audit.close()
    except Exception:
        pass
    if stale_count > 0:
        _log(f"WARNING: {stale_count} predictions still unverified after sync (date < {TODAY})")


if __name__ == '__main__':
    main()
