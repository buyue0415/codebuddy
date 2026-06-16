import json, os, sys, subprocess
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from db_helper import (
    get_db, get_watchlist_codes, get_paper_account,
    get_paper_positions, get_quotes, get_quotes_batch,
    get_daily_predictions_batch, reset_paper_account,
    upsert_paper_suggestion, init_backtest_tables, get_kline_daily,
    get_learning_params, save_suggestions_snapshot,
)
from signals import TODAY, calc_signals, gen_pred, new_lp
from market_utils import is_market_open
from env_paths import get_node, get_westock

_NODE = get_node()
_WESTOCK = get_westock()
_SCRIPT = 'scripts/index.js'

INITIAL_CAPITAL = 100000.0
COMMISSION_RATE = 0.0003
STAMP_TAX_RATE = 0.001
MIN_CONFIDENCE = 0.5
MAX_POSITION_WEIGHT = 0.3
LOT_SIZE = 100


def _market_code(stock_code: str) -> str:
    if stock_code.startswith('6'):
        return f'sh{stock_code}'
    elif stock_code.startswith('0') or stock_code.startswith('3'):
        return f'sz{stock_code}'
    elif stock_code.startswith('4') or stock_code.startswith('8'):
        return f'bj{stock_code}'
    return f'sh{stock_code}'


def fetch_live_price(code: str) -> float | None:
    mkt = _market_code(code)
    try:
        result = subprocess.run(
            [_NODE, _SCRIPT, 'kline', mkt, '--period', 'day', '--limit', '1', '--fq', 'qfq'],
            cwd=_WESTOCK, capture_output=True, timeout=10,
        )
        text = ''
        if result.stdout:
            try:
                text = result.stdout.decode('gbk')
            except (UnicodeDecodeError, LookupError):
                text = result.stdout.decode('utf-8', errors='replace')
        for line in text.strip().split('\n'):
            parts = [p.strip() for p in line.split('|') if p.strip()]
            if len(parts) >= 5 and parts[0][:4].isdigit():
                return float(parts[4])
        return None
    except Exception:
        return None


# ──────────────────────────────────────────────────────────
# 建议生成（开市前自动/手动触发）
# ──────────────────────────────────────────────────────────

def _generate_predictions_and_suggestions_in_txn(db, codes):
    """在已有事务中生成预测和建议。"""
    existing_preds = get_daily_predictions_batch(db, codes, TODAY)
    generated_count = 0
    for code in codes:
        kdata = get_kline_daily(code)
        if not kdata or len(kdata) < 14:
            continue

        # 获取最新价格（优先实时价格，其次数据库报价，最后K线最新收盘价）
        price = fetch_live_price(code)
        if price is None or price <= 0:
            quotes = get_quotes_batch(db, [code])
            price = quotes.get(code, {}).get('price') if quotes else None
        if price is None or price <= 0:
            price = kdata[0][2]  # 最新K线收盘价
        if price is None or price <= 0:
            continue

        sig_result = calc_signals(kdata)
        if sig_result is None:
            continue

        lp = get_learning_params(code) or new_lp()
        pred = gen_pred(code, {'close': price, 'atr': sig_result.get('atr', 0), 'signals': sig_result['signals']}, lp)
        if pred is None:
            continue

        nd = pred['next_day']

        # 插入或更新预测
        if code in existing_preds:
            pred_id = existing_preds[code]['id']
        else:
            db.execute(
                "INSERT INTO daily_predictions (code,date,prev_close,direction,confidence,high,low,advice,entry_zone) VALUES (?,?,?,?,?,?,?,?,?)",
                [code, TODAY, pred['prev_close'], nd['direction'], nd['confidence'], nd['high'], nd['low'], nd['advice'], nd.get('entry_zone')]
            )
            pred_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
            for hp in pred.get('hourly', []):
                db.execute(
                    "INSERT INTO prediction_hourly (pred_id,block,pred_open,pred_high,pred_low,pred_close,direction,strength,note) VALUES (?,?,?,?,?,?,?,?,?)",
                    [pred_id, hp['block'], hp['pred_open'], hp['pred_high'], hp['pred_low'], hp['pred_close'], hp['direction'], hp['strength'], hp['note']]
                )
            for sname, sdata in sig_result['signals'].items():
                if isinstance(sdata, dict):
                    db.execute(
                        "INSERT INTO prediction_signals (pred_id,name,value,direction,raw_value) VALUES (?,?,?,?,?)",
                        [pred_id, sname, str(sdata.get('value', '')), sdata.get('direction', ''), sdata.get('raw_value', 0)]
                    )

        # 生成交易建议（sell 建议需校验是否有持仓）
        current_positions_map = _get_positions_map_in_txn(db)
        action, position_weight, suggestion_qty = 'hold', 0, 0

        if nd['direction'] == 'bullish' and nd['confidence'] >= MIN_CONFIDENCE:
            action = 'buy'
        elif nd['direction'] == 'bearish' and nd['confidence'] >= MIN_CONFIDENCE:
            if code in current_positions_map:
                action = 'sell'
                suggestion_qty = current_positions_map[code]['qty']
            else:
                action = 'hold'
        elif nd['direction'] == 'bullish' and nd['confidence'] >= MIN_CONFIDENCE - 0.1:
            action = 'watch'
            position_weight = MAX_POSITION_WEIGHT * 0.5

        if action in ('buy',):
            position_weight = MAX_POSITION_WEIGHT

        suggestion = {
            'date': TODAY, 'code': code, 'action': action, 'qty': suggestion_qty,
            'price': price, 'confidence': nd['confidence'], 'direction': nd['direction'],
            'entry_zone': nd.get('entry_zone'), 'reason': nd.get('advice', ''),
            'signals_bullish': nd.get('signals_bullish', 0),
            'signals_bearish': nd.get('signals_bearish', 0),
            'position_weight': position_weight, 'executed': 0, 'pred_id': pred_id,
        }
        _upsert_suggestion_in_txn(db, suggestion, code)
        generated_count += 1

    return generated_count


def generate_today_suggestions():
    """开市前/手动触发：仅生成今日预测和建议，不执行交易。
    
    返回: {success: bool, generated_count: int, codes_count: int, error: str}
    """
    init_backtest_tables()
    if not get_paper_account():
        reset_paper_account(INITIAL_CAPITAL)

    codes = get_watchlist_codes()
    if not codes:
        return {'success': False, 'generated_count': 0, 'codes_count': 0, 'error': '无自选股'}

    db = get_db()
    try:
        db.execute("BEGIN EXCLUSIVE")
        generated = _generate_predictions_and_suggestions_in_txn(db, codes)
        # 保存今日建议到历史快照表（仅供查询对比，不影响执行逻辑）
        if generated > 0:
            save_suggestions_snapshot(db, TODAY)
        db.commit()
        return {'success': True, 'generated_count': generated, 'codes_count': len(codes), 'error': ''}
    except Exception as e:
        db.rollback()
        return {'success': False, 'generated_count': 0, 'codes_count': len(codes), 'error': str(e)}
    finally:
        db.close()


# ──────────────────────────────────────────────────────────
# 自动执行（盘中自动/手动触发）
# ──────────────────────────────────────────────────────────

def check_and_execute():
    """盘中自动执行：遍历当日未执行 buy/sell 建议，重新获取实时价格并校验 entry_zone。
    
    Price matching rules:
      - buy:  实时价 <= entry_zone（看涨时 entry_zone = predicted_low，价格跌到低位入场）
      - sell: 实时价 >= entry_zone（看跌时 entry_zone = predicted_high，价格涨到高位出场）
      - 无 entry_zone：直接执行（兼容旧数据/未设置的情况）
    
    使用 EXCLUSIVE 事务锁，执行后自动记录快照。
    
    返回: dict:
      success: bool       - 是否成功
      executed_count: int - 本次执行笔数
      skipped_count: int  - 因价格未达标跳过的笔数
      skipped_codes: list - 跳过的股票代码
      pending_count: int  - 剩余未执行建议数
      error: str
    """
    init_backtest_tables()
    if not get_paper_account():
        reset_paper_account(INITIAL_CAPITAL)

    db = get_db()
    try:
        db.execute("BEGIN EXCLUSIVE")
        result = _execute_trades_in_txn(db, TODAY, enable_price_matching=True)
        _take_snapshot_in_txn(db, TODAY)
        db.commit()
        return result
    except Exception as e:
        db.rollback()
        return {'success': False, 'executed_count': 0, 'skipped_count': 0, 'skipped_codes': [], 'pending_count': 0, 'error': str(e)}
    finally:
        db.close()


# ── 组合调用（兼容旧 API） ──

def auto_execute():
    """组合调用：先生成建议，再自动执行。后端手动触发时使用。"""
    generate_today_suggestions()
    return check_and_execute()


def _upsert_suggestion_in_txn(db, suggestion, code):
    """在事务中安全地插入或更新建议。
    
    关键逻辑：
    - 如果该股票当天已有已执行的建议（executed=1），则跳过不覆盖
    - 如果该股票当天有未执行的建议（executed=0），则更新
    - 如果该股票当天无建议，则插入
    """
    existing = db.execute(
        "SELECT id, executed FROM paper_suggestions WHERE date=? AND code=?",
        [suggestion['date'], code]
    ).fetchone()

    if existing:
        if existing['executed'] == 1:
            # 已执行：跳过，不覆盖（防止重复执行）
            return existing['id']
        # 未执行：更新
        db.execute(
            """UPDATE paper_suggestions SET action=?, qty=?, price=?, confidence=?,
               direction=?, entry_zone=?, reason=?, signals_bullish=?, signals_bearish=?,
               position_weight=?, executed=0, pred_id=? WHERE id=?""",
            [
                suggestion['action'], suggestion['qty'], suggestion['price'],
                suggestion['confidence'], suggestion['direction'],
                suggestion.get('entry_zone'), suggestion['reason'],
                suggestion['signals_bullish'], suggestion['signals_bearish'],
                suggestion['position_weight'], suggestion['pred_id'],
                existing['id']
            ]
        )
        return existing['id']
    else:
        db.execute(
            """INSERT INTO paper_suggestions
               (date,code,action,qty,price,confidence,direction,entry_zone,reason,
                signals_bullish,signals_bearish,position_weight,executed,pred_id)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,0,?)""",
            [
                suggestion['date'], code, suggestion['action'], suggestion['qty'],
                suggestion['price'], suggestion['confidence'], suggestion['direction'],
                suggestion.get('entry_zone'), suggestion['reason'],
                suggestion['signals_bullish'], suggestion['signals_bearish'],
                suggestion['position_weight'], suggestion['pred_id'],
            ]
        )
        return db.execute("SELECT last_insert_rowid()").fetchone()[0]


def _get_positions_map_in_txn(db):
    """在现有事务中获取持仓字典 {code: {qty, avg_cost, ...}}。"""
    rows = db.execute(
        """SELECT code, qty, avg_cost, last_price
           FROM paper_positions WHERE qty > 0"""
    ).fetchall()
    return {r['code']: dict(r) for r in rows}


def _execute_trades_in_txn(db, date, enable_price_matching=False):
    """在同一事务中执行买卖。支持 entry_zone 价格匹配。
    
    enable_price_matching=True 时，对每笔建议重新获取实时价格并校验 entry_zone：
      - buy:  实时价 <= entry_zone（价格跌到预测低位入场）
      - sell: 实时价 >= entry_zone（价格涨到预测高位出场）
      - 无 entry_zone：使用新获取的实时价直接执行
      - fetch_live_price 失败：跳过该建议
    
    返回: dict {executed_count, skipped_count, skipped_codes, pending_count}
    """
    account_row = db.execute(
        "SELECT cash, initial_capital FROM paper_account WHERE id=1"
    ).fetchone()
    if not account_row:
        return {'executed_count': 0, 'skipped_count': 0, 'skipped_codes': [], 'pending_count': 0}
    cash = account_row['cash']
    initial_capital = account_row['initial_capital']

    rows = db.execute(
        """SELECT ps.*, s.name
           FROM paper_suggestions ps
           LEFT JOIN stocks s ON ps.code=s.code
           WHERE ps.date=? AND ps.executed=0 AND ps.action IN ('buy','sell')""",
        [date]
    ).fetchall()
    suggestions = [dict(r) for r in rows]
    if not suggestions:
        return {'executed_count': 0, 'skipped_count': 0, 'skipped_codes': [], 'pending_count': 0}

    positions_map = _get_positions_map_in_txn(db)

    # ── 第一阶段：校验所有交易可行性（含可选的价格匹配） ──
    validated_trades = []
    cash_after = cash
    skipped_codes = []

    for sug in suggestions:
        code = sug['code']
        action = sug['action']

        # 价格匹配：重新获取实时价格
        if enable_price_matching:
            live_price = fetch_live_price(code)
            if live_price is None or live_price <= 0:
                skipped_codes.append(code)
                continue
            price = live_price

            # 校验 entry_zone
            ez = sug.get('entry_zone')
            if ez is not None and ez > 0:
                if action == 'buy' and live_price > ez:
                    skipped_codes.append(code)
                    continue
                elif action == 'sell' and live_price < ez:
                    skipped_codes.append(code)
                    continue
        else:
            price = sug['price']
            if price <= 0:
                continue

        if action == 'buy' and sug['confidence'] >= MIN_CONFIDENCE:
            max_position_value = cash_after * MAX_POSITION_WEIGHT
            max_shares = int(max_position_value / price / LOT_SIZE) * LOT_SIZE if price > 0 else 0
            if max_shares < LOT_SIZE:
                continue
            commission = round(price * max_shares * COMMISSION_RATE, 2)
            settlement = round(price * max_shares + commission, 2)
            if settlement > cash_after:
                continue

            validated_trades.append({
                'type': 'buy',
                'suggestion_id': sug['id'],
                'code': code, 'price': price, 'qty': max_shares,
                'commission': commission, 'stamp_tax': 0,
                'settlement': settlement,
            })
            cash_after -= settlement

        elif action == 'sell' and code in positions_map:
            pos = positions_map[code]
            sell_qty = sug['qty'] if sug['qty'] and sug['qty'] > 0 else pos['qty']
            sell_qty = min(sell_qty, pos['qty'])
            if sell_qty < LOT_SIZE:
                continue

            commission = round(price * sell_qty * COMMISSION_RATE, 2)
            stamp_tax = round(price * sell_qty * STAMP_TAX_RATE, 2)
            settlement = round(price * sell_qty - commission - stamp_tax, 2)
            realized_pnl = round((price - pos['avg_cost']) * sell_qty - commission - stamp_tax, 2)

            validated_trades.append({
                'type': 'sell',
                'suggestion_id': sug['id'],
                'code': code, 'price': price, 'qty': sell_qty,
                'commission': commission, 'stamp_tax': stamp_tax,
                'settlement': settlement, 'realized_pnl': realized_pnl,
                'avg_cost': pos['avg_cost'],
            })
            cash_after += settlement

    executed_count = len(validated_trades)
    skipped_count = len(skipped_codes)
    unique_skipped = list(dict.fromkeys(skipped_codes))

    if not validated_trades:
        return {'executed_count': 0, 'skipped_count': skipped_count, 'skipped_codes': unique_skipped, 'pending_count': 0}

    # ── 第二阶段：统一应用所有交易 ──
    total_cash_change = 0
    for t in validated_trades:
        if t['type'] == 'buy':
            total_cash_change -= t['settlement']
        else:
            total_cash_change += t['settlement']

    final_cash = round(cash + total_cash_change, 2)
    if final_cash < 0:
        raise ValueError(f"交易后现金不足: {cash} + ({total_cash_change}) = {final_cash}")

    db.execute(
        "UPDATE paper_account SET cash=?, updated_at=datetime('now','localtime') WHERE id=1",
        [final_cash]
    )

    for t in validated_trades:
        if t['type'] == 'buy':
            code = t['code']
            existing = db.execute(
                "SELECT id, qty, avg_cost FROM paper_positions WHERE code=?",
                [code]
            ).fetchone()
            if existing:
                old_qty = existing['qty']
                old_cost = existing['avg_cost']
                new_qty = old_qty + t['qty']
                new_cost = round((old_cost * old_qty + t['price'] * t['qty']) / new_qty, 4)
                db.execute(
                    "UPDATE paper_positions SET qty=?, avg_cost=?, last_price=?, updated_at=datetime('now','localtime') WHERE code=?",
                    [new_qty, new_cost, t['price'], code]
                )
            else:
                db.execute(
                    "INSERT INTO paper_positions (code,qty,avg_cost,last_price,updated_at) VALUES (?,?,?,?,datetime('now','localtime'))",
                    [code, t['qty'], t['price'], t['price']]
                )

            db.execute(
                """INSERT INTO paper_trades
                   (date,code,direction,qty,price,commission,stamp_tax,settlement,source,suggestion_id)
                   VALUES (?,?,'buy',?,?,?,0,?,'auto_suggestion',?)""",
                [date, code, t['qty'], t['price'], t['commission'], t['settlement'], t['suggestion_id']]
            )

            db.execute(
                "UPDATE paper_suggestions SET qty=?, price=?, executed=1 WHERE id=?",
                [t['qty'], t['price'], t['suggestion_id']]
            )

        elif t['type'] == 'sell':
            code = t['code']
            pos = db.execute(
                "SELECT qty FROM paper_positions WHERE code=?",
                [code]
            ).fetchone()
            if not pos:
                continue

            remaining = pos['qty'] - t['qty']
            if remaining <= 0:
                db.execute("DELETE FROM paper_positions WHERE code=?", [code])
                if code in positions_map:
                    del positions_map[code]
            else:
                db.execute(
                    "UPDATE paper_positions SET qty=?, last_price=?, updated_at=datetime('now','localtime') WHERE code=?",
                    [remaining, t['price'], code]
                )
                positions_map[code]['qty'] = remaining
                positions_map[code]['last_price'] = t['price']

            db.execute(
                """INSERT INTO paper_trades
                   (date,code,direction,qty,price,commission,stamp_tax,settlement,realized_pnl,source,suggestion_id)
                   VALUES (?,?,'sell',?,?,?,?,?,?,'auto_suggestion',?)""",
                [date, code, t['qty'], t['price'], t['commission'], t['stamp_tax'],
                 t['settlement'], t['realized_pnl'], t['suggestion_id']]
            )

            db.execute(
                "UPDATE paper_suggestions SET qty=?, price=?, executed=1 WHERE id=?",
                [t['qty'], t['price'], t['suggestion_id']]
            )

    # 统计剩余未执行建议数
    pending = db.execute(
        "SELECT COUNT(*) FROM paper_suggestions WHERE date=? AND executed=0 AND action IN ('buy','sell')",
        [date]
    ).fetchone()[0]

    return {
        'executed_count': executed_count,
        'skipped_count': skipped_count,
        'skipped_codes': unique_skipped,
        'pending_count': pending,
    }


def _take_snapshot_in_txn(db, date):
    """在同一事务中记录当日资产快照。"""
    account_row = db.execute(
        "SELECT cash, initial_capital FROM paper_account WHERE id=1"
    ).fetchone()
    if not account_row:
        return
    cash = account_row['cash']
    initial_capital = account_row['initial_capital']

    rows = db.execute(
        """SELECT pp.qty, COALESCE(pp.last_price, pp.avg_cost) AS cur_price
           FROM paper_positions pp WHERE pp.qty > 0"""
    ).fetchall()
    position_value = round(sum(r['qty'] * r['cur_price'] for r in rows), 2)
    total_asset = round(cash + position_value, 2)
    cumulative_return_pct = round(
        (total_asset - initial_capital) / initial_capital * 100, 2
    ) if initial_capital > 0 else 0

    # 查昨日快照算当日收益
    prev = db.execute(
        "SELECT total_asset FROM paper_daily_snapshot ORDER BY date DESC LIMIT 1"
    ).fetchone()
    daily_pnl = round(total_asset - prev['total_asset'], 2) if prev else 0
    daily_pnl_pct = round(
        (total_asset - prev['total_asset']) / prev['total_asset'] * 100, 2
    ) if prev and prev['total_asset'] > 0 else 0

    db.execute(
        """INSERT OR REPLACE INTO paper_daily_snapshot
           (date,total_asset,cash,position_value,daily_pnl,daily_pnl_pct,cumulative_return_pct)
           VALUES (?,?,?,?,?,?,?)""",
        [date, total_asset, cash, position_value, daily_pnl, daily_pnl_pct, cumulative_return_pct]
    )


# ──────────────────────────────────────────────────────────
# 数据一致性校验（对外暴露）
# ──────────────────────────────────────────────────────────

def verify_paper_consistency() -> dict:
    """全面校验纸面交易数据的完整性与一致性。
    
    校验项：
    1. 持仓数量 = 所有买入交易量 - 所有卖出交易量（按股票代码）
    2. 账户现金 = 初始本金 + 所有卖出结算 - 所有买入结算
    3. 每笔建议的执行标记与交易记录一一对应
    4. 总资产 = 现金 + 持仓市值（快照检查）
    
    Returns:
        dict: {consistent: bool, checks: [检查结果], errors: [错误信息]}
    """
    result = {
        'consistent': True,
        'checks': [],
        'errors': [],
        'details': {},
    }

    db = get_db()
    try:
        # ── 1. 账户现金校验 ──
        account = db.execute(
            "SELECT cash, initial_capital FROM paper_account WHERE id=1"
        ).fetchone()
        if account:
            initial_capital = account['initial_capital']
            actual_cash = account['cash']

            # 从交易记录推算现金
            buy_total = db.execute(
                "SELECT COALESCE(SUM(settlement), 0) FROM paper_trades WHERE direction='buy'"
            ).fetchone()[0]
            sell_total = db.execute(
                "SELECT COALESCE(SUM(settlement), 0) FROM paper_trades WHERE direction='sell'"
            ).fetchone()[0]
            expected_cash = round(initial_capital - buy_total + sell_total, 2)

            cash_ok = abs(actual_cash - expected_cash) < 0.02  # 允许2分钱舍入误差
            result['checks'].append({
                'name': '账户现金一致性',
                'passed': cash_ok,
                'detail': f"实际={actual_cash}, 理论={expected_cash}, 初始本金={initial_capital}",
            })
            if not cash_ok:
                result['consistent'] = False
                result['errors'].append(f"现金不一致: 实际{actual_cash} ≠ 理论{expected_cash}")
            result['details']['cash'] = {
                'actual': actual_cash, 'expected': expected_cash, 'initial_capital': initial_capital,
            }

        # ── 2. 持仓校验 ──
        positions = db.execute(
            "SELECT code, qty FROM paper_positions WHERE qty > 0"
        ).fetchall()
        for pos in positions:
            code = pos['code']
            buy_qty = db.execute(
                "SELECT COALESCE(SUM(qty), 0) FROM paper_trades WHERE code=? AND direction='buy'",
                [code]
            ).fetchone()[0]
            sell_qty = db.execute(
                "SELECT COALESCE(SUM(qty), 0) FROM paper_trades WHERE code=? AND direction='sell'",
                [code]
            ).fetchone()[0]
            expected_qty = buy_qty - sell_qty

            if expected_qty != pos['qty']:
                result['consistent'] = False
                result['errors'].append(
                    f"{code} 持仓不一致: DB={pos['qty']}, 交易记录推导={expected_qty} "
                    f"(买入={buy_qty}, 卖出={sell_qty})"
                )
                result['checks'].append({
                    'name': f'持仓校验({code})',
                    'passed': False,
                    'detail': f"DB={pos['qty']}, 理论={expected_qty}",
                })
            else:
                result['checks'].append({
                    'name': f'持仓校验({code})',
                    'passed': True,
                    'detail': f"qty={pos['qty']}",
                })

        # 检查孤立的持仓（交易记录缺失）
        all_trade_codes = db.execute(
            "SELECT DISTINCT code FROM paper_trades"
        ).fetchall()
        trade_codes_set = {r['code'] for r in all_trade_codes}
        for pos in positions:
            if pos['code'] not in trade_codes_set:
                result['consistent'] = False
                result['errors'].append(
                    f"{pos['code']} 有持仓但无对应交易记录（qty={pos['qty']}）"
                )

        # ── 3. 建议-交易对应关系 ──
        executed_suggestions = db.execute(
            "SELECT COUNT(*) FROM paper_suggestions WHERE executed=1"
        ).fetchone()[0]
        trade_with_suggestion = db.execute(
            "SELECT COUNT(DISTINCT suggestion_id) FROM paper_trades WHERE suggestion_id IS NOT NULL"
        ).fetchone()[0]
        if executed_suggestions != trade_with_suggestion:
            result['checks'].append({
                'name': '建议-交易对应关系',
                'passed': False,
                'detail': f"已执行建议={executed_suggestions}, 关联交易记录={trade_with_suggestion}",
            })
            result['consistent'] = False
            if executed_suggestions > trade_with_suggestion:
                result['errors'].append(f"有 {executed_suggestions - trade_with_suggestion} 条建议标记为已执行但无对应交易记录")
        else:
            result['checks'].append({
                'name': '建议-交易对应关系',
                'passed': True,
                'detail': f"已执行建议={executed_suggestions}, 关联交易记录={trade_with_suggestion}",
            })

        # ── 4. 快照总资产校验 ──
        latest_snapshot = db.execute(
            "SELECT * FROM paper_daily_snapshot ORDER BY date DESC LIMIT 1"
        ).fetchone()
        if latest_snapshot:
            actual_cash = db.execute(
                "SELECT cash FROM paper_account WHERE id=1"
            ).fetchone()['cash']
            rows = db.execute(
                "SELECT qty, COALESCE(last_price, avg_cost) AS cp FROM paper_positions WHERE qty>0"
            ).fetchall()
            computed_position_value = round(sum(r['qty'] * r['cp'] for r in rows), 2)
            computed_total = round(actual_cash + computed_position_value, 2)
            snapshot_total = latest_snapshot['total_asset']

            total_ok = abs(computed_total - snapshot_total) < 0.02
            result['checks'].append({
                'name': '快照总资产一致性',
                'passed': total_ok,
                'detail': f"快照={snapshot_total}, 实时计算={computed_total} (现金={actual_cash}+持仓={computed_position_value})",
            })
            if not total_ok:
                result['consistent'] = False
                result['errors'].append(f"快照总资产不一致: 快照={snapshot_total} ≠ 实时计算={computed_total}")

        # ── 5. 总交易笔数 ──
        total_trades = db.execute("SELECT COUNT(*) FROM paper_trades").fetchone()[0]
        buy_trades = db.execute(
            "SELECT COUNT(*) FROM paper_trades WHERE direction='buy'"
        ).fetchone()[0]
        sell_trades = db.execute(
            "SELECT COUNT(*) FROM paper_trades WHERE direction='sell'"
        ).fetchone()[0]
        result['details']['trades'] = {
            'total': total_trades, 'buy': buy_trades, 'sell': sell_trades,
        }
        result['checks'].append({
            'name': '交易记录总量',
            'passed': True,
            'detail': f"共 {total_trades} 笔 (买入{buy_trades}, 卖出{sell_trades})",
        })

        result['details']['position_count'] = len(positions)

    except Exception as e:
        result['consistent'] = False
        result['errors'].append(f"校验过程异常: {str(e)}")
    finally:
        db.close()

    return result
