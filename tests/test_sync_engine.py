"""P1 [CRITICAL] Sync engine tests — calc_signals, gen_pred, _ema.

Tests the 7 technical indicators, prediction generation, EMAs,
and self-learning parameter structures.
Uses self-contained function copies — does NOT import sync_all module
to avoid triggering its module-level execution.
"""
import os, sys, math, unittest
from collections import defaultdict
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from conftest import StockTestBase

# ======================================================================
# Self-contained copies of sync_all functions (avoids module-level exec)
# ======================================================================

SIGNALS = ['macd', 'rsi', 'bollinger', 'kdj', 'seasonal', 'atr', 'money_flow']
BLOCKS = ['09:30-10:30', '10:30-11:30', '13:00-14:00', '14:00-15:00', 'next_day']


def _ema(data: list, n: int) -> float:
    """True Exponential Moving Average (EMA), not SMA."""
    k = 2.0 / (n + 1)
    result = sum(data[:n]) / n
    for price in data[n:]:
        result = price * k + result * (1 - k)
    return result


def new_lp() -> dict:
    """Initialize fresh learning parameters."""
    return {
        'signal_weights': {s: {b: 1.0 for b in BLOCKS} for s in SIGNALS},
        'hourly_bias': {b: 0.0 for b in BLOCKS},
        'seasonal_adj': {str(m): 0.0 for m in range(1, 13)},
        'confidence_beta': {
            'bullish': {'alpha': 1, 'beta': 1},
            'bearish': {'alpha': 1, 'beta': 1},
            'neutral': {'alpha': 1, 'beta': 1},
        },
        'learning_rate': 0.01, 'mw_beta': 0.7, 'update_count': 0,
    }


def calc_signals(kdata: list, seasonal_factor: float = 1.0) -> dict | None:
    """Compute 7 technical signals (copied from sync_all.py)."""
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

    # MACD
    ema12 = _ema(closes, 12)
    ema26 = _ema(closes, 26)
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

    # Seasonal factor
    sf = seasonal_factor

    # Money flow
    chg_3d = ((closes[0] - closes[3]) / closes[3]) * 100 if len(closes) > 3 else 0
    chg_10d = ((closes[0] - closes[10]) / closes[10]) * 100 if len(closes) > 10 else chg_3d

    return {
        'close': close, 'atr': round(atr, 3),
        'signals': {
            'macd': {
                'value': f'{macd_pct:+.2f}%', 'direction': macd_dir,
                'diff': round(macd_val, 4), 'signal': round(signal_val, 4),
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
                'upper': round(bb_upper, 2), 'lower': round(bb_lower, 2),
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
                'value': round(atr, 3), 'pct': round(atr / close * 100, 2),
                'direction': 'neutral', 'raw': round(atr, 3),
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
    """Generate a daily prediction (copied from sync_all.py)."""
    close = info['close']
    atr   = info['atr']
    sig   = info['signals']
    w     = lp['signal_weights']
    bias  = lp['hourly_bias']
    sa    = lp['seasonal_adj']

    bullish_count = sum(1 for s in SIGNALS if sig[s]['direction'] == 'bullish')
    bearish_count = sum(1 for s in SIGNALS if sig[s]['direction'] == 'bearish')
    ws = sum(
        w[s]['next_day']
        * (1 if sig[s]['direction'] == 'bullish'
           else -1 if sig[s]['direction'] == 'bearish'
           else 0)
        for s in SIGNALS
    )
    ws += sa.get(str(datetime.now().month), 0) * 2
    dd = 'bullish' if ws > 0.5 else 'bearish' if ws < -0.5 else 'neutral'

    cb = lp['confidence_beta'].get(dd, {'alpha': 1, 'beta': 1})
    beta_conf = cb['alpha'] / (cb['alpha'] + cb['beta'])
    if dd == 'bullish':
        consensus = bullish_count / (bullish_count + bearish_count) if (bullish_count + bearish_count) > 0 else 0.5
    elif dd == 'bearish':
        consensus = bearish_count / (bullish_count + bearish_count) if (bullish_count + bearish_count) > 0 else 0.5
    else:
        consensus = 0.5
    conf = max(0.4, round(0.6 * consensus + 0.4 * beta_conf, 2))

    dr = atr * 2.5
    nh, nl = round(close + dr * 0.6, 2), round(close - dr * 0.4, 2)

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
        'date': datetime.now().strftime('%Y-%m-%d'), 'code': code, 'prev_close': close,
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


# ======================================================================
# Synthetic K-line data: 60 days descending, newest-first
# ======================================================================
def _make_kdata(days=60, base_price=20.0, trend=-0.001, volatility=0.02):
    """Generate synthetic K-line data newest-first."""
    import random
    random.seed(42)
    from datetime import datetime, timedelta
    today = datetime.now()
    bars = []
    price = base_price
    for i in range(days):
        d = (today - timedelta(days=i)).strftime('%Y-%m-%d')
        change = price * (trend + random.uniform(-volatility, volatility))
        open_p = price
        close = price + change
        high = max(open_p, close) * (1 + random.uniform(0, volatility * 0.5))
        low = min(open_p, close) * (1 - random.uniform(0, volatility * 0.5))
        bars.append([d, round(open_p, 2), round(close, 2), round(high, 2), round(low, 2)])
        price = close
    return bars

KLINE_DATA = _make_kdata(60, 20.0)


# ======================================================================
# Tests
# ======================================================================

class TestEMA(StockTestBase):
    def test_ema_constant(self):
        result = _ema([10.0] * 20, 10)
        self.assertAlmostEqual(result, 10.0, places=4)

    def test_ema_rising(self):
        data = [float(i) for i in range(1, 31)]
        self.assertLess(_ema(data, 10), _ema(data, 5))

    def test_ema_falling(self):
        data = [float(30 - i) for i in range(30)]
        self.assertGreater(_ema(data, 10), _ema(data, 5))

    def test_ema_n1(self):
        self.assertAlmostEqual(_ema([1, 2, 3, 4, 5], 1), 5.0, places=2)


class TestCalcSignals(StockTestBase):
    def test_insufficient_data_returns_none(self):
        self.assertIsNone(calc_signals([['2026-01-01', 10, 10, 10, 10]] * 10))

    def test_sufficient_data_returns_dict(self):
        self.assertIsNotNone(calc_signals(KLINE_DATA))

    def test_output_has_close_and_atr(self):
        result = calc_signals(KLINE_DATA)
        self.assertIn('close', result)
        self.assertIn('atr', result)
        self.assertGreater(result['atr'], 0)

    def test_all_7_signals_present(self):
        result = calc_signals(KLINE_DATA)
        for name in SIGNALS:
            self.assertIn(name, result['signals'])

    def test_signal_directions_valid(self):
        result = calc_signals(KLINE_DATA)
        for name, s in result['signals'].items():
            self.assertIn(s['direction'], ['bullish', 'bearish', 'neutral'])

    def test_rsi_range(self):
        rsi = calc_signals(KLINE_DATA)['signals']['rsi']['raw']
        self.assertGreaterEqual(rsi, 0)
        self.assertLessEqual(rsi, 100)

    def test_bollinger_upper_gt_lower(self):
        bb = calc_signals(KLINE_DATA)['signals']['bollinger']
        self.assertGreater(bb['upper'], bb['lower'])

    def test_macd_has_diff_and_signal(self):
        macd = calc_signals(KLINE_DATA)['signals']['macd']
        self.assertIn('diff', macd)
        self.assertIn('signal', macd)

    def test_kdj_has_j_value(self):
        self.assertIn('raw', calc_signals(KLINE_DATA)['signals']['kdj'])

    def test_atr_pct(self):
        atr = calc_signals(KLINE_DATA)['signals']['atr']
        close = calc_signals(KLINE_DATA)['close']
        expected = round(atr['raw'] / close * 100, 2)
        self.assertAlmostEqual(atr['pct'], expected, places=1)

    def test_bullish_seasonal_factor(self):
        result = calc_signals(KLINE_DATA, seasonal_factor=1.2)
        self.assertEqual(result['signals']['seasonal']['direction'], 'bullish')

    def test_bearish_seasonal_factor(self):
        result = calc_signals(KLINE_DATA, seasonal_factor=0.8)
        self.assertEqual(result['signals']['seasonal']['direction'], 'bearish')


class TestGenPred(StockTestBase):
    def setUp(self):
        super().setUp()
        self.info = calc_signals(KLINE_DATA)
        self.assertIsNotNone(self.info)
        self.lp = new_lp()

    def test_output_structure(self):
        pred = gen_pred('601166', self.info, self.lp)
        for key in ['date', 'code', 'prev_close', 'next_day', 'hourly', 'signals', 'actual']:
            self.assertIn(key, pred)

    def test_next_day_direction(self):
        nd = gen_pred('601166', self.info, self.lp)['next_day']
        self.assertIn(nd['direction'], ['bullish', 'bearish', 'neutral'])
        self.assertGreaterEqual(nd['confidence'], 0.4)
        self.assertLessEqual(nd['confidence'], 1.0)

    def test_price_range(self):
        nd = gen_pred('601166', self.info, self.lp)['next_day']
        self.assertGreater(nd['high'], nd['low'])

    def test_hourly_4_blocks(self):
        pred = gen_pred('601166', self.info, self.lp)
        self.assertEqual(len(pred['hourly']), 4)
        blocks = ['09:30-10:30', '10:30-11:30', '13:00-14:00', '14:00-15:00']
        for i, h in enumerate(pred['hourly']):
            self.assertEqual(h['block'], blocks[i])

    def test_hourly_strength_range(self):
        for h in gen_pred('601166', self.info, self.lp)['hourly']:
            self.assertGreaterEqual(h['strength'], 1)
            self.assertLessEqual(h['strength'], 5)

    def test_actual_is_none(self):
        act = gen_pred('601166', self.info, self.lp)['actual']
        for field in ['open', 'high', 'low', 'close', 'next_day_direction_hit', 'daily_range_hit']:
            self.assertIsNone(act[field])

    def test_advice_valid(self):
        advice = gen_pred('601166', self.info, self.lp)['next_day']['advice']
        self.assertIn(advice, ['低吸为主', '观望为主', '逢高减仓'])

    def test_entry_zone_nonzero(self):
        self.assertGreater(gen_pred('601166', self.info, self.lp)['next_day']['entry_zone'], 0)


class TestNewLP(StockTestBase):
    def test_structure(self):
        lp = new_lp()
        for key in ['signal_weights', 'hourly_bias', 'seasonal_adj',
                     'confidence_beta', 'learning_rate', 'mw_beta', 'update_count']:
            self.assertIn(key, lp)

    def test_signal_weights_7x5(self):
        sw = new_lp()['signal_weights']
        self.assertEqual(len(sw), 7)
        for s in SIGNALS:
            self.assertEqual(len(sw[s]), 5)

    def test_all_weights_default_1(self):
        lp = new_lp()
        for s in SIGNALS:
            for b in BLOCKS:
                self.assertEqual(lp['signal_weights'][s][b], 1.0)

    def test_confidence_beta_default(self):
        lp = new_lp()
        for d in ['bullish', 'bearish', 'neutral']:
            self.assertEqual(lp['confidence_beta'][d]['alpha'], 1)
            self.assertEqual(lp['confidence_beta'][d]['beta'], 1)

    def test_hourly_bias_zero(self):
        lp = new_lp()
        for b in BLOCKS:
            self.assertEqual(lp['hourly_bias'][b], 0.0)

    def test_seasonal_adj_12(self):
        lp = new_lp()
        for m in range(1, 13):
            self.assertEqual(lp['seasonal_adj'][str(m)], 0.0)

    def test_defaults(self):
        lp = new_lp()
        self.assertEqual(lp['update_count'], 0)
        self.assertAlmostEqual(lp['learning_rate'], 0.01)
        self.assertAlmostEqual(lp['mw_beta'], 0.7)


class TestConstants(StockTestBase):
    def test_7_signals(self):
        expected = ['macd', 'rsi', 'bollinger', 'kdj', 'seasonal', 'atr', 'money_flow']
        self.assertEqual(SIGNALS, expected)

    def test_5_blocks(self):
        expected = ['09:30-10:30', '10:30-11:30', '13:00-14:00', '14:00-15:00', 'next_day']
        self.assertEqual(BLOCKS, expected)


if __name__ == '__main__':
    unittest.main(verbosity=2)
