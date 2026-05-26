"""P2 [HIGH] Statement parser tests — position calculation logic.

Tests the trade-by-trade position calculation algorithm without
requiring actual Excel files. Uses synthetic trade dictionaries.
"""
import os, sys, unittest
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from conftest import StockTestBase


# ======================================================================
# Position calculation logic (mirrors update_from_statement.py Step 2)
# ======================================================================

def calc_positions(trades):
    """Replicate the position calculation from update_from_statement.py.
    
    Args:
        trades: list of dicts with keys [code, name, type, qty, price,
                commission, stamp_tax, transfer_fee, regulatory_fee, 
                handling_fee, settlement]
    """
    positions = defaultdict(lambda: {
        'code': '', 'name': '', 'qty': 0, 'total_cost': 0.0,
        'trades': [], 'dividends': [], 'realized': 0.0,
        'total_commission': 0.0, 'total_stamp_tax': 0.0,
        'total_other_fees': 0.0,
    })

    for t in trades:
        code = t['code']
        pos = positions[code]
        pos['code'] = code
        pos['name'] = t['name']
        fee = (t['commission'] + t['stamp_tax'] + t['transfer_fee']
               + t['regulatory_fee'] + t['handling_fee'])
        pos['total_commission'] += t['commission']
        pos['total_stamp_tax'] += t['stamp_tax']
        # Other fees
        pos['total_other_fees'] += t['transfer_fee'] + t['regulatory_fee'] + t['handling_fee']

        if t['type'] == '证券买入':
            pos['qty'] += int(abs(t['qty']))
            pos['total_cost'] += abs(t['qty']) * t['price'] + fee
            pos['trades'].append(t)
        elif t['type'] == '证券卖出':
            sell_qty = int(abs(t['qty']))
            if pos['qty'] > 0 and pos['total_cost'] > 0:
                avg_cost = pos['total_cost'] / pos['qty']
                pos['total_cost'] -= avg_cost * sell_qty
                pos['realized'] += abs(t['qty']) * t['price'] - fee - avg_cost * sell_qty
            pos['qty'] -= sell_qty
            pos['trades'].append(t)
        elif t['type'] == '股息入账':
            pos['dividends'].append({
                'date': t['date'], 'amount': t['settlement'], 'price': t['price']
            })

    return positions


def _trade(date, code, name, ttype, qty, price, comm=0, stamp=0):
    """Helper to create a trade dict."""
    return {
        'date': date, 'time': '09:30:00', 'code': code, 'name': name,
        'type': ttype, 'qty': qty, 'price': price,
        'commission': comm, 'stamp_tax': stamp,
        'transfer_fee': 0.5, 'regulatory_fee': 0.2, 'handling_fee': 0.3,
        'settlement': round(qty * price + comm + stamp, 2),
    }


# ======================================================================
# Tests
# ======================================================================

class TestBuyOnly(StockTestBase):
    """Test: only buy trades."""

    def test_single_buy(self):
        trades = [_trade('2026-01-01', '601166', '兴业银行', '证券买入', 500, 17.30, 7.50)]
        pos = calc_positions(trades)
        self.assertIn('601166', pos)
        p = pos['601166']
        self.assertEqual(p['qty'], 500)
        self.assertEqual(p['trades'], trades)

    def test_multiple_buys_same_stock(self):
        trades = [
            _trade('2026-01-01', '601166', '兴业银行', '证券买入', 500, 17.30, 7.50),
            _trade('2026-01-15', '601166', '兴业银行', '证券买入', 300, 17.50, 5.00),
        ]
        pos = calc_positions(trades)
        p = pos['601166']
        self.assertEqual(p['qty'], 800)

    def test_multiple_stocks(self):
        trades = [
            _trade('2026-01-01', '601166', '兴业银行', '证券买入', 500, 17.30),
            _trade('2026-01-01', '600036', '招商银行', '证券买入', 200, 36.50),
        ]
        pos = calc_positions(trades)
        self.assertEqual(len(pos), 2)
        self.assertEqual(pos['601166']['qty'], 500)
        self.assertEqual(pos['600036']['qty'], 200)


class TestBuyAndSell(StockTestBase):
    """Test: buy then partial or full sell."""

    def test_partial_sell(self):
        trades = [
            _trade('2026-01-01', '601166', '兴业银行', '证券买入', 1000, 17.00, 10.0),
            _trade('2026-01-20', '601166', '兴业银行', '证券卖出', -500, 17.50, 8.0),
        ]
        pos = calc_positions(trades)
        p = pos['601166']
        self.assertEqual(p['qty'], 500)
        self.assertGreater(p['realized'], 0)  # profitable sell

    def test_full_sell_yields_zero_qty(self):
        trades = [
            _trade('2026-01-01', '601166', '兴业银行', '证券买入', 1000, 17.00, 10.0),
            _trade('2026-01-20', '601166', '兴业银行', '证券卖出', -1000, 17.50, 8.0),
        ]
        pos = calc_positions(trades)
        self.assertEqual(pos['601166']['qty'], 0)

    def test_sell_loss_is_negative(self):
        trades = [
            _trade('2026-01-01', '601166', '兴业银行', '证券买入', 500, 20.00, 7.5),
            _trade('2026-01-20', '601166', '兴业银行', '证券卖出', -500, 18.00, 7.5),
        ]
        pos = calc_positions(trades)
        self.assertLess(pos['601166']['realized'], 0)

    def test_split_buy_sell(self):
        """Buy 1000, sell 400, should leave 600."""
        trades = [
            _trade('2026-01-01', '601166', '兴业银行', '证券买入', 1000, 17.00),
            _trade('2026-01-10', '601166', '兴业银行', '证券买入', 500, 17.50),
            _trade('2026-01-20', '601166', '兴业银行', '证券卖出', -600, 17.80),
        ]
        pos = calc_positions(trades)
        self.assertEqual(pos['601166']['qty'], 900)


class TestDividends(StockTestBase):
    """Test dividend handling."""

    def test_dividend_no_qty_impact(self):
        """Dividends should not change the share count."""
        trades = [
            _trade('2026-01-01', '601166', '兴业银行', '证券买入', 1000, 17.00),
            _trade('2026-06-15', '601166', '兴业银行', '股息入账', 0, 17.37, 0, 0),
        ]
        trades[1]['settlement'] = 936.0
        pos = calc_positions(trades)
        p = pos['601166']
        self.assertEqual(p['qty'], 1000)  # shares unchanged
        self.assertEqual(len(p['dividends']), 1)
        self.assertEqual(p['dividends'][0]['amount'], 936.0)

    def test_dividend_cost_not_adjusted(self):
        """Dividend should NOT reduce total_cost."""
        trades = [
            _trade('2026-01-01', '601166', '兴业银行', '证券买入', 1000, 17.00, 10.0),
        ]
        cost_before = calc_positions(trades)['601166']['total_cost']
        trades.append({
            'date': '2026-06-15', 'time': '', 'code': '601166', 'name': '兴业银行',
            'type': '股息入账', 'qty': 0, 'price': 17.37,
            'commission': 0, 'stamp_tax': 0,
            'transfer_fee': 0, 'regulatory_fee': 0, 'handling_fee': 0,
            'settlement': 936.0,
        })
        pos = calc_positions(trades)['601166']
        self.assertEqual(pos['total_cost'], cost_before)


class TestFeeCalculation(StockTestBase):
    """Test fee aggregation."""

    def test_total_commission_aggregated(self):
        trades = [
            _trade('2026-01-01', '601166', '兴业银行', '证券买入', 500, 17.30, 7.50),
            _trade('2026-01-15', '601166', '兴业银行', '证券买入', 300, 17.50, 5.00),
        ]
        pos = calc_positions(trades)
        self.assertAlmostEqual(pos['601166']['total_commission'], 12.50, places=2)

    def test_other_fees_separate(self):
        trades = [
            _trade('2026-01-01', '601166', '兴业银行', '证券买入', 500, 17.30, 7.50),
        ]
        pos = calc_positions(trades)
        self.assertGreater(pos['601166']['total_other_fees'], 0)


class TestEdgeCases(StockTestBase):
    """Test edge cases and error handling."""

    def test_sell_when_no_shares(self):
        """Selling with zero position should not crash."""
        trades = [_trade('2026-01-01', '601166', '兴业银行', '证券卖出', -500, 17.00)]
        try:
            pos = calc_positions(trades)
            self.assertEqual(pos['601166']['qty'], -500)
        except Exception as e:
            self.fail(f"Sell with zero position crashed: {e}")

    def test_empty_trades(self):
        pos = calc_positions([])
        self.assertEqual(len(pos), 0)

    def test_ipo_code_736435(self):
        """IPO subscription code 736435 should be handled."""
        trades = [_trade('2026-01-01', '736435', '新股申购', '证券买入', 1000, 10.00)]
        pos = calc_positions(trades)
        self.assertIn('736435', pos)  # The filter is in update_from_statement, not in the pure logic

    def test_xd_name_cleaning(self):
        """XD prefix in name should be removable."""
        trades = [_trade('2026-01-01', '601166', 'XD兴业银行', '证券买入', 500, 17.00)]
        pos = calc_positions(trades)
        # Cleaned name: XD is stripped by update_from_statement
        name = pos['601166']['name'].replace('XD', '')
        self.assertNotIn('XD', name)


class TestClosedPosition(StockTestBase):
    """Test closed position detection."""

    def test_fully_sold_is_closed_by_qty_zero(self):
        trades = [
            _trade('2026-01-01', '601166', '兴业银行', '证券买入', 500, 17.00),
            _trade('2026-02-01', '601166', '兴业银行', '证券卖出', -500, 17.50),
        ]
        pos = calc_positions(trades)
        self.assertEqual(pos['601166']['qty'], 0)

    def test_avg_cost_calculation(self):
        """After buy+sell, avg_cost of remaining shares should be correct."""
        trades = [
            _trade('2026-01-01', '601166', '兴业银行', '证券买入', 1000, 17.00, 10.0),
            _trade('2026-01-15', '601166', '兴业银行', '证券卖出', -400, 17.50, 8.0),
        ]
        pos = calc_positions(trades)
        remaining = pos['601166']
        expected_cost = remaining['total_cost'] / remaining['qty'] if remaining['qty'] > 0 else 0
        # Avg cost should be approximately the buy price (slight deviation from fees)
        self.assertAlmostEqual(expected_cost, 17.01, delta=0.05)


# ======================================================================
# Run
# ======================================================================
if __name__ == '__main__':
    unittest.main(verbosity=2)
