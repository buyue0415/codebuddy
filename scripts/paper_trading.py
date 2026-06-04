"""
Paper Trading: Automated simulated trading based on daily predictions.

Auto-executes buy/sell decisions from daily_predictions table.
No user confirmation required. Data source must match Intelligence.vue.

Usage:
    python paper_trading.py auto    # Auto-execute today's trades
    python paper_trading.py reset   # Reset account to initial state
    python paper_trading.py status  # Show current account status

Architecture: Business Logic layer.
Data access: only via db_helper.py.
Called by: scheduler.py (auto), server_v2.py (API backend)
"""
import json, os, sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from db_helper import (
    get_db, get_watchlist_codes, get_paper_account,
    get_paper_positions, get_quotes, get_quotes_batch,
    get_daily_predictions_batch, reset_paper_account,
    upsert_paper_suggestion, init_backtest_tables,
)
from signals import TODAY

# ── Constants ──────────────────────────────────────────────────────────
INITIAL_CAPITAL = 100000.0
COMMISSION_RATE = 0.0003   # 0.03%
STAMP_TAX_RATE = 0.001     # 0.1% (sell only)
MIN_CONFIDENCE = 0.5        # Minimum confidence to act
MAX_POSITION_WEIGHT = 0.3   # Max 30% of portfolio in one stock
LOT_SIZE = 100


# ── Core Functions ──────────────────────────────────────────────────────

def init_account(initial_capital: float = INITIAL_CAPITAL):
    """Initialize paper account if not exists."""
    account = get_paper_account()
    if not account:
        reset_paper_account(initial_capital)
        sys.stderr.write(f"[Paper] Account initialized: ¥{initial_capital:,.0f}\n")
    else:
        sys.stderr.write(f"[Paper] Account exists: ¥{account['cash']:,.0f} cash\n")
    return get_paper_account()


def generate_suggestions() -> list:
    """Generate today's trading suggestions from daily_predictions.

    🔴 MUST use daily_predictions table (same source as Intelligence.vue).

    Optimized: single DB connection, batch queries for predictions and quotes.
    """
    # ── Open ONE db connection for the entire function ──
    db = get_db()
    try:
        # Batch: get watchlist codes
        codes = [r['code'] for r in db.execute("SELECT code FROM watchlist").fetchall()]
        if not codes:
            return []

        # Batch: get today's predictions for all codes in ONE query
        today_preds = get_daily_predictions_batch(db, codes, TODAY)

        # Batch: get quotes only for watchlist codes (not SELECT * FROM quotes!)
        quotes = get_quotes_batch(db, codes)

        # Get account and positions using the SAME db connection
        account_row = db.execute(
            "SELECT * FROM paper_account ORDER BY id DESC LIMIT 1"
        ).fetchone()
        account = dict(account_row) if account_row else None
        if not account:
            init_account()
            account_row = db.execute(
                "SELECT * FROM paper_account ORDER BY id DESC LIMIT 1"
            ).fetchone()
            account = dict(account_row) if account_row else None
        if not account:
            return []

        pos_rows = db.execute(
            "SELECT pp.*, s.name FROM paper_positions pp "
            "LEFT JOIN stocks s ON pp.code=s.code WHERE pp.qty>0"
        ).fetchall()
        positions = {p['code']: dict(p) for p in pos_rows}

        cash = account['cash']
        total_asset = cash + sum(
            p.get('market_value', 0) for p in positions.values()
        )

        # Generate suggestions
        suggestions = []
        for code in codes:
            pred = today_preds.get(code)
            if not pred:
                continue

            direction = pred.get('direction', 'neutral')
            confidence = pred.get('confidence', 0) or 0
            entry_zone = pred.get('entry_zone', 0) or 0
            price = quotes.get(code, {}).get('price', entry_zone) or entry_zone
            position = positions.get(code)
            holding_qty = position['qty'] if position else 0

            # Determine action
            if direction == 'bullish' and confidence >= MIN_CONFIDENCE:
                kelly = max(0, min(MAX_POSITION_WEIGHT, confidence * 2 - 1 + 0.05))
                amount = total_asset * kelly
                qty = int(amount / price / LOT_SIZE) * LOT_SIZE if price > 0 else 0
                action = 'buy' if qty >= LOT_SIZE else 'watch'
                reason = f"bullish conf={confidence:.0%}, signals={pred.get('signals_bullish',0)}/{pred.get('signals_bearish',0)}"
            elif direction == 'bearish' and holding_qty > 0 and confidence >= MIN_CONFIDENCE:
                qty = holding_qty
                action = 'sell'
                reason = f"bearish conf={confidence:.0%}, holding {holding_qty} shares"
            else:
                action = 'hold'
                qty = 0
                reason = f"neutral/low conf ({confidence:.0%})" if direction == 'neutral' else f"no position for {direction}"

            suggestions.append({
                'date': TODAY, 'code': code, 'action': action, 'qty': qty,
                'price': price, 'confidence': confidence, 'direction': direction,
                'entry_zone': entry_zone, 'reason': reason,
                'signals_bullish': 0, 'signals_bearish': 0,
                'position_weight': kelly if action == 'buy' else 0,
                'pred_id': pred.get('id'),
            })

        return suggestions
    finally:
        db.close()


def auto_execute():
    """Generate suggestions and auto-execute trades. Called by scheduler."""
    # Ensure tables exist
    init_backtest_tables()
    init_account()

    suggestions = generate_suggestions()
    if not suggestions:
        sys.stderr.write("[Paper] No predictions for today. Skipping.\n")
        return

    db = get_db()
    try:
        # Check if already executed today
        today_exec = db.execute(
            "SELECT COUNT(*) FROM paper_suggestions WHERE date=? AND executed=1", [TODAY]
        ).fetchone()[0]
        if today_exec > 0:
            sys.stderr.write(f"[Paper] Already executed today ({today_exec} trades). Skipping.\n")
            return

        # Get positions and account using SAME db connection
        pos_rows = db.execute(
            "SELECT pp.*, s.name FROM paper_positions pp "
            "LEFT JOIN stocks s ON pp.code=s.code WHERE pp.qty>0"
        ).fetchall()
        positions = {p['code']: dict(p) for p in pos_rows}

        account_row = db.execute(
            "SELECT * FROM paper_account ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if not account_row:
            return
        account = dict(account_row)
        cash = account['cash']

        # Batch: get quotes only for codes that matter
        pos_codes = [sug['code'] for sug in suggestions]
        quotes = get_quotes_batch(db, list(set(pos_codes)))

        executed = 0
        for sug in suggestions:
            sug['executed'] = 0
            # Inline upsert using SAME db connection (avoid separate connection lock conflict)
            sug_ex = db.execute(
                "SELECT id FROM paper_suggestions WHERE date=? AND code=?",
                [TODAY, sug['code']]
            ).fetchone()
            if sug_ex:
                db.execute(
                    "UPDATE paper_suggestions SET action=?,qty=?,price=?,confidence=?,direction=?,"
                    "entry_zone=?,reason=?,signals_bullish=?,signals_bearish=?,position_weight=?,"
                    "executed=?,pred_id=? WHERE id=?",
                    [sug['action'], sug['qty'], sug['price'], sug['confidence'], sug['direction'],
                     sug.get('entry_zone'), sug.get('reason', ''), sug.get('signals_bullish', 0),
                     sug.get('signals_bearish', 0), sug.get('position_weight', 0), 0,
                     sug.get('pred_id'), sug_ex['id']]
                )
            else:
                db.execute(
                    "INSERT INTO paper_suggestions (date,code,action,qty,price,confidence,direction,"
                    "entry_zone,reason,signals_bullish,signals_bearish,position_weight,executed,pred_id) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    [TODAY, sug['code'], sug['action'], sug['qty'], sug['price'], sug['confidence'],
                     sug['direction'], sug.get('entry_zone'), sug.get('reason', ''),
                     sug.get('signals_bullish', 0), sug.get('signals_bearish', 0),
                     sug.get('position_weight', 0), 0, sug.get('pred_id')]
                )

            if sug['action'] == 'buy' and sug['qty'] >= LOT_SIZE:
                qty = sug['qty']
                price = sug['price']
                cost = qty * price
                commission = cost * COMMISSION_RATE
                settlement = -(cost + commission)
                if abs(settlement) <= cash:
                    db.execute(
                        "INSERT INTO paper_trades (date, code, direction, qty, price, commission, stamp_tax, settlement, source, suggestion_id) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'auto_suggestion', ?)",
                        [TODAY, sug['code'], 'buy', qty, price, round(commission, 2), 0.0, round(settlement, 2), sug.get('pred_id')]
                    )
                    cash += settlement
                    existing = positions.get(sug['code'])
                    if existing:
                        new_qty = existing['qty'] + qty
                        new_cost = (existing['avg_cost'] * existing['qty'] + cost) / new_qty
                        db.execute(
                            "UPDATE paper_positions SET qty=?, avg_cost=?, last_price=?, market_value=qty*?, updated_at=datetime('now','localtime') WHERE code=?",
                            [new_qty, round(new_cost, 4), round(price, 4), round(price, 4), sug['code']]
                        )
                    else:
                        db.execute(
                            "INSERT INTO paper_positions (code, qty, avg_cost, last_price, market_value, updated_at) VALUES (?, ?, ?, ?, ?, datetime('now','localtime'))",
                            [sug['code'], qty, round(price, 4), round(price, 4), round(qty * price, 2)]
                        )
                    db.execute(
                        "UPDATE paper_suggestions SET executed=1 WHERE date=? AND code=?",
                        [TODAY, sug['code']]
                    )
                    executed += 1
                    sys.stderr.write(f"  BUY  {sug['code']} {qty}sh @ ¥{price:.2f} (cash: ¥{cash:,.0f})\n")

            elif sug['action'] == 'sell' and sug['qty'] > 0:
                qty = sug['qty']
                price = sug['price']
                revenue = qty * price
                commission = revenue * COMMISSION_RATE
                tax = revenue * STAMP_TAX_RATE
                settlement = revenue - commission - tax

                existing = positions.get(sug['code'])
                if existing and existing['qty'] >= qty:
                    realized_pnl = settlement - (existing['avg_cost'] * qty)
                    db.execute(
                        "INSERT INTO paper_trades (date, code, direction, qty, price, commission, stamp_tax, settlement, realized_pnl, source, suggestion_id) "
                        "VALUES (?, ?, 'sell', ?, ?, ?, ?, ?, ?, 'auto_suggestion', ?)",
                        [TODAY, sug['code'], qty, price, round(commission, 2), round(tax, 2), round(settlement, 2), round(realized_pnl, 2), sug.get('pred_id')]
                    )
                    cash += settlement
                    remaining = existing['qty'] - qty
                    if remaining > 0:
                        db.execute("UPDATE paper_positions SET qty=?, updated_at=datetime('now','localtime') WHERE code=?", [remaining, sug['code']])
                    else:
                        db.execute("DELETE FROM paper_positions WHERE code=?", [sug['code']])
                    db.execute("UPDATE paper_suggestions SET executed=1 WHERE date=? AND code=?", [TODAY, sug['code']])
                    executed += 1
                    sys.stderr.write(f"  SELL {sug['code']} {qty}sh @ ¥{price:.2f} pnl=¥{realized_pnl:,.0f} (cash: ¥{cash:,.0f})\n")

        # Update account — re-fetch latest positions after trade execution
        total_value = cash
        latest_pos_rows = db.execute(
            "SELECT pp.* FROM paper_positions pp WHERE pp.qty>0"
        ).fetchall()
        for p in latest_pos_rows:
            pcode = p['code']
            q = quotes.get(pcode, {}).get('price', 0) or 0
            total_value += p['qty'] * q
        cumulative_return = round((total_value / INITIAL_CAPITAL - 1) * 100, 2)
        db.execute(
            "INSERT OR REPLACE INTO paper_daily_snapshot (date, total_asset, cash, position_value, cumulative_return_pct) "
            "VALUES (?, ?, ?, ?, ?)",
            [TODAY, round(total_value, 2), round(cash, 2), round(total_value - cash, 2), cumulative_return]
        )
        db.execute("UPDATE paper_account SET cash=?, updated_at=datetime('now','localtime') WHERE id=(SELECT id FROM paper_account ORDER BY id DESC LIMIT 1)",
                   [round(cash, 2)])
        db.commit()

        sys.stderr.write(f"[Paper] Auto-executed {executed}/{len(suggestions)} trades. Cash: ¥{cash:,.0f}\n")
    finally:
        db.close()


# ── CLI ─────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('action', choices=['auto', 'reset', 'status'], default='auto')
    args = ap.parse_args()

    init_backtest_tables()

    if args.action == 'auto':
        auto_execute()
    elif args.action == 'reset':
        reset_paper_account()
        print(json.dumps({'success': True, 'message': 'Paper account reset'}))
    elif args.action == 'status':
        account = get_paper_account()
        positions = get_paper_positions()
        print(json.dumps({
            'account': account,
            'positions': positions,
            'success': True,
        }, ensure_ascii=False, default=str))
