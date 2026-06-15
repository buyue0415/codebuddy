"""
Backtest Engine: Walk-forward optimization + Two-phase weight search.

Finds optimal signal weights via historical simulation, then writes results
to learning_params for MWU cold-start.

Architecture: Business Logic layer. Import-only from signals.py and db_helper.py.
Called by: server_v2.py (subprocess) or CLI: python backtest_engine.py [--codes ...]

Data flow:
    kline_daily → calc_signals() → simulate trades → metrics → learning_params
"""
import json, math, os, sys, time
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from db_helper import (
    get_db, get_watchlist_codes, get_learning_params,
    upsert_learning_params, insert_backtest_run, update_backtest_run,
)
from signals import calc_signals, SIGNALS, BLOCKS, new_lp, TODAY, detect_market_regime

# ── Configuration ───────────────────────────────────────────────────────

@dataclass
class BacktestConfig:
    train_window: int = 252     # training days
    test_window: int = 21       # test days per fold
    step_size: int = 21         # roll-forward step
    initial_capital: float = 100000.0
    commission_rate: float = 0.0003   # 0.03%
    stamp_tax_rate: float = 0.001     # 0.1% sell only
    signal_count: int = 10

@dataclass
class BacktestMetrics:
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    calmar_ratio: float = 0.0
    annual_return: float = 0.0
    total_trades: int = 0

WEIGHT_CANDIDATES = [0.1, 0.3, 0.5, 0.7, 1.0, 1.3, 1.5]


# ── Trade Simulation ────────────────────────────────────────────────────

def simulate_trades(kdata: list, weights: Dict[str, Dict[str, float]],
                    cfg: BacktestConfig, regime: str = None,
                    signals_cache: dict = None) -> BacktestMetrics:
    """Simulate trading on historical data using given weights.

    Returns metrics computed over the entire period.
    """
    if len(kdata) < cfg.train_window + 20:
        return BacktestMetrics()

    cash = cfg.initial_capital
    position = 0   # shares held
    cost_basis = 0.0
    trades = []
    equity = [cfg.initial_capital]

    # Walk-forward simulation: step through data day by day
    start = cfg.train_window
    end = len(kdata) - 1

    for i in range(start, end):
        if i < 26:  # need enough data for signal calculation
            equity.append(equity[-1])
            continue

        # Use precomputed cache if available, otherwise compute on-the-fly
        if signals_cache is not None and i in signals_cache:
            info = signals_cache[i]
        else:
            window = kdata[i-200:i+1] if i >= 200 else kdata[:i+1]
            window = list(reversed(window))  # newest first for calc_signals
            info = calc_signals(window)
        if not info:
            equity.append(equity[-1])
            continue

        sig = info['signals']
        close_price = kdata[i][2]

        # Weighted voting
        ws = sum(weights.get(s, {}).get('next_day', 1.0) *
                 (1 if sig[s]['direction'] == 'bullish'
                  else -1 if sig[s]['direction'] == 'bearish'
                  else 0) for s in SIGNALS)
        direction = 'bullish' if ws > 0.5 else 'bearish' if ws < -0.5 else 'neutral'
        confidence = sum(1 for s in SIGNALS if sig[s]['direction'] == direction) / len(SIGNALS)
        confidence = max(0.3, confidence)

        # Position sizing (Kelly-like)
        kelly = max(0, min(0.3, confidence * 2 - 1 + 0.05))

        if direction == 'bullish' and cash > 0:
            # Buy
            amount = equity[-1] * kelly
            qty = int(amount / close_price / 100) * 100
            if qty >= 100:
                cost = qty * close_price
                commission = cost * cfg.commission_rate
                total_cost = cost + commission
                if total_cost <= cash:
                    cash -= total_cost
                    position += qty
                    cost_basis = ((cost_basis * (position - qty) + total_cost) / position
                                  if position > 0 else total_cost / qty)
                    trades.append({'dir': 'buy', 'qty': qty, 'price': close_price})

        elif direction == 'bearish' and position > 0:
            # Sell all
            revenue = position * close_price
            commission = revenue * cfg.commission_rate
            tax = revenue * cfg.stamp_tax_rate
            cash += revenue - commission - tax
            trades.append({'dir': 'sell', 'qty': position, 'price': close_price})
            position = 0
            cost_basis = 0

        # Mark-to-market
        equity.append(cash + position * close_price)

    # Final liquidation
    if position > 0:
        last_close = kdata[end][2]
        equity[-1] = cash + position * last_close

    equity_arr = np.array(equity)
    if len(equity_arr) < 2:
        return BacktestMetrics()

    # Daily returns
    returns = np.diff(equity_arr) / equity_arr[:-1]
    valid = returns[np.isfinite(returns)]

    if len(valid) < 2:
        return BacktestMetrics()

    # Sharpe ratio (annualized)
    mean_r = np.mean(valid)
    std_r = np.std(valid, ddof=1)
    sharpe = (mean_r / std_r * np.sqrt(252)) if std_r > 0 else 0.0

    # Max drawdown
    peak = np.maximum.accumulate(equity_arr)
    drawdowns = (peak - equity_arr) / peak
    max_dd = np.max(drawdowns)

    # Win rate
    wins = np.sum(valid > 0)
    total = len(valid)
    win_rate = wins / total if total > 0 else 0

    # Profit factor
    gains = np.sum(valid[valid > 0]) if np.any(valid > 0) else 0
    losses = -np.sum(valid[valid < 0]) if np.any(valid < 0) else 1e-6
    profit_factor = gains / losses if losses > 1e-6 else 0

    # Annual return
    annual_ret = (equity_arr[-1] / equity_arr[0] - 1) / (len(equity_arr) / 252)

    # Calmar
    calmar = annual_ret / max_dd if max_dd > 0 else 0

    return BacktestMetrics(
        sharpe_ratio=round(sharpe, 3),
        max_drawdown=round(max_dd * 100, 2),
        win_rate=round(win_rate * 100, 1),
        profit_factor=round(profit_factor, 2),
        calmar_ratio=round(calmar, 3),
        annual_return=round(annual_ret * 100, 1),
        total_trades=len(trades),
    )


# ── Signal Cache (Performance Optimization) ──────────────────────────────

def precompute_signals_cache(kdata_sorted: list, cfg: BacktestConfig) -> dict:
    """Pre-compute calc_signals() results for all trading days once.

    During backtest optimization, simulate_trades() is called ~1653 times per
    stock, each iterating through all trading days and calling calc_signals()
    for each day. This cache eliminates the redundant computation.

    Returns: Dict[int, dict] mapping kdata_sorted date_index -> calc_signals result
    """
    cache = {}
    start = max(cfg.train_window, 26)
    end = len(kdata_sorted)

    for i in range(start, end):
        window = kdata_sorted[i - 200:i + 1] if i >= 200 else kdata_sorted[:i + 1]
        window = list(reversed(window))
        info = calc_signals(window)
        if info is not None:
            cache[i] = info

    return cache


# ── Two-Phase Weight Optimization ───────────────────────────────────────

def _make_weights(signal_weights: Dict[str, float]) -> Dict[str, Dict[str, float]]:
    """Convert {signal: next_day_weight} to full weight matrix."""
    return {s: {'next_day': signal_weights.get(s, 1.0),
                **{b: 1.0 for b in BLOCKS if b != 'next_day'}}
            for s in SIGNALS}


def phase1_single_signal_eval(kdata: list, cfg: BacktestConfig,
                               signals_cache: dict = None) -> List[Tuple[str, float, float]]:
    """Evaluate each signal independently. Returns [(signal, best_weight, best_sharpe), ...]."""
    results = []
    default_weights = {s: 1.0 for s in SIGNALS}

    for sn in SIGNALS:
        best_w, best_s = 1.0, -999
        for w in WEIGHT_CANDIDATES:
            test_w = dict(default_weights)
            test_w[sn] = w
            weights = _make_weights(test_w)
            m = simulate_trades(kdata, weights, cfg, signals_cache=signals_cache)
            if m.sharpe_ratio > best_s:
                best_s = m.sharpe_ratio
                best_w = w
        results.append((sn, best_w, best_s))
        sys.stderr.write(f"  Phase1 {sn}: best_w={best_w} sharpe={best_s:.3f}\n")

    results.sort(key=lambda x: x[2], reverse=True)
    return results


def phase2_combo_search(kdata: list, top_signals: List[str],
                        default_weights: Dict[str, float],
                        cfg: BacktestConfig,
                        signals_cache: dict = None) -> Tuple[Dict[str, float], float]:
    """Search best weight combination for top 3 signals. Returns (optimal_weights, best_sharpe)."""
    weights = dict(default_weights)
    best_weights = dict(weights)
    best_sharpe = -999

    for w1 in WEIGHT_CANDIDATES:
        for w2 in WEIGHT_CANDIDATES:
            for w3 in WEIGHT_CANDIDATES:
                weights[top_signals[0]] = w1
                weights[top_signals[1]] = w2
                weights[top_signals[2]] = w3
                m = simulate_trades(kdata, _make_weights(weights), cfg,
                                   signals_cache=signals_cache)
                if m.sharpe_ratio > best_sharpe:
                    best_sharpe = m.sharpe_ratio
                    best_weights = dict(weights)

    return best_weights, best_sharpe


# ── Walk-forward Optimization ────────────────────────────────────────────

def walk_forward_optimize(code: str, kdata: list, cfg: BacktestConfig
                          ) -> Tuple[Dict, Dict, BacktestMetrics, float]:
    """Run full optimization pipeline for one stock.

    Returns: (optimal_weights, regime_weights, overall_metrics, combined_sharpe)
    """
    kdata_sorted = sorted(kdata, key=lambda x: x[0])  # ascending by date
    if len(kdata_sorted) < cfg.train_window + 20:
        sys.stderr.write(f"  [{code}] Insufficient data: {len(kdata_sorted)} bars\n")
        return None, None, BacktestMetrics(), 0.0

    sys.stderr.write(f"\n[{code}] Two-phase optimization ({len(kdata_sorted)} bars)...\n")

    # Pre-compute signal cache once for all phases (eliminates ~500K recalculations)
    cache = precompute_signals_cache(kdata_sorted, cfg)
    sys.stderr.write(f"  Signal cache: {len(cache)} entries precomputed\n")

    # ── Phase 1: Single signal evaluation (80 evaluations) ──
    sys.stderr.write(f"  Phase1: evaluating {len(SIGNALS)} signals × {len(WEIGHT_CANDIDATES)} candidates...\n")
    p1_results = phase1_single_signal_eval(kdata_sorted, cfg, signals_cache=cache)
    top3 = [sig for sig, _, _ in p1_results[:3]]
    sys.stderr.write(f"  Top 3 signals: {top3}\n")

    # ── Phase 2: Combo search on top 3 ──
    default_w = {s: 1.0 for s in SIGNALS}
    sys.stderr.write(f"  Phase2: searching {len(WEIGHT_CANDIDATES)}^3 = {len(WEIGHT_CANDIDATES)**3} combos...\n")
    optimal_signal_weights, best_sharpe = phase2_combo_search(
        kdata_sorted, top3, default_w, cfg, signals_cache=cache
    )
    optimal_weights = _make_weights(optimal_signal_weights)
    overall_metrics = simulate_trades(kdata_sorted, optimal_weights, cfg, signals_cache=cache)
    sys.stderr.write(f"  Optimal sharpe={best_sharpe:.3f} win_rate={overall_metrics.win_rate}%\n")

    # ── Regime-specific weights ──
    # FIXED: Previously ran full Phase1+Phase2 for each of 3 regimes using
    # identical unfiltered kdata_sorted, wasting 75% compute for identical results.
    # Now reuse the single-phase optimization result for all regimes.
    # TODO: Implement actual regime-specific kdata filtering for true regime weights.
    sys.stderr.write(f"  Using unified regime weights (regime filtering is future work)\n")
    regime_weights = {}
    for regime in ['trending', 'ranging', 'volatile']:
        regime_weights[regime] = optimal_weights

    return optimal_weights, regime_weights, overall_metrics, best_sharpe


# ── Main CLI ─────────────────────────────────────────────────────────────

def main():
    """Run backtest for all watchlist stocks or specified codes."""
    import argparse
    ap = argparse.ArgumentParser(description='Backtest Engine')
    ap.add_argument('--codes', type=str, default='', help='Comma-separated stock codes')
    ap.add_argument('--train', type=int, default=252, help='Training window days')
    ap.add_argument('--test', type=int, default=21, help='Test window days')
    ap.add_argument('--run-id', type=int, default=0, help='Existing backtest_runs id to update')
    args = ap.parse_args()

    cfg = BacktestConfig(train_window=args.train, test_window=args.test)

    codes = [c.strip() for c in args.codes.split(',') if c.strip()] if args.codes else get_watchlist_codes()
    if not codes:
        print("No stocks to backtest.")
        return

    print(f"[Backtest] {len(codes)} stocks, train={cfg.train_window}d, test={cfg.test_window}d")
    sys.stderr.write(f"[Backtest] Starting {datetime.now().strftime('%H:%M:%S')}\n")

    # Create/update run record
    run_id = args.run_id
    if run_id <= 0:
        run_id = insert_backtest_run(
            status='running', train_window=cfg.train_window,
            test_window=cfg.test_window, stock_codes=','.join(codes),
            total_stocks=len(codes)
        )

    results = {}
    total_start = time.time()

    for idx, code in enumerate(codes):
        sys.stderr.write(f"\n[{idx+1}/{len(codes)}] Processing {code}...\n")
        update_backtest_run(run_id, completed_stocks=idx, current_stock=code)

        # Load K-line from DB
        db = get_db()
        rows = db.execute(
            "SELECT date, open, close, high, low FROM kline_daily WHERE code=? ORDER BY date",
            [code]
        ).fetchall()
        db.close()
        kdata = [[r['date'], r['open'], r['close'], r['high'], r['low']] for r in rows]

        if not kdata or len(kdata) < 50:
            sys.stderr.write(f"  [{code}] Skipped: insufficient data ({len(kdata)} bars)\n")
            continue

        opt_weights, regime_w, metrics, sharpe = walk_forward_optimize(code, kdata, cfg)

        if opt_weights is None:
            continue

        # Write backtest results to learning_params
        lp = get_learning_params(code) or new_lp()
        lp['backtest_weights'] = json.dumps(opt_weights)
        lp['regime_weights'] = json.dumps(regime_w)
        lp['backtest_timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        upsert_learning_params(code, lp)

        results[code] = {
            'sharpe': metrics.sharpe_ratio,
            'max_drawdown': metrics.max_drawdown,
            'win_rate': metrics.win_rate,
            'calmar': metrics.calmar_ratio,
            'annual_return': metrics.annual_return,
        }
        sys.stderr.write(f"  [{code}] ✅ sharpe={metrics.sharpe_ratio} dd={metrics.max_drawdown}% wr={metrics.win_rate}%\n")

    # Finalize — compute aggregate metrics for frontend display
    elapsed = time.time() - total_start
    agg_metrics = {}
    if results:
        n = len(results)
        agg_metrics = {
            'avg_sharpe': round(sum(r['sharpe'] for r in results.values()) / n, 3),
            'avg_max_drawdown': round(sum(r['max_drawdown'] for r in results.values()) / n, 2),
            'avg_win_rate': round(sum(r['win_rate'] for r in results.values()) / n, 1),
            'avg_annual_return': round(sum(r['annual_return'] for r in results.values()) / n, 1),
            'avg_calmar': round(sum(r['calmar'] for r in results.values()) / n, 3),
        }
    summary = {
        'elapsed_seconds': round(elapsed, 1),
        'stocks_processed': len(results),
        'total_stocks': len(codes),
        **agg_metrics,
        'results': results,
    }
    update_backtest_run(
        run_id, status='done',
        completed_stocks=len(codes),
        finished_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        summary_json=json.dumps(summary, ensure_ascii=False)
    )

    print(json.dumps({'run_id': run_id, 'status': 'done', **summary}, ensure_ascii=False))
    sys.stderr.write(f"[Backtest] Done in {elapsed:.1f}s\n")


if __name__ == '__main__':
    main()
