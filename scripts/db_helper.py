"""SQLite database helper for server.py API endpoints"""
import sqlite3, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(ROOT, 'data', 'stock.db')

def get_db():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    return db

# ---- Query functions ----

def get_stock_search(keyword):
    db = get_db()
    kw = keyword.lower().strip()
    rows = db.execute("SELECT code, name, market, py FROM stocks WHERE code LIKE ? OR name LIKE ? OR py LIKE ? ORDER BY CASE WHEN code LIKE ? THEN 0 WHEN name LIKE ? THEN 1 ELSE 2 END LIMIT 15",
        ['%'+kw+'%', '%'+kw+'%', '%'+kw+'%', kw+'%', kw+'%']).fetchall()
    return [dict(r) for r in rows]

def get_watchlist():
    db = get_db()
    return [dict(r) for r in db.execute("SELECT code, name, market FROM watchlist ORDER BY sort_order").fetchall()]

def get_watchlist_codes():
    db = get_db()
    return [r['code'] for r in db.execute("SELECT code FROM watchlist").fetchall()]

def add_watchlist(code, name, market):
    db = get_db()
    db.execute("UPDATE stocks SET watchlist=1 WHERE code=?", [code])
    max_s = db.execute("SELECT MAX(sort_order) as m FROM watchlist").fetchone()['m'] or 0
    db.execute("INSERT OR REPLACE INTO watchlist(code,name,market,sort_order) VALUES(?,?,?,?)", [code, name, market, max_s+1])
    db.commit(); db.close()

def remove_watchlist(code):
    db = get_db()
    db.execute("UPDATE stocks SET watchlist=0 WHERE code=?", [code])
    db.execute("DELETE FROM watchlist WHERE code=?", [code])
    db.commit(); db.close()

def get_kline_daily(code):
    db = get_db()
    rows = db.execute("SELECT date, open, close, high, low FROM kline_daily WHERE code=? ORDER BY date DESC", [code]).fetchall()
    return [[r['date'], r['open'], r['close'], r['high'], r['low']] for r in rows]

def get_kline_monthly(code):
    db = get_db()
    rows = db.execute(
        "SELECT date, open, high, low, close, volume, change_pct FROM kline_monthly "
        "WHERE code=? AND substr(date,9,2)='01' ORDER BY date DESC",
        [code]
    ).fetchall()
    return [[r['date'], r['open'], r['high'], r['low'], r['close'], r['volume'], r['change_pct']] for r in rows]

def get_quotes():
    db = get_db()
    rows = db.execute("SELECT * FROM quotes").fetchall()
    return {r['code']: {'price': r['price'], 'change': r['change'], 'open': r['open'], 'high': r['high'], 'low': r['low'], 'pe': r['pe'], 'pb': r['pb'], 'dy': r['dy']} for r in rows}

def get_positions():
    db = get_db()
    open_pos = {}
    for r in db.execute("SELECT p.*, GROUP_CONCAT(d.date||':'||d.amount||':'||d.price,'|') as divs FROM positions p LEFT JOIN dividends d ON p.code=d.code GROUP BY p.code").fetchall():
        div_list = []
        if r['divs']:
            for d in r['divs'].split('|'):
                parts = d.split(':')
                if len(parts) >= 3:
                    div_list.append({'date': parts[0], 'amount': float(parts[1]), 'price': float(parts[2])})
        open_pos[r['code']] = {'code': r['code'], 'name': r['name'], 'qty': r['qty'], 'total_cost': r['total_cost'], 'avg_cost': r['avg_cost'], 'realized_pnl': r['realized_pnl'], 'dividends': div_list}

    closed_pos = {r['code']: dict(r) for r in db.execute("SELECT * FROM closed_positions").fetchall()}

    trades = [dict(r) for r in db.execute("SELECT * FROM trades ORDER BY date DESC, time DESC").fetchall()]

    return {'current_positions': open_pos, 'closed_positions': closed_pos, 'all_trades': trades}

def get_daily_predictions(code):
    db = get_db()
    rows = db.execute("SELECT * FROM daily_predictions WHERE code=? ORDER BY date DESC", [code]).fetchall()
    result = []
    for r in rows:
        pred = dict(r)
        pred['id'] = pred.pop('id')
        hourly = [dict(h) for h in db.execute("SELECT * FROM prediction_hourly WHERE pred_id=?", [pred['id']]).fetchall()]
        signals = {}
        for s in db.execute("SELECT * FROM prediction_signals WHERE pred_id=?", [pred['id']]).fetchall():
            signals[s['name']] = {'value': s['value'], 'direction': s['direction'], 'raw': s['raw_value']}
        # Map back to old format
        dp = {
            'date': r['date'], 'code': r['code'], 'prev_close': r['prev_close'],
            'next_day': {'direction': r['direction'], 'confidence': r['confidence'], 'high': r['high'], 'low': r['low'], 'advice': r['advice'], 'entry_zone': r['entry_zone']},
            'hourly': [{'block': h['block'], 'pred_open': h['pred_open'], 'pred_high': h['pred_high'], 'pred_low': h['pred_low'], 'pred_close': h['pred_close'], 'direction': h['direction'], 'strength': h['strength'], 'note': h['note']} for h in hourly],
            'signals': signals,
            'actual': {'open': r['actual_open'], 'high': r['actual_high'], 'low': r['actual_low'], 'close': r['actual_close'], 'next_day_direction_hit': bool(r['dir_hit']) if r['dir_hit'] is not None else None, 'daily_range_hit': bool(r['range_hit']) if r['range_hit'] is not None else None, 'hourly_hits': [h['hit'] for h in hourly]}
        }
        result.append(dp)
    return result

def get_learning_params(code):
    db = get_db()
    import json
    r = db.execute("SELECT * FROM learning_params WHERE code=?", [code]).fetchone()
    if not r: return None
    return {
        'signal_weights': json.loads(r['signal_weights']),
        'hourly_bias': json.loads(r['hourly_bias']),
        'seasonal_adj': json.loads(r['seasonal_adj']),
        'confidence_beta': json.loads(r['confidence_beta']),
        'learning_rate': r['learning_rate'], 'mw_beta': r['mw_beta'], 'update_count': r['update_count']
    }

def get_accuracy_stats(code):
    db = get_db()
    import json
    result = {}
    for r in db.execute("SELECT * FROM accuracy_stats WHERE code=?", [code]).fetchall():
        result[r['period']] = {
            'direction': {'correct': r['dir_correct'], 'total': r['dir_total'], 'rate': r['dir_rate']},
            'range': {'correct': r['range_correct'], 'total': r['range_total'], 'rate': r['range_rate']},
            'hourly': json.loads(r['hourly_stats'])
        }
    return result

def get_news(filter_type='all'):
    db = get_db()
    if filter_type == 'major':
        rows = db.execute("SELECT * FROM news WHERE major=1 ORDER BY date DESC").fetchall()
    elif filter_type == 'all':
        rows = db.execute("SELECT * FROM news ORDER BY date DESC").fetchall()
    else:
        rows = db.execute("SELECT * FROM news WHERE code=? ORDER BY date DESC", [filter_type]).fetchall()
    return [dict(r) for r in rows]

def get_expert_reports():
    db = get_db()
    import json
    rows = db.execute("SELECT * FROM expert_reports ORDER BY date DESC").fetchall()
    return [json.loads(r['report_data']) for r in rows]

def get_seasonal(code):
    db = get_db()
    import json
    r = db.execute("SELECT factors FROM seasonal WHERE code=?", [code]).fetchone()
    return json.loads(r['factors']) if r else []

# ===== V0.6 New query functions =====

def get_config():
    """Read system config from data/config.json"""
    import json
    config_path = os.path.join(ROOT, 'data', 'config.json')
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def _calc_fees(qty, price, config=None):
    """Calculate transfer_fee, regulatory_fee, handling_fee from config rates"""
    if config is None:
        config = get_config()
    rates = config.get('fee_rates', {})
    qa = abs(qty)
    tf = max(1.0, round(qa / 1000.0 * rates.get('transfer_fee_per_1000', 1.0), 2))
    rf = round(qa * price * rates.get('regulatory_fee_rate', 0.00002), 2)
    hf = round(qa * price * rates.get('handling_fee_rate', 0.0000487), 2)
    return tf, rf, hf

def get_current_positions():
    """Return current positions with dividends, trades, and fee totals"""
    import json
    db = get_db()
    config = get_config()

    # Positions + dividends (aggregated)
    open_pos = {}
    for r in db.execute("SELECT p.*, GROUP_CONCAT(d.date||':'||d.amount||':'||d.price,'|') as divs FROM positions p LEFT JOIN dividends d ON p.code=d.code GROUP BY p.code").fetchall():
        div_list = []
        if r['divs']:
            for d in r['divs'].split('|'):
                parts = d.split(':')
                if len(parts) >= 3:
                    div_list.append({'date': parts[0], 'amount': float(parts[1]), 'price': float(parts[2])})
        code = r['code']
        open_pos[code] = {'code': code, 'name': r['name'], 'qty': r['qty'],
            'total_cost': r['total_cost'], 'avg_cost': r['avg_cost'],
            'realized_pnl': r['realized_pnl'], 'dividends': div_list}

    # Trades with fees
    all_trades = get_trades()

    # Merge trades + fees into positions
    for code in open_pos:
        stock_trades = [t for t in all_trades if t['code'] == code]
        total_comm = sum(t['commission'] for t in stock_trades)
        total_stamp = sum(t['stamp_tax'] for t in stock_trades)
        total_other = sum(t['transfer_fee'] + t['regulatory_fee'] + t['handling_fee'] for t in stock_trades)
        open_pos[code]['trades'] = stock_trades
        open_pos[code]['total_commission'] = total_comm
        open_pos[code]['total_stamp_tax'] = total_stamp
        open_pos[code]['total_other_fees'] = total_other

    db.close()
    return open_pos

def get_closed_positions():
    """Return closed positions with trades and fee totals"""
    db = get_db()
    all_trades = get_trades()
    closed = {}
    for r in db.execute("SELECT * FROM closed_positions").fetchall():
        code = r['code']
        stock_trades = [t for t in all_trades if t['code'] == code]
        total_comm = sum(t['commission'] for t in stock_trades)
        total_stamp = sum(t['stamp_tax'] for t in stock_trades)
        total_other = sum(t['transfer_fee'] + t['regulatory_fee'] + t['handling_fee'] for t in stock_trades)
        closed[code] = {
            'code': code, 'name': r['name'],
            'realized_pnl': r['realized_pnl'], 'dividends_total': r['dividends_total'],
            'total_commission': total_comm or r['total_commission'],
            'total_stamp_tax': total_stamp or r['total_stamp_tax'],
            'total_other_fees': total_other or r['total_other_fees'],
            'trades': stock_trades
        }
    db.close()
    return closed

def get_trades(code=None):
    """Return all trades with calculated fees; optionally filtered by code"""
    db = get_db()
    config = get_config()
    if code:
        rows = db.execute("SELECT * FROM trades WHERE code=? ORDER BY date DESC, time DESC", [code]).fetchall()
    else:
        rows = db.execute("SELECT * FROM trades ORDER BY date DESC, time DESC").fetchall()

    result = []
    for r in rows:
        tf, rf, hf = _calc_fees(r['qty'], r['price'], config)
        result.append({
            'date': r['date'], 'time': r['time'],
            'code': r['code'], 'name': r['name'],
            'type': r['type'], 'qty': int(r['qty']), 'price': r['price'],
            'commission': r['commission'], 'stamp_tax': r['stamp_tax'],
            'transfer_fee': tf, 'regulatory_fee': rf, 'handling_fee': hf,
            'settlement': r['settlement']
        })
    db.close()
    return result

def _shares_before_date(code, date):
    """Calculate shares held for a stock just before a given date."""
    db = get_db()
    buys = db.execute(
        "SELECT COALESCE(SUM(qty), 0) FROM trades WHERE code=? AND date<? AND type='证券买入'",
        [code, date]
    ).fetchone()[0]
    sells = db.execute(
        "SELECT COALESCE(SUM(ABS(qty)), 0) FROM trades WHERE code=? AND date<? AND type='证券卖出'",
        [code, date]
    ).fetchone()[0]
    db.close()
    return int(buys - sells)

def get_dividends(code=None):
    """Return all dividends with per_share calculation; optionally filtered by code"""
    db = get_db()
    if code:
        rows = db.execute("SELECT date, code, amount, price FROM dividends WHERE code=? ORDER BY date DESC", [code]).fetchall()
    else:
        rows = db.execute("SELECT date, code, amount, price FROM dividends ORDER BY date DESC").fetchall()
    result = []
    for r in rows:
        shares = _shares_before_date(r['code'], r['date'])
        per_share = round(r['amount'] / shares, 4) if shares > 0 else 0
        result.append({
            'date': r['date'],
            'code': r['code'],
            'amount': r['amount'],
            'price': r['price'],
            'per_share': per_share,
        })
    db.close()
    return result

def get_all_kline_daily(codes=None):
    """Batch daily kline: all watchlist stocks or specific codes"""
    db = get_db()
    if codes is None:
        codes = get_watchlist_codes()
    kd = {}
    for code in codes:
        rows = db.execute("SELECT date, open, close, high, low FROM kline_daily WHERE code=? ORDER BY date DESC", [code]).fetchall()
        kd[code] = [[r['date'], r['open'], r['close'], r['high'], r['low']] for r in rows]
    db.close()
    return kd

def get_all_kline_monthly(codes=None):
    """Batch monthly kline (only true monthly bars with day=01)"""
    db = get_db()
    if codes is None:
        codes = get_watchlist_codes()
    km = {}
    for code in codes:
        rows = db.execute(
            "SELECT date, open, high, low, close, volume, change_pct FROM kline_monthly "
            "WHERE code=? AND substr(date,9,2)='01' ORDER BY date DESC",
            [code]
        ).fetchall()
        km[code] = [[r['date'], r['open'], r['high'], r['low'], r['close'], r['volume'], r['change_pct']] for r in rows]
    db.close()
    return km

def get_all_predictions(codes=None):
    """Batch daily predictions with hourly signals"""
    import json
    db = get_db()
    if codes is None:
        codes = get_watchlist_codes()

    result = []
    for code in codes:
        rows = db.execute("SELECT * FROM daily_predictions WHERE code=? ORDER BY date DESC", [code]).fetchall()
        for r in rows:
            pid = r['id']
            hourly = [dict(h) for h in db.execute("SELECT * FROM prediction_hourly WHERE pred_id=? ORDER BY id", [pid]).fetchall()]
            signals = {}
            for s in db.execute("SELECT * FROM prediction_signals WHERE pred_id=?", [pid]).fetchall():
                signals[s['name']] = {'value': s['value'], 'direction': s['direction'], 'raw': s['raw_value']}
            result.append({
                'date': r['date'], 'code': r['code'], 'prev_close': r['prev_close'],
                'next_day': {'direction': r['direction'], 'confidence': r['confidence'],
                    'high': r['high'], 'low': r['low'], 'advice': r['advice'], 'entry_zone': r['entry_zone']},
                'hourly': [{'block': h['block'], 'pred_open': h['pred_open'], 'pred_high': h['pred_high'],
                    'pred_low': h['pred_low'], 'pred_close': h['pred_close'], 'direction': h['direction'],
                    'strength': h['strength'], 'note': h['note']} for h in hourly],
                'signals': signals,
                'actual': {'open': r['actual_open'], 'high': r['actual_high'], 'low': r['actual_low'],
                    'close': r['actual_close'],
                    'next_day_direction_hit': bool(r['dir_hit']) if r['dir_hit'] is not None else None,
                    'daily_range_hit': bool(r['range_hit']) if r['range_hit'] is not None else None,
                    'hourly_hits': [h.get('hit') for h in hourly]}
            })
    db.close()
    return result

def get_all_seasonal(codes=None):
    """Batch seasonal factors"""
    import json
    db = get_db()
    if codes is None:
        codes = get_watchlist_codes()
    result = {}
    for code in codes:
        r = db.execute("SELECT factors FROM seasonal WHERE code=?", [code]).fetchone()
        result[code] = json.loads(r['factors']) if r else []
    db.close()
    return result

def get_all_accuracy_stats(codes=None):
    """Batch accuracy stats"""
    import json
    db = get_db()
    if codes is None:
        codes = get_watchlist_codes()
    result = {}
    for code in codes:
        acc = {}
        for r in db.execute("SELECT * FROM accuracy_stats WHERE code=? ORDER BY period", [code]).fetchall():
            acc[r['period']] = {
                'direction': {'correct': r['dir_correct'], 'total': r['dir_total'], 'rate': r['dir_rate']},
                'range': {'correct': r['range_correct'], 'total': r['range_total'], 'rate': r['range_rate']},
                'hourly': json.loads(r['hourly_stats'])
            }
        result[code] = acc
    db.close()
    return result

def get_all_monthly_changes(codes=None):
    """Batch monthly changes per stock"""
    db = get_db()
    if codes is None:
        codes = get_watchlist_codes()
    result = {}
    for code in codes:
        rows = db.execute("SELECT date, change_pct FROM kline_monthly WHERE code=? ORDER BY date DESC", [code]).fetchall()
        result[code] = [[r['date'], r['change_pct']] for r in rows if r['change_pct'] != 0]
    db.close()
    return result


def get_all_learning_params(codes=None):
    """Batch learning params per stock"""
    import json
    db = get_db()
    if codes is None:
        codes = get_watchlist_codes()
    result = {}
    for code in codes:
        lp = get_learning_params(code)
        if lp:
            result[code] = lp
    db.close()
    return result


# ===== Write functions (used by sync scripts) =====

def upsert_kline_daily(code, bars):
    db = get_db()
    db.execute("DELETE FROM kline_daily WHERE code=?", [code])
    db.executemany("INSERT INTO kline_daily(code,date,open,close,high,low) VALUES(?,?,?,?,?,?)",
        [[code, b[0], b[1], b[2], b[3], b[4]] for b in bars])
    db.commit(); db.close()

def upsert_kline_monthly(code, bars):
    db = get_db()
    db.execute("DELETE FROM kline_monthly WHERE code=?", [code])
    db.executemany("INSERT INTO kline_monthly(code,date,open,high,low,close,volume,change_pct) VALUES(?,?,?,?,?,?,?,?)",
        [[code, b[0], b[1], b[2], b[3], b[4], b[5] if len(b)>5 else 0, b[6] if len(b)>6 else 0] for b in bars])
    db.commit(); db.close()

def upsert_quotes(quotes_dict):
    db = get_db()
    for code, q in quotes_dict.items():
        db.execute("INSERT OR REPLACE INTO quotes(code,price,change,open,high,low,pe,pb,dy) VALUES(?,?,?,?,?,?,?,?,?)",
            [code, q.get('price'), q.get('change'), q.get('open'), q.get('high'), q.get('low'), q.get('pe'), q.get('pb'), q.get('dy')])
    db.commit(); db.close()

def upsert_news(news_list, today=None):
    import json
    db = get_db()
    if today:
        db.execute("DELETE FROM news WHERE date=?", [today])
    for n in news_list:
        db.execute("INSERT INTO news(date,code,title,summary,source,sentiment,major) VALUES(?,?,?,?,?,?,?)",
            [n.get('date'), n.get('code'), n.get('title'), n.get('summary',''), n.get('source',''), n.get('sentiment',''), 1 if n.get('major') else 0])
    db.commit(); db.close()

def upsert_seasonal(code, factors):
    import json
    db = get_db()
    db.execute("INSERT OR REPLACE INTO seasonal(code,factors) VALUES(?,?)", [code, json.dumps(factors)])
    db.commit(); db.close()

def insert_daily_prediction(code, date, prev_close, next_day, hourly, signals):
    db = get_db()
    cur = db.execute("INSERT INTO daily_predictions(code,date,prev_close,direction,confidence,high,low,advice,entry_zone) VALUES(?,?,?,?,?,?,?,?,?)",
        [code, date, prev_close, next_day['direction'], next_day['confidence'], next_day['high'], next_day['low'], next_day.get('advice',''), next_day.get('entry_zone',0)])
    pid = cur.lastrowid
    for hp in hourly:
        db.execute("INSERT INTO prediction_hourly(pred_id,block,pred_open,pred_high,pred_low,pred_close,direction,strength,note) VALUES(?,?,?,?,?,?,?,?,?)",
            [pid, hp['block'], hp.get('pred_open'), hp.get('pred_high'), hp.get('pred_low'), hp.get('pred_close'), hp.get('direction'), hp.get('strength'), hp.get('note','')])
    for sn, sv in signals.items():
        db.execute("INSERT INTO prediction_signals(pred_id,name,value,direction,raw_value) VALUES(?,?,?,?,?)",
            [pid, sn, str(sv.get('value','')), sv.get('direction'), sv.get('raw')])
    db.commit(); db.close()
    return pid

def clear_today_predictions(date):
    db = get_db()
    db.execute("DELETE FROM prediction_signals WHERE pred_id IN (SELECT id FROM daily_predictions WHERE date=?)", [date])
    db.execute("DELETE FROM prediction_hourly WHERE pred_id IN (SELECT id FROM daily_predictions WHERE date=?)", [date])
    db.execute("DELETE FROM daily_predictions WHERE date=?", [date])
    db.commit(); db.close()

def upsert_learning_params(code, lp):
    import json
    db = get_db()
    db.execute("INSERT OR REPLACE INTO learning_params(code,signal_weights,hourly_bias,seasonal_adj,confidence_beta,learning_rate,mw_beta,update_count) VALUES(?,?,?,?,?,?,?,?)",
        [code, json.dumps(lp.get('signal_weights',{})), json.dumps(lp.get('hourly_bias',{})), json.dumps(lp.get('seasonal_adj',{})), json.dumps(lp.get('confidence_beta',{})), lp.get('learning_rate',0.01), lp.get('mw_beta',0.7), lp.get('update_count',0)])
    db.commit(); db.close()

def upsert_accuracy_stats(code, period, stats):
    import json
    db = get_db()
    db.execute("INSERT OR REPLACE INTO accuracy_stats(code,period,dir_correct,dir_total,dir_rate,range_correct,range_total,range_rate,hourly_stats) VALUES(?,?,?,?,?,?,?,?,?)",
        [code, period, stats.get('direction',{}).get('correct',0), stats.get('direction',{}).get('total',0), stats.get('direction',{}).get('rate',0), stats.get('range',{}).get('correct',0), stats.get('range',{}).get('total',0), stats.get('range',{}).get('rate',0), json.dumps(stats.get('hourly',{}))])
    db.commit(); db.close()

def upsert_positions(current_positions, closed_positions, all_trades):
    db = get_db()
    db.execute("DELETE FROM positions"); db.execute("DELETE FROM closed_positions")
    db.execute("DELETE FROM trades"); db.execute("DELETE FROM dividends")
    for code, p in current_positions.items():
        db.execute("INSERT INTO positions(code,name,qty,total_cost,avg_cost,realized_pnl) VALUES(?,?,?,?,?,?)",
            [code, p['name'], p['qty'], p['total_cost'], p.get('avg_cost',0), p.get('realized_pnl',0)])
        for d in p.get('dividends', []):
            db.execute("INSERT INTO dividends(code,date,amount,price) VALUES(?,?,?,?)", [code, d['date'], d['amount'], d['price']])
    for code, p in closed_positions.items():
        db.execute("INSERT INTO closed_positions(code,name,realized_pnl,dividends_total,total_commission,total_stamp_tax,total_other_fees) VALUES(?,?,?,?,?,?,?)",
            [code, p['name'], p.get('realized_pnl',0), p.get('dividends_total',0), p.get('total_commission',0), p.get('total_stamp_tax',0), p.get('total_other_fees',0)])
    for t in all_trades:
        db.execute("INSERT INTO trades(date,time,code,name,type,qty,price,commission,stamp_tax,settlement) VALUES(?,?,?,?,?,?,?,?,?,?)",
            [t['date'], t.get('time',''), t['code'], t['name'], t['type'], int(t['qty']), t['price'], t.get('commission',0), t.get('stamp_tax',0), t['settlement']])
    db.commit(); db.close()
