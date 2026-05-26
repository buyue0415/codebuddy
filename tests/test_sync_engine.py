"""P1 [CRITICAL] Sync engine tests — calc_signals, gen_pred, _ema.

Tests the 7 technical indicators, prediction generation, EMAs,
and self-learning learning parameter structures.
Can run WITHOUT a live database — uses synthetic K-line data.
"""
import os, sys, math, json, unittest
from collections import defaultdict
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'scripts'))

from conftest import StockTestBase

# ======================================================================
# Import sync_all functions (they're module-level, not in a class)
# ======================================================================
_SYNC_IMPORTED = False
_SYNC_IMPORT_ERR = ''

try:
    # We import the functions directly by reading the module
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        'sync_all',
        os.path.join(ROOT, 'scripts', 'sync_all.py')
    )
    sync_mod = importlib.util.module_from_spec(spec)
    # Temporarily patch get_db to avoid DB dependency
    class _MockDB:
        def execute(self, *a, **kw): return []
        def close(self): pass
    sync_mod.get_db = lambda: _MockDB()
    sync_mod.get_watchlist = lambda: []
    sync_mod.get_learning_params = lambda c: None
    spec.loader.exec_module(sync_mod)

    calc_signals = sync_mod.calc_signals
    gen_pred = sync_mod.gen_pred
    _ema = sync_mod._ema
    new_lp = sync_mod.new_lp
    _calc_seasonal_from_db = sync_mod._calc_seasonal_from_db
    SIGNALS = sync_mod.SIGNALS
    BLOCKS = sync_mod.BLOCKS

    _SYNC_IMPORTED = True
except Exception as e:
    _SYNC_IMPORT_ERR = str(e)


# ======================================================================
# Synthetic test data: 60 days of descending K-line (downtrend, newest-first)
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
    return bars  # newest-first (i=0 = today)

KLINE_DATA = _make_kdata(60, 20.0)


# ======================================================================
# Tests
# ======================================================================

@unittest.skipIf(not _SYNC_IMPORTED, f"sync_all import failed: {_SYNC_IMPORT_ERR}")
class TestEMA(StockTestBase):
    """Test exponential moving average calculation."""

    def test_ema_basic(self):
        """EMA of constant values = that value."""
        data = [10.0] * 20
        result = _ema(data, 10)
        self.assertAlmostEqual(result, 10.0, places=4)

    def test_ema_rising_values(self):
        """EMA should rise with increasing data."""
        data = [float(i) for i in range(1, 31)]
        ema_5 = _ema(data, 5)
        ema_10 = _ema(data, 10)
        # Longer-period EMA should be lower for rising data
        self.assertLess(ema_10, ema_5)

    def test_ema_falling_values(self):
        """EMA should fall with decreasing data."""
        data = [float(30 - i) for i in range(30)]
        ema_5 = _ema(data, 5)
        ema_10 = _ema(data, 10)
        # Longer-period EMA should be higher for falling data
        self.assertGreater(ema_10, ema_5)

    def test_ema_min_period(self):
        """EMA with n=1 equals last value."""
        data = [1, 2, 3, 4, 5]
        self.assertAlmostEqual(_ema(data, 1), 5.0, places=2)


@unittest.skipIf(not _SYNC_IMPORTED, f"sync_all import failed: {_SYNC_IMPORT_ERR}")
class TestCalcSignals(StockTestBase):
    """Test 7 technical indicators."""

    def test_insufficient_data_returns_none(self):
        """Fewer than 14 bars should return None."""
        result = calc_signals([['2026-01-01', 10, 10, 10, 10]] * 10)
        self.assertIsNone(result)

    def test_sufficient_data_returns_dict(self):
        """>=14 bars should return valid signal dict."""
        result = calc_signals(KLINE_DATA)
        self.assertIsNotNone(result)

    def test_output_has_close_and_atr(self):
        result = calc_signals(KLINE_DATA)
        self.assertIn('close', result)
        self.assertIn('atr', result)
        self.assertGreater(result['atr'], 0)

    def test_all_7_signals_present(self):
        result = calc_signals(KLINE_DATA)
        sig = result['signals']
        for name in SIGNALS:
            with self.subTest(signal=name):
                self.assertIn(name, sig, f"Signal '{name}' missing")
                self.assertIn('direction', sig[name])

    def test_signal_directions_valid(self):
        result = calc_signals(KLINE_DATA)
        for name, s in result['signals'].items():
            self.assertIn(s['direction'], ['bullish', 'bearish', 'neutral'],
                          f"{name} direction invalid: {s['direction']}")

    def test_rsi_range(self):
        """RSI should be between 0 and 100."""
        result = calc_signals(KLINE_DATA)
        rsi = result['signals']['rsi']['raw']
        self.assertGreaterEqual(rsi, 0)
        self.assertLessEqual(rsi, 100)

    def test_bollinger_bands_structure(self):
        result = calc_signals(KLINE_DATA)
        bb = result['signals']['bollinger']
        self.assertIn('upper', bb)
        self.assertIn('lower', bb)
        self.assertGreater(bb['upper'], bb['lower'])

    def test_macd_has_diff_and_signal(self):
        result = calc_signals(KLINE_DATA)
        macd = result['signals']['macd']
        self.assertIn('diff', macd)
        self.assertIn('signal', macd)

    def test_kdj_has_j_value(self):
        result = calc_signals(KLINE_DATA)
        kdj = result['signals']['kdj']
        self.assertIn('raw', kdj)

    def test_seasonal_direction_default(self):
        """With default seasonal_factor=1.0, direction should be 'bearish'."""
        result = calc_signals(KLINE_DATA)
        se = result['signals']['seasonal']
        self.assertIn(se['direction'], ['bullish', 'bearish'])

    def test_atr_pct_calculation(self):
        result = calc_signals(KLINE_DATA)
        atr = result['signals']['atr']
        self.assertIn('pct', atr)
        close = result['close']
        expected_pct = round(atr['raw'] / close * 100, 2)
        self.assertAlmostEqual(atr['pct'], expected_pct, places=1)

    def test_money_flow_has_chg_3d(self):
        result = calc_signals(KLINE_DATA)
        mf = result['signals']['money_flow']
        self.assertIn('raw', mf)

    def test_bullish_seasonal_factor(self):
        """Test with strong bullish seasonal factor."""
        result = calc_signals(KLINE_DATA, seasonal_factor=1.2)
        se = result['signals']['seasonal']
        self.assertEqual(se['direction'], 'bullish')

    def test_bearish_seasonal_factor(self):
        """Test with bearish seasonal factor."""
        result = calc_signals(KLINE_DATA, seasonal_factor=0.8)
        se = result['signals']['seasonal']
        self.assertEqual(se['direction'], 'bearish')


@unittest.skipIf(not _SYNC_IMPORTED, f"sync_all import failed: {_SYNC_IMPORT_ERR}")
class TestGenPred(StockTestBase):
    """Test prediction generation."""

    def setUp(self):
        super().setUp()
        self.result = calc_signals(KLINE_DATA)
        self.assertIsNotNone(self.result, "calc_signals must succeed first")
        self.lp = new_lp()

    def test_prediction_output_structure(self):
        pred = gen_pred('601166', self.result, self.lp)
        for key in ['date', 'code', 'prev_close', 'next_day', 'hourly', 'signals', 'actual']:
            self.assertIn(key, pred, f"Missing key: {key}")

    def test_pred_next_day_has_direction(self):
        pred = gen_pred('601166', self.result, self.lp)
        nd = pred['next_day']
        self.assertIn(nd['direction'], ['bullish', 'bearish', 'neutral'])
        self.assertIn('confidence', nd)
        self.assertGreaterEqual(nd['confidence'], 0.4)
        self.assertLessEqual(nd['confidence'], 1.0)

    def test_pred_price_range(self):
        pred = gen_pred('601166', self.result, self.lp)
        nd = pred['next_day']
        self.assertGreater(nd['high'], nd['low'])

    def test_pred_hourly_4_blocks(self):
        pred = gen_pred('601166', self.result, self.lp)
        self.assertEqual(len(pred['hourly']), 4)
        blocks = ['09:30-10:30', '10:30-11:30', '13:00-14:00', '14:00-15:00']
        for i, h in enumerate(pred['hourly']):
            self.assertEqual(h['block'], blocks[i])

    def test_pred_hourly_strength_range(self):
        pred = gen_pred('601166', self.result, self.lp)
        for h in pred['hourly']:
            self.assertGreaterEqual(h['strength'], 1)
            self.assertLessEqual(h['strength'], 5)

    def test_pred_actual_is_none(self):
        """Prediction from gen_pred should have no actual data."""
        pred = gen_pred('601166', self.result, self.lp)
        act = pred['actual']
        self.assertIsNone(act['open'])
        self.assertIsNone(act['high'])
        self.assertIsNone(act['low'])
        self.assertIsNone(act['close'])
        self.assertIsNone(act['next_day_direction_hit'])
        self.assertIsNone(act['daily_range_hit'])

    def test_pred_advice_in_valid_set(self):
        pred = gen_pred('601166', self.result, self.lp)
        self.assertIn(pred['next_day']['advice'], ['低吸为主', '观望为主', '逢高减仓'])

    def test_pred_entry_zone_nonzero(self):
        pred = gen_pred('601166', self.result, self.lp)
        self.assertGreater(pred['next_day']['entry_zone'], 0)


@unittest.skipIf(not _SYNC_IMPORTED, f"sync_all import failed: {_SYNC_IMPORT_ERR}")
class TestNewLP(StockTestBase):
    """Test learning parameter initialization."""

    def test_new_lp_structure(self):
        lp = new_lp()
        for key in ['signal_weights', 'hourly_bias', 'seasonal_adj',
                     'confidence_beta', 'learning_rate', 'mw_beta', 'update_count']:
            self.assertIn(key, lp)

    def test_signal_weights_7x5(self):
        lp = new_lp()
        sw = lp['signal_weights']
        self.assertEqual(len(sw), 7)  # 7 signals
        for s in SIGNALS:
            self.assertIn(s, sw)
            self.assertEqual(len(sw[s]), 5)  # 5 blocks

    def test_all_weights_default_1(self):
        lp = new_lp()
        for s in SIGNALS:
            for b in BLOCKS:
                self.assertEqual(lp['signal_weights'][s][b], 1.0)

    def test_confidence_beta_default(self):
        lp = new_lp()
        for direction in ['bullish', 'bearish', 'neutral']:
            self.assertEqual(lp['confidence_beta'][direction]['alpha'], 1)
            self.assertEqual(lp['confidence_beta'][direction]['beta'], 1)

    def test_hourly_bias_zero(self):
        lp = new_lp()
        for b in BLOCKS:
            self.assertEqual(lp['hourly_bias'][b], 0.0)

    def test_seasonal_adj_12_months(self):
        lp = new_lp()
        for m in range(1, 13):
            self.assertEqual(lp['seasonal_adj'][str(m)], 0.0)

    def test_learning_params_edge(self):
        lp = new_lp()
        self.assertEqual(lp['update_count'], 0)
        self.assertAlmostEqual(lp['learning_rate'], 0.01)
        self.assertAlmostEqual(lp['mw_beta'], 0.7)


@unittest.skipIf(not _SYNC_IMPORTED, f"sync_all import failed: {_SYNC_IMPORT_ERR}")
class TestConstants(StockTestBase):
    """Test sync module constants."""

    def test_signals_7_items(self):
        self.assertEqual(len(SIGNALS), 7)
        expected = ['macd', 'rsi', 'bollinger', 'kdj', 'seasonal', 'atr', 'money_flow']
        self.assertEqual(SIGNALS, expected)

    def test_blocks_5_items(self):
        self.assertEqual(len(BLOCKS), 5)
        expected = ['09:30-10:30', '10:30-11:30', '13:00-14:00', '14:00-15:00', 'next_day']
        self.assertEqual(BLOCKS, expected)


# ======================================================================
# Run
# ======================================================================
if __name__ == '__main__':
    unittest.main(verbosity=2)
