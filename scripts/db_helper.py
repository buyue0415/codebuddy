"""SQLite database helper for server.py API endpoints"""
import sqlite3, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(ROOT, 'data', 'stock.db')

def get_db():
    db = sqlite3.connect(DB_PATH, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=5000")
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
        "WHERE code=? "
        "GROUP BY substr(date,1,7) "
        "ORDER BY date DESC",
        [code]
    ).fetchall()
    return [[r['date'], r['open'], r['high'], r['low'], r['close'], r['volume'], r['change_pct']] for r in rows]

def get_quotes():
    db = get_db()
    rows = db.execute("SELECT * FROM quotes").fetchall()
    return {r['code']: {'price': r['price'], 'change': r['change'], 'open': r['open'], 'high': r['high'], 'low': r['low'], 'pe': r['pe'], 'pb': r['pb'], 'dy': r['dy']} for r in rows}

def get_positions():
    """Return all positions with correctly computed per_share dividends.

    Uses get_dividends() for each position to compute per_share as
    amount / shares_before_date, rather than the raw 'price' column
    (which is stock market price, NOT dividend per share).
    """
    db = get_db()
    open_pos = {}
    for r in db.execute("SELECT * FROM positions").fetchall():
        code = r['code']
        stock_divs = get_dividends(code)
        div_list = [{'date': d['date'], 'amount': d['amount'],
                      'per_share': d['per_share']} for d in stock_divs]
        open_pos[code] = {'code': r['code'], 'name': r['name'], 'qty': r['qty'],
            'total_cost': r['total_cost'], 'avg_cost': r['avg_cost'],
            'realized_pnl': r['realized_pnl'], 'dividends': div_list}

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
    """Return news list with id, news_id, content, content_status fields."""
    db = get_db()
    sql = "SELECT id, date, code, title, summary, content, content_status, source, sentiment, major, url, news_id FROM news"
    if filter_type == 'major':
        rows = db.execute(sql + " WHERE major=1 ORDER BY date DESC").fetchall()
    elif filter_type == 'all':
        rows = db.execute(sql + " ORDER BY date DESC").fetchall()
    else:
        rows = db.execute(sql + " WHERE code=? ORDER BY date DESC", [filter_type]).fetchall()
    return [dict(r) for r in rows]

def update_news_content(news_id: int, content: str):
    """Update the content field for a single news item (V0.7 on-demand caching)."""
    db = get_db()
    db.execute("UPDATE news SET content=? WHERE id=?", [content, news_id])
    db.commit()
    db.close()

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
    """Return current positions with dividends, trades, and fee totals.

    IMPORTANT: dividend entries now use 'per_share' (correctly calculated as
    amount / shares_before_date) instead of the raw 'price' column (which is
    the stock market price, NOT the per-share dividend amount).
    """
    import json
    db = get_db()
    config = get_config()

    # Build positions from DB — use get_dividends() for each stock
    # which correctly computes per_share via _shares_before_date()
    open_pos = {}
    for r in db.execute("SELECT * FROM positions").fetchall():
        code = r['code']
        stock_divs = get_dividends(code)
        div_list = [{'date': d['date'], 'amount': d['amount'],
                      'per_share': d['per_share']} for d in stock_divs]

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
    """Return all dividends with per_share calculation; optionally filtered by code.

    IMPORTANT: Uses record_date (股权登记日) instead of payment_date (派息日)
    for shares-before calculation. In China A-shares, dividend eligibility is
    determined by holdings on the record date, which is typically 2-5 trading
    days before the payment date in the broker statement.
    We subtract 2 calendar days from the payment date as a conservative
    approximation of the record date.
    """
    from datetime import datetime, timedelta
    db = get_db()
    if code:
        rows = db.execute("SELECT date, code, amount, price FROM dividends WHERE code=? ORDER BY date DESC", [code]).fetchall()
    else:
        rows = db.execute("SELECT date, code, amount, price FROM dividends ORDER BY date DESC").fetchall()
    result = []
    for r in rows:
        # Use record date (≈ payment_date - 2 days) for share counting
        # Broker statements record the payment date, not the record date.
        # Shares bought between record date and payment date do NOT qualify.
        try:
            pay_date = datetime.strptime(r['date'][:10], '%Y-%m-%d')
            record_date = (pay_date - timedelta(days=2)).strftime('%Y-%m-%d')
        except (ValueError, IndexError):
            record_date = r['date']
        shares = _shares_before_date(r['code'], record_date)
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
    """Batch monthly kline — one bar per month, dedup by year-month"""
    db = get_db()
    if codes is None:
        codes = get_watchlist_codes()
    km = {}
    for code in codes:
        rows = db.execute(
            "SELECT date, open, high, low, close, volume, change_pct FROM kline_monthly "
            "WHERE code=? "
            "GROUP BY substr(date,1,7) "
            "ORDER BY date DESC",
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
    """Persist news to SQLite with strict dedup.

    Uses INSERT OR IGNORE with unique index idx_news_unique(code, date, title)
    to silently skip duplicates. The `today` parameter is kept for backward
    compatibility but no longer performs bulk DELETE — dedup is handled at
    the DB constraint level.

    Includes content_status field: 'ok' | 'failed' | '' (empty=legacy/pending).
    """
    db = get_db()
    # Ensure content + news_id + content_status columns exist (migration)
    try:
        cols = [r[1] for r in db.execute("PRAGMA table_info(news)").fetchall()]
        if 'content' not in cols:
            db.execute("ALTER TABLE news ADD COLUMN content TEXT DEFAULT ''")
            print("  [MIGRATE] Added 'content' column to news table")
        if 'news_id' not in cols:
            db.execute("ALTER TABLE news ADD COLUMN news_id TEXT DEFAULT ''")
            print("  [MIGRATE] Added 'news_id' column to news table")
        if 'content_status' not in cols:
            db.execute("ALTER TABLE news ADD COLUMN content_status TEXT DEFAULT ''")
            print("  [MIGRATE] Added 'content_status' column to news table")
    except Exception:
        pass
    inserted = 0
    skipped = 0
    for n in news_list:
        try:
            db.execute(
                "INSERT OR IGNORE INTO news(date,code,title,summary,content,content_status,source,sentiment,major,url,news_id) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                [
                    n.get('date'), n.get('code'), n.get('title'),
                    n.get('summary', ''), n.get('content', ''),
                    n.get('content_status', ''),
                    n.get('source', '综合'),
                    n.get('sentiment', 'neutral'), 1 if n.get('major') else 0,
                    n.get('url', ''), n.get('news_id', ''),
                ]
            )
            if db.total_changes > 0:
                inserted += 1
            else:
                skipped += 1
        except Exception as e:
            pass
    db.commit()
    if inserted or skipped:
        print(f"  DB upsert: {inserted} inserted, {skipped} skipped (duplicate)")
    db.close()

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


def _estimate_dividends_from_kline(code: str) -> list:
    """Estimate dividend events from ex-dividend price gaps in daily K-line.

    When a stock goes ex-dividend (除权除息), the opening price typically gaps
    down by the dividend per share. Detects such gaps by comparing against the
    stock's own historical volatility to filter out normal price movements.

    Filters (in order of application):
      1. Gap range: -0.5% to -10% (dividend range, exclude crashes/splits)
      2. Per-share sanity: 0.01 ~ 5.0 元
      3. Statistical: gap > 2x 20-day avg absolute daily change (outlier)
      4. Recovery: next day close > ex-div open (gap not a trend start)
      5. Uniqueness: at most 1 gap per 30 days (yearly dividends)
    """
    from datetime import datetime

    db = get_db()
    db.row_factory = sqlite3.Row

    rows = db.execute(
        "SELECT date, open, close FROM kline_daily WHERE code=? ORDER BY date ASC",
        [code]
    ).fetchall()
    db.close()

    n = len(rows)
    if n < 30:
        return []

    # Pre-compute daily change% and 20-day avg absolute change
    daily_chg = []
    for i in range(1, n):
        pc = rows[i - 1]['close']
        to_ = rows[i]['open']
        if pc and pc > 0:
            daily_chg.append((to_ - pc) / pc * 100)
        else:
            daily_chg.append(0)

    # Rolling 20-day avg absolute change
    avg_abs_chg = []
    for i in range(len(daily_chg)):
        window = daily_chg[max(0, i - 20):i + 1]
        avg_abs_chg.append(sum(abs(v) for v in window) / len(window))

    estimated = []
    skip_last = 5

    for i in range(1, n - skip_last):
        prev_close = rows[i - 1]['close']
        today_open = rows[i]['open']
        today_date = rows[i]['date']

        if not prev_close or prev_close <= 0 or not today_open or today_open <= 0:
            continue

        gap_pct = (today_open - prev_close) / prev_close * 100

        # Filter 1: gap range
        if not (-10 < gap_pct < -0.5):
            continue

        # Filter 2: per-share sanity
        est_per_share = abs(gap_pct) / 100 * prev_close
        if not (0.01 <= est_per_share <= 5.0):
            continue

        # Filter 3: statistically significant vs own history
        avg_chg = avg_abs_chg[i - 1] if i > 0 else 0
        if abs(gap_pct) < max(avg_chg * 2, 0.8):
            continue

        # Filter 4: recovery check (next day should not continue falling)
        if i + 1 < n:
            next_close = rows[i + 1]['close']
            if next_close and next_close < today_open:
                continue

        # Filter 5: no other gap within 30 days
        if estimated:
            try:
                last_dt = datetime.strptime(estimated[-1]['date'], '%Y-%m-%d')
                this_dt = datetime.strptime(today_date, '%Y-%m-%d')
                if (this_dt - last_dt).days < 30:
                    continue
            except ValueError:
                pass

        estimated.append({
            'date': today_date,
            'per_share': round(est_per_share, 4),
            'amount': round(est_per_share, 2)
        })

    return estimated


def get_dividend_yield_series(code: str) -> dict:
    """Compute daily dividend yield time-series for a single stock.

    Uses EXACTLY the same TTM logic as calc_dividend_yield() in
    refresh_quotes.py to guarantee consistency between the position
    page dy value and the K-line trend chart.

    Falls back to estimating dividends from K-line ex-dividend gaps
    when no explicit dividend records exist.

    Returns:
        {
            "labels":       [date_str, ...],           # oldest-first
            "dy_series":    [dy_value_or_None, ...],
            "close_prices": [close_price, ...],
            "dividend_events": [{"date","per_share","amount"}, ...]
        }
    """
    from datetime import datetime, timedelta
    import sqlite3

    db = get_db()
    db.row_factory = sqlite3.Row

    # Load daily K-line (oldest-first for time-series alignment)
    kline_rows = db.execute(
        "SELECT date, close FROM kline_daily WHERE code=? ORDER BY date ASC",
        [code]
    ).fetchall()

    if not kline_rows:
        db.close()
        return {"labels": [], "dy_series": [], "close_prices": [],
                "dividend_events": []}

    labels = [r['date'] for r in kline_rows]
    closes = [r['close'] for r in kline_rows]

    # Load dividends with properly computed per_share (record_date offset in get_dividends)
    divs = get_dividends(code)

    # Build sorted dividend timeline (oldest-first)
    div_timeline = []
    for d in divs:
        if d['per_share'] > 0:
            div_timeline.append({
                'date': d['date'],
                'per_share': d['per_share'],
                'amount': d['amount']
            })
    div_timeline.sort(key=lambda x: x['date'])

    # If no dividend records, estimate from ex-dividend price gaps in K-line
    if not div_timeline:
        estimated = _estimate_dividends_from_kline(code)
        if estimated:
            div_timeline = estimated

    # Compute dy for each trading day (same formula as calc_dividend_yield)
    if not div_timeline:
        dy_series = [None] * len(labels)
    else:
        dy_series = []
        for date_str, close in zip(labels, closes):
            if not close or close <= 0:
                dy_series.append(None)
                continue

            # TTM window: date - 365 days (matching timedelta(days=365))
            try:
                dt = datetime.strptime(date_str, '%Y-%m-%d')
                cutoff = dt - timedelta(days=365)
                cutoff_str = cutoff.strftime('%Y-%m-%d')
            except (ValueError, TypeError):
                dy_series.append(None)
                continue

            # Sum per_share dividends within the TTM window
            ttm_sum = 0.0
            for div in div_timeline:
                if div['date'] > date_str:
                    break
                if div['date'] >= cutoff_str:
                    ttm_sum += div['per_share']

            if ttm_sum > 0:
                dy = round(ttm_sum / close * 100, 2)
                dy_series.append(dy)
            else:
                dy_series.append(None)

    # Build dividend events list from div_timeline (includes estimated)
    dividend_events = [
        {'date': d['date'], 'per_share': d['per_share'], 'amount': d['amount']}
        for d in div_timeline
    ]

    # Determine if dividends are estimated (from K-line gaps) vs real records
    real_divs = [d for d in divs if d['per_share'] > 0]
    is_estimated = not real_divs and bool(div_timeline)

    db.close()
    return {
        "labels": labels,
        "dy_series": dy_series,
        "close_prices": closes,
        "dividend_events": dividend_events,
        "estimated": is_estimated
    }
