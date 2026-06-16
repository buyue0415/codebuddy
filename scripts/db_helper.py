"""SQLite database helper for server.py API endpoints"""
import sqlite3, os
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(ROOT, 'data', 'stock.db')

def get_db():
    db = sqlite3.connect(DB_PATH, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=5000")
    # Ensure UNIQUE indexes for INSERT OR REPLACE (accumulate mode)
    db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_kd_code_date_u ON kline_daily(code, date)")
    db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_km_code_date_u ON kline_monthly(code, date)")
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


def get_quotes_by_date(date_str: str) -> dict:
    """Return quotes-like data for a specific historical date.
    
    For each watchlist stock, fetches daily K-line data for the given date:
      - price: close price of that day
      - change: close relative to previous trading day
      - open, high, low: from that day's K-line
      - volume: from that day's K-line
      - pe, pb: from kline_daily (0 if not available)
      - dy: calculated as TTM dividend yield using the date's close price
    
    Returns dict in same format as get_quotes(): {code: {...}}.
    """
    _ensure_kline_daily_schema()
    db = get_db()
    try:
        codes = [r['code'] for r in db.execute("SELECT code FROM watchlist").fetchall()]
        if not codes:
            return {}
        
        result = {}
        for code in codes:
            row = db.execute(
                "SELECT date, open, close, high, low, COALESCE(volume, 0) as volume, "
                "COALESCE(pe, 0) as pe, COALESCE(pb, 0) as pb, COALESCE(dy, 0) as dy "
                "FROM kline_daily WHERE code=? AND date=? LIMIT 1",
                [code, date_str]
            ).fetchone()
            if not row:
                continue
            
            # Previous day's close for change calculation
            prev = db.execute(
                "SELECT close FROM kline_daily WHERE code=? AND date<? "
                "ORDER BY date DESC LIMIT 1",
                [code, date_str]
            ).fetchone()
            
            price = row['close']
            prev_close = prev['close'] if prev else price
            change = round(price - prev_close, 2) if prev_close else 0
            
            # Calculate DY from TTM dividends at this date's price
            dy = _calc_dy_at_date(db, code, price, date_str)
            
            result[code] = {
                'price': price,
                'change': change,
                'open': row['open'],
                'high': row['high'],
                'low': row['low'],
                'volume': row['volume'],
                'pe': row['pe'],
                'pb': row['pb'],
                'dy': dy,
            }
        return result
    finally:
        db.close()

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
    return {r['code']: {'price': r['price'], 'change': r['change'], 'open': r['open'], 'high': r['high'], 'low': r['low'], 'volume': r['volume'] if 'volume' in r.keys() else 0, 'pe': r['pe'], 'pb': r['pb'], 'dy': r['dy']} for r in rows}


def get_quotes_batch(db, codes: list) -> dict:
    """Return quotes only for given codes using a single IN query. Reuses existing db connection."""
    codes = list(codes)  # ensure list (not set) for sqlite3 params
    if not codes:
        return {}
    placeholders = ','.join(['?' for _ in codes])
    rows = db.execute(
        f"SELECT * FROM quotes WHERE code IN ({placeholders})", codes
    ).fetchall()
    return {r['code']: {'price': r['price'], 'change': r['change'], 'open': r['open'],
                         'high': r['high'], 'low': r['low'], 'volume': r['volume'] if 'volume' in r.keys() else 0,
                         'pe': r['pe'], 'pb': r['pb'], 'dy': r['dy']}
            for r in rows}


def get_daily_predictions_batch(db, codes: list, date: str) -> dict:
    """Return today's predictions for given codes in a single query. Reuses existing db connection."""
    if not codes:
        return {}
    placeholders = ','.join(['?' for _ in codes])
    # Use ROW_NUMBER to get the latest prediction per code for the given date
    rows = db.execute(f"""
        SELECT id, date, code, direction, confidence, entry_zone,
               prev_close, high, low
        FROM daily_predictions
        WHERE code IN ({placeholders}) AND date = ?
        ORDER BY id DESC
    """, codes + [date]).fetchall()
    # Keep only first (latest) per code since ORDER BY id DESC
    result = {}
    for r in rows:
        code = r['code']
        if code not in result:
            result[code] = dict(r)
    return result

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

    DIVIDENDS DISPLAY POLICY:
      - 分红收入明细表格显示 source='statement' 的对账单实际到账数据
      - 不包括 web/kline_estimated/ttm_calculated 来源的分红记录
      - 这与前端表格标题"对账单实际到账数据"保持一致
    """
    import json
    db = get_db()
    config = get_config()

    # Build positions from DB — use get_dividends() for each stock
    # which correctly computes per_share via _shares_before_date()
    # Filter to only statement-source dividends for display
    open_pos = {}
    for r in db.execute("SELECT * FROM positions").fetchall():
        code = r['code']
        stock_divs = get_dividends(code)
        # Only statement-source dividends belong in the "分红收入明细" table
        # (matches the table header "对账单实际到账数据")
        div_list = [{'date': d['date'], 'amount': d['amount'],
                      'per_share': d['per_share']} for d in stock_divs
                    if d['source'] == 'statement']

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
    """Return closed positions with trades and fee totals.

    DIVIDENDS DISPLAY POLICY (same as current_positions):
      - dividends 数组只包含 source='statement' 的对账单实际到账数据
      - dividends_total 保留汇总值用于摘要显示
    """
    db = get_db()
    all_trades = get_trades()
    closed = {}
    for r in db.execute("SELECT * FROM closed_positions").fetchall():
        code = r['code']
        stock_trades = [t for t in all_trades if t['code'] == code]
        total_comm = sum(t['commission'] for t in stock_trades)
        total_stamp = sum(t['stamp_tax'] for t in stock_trades)
        total_other = sum(t['transfer_fee'] + t['regulatory_fee'] + t['handling_fee'] for t in stock_trades)
        # Get statement-source dividends for this stock
        stock_divs = get_dividends(code)
        div_list = [{'date': d['date'], 'amount': d['amount'],
                      'per_share': d['per_share']} for d in stock_divs
                    if d['source'] == 'statement']
        closed[code] = {
            'code': code, 'name': r['name'],
            'realized_pnl': r['realized_pnl'], 'dividends_total': r['dividends_total'],
            'total_commission': total_comm or r['total_commission'],
            'total_stamp_tax': total_stamp or r['total_stamp_tax'],
            'total_other_fees': total_other or r['total_other_fees'],
            'trades': stock_trades,
            'dividends': div_list,
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

def _ensure_dividends_schema():
    """Migrate dividends table if ex_date/source columns or unique index missing."""
    db = get_db()
    try:
        cols = [r[1] for r in db.execute("PRAGMA table_info(dividends)").fetchall()]
        if 'ex_date' not in cols:
            db.execute("ALTER TABLE dividends ADD COLUMN ex_date TEXT")
            db.execute("UPDATE dividends SET ex_date = date(date, '-3 days') WHERE ex_date IS NULL")
            print("  [MIGRATE] Added 'ex_date' column to dividends table, backfilled")
        if 'source' not in cols:
            db.execute("ALTER TABLE dividends ADD COLUMN source TEXT DEFAULT 'statement'")
            db.execute("UPDATE dividends SET source='statement' WHERE source IS NULL")
            print("  [MIGRATE] Added 'source' column to dividends table, backfilled")
        if 'fiscal_year' not in cols:
            db.execute("ALTER TABLE dividends ADD COLUMN fiscal_year INTEGER")
            # Backfill: fiscal_year = year of ex_date, adjusted for Q1 dividends
            db.execute(
                "UPDATE dividends SET fiscal_year = "
                "CASE WHEN CAST(strftime('%m', COALESCE(ex_date, date(date, '-3 days'))) AS INTEGER) <= 4 "
                "THEN CAST(strftime('%Y', COALESCE(ex_date, date(date, '-3 days'))) AS INTEGER) - 1 "
                "ELSE CAST(strftime('%Y', COALESCE(ex_date, date(date, '-3 days'))) AS INTEGER) END "
                "WHERE fiscal_year IS NULL"
            )
            print("  [MIGRATE] Added 'fiscal_year' column to dividends table, backfilled")
        if 'dividend_type' not in cols:
            db.execute("ALTER TABLE dividends ADD COLUMN dividend_type TEXT DEFAULT 'regular'")
            print("  [MIGRATE] Added 'dividend_type' column to dividends table")
        # Create unique index to prevent duplicate dividends
        db.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_div_unique ON dividends(code, date, amount)"
        )
    except Exception as e:
        print(f"  [MIGRATE] dividends schema check: {e}")
    finally:
        db.commit()
        db.close()


def sync_dividends_from_trades():
    """从 trades 表中提取 type='股息入账' 的记录，同步到 dividends 表。

    这解决了长江电力（600900）等已清仓股票的分红数据缺失问题：
      - trades 表中有股息入账记录（settlement=实际到账金额）
      - 但这些记录未写入 dividends 表，导致"分红收入明细"中看不到
      - 本函数自动将股息入账同步为 source='statement' 的分红记录

    同步规则：
      - 从 trades 表筛选 type='股息入账' 且 code 不为空
      - 存入 dividends 表：date=派息日, amount=settlement(到账金额),
        price=stock price at time(股息入账时的股价，用于参考),
        source='statement', ex_date=date-3天
      - 使用 INSERT OR IGNORE 避免重复（依赖 UNIQUE 索引）
    """
    db = get_db()
    db.execute("PRAGMA journal_mode=WAL")
    _ensure_dividends_schema()

    # Find dividend income records in trades table
    div_trades = db.execute(
        "SELECT date, code, name, price, settlement FROM trades "
        "WHERE type='股息入账' AND code IS NOT NULL AND code != '' AND settlement > 0"
    ).fetchall()

    if not div_trades:
        db.close()
        print("  [SYNC] No dividend trades found in trades table")
        return 0

    count = 0
    for t in div_trades:
        code = t['code']
        pay_date = t['date']
        amount = float(t['settlement'])  # 实际到账金额
        stock_price = float(t['price']) if t['price'] else None  # 股息入账时股价

        # ex_date = pay_date - 3 days (standard A-share convention)
        try:
            ex_dt = datetime.strptime(pay_date[:10], '%Y-%m-%d')
            ex_date = (ex_dt - timedelta(days=3)).strftime('%Y-%m-%d')
        except (ValueError, TypeError):
            ex_date = pay_date

        # Infer fiscal year from pay_date
        try:
            pay_dt = datetime.strptime(pay_date[:10], '%Y-%m-%d')
            fiscal_year = pay_dt.year - 1 if pay_dt.month <= 4 else pay_dt.year
        except (ValueError, TypeError):
            fiscal_year = 0

        try:
            db.execute(
                "INSERT OR IGNORE INTO dividends(code, date, amount, price, ex_date, source, "
                "fiscal_year, dividend_type) VALUES (?, ?, ?, ?, ?, 'statement', ?, 'regular')",
                [code, pay_date, amount, stock_price, ex_date, fiscal_year]
            )
            if db.total_changes > 0:
                count += 1
        except Exception as e:
            print(f"  [SYNC] {code} {pay_date} 写入失败: {e}")

    db.commit()
    db.close()
    print(f"  [SYNC] Synced {count} dividend records from trades table")
    return count


def _calc_dy_at_date(db, code: str, price: float, date_str: str) -> float:
    """Calculate TTM dividend yield for a stock at a specific historical date.
    
    Looks back 365 days from the given date, summing per_share dividends
    within that window, then divides by the historical close price.
    Uses ex_date (除权日) for TTM window filtering.
    Returns percentage value (e.g. 5.23 means 5.23%).
    """
    from datetime import datetime, timedelta

    if not price or price <= 0:
        return 0.0

    try:
        cutoff = datetime.strptime(date_str[:10], '%Y-%m-%d') - timedelta(days=365)
        cutoff_str = cutoff.strftime('%Y-%m-%d')
    except (ValueError, TypeError):
        return 0.0

    div_rows = db.execute(
        "SELECT date, amount, price, source, "
        "COALESCE(ex_date, date(date, '-3 days')) as ex_date "
        "FROM dividends WHERE code=? AND "
        "COALESCE(ex_date, date(date, '-3 days')) >= ? AND "
        "COALESCE(ex_date, date(date, '-3 days')) < ? "
        "ORDER BY date DESC",
        [code, cutoff_str, date_str]
    ).fetchall()

    total_per_share = 0.0
    dedup_dates = set()
    for r in div_rows:
        source = r['source'] if r['source'] else 'statement'
        amount = float(r['amount']) if r['amount'] else 0.0
        div_price = float(r['price']) if r['price'] else None
        ex_date = r['ex_date'] if r['ex_date'] else r['date']
        ps = _get_dividend_per_share(code, r['date'], amount, div_price, source)
        if ps <= 0:
            continue
        # Dedup: same dividend event within 5 days
        ex_norm = ex_date[:7]
        if ex_norm in dedup_dates:
            # Use the first encountered (highest priority per TTm mode)
            continue
        dedup_dates.add(ex_norm)
        total_per_share += ps

    # Cap total_per_share
    MAX_TTM_PER_SHARE = 10.0
    if total_per_share > MAX_TTM_PER_SHARE:
        total_per_share = MAX_TTM_PER_SHARE

    if total_per_share <= 0:
        return 0.0

    return round(total_per_share / price * 100, 2)


def _get_dividend_per_share(code: str, pay_date: str, amount: float,
                            price: float, source: str) -> float:
    """Unified per-share dividend calculator handling all source types correctly.

    Source semantics:
      - 'statement': amount = total cash actually received by user.
        per_share = amount / shares_held_before_record_date
      - 'web': amount = total payout scaled (e.g., per_10_shares * 1000).
        price = actual per-share dividend. Use price directly.
      - 'ttm_calculated' / 'kline_estimated': amount = per_share already.
        Use amount directly.
      - '_estimated' (dict flag): amount IS per_share (K-line gap estimate).

    Validation:
      - Per-share cap at 5.0 yuan (sanity max for A-shares)
      - Skip if amount <= 0
      - Skip if computed per_share <= 0 or > 5.0
    """
    from datetime import datetime

    if amount <= 0:
        return 0.0

    try:
        if source in ('web', 'kline_estimated', 'ttm_calculated'):
            # price column stores actual per-share dividend
            if price is not None and float(price) > 0:
                per_share = float(price)
            else:
                # Fallback: amount may be per_share directly
                per_share = float(amount)
        elif source == 'statement':
            # amount = total cash received, compute per_share from holdings
            per_share = _compute_per_share(code, pay_date, amount)
        else:
            # Unknown source: treat as statement (safest)
            per_share = _compute_per_share(code, pay_date, amount)
    except (ValueError, TypeError):
        return 0.0

    # Sanity cap: per-share dividend > 5 元 is virtually impossible in A-shares
    MAX_PER_SHARE = 5.0
    if per_share <= 0 or per_share > MAX_PER_SHARE:
        return 0.0

    return round(per_share, 4)


def _deduplicate_dividend_events(div_list: list, ttm_mode: bool = False) -> list:
    """Deduplicate dividend entries representing the same dividend event.

    When the same dividend event exists from multiple sources (e.g., a web
    entry from East Money API and a statement entry from broker import), keep
    only the best-quality entry.

    Dedup window: entries with ex_date within 5 days of each other are
    considered the same event.

    Source priority (depends on mode):
      Normal mode (ttm_mode=False):
        1. 'statement' — actual cash received by user, most reliable for display
        2. 'web' — public API data
        3. 'ttm_calculated' / 'kline_estimated' — estimated
      TTM mode (ttm_mode=True):
        1. 'web' — publicly verified per-share rate, NOT affected by
           record_date estimation errors or individual share count
        2. 'statement' — computed per_share depends on record_date accuracy,
           which may be off by 1-2 days causing wrong share count
        3. 'ttm_calculated' / 'kline_estimated' — estimated from K-line gaps

    Returns deduplicated list sorted by ex_date ascending.
    """
    if len(div_list) <= 1:
        return div_list

    if ttm_mode:
        # TTM: prefer web for accurate per-share dividend rate
        SOURCE_PRIORITY = {'web': 0, 'statement': 1,
                           'ttm_calculated': 2, 'kline_estimated': 3}
    else:
        SOURCE_PRIORITY = {'statement': 0, 'web': 1,
                           'ttm_calculated': 2, 'kline_estimated': 3}

    # Sort by ex_date
    sorted_divs = sorted(div_list, key=lambda x: x.get('ex_date', x.get('date', '')))

    merged = []
    current_group = [sorted_divs[0]]

    for div in sorted_divs[1:]:
        prev = current_group[-1]
        # If ex_date within 5 days of previous, same group
        if abs(_date_diff_days(prev.get('ex_date', prev.get('date')),
                               div.get('ex_date', div.get('date')))) <= 5:
            current_group.append(div)
        else:
            # Pick best from current group
            merged.append(_pick_best_source(current_group, SOURCE_PRIORITY))
            current_group = [div]

    # Last group
    if current_group:
        merged.append(_pick_best_source(current_group, SOURCE_PRIORITY))

    return merged


def _date_diff_days(d1: str, d2: str) -> int:
    """Calculate absolute difference in days between two date strings."""
    from datetime import datetime
    try:
        dt1 = datetime.strptime(d1[:10], '%Y-%m-%d')
        dt2 = datetime.strptime(d2[:10], '%Y-%m-%d')
        return abs((dt1 - dt2).days)
    except (ValueError, TypeError):
        return 999  # Can't parse → treat as different events


def _pick_best_source(group: list, priority: dict) -> dict:
    """From a group of duplicate entries, pick the one with highest-quality source."""
    return min(group, key=lambda x: priority.get(x.get('source', ''), 99))


def _identify_fiscal_year(ex_date_str: str) -> int:
    """Infer fiscal year from ex-dividend date.

    Chinese A-share convention:
      - Most annual dividends ex-date in May-September → fiscal year = year - 1
        (e.g., 2024 annual dividend with ex_date 2025-07-01 → fiscal_year=2024)
      - Q1 dividends (rare) may ex-date in Jan-April → fiscal year = year - 1
      - Edge case: ex_date before April could be current fiscal year's
        preliminary dividend
    """
    from datetime import datetime
    try:
        dt = datetime.strptime(ex_date_str[:10], '%Y-%m-%d')
        if dt.month <= 4:
            return dt.year - 1
        else:
            return dt.year
    except (ValueError, TypeError):
        return 0


def _clean_dividends_data():
    """One-time data cleaning: deduplicate and normalize dividends table.

    Performs:
      1. Runs schema migration to ensure all columns exist
      2. Identifies and removes duplicate entries (same event from multiple sources)
      3. Backfills fiscal_year for entries where it's NULL
      4. Marks suspicious entries (per_share > 5.0) for review

    This should be called after each divider import or schema change.
    """
    _ensure_dividends_schema()

    db = get_db()
    db.row_factory = sqlite3.Row

    # 1. Backfill fiscal_year
    db.execute(
        "UPDATE dividends SET fiscal_year = "
        "CASE WHEN CAST(strftime('%m', COALESCE(ex_date, date(date, '-3 days'))) AS INTEGER) <= 4 "
        "THEN CAST(strftime('%Y', COALESCE(ex_date, date(date, '-3 days'))) AS INTEGER) - 1 "
        "ELSE CAST(strftime('%Y', COALESCE(ex_date, date(date, '-3 days'))) AS INTEGER) END "
        "WHERE fiscal_year IS NULL"
    )

    # 2. Validate per_share sanity for non-statement sources
    #    Statement sources need shares_held to validate
    suspicious = db.execute(
        "SELECT rowid, code, date, amount, price, source FROM dividends "
        "WHERE source IN ('web', 'kline_estimated', 'ttm_calculated') "
        "AND (price IS NULL OR CAST(price AS REAL) <= 0 OR CAST(price AS REAL) > 5.0)"
    ).fetchall()
    if suspicious:
        print(f"  [CLEAN] Found {len(suspicious)} suspicious dividend entries "
              f"(per_share out of range 0.01-5.0)")
        for s in suspicious:
            print(f"    {s['code']} {s['date']} amount={s['amount']} price={s['price']}")

    db.commit()
    db.close()
    print("  [CLEAN] Dividends data cleanup complete")


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

def _compute_per_share(code, pay_date, amount):
    """Compute per-share dividend based on holdings at record date (股权登记日).

    Unified function used by both get_dividends() (general queries) and
    calc_dividend_yield() (position page / refresh). Eliminates the previous
    inconsistency where both functions computed per_share independently.

    Algorithm:
      1. record_date ≈ pay_date - 2 days (conservative estimate matching original
         behavior; 2 calendar days ≈ typical gap between record date and payment
         date in broker statements)
      2. shares = holdings before record_date (strict <, excludes record-date buys)
      3. per_share = amount / shares if shares > 0 else 0

    Note: This uses a conservative -2 calendar day estimate for record_date
    (matching original behavior). For TTM window filtering, the separate ex_date
    field (set to pay_date - 3) is used instead, providing better alignment with
    actual stock price adjustments.
    """
    from datetime import datetime, timedelta
    try:
        pay_dt = datetime.strptime(pay_date[:10], '%Y-%m-%d')
    except (ValueError, IndexError, TypeError):
        return 0.0
    record_dt = pay_dt - timedelta(days=2)
    record_str = record_dt.strftime('%Y-%m-%d')
    shares = _shares_before_date(code, record_str)
    return round(amount / shares, 4) if shares > 0 else 0.0

def get_dividends(code=None):
    """Return all dividends with per_share calculation; optionally filtered by code.

    Uses _compute_per_share() unified function: record_date = pay_date - 4 days
    (3 days to ex-date + 1 day to record date), shares counted before record_date.

    Returns fields: date, code, amount, price, per_share, ex_date, source
    - source='statement' → 对账单实际到账数据
    - source='web' → 网络公开数据（东方财富API）
    - source='ttm_calculated' → TTM公式推算（K线除权缺口反推）
    - per_share → 每股分红（公式计算值 = 到账金额 ÷ 持仓股数）
    """
    _ensure_dividends_schema()
    db = get_db()
    if code:
        rows = db.execute(
            "SELECT date, code, amount, price, COALESCE(ex_date, date(date, '-3 days')) as ex_date, "
            "COALESCE(source, 'statement') as source "
            "FROM dividends WHERE code=? ORDER BY date DESC", [code]
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT date, code, amount, price, COALESCE(ex_date, date(date, '-3 days')) as ex_date, "
            "COALESCE(source, 'statement') as source "
            "FROM dividends ORDER BY date DESC"
        ).fetchall()
    result = []
    for r in rows:
        # 严格来源判定：NULL/空 → 标记为 unknown，不算 statement
        raw_source = r['source']
        if raw_source is None or raw_source == '':
            source = 'unknown'
        else:
            source = raw_source
        
        if source in ('web', 'kline_estimated', 'ttm_calculated'):
            # Web/K线预估来源: price 字段直接存储每股分红（per_share）
            per_share = float(r['price']) if r['price'] else 0.0
        elif source == 'statement':
            # 对账单来源: amount / shares_before_date 计算每股分红
            per_share = _compute_per_share(r['code'], r['date'], r['amount'])
        else:
            # unknown 来源：不参与 display，跳过 per_share 计算
            per_share = 0.0
        result.append({
            'date': r['date'],
            'code': r['code'],
            'amount': r['amount'],
            'price': r['price'],
            'per_share': per_share,
            'ex_date': r['ex_date'],
            'source': source,
            'fiscal_year': r['fiscal_year'] if 'fiscal_year' in r.keys() else None,
            'dividend_type': r['dividend_type'] if 'dividend_type' in r.keys() else 'regular',
        })
    db.close()
    return result


def get_statement_dividends(code=None):
    """Return ONLY statement-source dividends (broker import data).
    
    用于分红收入明细表格 —— 仅对账单实际到账数据，不包含网络抓取/估算数据。
    """
    all_divs = get_dividends(code)
    return [d for d in all_divs if d['source'] == 'statement']


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
        rows = db.execute("SELECT date, change_pct FROM kline_monthly WHERE code=? ORDER BY date ASC", [code]).fetchall()
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

def _ensure_kline_daily_schema():
    """Migrate kline_daily table if volume/pe/pb/dy columns missing."""
    db = get_db()
    try:
        cols = [r[1] for r in db.execute("PRAGMA table_info(kline_daily)").fetchall()]
        if 'volume' not in cols:
            db.execute("ALTER TABLE kline_daily ADD COLUMN volume REAL DEFAULT 0")
            print("  [MIGRATE] Added 'volume' column to kline_daily table")
        if 'pe' not in cols:
            db.execute("ALTER TABLE kline_daily ADD COLUMN pe REAL DEFAULT 0")
            print("  [MIGRATE] Added 'pe' column to kline_daily table")
        if 'pb' not in cols:
            db.execute("ALTER TABLE kline_daily ADD COLUMN pb REAL DEFAULT 0")
            print("  [MIGRATE] Added 'pb' column to kline_daily table")
        if 'dy' not in cols:
            db.execute("ALTER TABLE kline_daily ADD COLUMN dy REAL DEFAULT 0")
            print("  [MIGRATE] Added 'dy' column to kline_daily table")
        db.commit()
    except Exception as e:
        print(f"  [MIGRATE] kline_daily schema check: {e}")
    finally:
        db.close()

def upsert_kline_daily(code, bars):
    """Accumulate daily kline — INSERT OR REPLACE prevents duplicates by (code, date).
    bars format: [date, open, close, high, low, volume, pe?, pb?, dy?]
    pe/pb/dy are stored if available (len >= 9)."""
    _ensure_kline_daily_schema()
    db = get_db()
    cols = "code,date,open,close,high,low,volume"
    placeholders = "?,?,?,?,?,?,?"
    params = []
    for b in bars:
        p = [code, b[0], b[1], b[2], b[3], b[4], b[5] if len(b) >= 6 else 0]
        if len(b) >= 9:
            # Full data with pe/pb/dy
            cols = "code,date,open,close,high,low,volume,pe,pb,dy"
            placeholders = "?,?,?,?,?,?,?,?,?,?"
            p += [b[6], b[7], b[8]]
        params.append(p)
    db.executemany(
        f"INSERT OR REPLACE INTO kline_daily({cols}) VALUES({placeholders})",
        params
    )
    db.commit(); db.close()

def upsert_kline_monthly(code, bars):
    """Accumulate monthly kline — INSERT OR REPLACE prevents duplicates by (code, date)."""
    db = get_db()
    db.executemany("INSERT OR REPLACE INTO kline_monthly(code,date,open,high,low,close,volume,change_pct) VALUES(?,?,?,?,?,?,?,?)",
        [[code, b[0], b[1], b[2], b[3], b[4], b[5] if len(b)>5 else 0, b[6] if len(b)>6 else 0] for b in bars])
    db.commit(); db.close()

def upsert_quotes(quotes_dict):
    _ensure_quotes_schema()
    db = get_db()
    for code, q in quotes_dict.items():
        db.execute("INSERT OR REPLACE INTO quotes(code,price,change,open,high,low,volume,pe,pb,dy) VALUES(?,?,?,?,?,?,?,?,?,?)",
            [code, q.get('price'), q.get('change'), q.get('open'), q.get('high'), q.get('low'), q.get('volume', 0), q.get('pe'), q.get('pb'), q.get('dy')])
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
    """Clear predictions for >=date (today and future), preserving only past backfilled data."""
    db = get_db()
    db.execute("DELETE FROM prediction_signals WHERE pred_id IN (SELECT id FROM daily_predictions WHERE date>=?)", [date])
    db.execute("DELETE FROM prediction_hourly WHERE pred_id IN (SELECT id FROM daily_predictions WHERE date>=?)", [date])
    db.execute("DELETE FROM daily_predictions WHERE date>=?", [date])
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

def _ensure_quotes_schema():
    """Migrate quotes table if volume column missing."""
    db = get_db()
    try:
        cols = [r[1] for r in db.execute("PRAGMA table_info(quotes)").fetchall()]
        if 'volume' not in cols:
            db.execute("ALTER TABLE quotes ADD COLUMN volume INTEGER DEFAULT 0")
            print("  [MIGRATE] Added 'volume' column to quotes table")
        db.commit()
    except Exception as e:
        print(f"  [MIGRATE] quotes schema check: {e}")
    finally:
        db.close()

def upsert_positions(current_positions, closed_positions, all_trades):
    """Persist positions/trades/dividends from statement parsing.

    Uses INSERT OR REPLACE with UNIQUE constraint on dividends(code,date,amount)
    to prevent duplicate dividend entries. Wrapped in a transaction to ensure
    atomicity — if the process crashes between DELETE and INSERT, the partial
    changes are rolled back.
    """
    from datetime import datetime, timedelta
    db = get_db()
    try:
        db.execute("BEGIN TRANSACTION")
        db.execute("DELETE FROM positions"); db.execute("DELETE FROM closed_positions")
        db.execute("DELETE FROM trades"); db.execute("DELETE FROM dividends")
        for code, p in current_positions.items():
            db.execute("INSERT INTO positions(code,name,qty,total_cost,avg_cost,realized_pnl) VALUES(?,?,?,?,?,?)",
                [code, p['name'], p['qty'], p['total_cost'], p.get('avg_cost',0), p.get('realized_pnl',0)])
            for d in p.get('dividends', []):
                pay_date = d['date']
                ex_date = (datetime.strptime(pay_date[:10], '%Y-%m-%d') - timedelta(days=3)).strftime('%Y-%m-%d')
                db.execute("INSERT OR REPLACE INTO dividends(code,date,amount,price,ex_date,source) VALUES(?,?,?,?,?,?)",
                    [code, pay_date, d['amount'], d['price'], ex_date, 'statement'])
        for code, p in closed_positions.items():
            db.execute("INSERT INTO closed_positions(code,name,realized_pnl,dividends_total,total_commission,total_stamp_tax,total_other_fees) VALUES(?,?,?,?,?,?,?)",
                [code, p['name'], p.get('realized_pnl',0), p.get('dividends_total',0), p.get('total_commission',0), p.get('total_stamp_tax',0), p.get('total_other_fees',0)])
        for t in all_trades:
            db.execute("INSERT INTO trades(date,time,code,name,type,qty,price,commission,stamp_tax,settlement) VALUES(?,?,?,?,?,?,?,?,?,?)",
                [t['date'], t.get('time',''), t['code'], t['name'], t['type'], int(t['qty']), t['price'], t.get('commission',0), t.get('stamp_tax',0), t['settlement']])
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


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
    """Compute daily dividend yield time-series for a single stock (公式计算值 · TTM推算).

    Uses the same TTM logic as calc_dividend_yield() for consistency:
    - Rolling 365-day window anchored at each trading day (not latest ex_date)
    - ex_date used for TTM window filtering (not payment date)
    - Deduplication by (code, date, amount)

    Falls back to estimating dividends from K-line ex-dividend gaps
    when no explicit dividend records exist.

    Returns:
        {
            "labels":            [date_str, ...],           # oldest-first
            "dy_series":         [dy_value_or_None, ...],
            "close_prices":      [close_price, ...],
            "dividend_events":   [{"date","per_share","amount","ex_date","source"}, ...],
            "estimated":         bool,
            "source":            "ttm_calculated"           # 公式计算值标识
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
                "dividend_events": [], "estimated": False, "source": "ttm_calculated"}

    labels = [r['date'] for r in kline_rows]
    closes = [r['close'] for r in kline_rows]

    # Load dividends — use the SAME per_share computation as calc_dividend_yield()
    # (via _get_dividend_per_share) for consistency between chart and position table.
    # Previously used get_dividends(code) which lacked the 5.0-per-share cap
    # and had different web-source fallback logic, causing chart-vs-table mismatch
    # and potentially unreasonably high TTM sums from uncapped statement dividends.
    div_rows = db.execute(
        "SELECT date, amount, price, source, "
        "COALESCE(ex_date, date(date, '-3 days')) as ex_date "
        "FROM dividends WHERE code=? ORDER BY date ASC",
        [code]
    ).fetchall()

    raw_events = []
    for r in div_rows:
        source = r['source'] if r['source'] else 'statement'
        amount = float(r['amount']) if r['amount'] else 0.0
        price = float(r['price']) if r['price'] else None
        ex_date = r['ex_date'] if r['ex_date'] else r['date']

        # Unified per_share calculation — same as calc_dividend_yield() in refresh_quotes.py
        ps = _get_dividend_per_share(code, r['date'], amount, price, source)
        if ps <= 0:
            continue
        raw_events.append({
            'date': r['date'],
            'ex_date': ex_date,
            'per_share': ps,
            'amount': amount,
            'source': source,
        })

    # Deduplicate by ex_date window (5 days) — same as calc_dividend_yield()
    div_timeline = _deduplicate_dividend_events(raw_events, ttm_mode=True)
    div_timeline.sort(key=lambda x: x['ex_date'])

    # If no dividend records, estimate from ex-dividend price gaps in K-line
    is_estimated = False
    if not div_timeline:
        estimated = _estimate_dividends_from_kline(code)
        if estimated:
            div_timeline = [{
                'date': e['date'], 'ex_date': e['date'],
                'per_share': e['per_share'], 'amount': e['amount'],
                'source': 'ttm_calculated',
            } for e in estimated]

    # Compute dy for each trading day
    if not div_timeline:
        dy_series = [None] * len(labels)
    else:
        dy_series = []
        for date_str, close in zip(labels, closes):
            if not close or close <= 0:
                dy_series.append(None)
                continue

            try:
                dt = datetime.strptime(date_str, '%Y-%m-%d')
            except (ValueError, TypeError):
                dy_series.append(None)
                continue

            # TTM dividend yield: rolling 365-day window, but avoid double-counting
            # annual dividends that fall ~365 days apart (e.g., 2023-07-21 and
            # 2024-07-19, only 364 days apart). Strategy:
            #   - If max gap between dividends in window > 340 days
            #     → annual payer → use only the most recent per_share
            #   - Otherwise (quarterly/semi-annual, gaps < 180 days)
            #     → sum all per_share values
            cutoff = dt - timedelta(days=365)
            cutoff_str = cutoff.strftime('%Y-%m-%d')

            # Gather qualifying dividends within 365-day window.
            # Exclude dividend on the EX-DATE itself: the price has already
            # dropped but the new dividend should not be counted until the
            # next trading day. This prevents artificial spikes when a new
            # dividend enters the TTM window.
            qualifying = []
            for div in div_timeline:
                div_ex = div.get('ex_date', div['date'])
                if div_ex >= date_str:
                    break  # exclude current & future ex-dates
                if div_ex >= cutoff_str:
                    qualifying.append(div)

            if qualifying:
                dates = [q.get('ex_date', q['date']) for q in qualifying]
                dates.sort()
                span = _date_diff_days(dates[0], dates[-1]) if dates else 0

                if span >= 350:
                    # Annual payer with overlapping window: only latest dividend
                    ttm_sum = float(qualifying[-1]['per_share'])
                else:
                    # Quarterly/semi-annual payer: sum all dividends in window
                    ttm_sum = sum(float(q['per_share']) for q in qualifying)
            else:
                ttm_sum = 0.0


            if ttm_sum > 0:
                dy = round(ttm_sum / close * 100, 2)
                dy_series.append(dy)
            else:
                dy_series.append(None)

    # Build dividend events list with source field
    dividend_events = [
        {
            'date': d['date'],
            'ex_date': d.get('ex_date', d['date']),
            'per_share': d['per_share'],
            'amount': d['amount'],
            'source': d.get('source', 'statement'),
        }
        for d in div_timeline
    ]

    db.close()
    return {
        "labels": labels,
        "dy_series": dy_series,
        "close_prices": closes,
        "dividend_events": dividend_events,
        "estimated": is_estimated,
        "source": "ttm_calculated",
    }


# ── Batch Operations ───────────────────────────────────────────────────

def insert_daily_predictions_batch(predictions: list) -> int:
    """Insert multiple daily predictions in a single transaction (executemany).
    
    Args:
        predictions: list of dicts with keys: code, date, prev_close,
                     next_day (dict with direction,confidence,high,low,advice,entry_zone),
                     hourly (list), signals (dict)
    Returns:
        int: number of rows inserted
    """
    if not predictions:
        return 0
    db = get_db()
    count = 0
    try:
        for pred in predictions:
            nd = pred.get('next_day', {})
            db.execute(
                "INSERT OR REPLACE INTO daily_predictions "
                "(code, date, prev_close, direction, confidence, high, low, advice, entry_zone) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    pred['code'], pred['date'], pred['prev_close'],
                    nd.get('direction'), nd.get('confidence'),
                    nd.get('high'), nd.get('low'),
                    nd.get('advice'), nd.get('entry_zone'),
                ]
            )
            pred_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
            # Insert hourly predictions
            for h in pred.get('hourly', []):
                db.execute(
                    "INSERT OR REPLACE INTO prediction_hourly "
                    "(pred_id, block, pred_open, pred_high, pred_low, pred_close, direction, strength, note) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    [pred_id, h.get('block'), h.get('pred_open'), h.get('pred_high'),
                     h.get('pred_low'), h.get('pred_close'), h.get('direction'),
                     h.get('strength'), h.get('note')]
                )
            # Insert signal snapshot
            sig = pred.get('signals', {})
            for sn, sv in sig.items():
                if isinstance(sv, dict):
                    db.execute(
                        "INSERT OR REPLACE INTO prediction_signals "
                        "(pred_id, name, value, direction, raw_value) "
                        "VALUES (?, ?, ?, ?, ?)",
                        [pred_id, sn, str(sv.get('value', '')),
                         sv.get('direction'), sv.get('raw')]
                    )
            count += 1
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    return count


def insert_paper_trades_batch(trades: list) -> int:
    """Insert multiple paper trades in a single transaction."""
    if not trades:
        return 0
    db = get_db()
    count = 0
    try:
        for t in trades:
            db.execute(
                "INSERT INTO paper_trades "
                "(date, code, direction, qty, price, commission, stamp_tax, settlement, source, suggestion_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [t['date'], t['code'], t['direction'], t['qty'], t['price'],
                 t.get('commission', 0), t.get('stamp_tax', 0),
                 t['settlement'], t.get('source', 'auto_suggestion'),
                 t.get('suggestion_id')]
            )
            count += 1
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    return count


# ── Schema Init & Paper Trading Queries ────────────────────────────────

def init_backtest_tables():
    """Initialize backtest/paper-trading tables. Idempotent."""
    db = get_db()
    try:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS paper_account (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cash REAL NOT NULL DEFAULT 100000.0,
                initial_capital REAL NOT NULL DEFAULT 100000.0,
                created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
            );
            CREATE TABLE IF NOT EXISTS paper_positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT NOT NULL UNIQUE,
                qty INTEGER NOT NULL DEFAULT 0, avg_cost REAL NOT NULL DEFAULT 0.0,
                last_price REAL DEFAULT 0.0, market_value REAL DEFAULT 0.0,
                unrealized_pnl REAL DEFAULT 0.0, unrealized_pnl_pct REAL DEFAULT 0.0,
                updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (code) REFERENCES stocks(code)
            );
            CREATE INDEX IF NOT EXISTS idx_pp_code ON paper_positions(code);
            CREATE TABLE IF NOT EXISTS paper_trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT NOT NULL, code TEXT NOT NULL,
                direction TEXT NOT NULL CHECK(direction IN ('buy','sell')),
                qty INTEGER NOT NULL, price REAL NOT NULL,
                commission REAL DEFAULT 0.0, stamp_tax REAL DEFAULT 0.0,
                settlement REAL NOT NULL, source TEXT DEFAULT 'auto_suggestion',
                suggestion_id INTEGER DEFAULT NULL, realized_pnl REAL DEFAULT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (code) REFERENCES stocks(code)
            );
            CREATE INDEX IF NOT EXISTS idx_pt_date ON paper_trades(date);
            CREATE INDEX IF NOT EXISTS idx_pt_code ON paper_trades(code);
            CREATE INDEX IF NOT EXISTS idx_pt_code_date ON paper_trades(code, date);
            CREATE TABLE IF NOT EXISTS paper_daily_snapshot (
                id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT NOT NULL UNIQUE,
                total_asset REAL NOT NULL, cash REAL NOT NULL, position_value REAL NOT NULL,
                daily_pnl REAL DEFAULT 0.0, daily_pnl_pct REAL DEFAULT 0.0,
                cumulative_return_pct REAL DEFAULT 0.0, note TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
            );
            CREATE INDEX IF NOT EXISTS idx_pds_date ON paper_daily_snapshot(date);
            CREATE TABLE IF NOT EXISTS backtest_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT, started_at TEXT NOT NULL,
                finished_at TEXT, status TEXT NOT NULL DEFAULT 'running'
                CHECK(status IN ('running','done','error')),
                train_window INTEGER NOT NULL DEFAULT 252, test_window INTEGER NOT NULL DEFAULT 21,
                stock_codes TEXT, total_stocks INTEGER DEFAULT 0,
                completed_stocks INTEGER DEFAULT 0, current_stock TEXT,
                summary_json TEXT, error_msg TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_br_status ON backtest_runs(status);
            CREATE TABLE IF NOT EXISTS paper_suggestions (
                id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT NOT NULL, code TEXT NOT NULL,
                action TEXT NOT NULL CHECK(action IN ('buy','sell','hold','watch')),
                qty INTEGER NOT NULL DEFAULT 0, price REAL NOT NULL DEFAULT 0.0,
                confidence REAL NOT NULL DEFAULT 0.0, direction TEXT NOT NULL,
                entry_zone REAL, reason TEXT, signals_bullish INTEGER DEFAULT 0,
                signals_bearish INTEGER DEFAULT 0, position_weight REAL DEFAULT 0.0,
                executed INTEGER NOT NULL DEFAULT 0, pred_id INTEGER,
                created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (code) REFERENCES stocks(code),
                FOREIGN KEY (pred_id) REFERENCES daily_predictions(id)
            );
            CREATE INDEX IF NOT EXISTS idx_ps_date ON paper_suggestions(date);
            CREATE INDEX IF NOT EXISTS idx_ps_code ON paper_suggestions(code);
            CREATE INDEX IF NOT EXISTS idx_ps_date_exec ON paper_suggestions(date, executed);
            CREATE TABLE IF NOT EXISTS paper_suggestions_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT NOT NULL, code TEXT NOT NULL,
                action TEXT NOT NULL, qty INTEGER NOT NULL DEFAULT 0,
                price REAL NOT NULL DEFAULT 0.0, confidence REAL NOT NULL DEFAULT 0.0,
                direction TEXT NOT NULL, entry_zone REAL, reason TEXT,
                signals_bullish INTEGER DEFAULT 0, signals_bearish INTEGER DEFAULT 0,
                position_weight REAL DEFAULT 0.0, pred_id INTEGER,
                snapshot_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (code) REFERENCES stocks(code)
            );
            CREATE INDEX IF NOT EXISTS idx_psh_date ON paper_suggestions_history(date);
            CREATE INDEX IF NOT EXISTS idx_psh_code ON paper_suggestions_history(code);
            CREATE INDEX IF NOT EXISTS idx_psh_date_code ON paper_suggestions_history(date, code);
            -- Intraday quotes for minute-level price tracking
            CREATE TABLE IF NOT EXISTS intraday_quotes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                price REAL NOT NULL,
                change_pct REAL DEFAULT 0,
                volume INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (code) REFERENCES stocks(code)
            );
            CREATE UNIQUE INDEX IF NOT EXISTS idx_iq_code_ts ON intraday_quotes(code, timestamp);
            CREATE INDEX IF NOT EXISTS idx_iq_code_date ON intraday_quotes(code, date(timestamp));
        """)
        for col in ['backtest_weights', 'regime_weights', 'backtest_timestamp']:
            try: db.execute(f"ALTER TABLE learning_params ADD COLUMN {col} TEXT")
            except: pass
        db.commit()
    finally:
        db.close()


def get_paper_account() -> dict | None:
    db = get_db()
    row = db.execute("SELECT * FROM paper_account ORDER BY id DESC LIMIT 1").fetchone()
    db.close()
    return dict(row) if row else None

def get_paper_positions() -> list:
    db = get_db()
    # MUST list columns explicitly — DON'T use pp.* because the table stores
    # market_value/unrealized_pnl which would shadow the live-computed values.
    # Use kline_daily latest close as second fallback after quotes table
    _kd = "(SELECT close FROM kline_daily WHERE code=pp.code ORDER BY date DESC LIMIT 1)"
    rows = db.execute(f"""
        SELECT pp.id, pp.code, pp.qty, pp.avg_cost, pp.updated_at,
               s.name,
               COALESCE(q.price, {_kd}, pp.last_price, pp.avg_cost, 0) AS last_price,
               pp.qty * COALESCE(q.price, {_kd}, pp.last_price, pp.avg_cost, 0) AS market_value,
               pp.qty * COALESCE(q.price, {_kd}, pp.last_price, pp.avg_cost, 0) - pp.qty * pp.avg_cost AS unrealized_pnl,
               CASE WHEN pp.avg_cost > 0
                    THEN ROUND((COALESCE(q.price, {_kd}, pp.last_price, pp.avg_cost, 0) - pp.avg_cost) / pp.avg_cost * 100, 2)
                    ELSE 0 END AS unrealized_pnl_pct
        FROM paper_positions pp
        LEFT JOIN stocks s ON pp.code = s.code
        LEFT JOIN quotes q ON pp.code = q.code
        WHERE pp.qty > 0
    """).fetchall()
    db.close()
    return [dict(r) for r in rows]

def get_paper_trades(code=None, limit=50, offset=0):
    db = get_db()
    if code:
        rows = db.execute("SELECT pt.*, s.name FROM paper_trades pt LEFT JOIN stocks s ON pt.code=s.code WHERE pt.code=? ORDER BY pt.date DESC, pt.id DESC LIMIT ? OFFSET ?", [code, limit, offset]).fetchall()
        total = db.execute("SELECT COUNT(*) FROM paper_trades WHERE code=?", [code]).fetchone()[0]
    else:
        rows = db.execute("SELECT pt.*, s.name FROM paper_trades pt LEFT JOIN stocks s ON pt.code=s.code ORDER BY pt.date DESC, pt.id DESC LIMIT ? OFFSET ?", [limit, offset]).fetchall()
        total = db.execute("SELECT COUNT(*) FROM paper_trades").fetchone()[0]
    db.close()
    return [dict(r) for r in rows], total

def get_paper_suggestions(date=None, code=None):
    db = get_db()
    q = "SELECT ps.*, s.name FROM paper_suggestions ps LEFT JOIN stocks s ON ps.code=s.code WHERE 1=1"
    params = []
    if date: q += " AND ps.date=?"; params.append(date)
    if code: q += " AND ps.code=?"; params.append(code)
    rows = db.execute(q + " ORDER BY ps.date DESC, ps.id DESC", params).fetchall()
    db.close()
    return [dict(r) for r in rows]

def get_paper_daily_snapshots(days=90):
    db = get_db()
    rows = db.execute("SELECT * FROM paper_daily_snapshot ORDER BY date DESC LIMIT ?", [days]).fetchall()
    db.close()
    return [dict(r) for r in rows]


def get_paper_suggestions_history(date=None, code=None, days=30):
    """查询历史建议快照。可按日期、股票筛选。返回按日期倒序的结果。"""
    db = get_db()
    q = """SELECT psh.*, s.name
           FROM paper_suggestions_history psh
           LEFT JOIN stocks s ON psh.code=s.code
           WHERE 1=1"""
    params = []
    if date:
        q += " AND psh.date=?"
        params.append(date)
    if code:
        q += " AND psh.code=?"
        params.append(code)
    q += " ORDER BY psh.date DESC, psh.id DESC"
    if not date and not code:
        # 无筛选时限制返回行数
        q += f" LIMIT ?"
        params.append(days * 20)
    rows = db.execute(q, params).fetchall()
    db.close()
    return [dict(r) for r in rows]


def save_suggestions_snapshot(db, date):
    """将 paper_suggestions 中当天的建议快照到 history 表（幂等：同天同股不会重复插入）。"""
    rows = db.execute(
        """SELECT date, code, action, qty, price, confidence, direction,
                  entry_zone, reason, signals_bullish, signals_bearish,
                  position_weight, pred_id
           FROM paper_suggestions WHERE date=?""",
        [date]
    ).fetchall()
    saved = 0
    for r in rows:
        d = dict(r)
        # 检查是否已存在同天同股的历史记录
        exists = db.execute(
            "SELECT id FROM paper_suggestions_history WHERE date=? AND code=?",
            [d['date'], d['code']]
        ).fetchone()
        if exists:
            continue
        db.execute(
            """INSERT INTO paper_suggestions_history
               (date,code,action,qty,price,confidence,direction,entry_zone,reason,
                signals_bullish,signals_bearish,position_weight,pred_id,snapshot_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,datetime('now','localtime'))""",
            [d['date'], d['code'], d['action'], d['qty'], d['price'],
             d['confidence'], d['direction'], d.get('entry_zone'), d.get('reason', ''),
             d['signals_bullish'], d['signals_bearish'], d['position_weight'], d['pred_id']]
        )
        saved += 1
    return saved

def insert_backtest_run(status='running', train_window=252, test_window=21, stock_codes='', total_stocks=0):
    db = get_db()
    db.execute("INSERT INTO backtest_runs (started_at,status,train_window,test_window,stock_codes,total_stocks) VALUES (datetime('now','localtime'),?,?,?,?,?)", [status, train_window, test_window, stock_codes, total_stocks])
    rid = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    db.commit(); db.close()
    return rid

def update_backtest_run(run_id, **kwargs):
    db = get_db()
    sets = ", ".join(f"{k}=?" for k in kwargs)
    db.execute(f"UPDATE backtest_runs SET {sets} WHERE id=?", list(kwargs.values())+[run_id])
    db.commit(); db.close()

def get_backtest_runs():
    db = get_db()
    try:
        return [dict(r) for r in db.execute("SELECT * FROM backtest_runs ORDER BY started_at DESC LIMIT 20").fetchall()]
    finally:
        db.close()

def reset_paper_account(initial_capital=100000.0):
    db = get_db()
    db.execute("DELETE FROM paper_positions")
    db.execute("DELETE FROM paper_account")
    db.execute("INSERT INTO paper_account (cash,initial_capital) VALUES (?,?)", [initial_capital, initial_capital])
    db.commit(); db.close()

def upsert_paper_suggestion(sug):
    db = get_db()
    ex = db.execute("SELECT id FROM paper_suggestions WHERE date=? AND code=?", [sug['date'], sug['code']]).fetchone()
    if ex:
        db.execute("UPDATE paper_suggestions SET action=?,qty=?,price=?,confidence=?,direction=?,entry_zone=?,reason=?,signals_bullish=?,signals_bearish=?,position_weight=?,executed=?,pred_id=? WHERE id=?", [sug['action'], sug['qty'], sug['price'], sug['confidence'], sug['direction'], sug.get('entry_zone'), sug.get('reason',''), sug.get('signals_bullish',0), sug.get('signals_bearish',0), sug.get('position_weight',0), sug.get('executed',0), sug.get('pred_id'), ex['id']])
    else:
        db.execute("INSERT INTO paper_suggestions (date,code,action,qty,price,confidence,direction,entry_zone,reason,signals_bullish,signals_bearish,position_weight,executed,pred_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", [sug['date'], sug['code'], sug['action'], sug['qty'], sug['price'], sug['confidence'], sug['direction'], sug.get('entry_zone'), sug.get('reason',''), sug.get('signals_bullish',0), sug.get('signals_bearish',0), sug.get('position_weight',0), sug.get('executed',0), sug.get('pred_id')])
    db.commit(); db.close()


# ── Intraday Quotes ─────────────────────────────────────────────────────

def get_intraday_quotes(code: str, date: str = None) -> list:
    """Get intraday minute-level quotes for a stock on a given date.

    Falls back to daily K-line data when no minute-level data exists for a
    historical date (minute data only kept ~5 trading days by data source).
    K-line fallback generates 4 key points: open(09:30), high(10:00),
    low(14:30), close(15:00), with is_kline_fallback=True.

    Args:
        code: Stock code
        date: Date string 'YYYY-MM-DD'. Defaults to today.

    Returns:
        List of dicts with keys: timestamp, price, change_pct, volume
        (plus is_kline_fallback=True if generated from daily K-line)
    """
    if date is None:
        from datetime import datetime as _dt
        date = _dt.now().strftime('%Y-%m-%d')

    db = get_db()
    try:
        rows = db.execute(
            "SELECT timestamp, price, change_pct, volume FROM intraday_quotes "
            "WHERE code=? AND date(timestamp)=? ORDER BY timestamp ASC",
            [code, date]
        ).fetchall()
        if rows:
            return [dict(r) for r in rows]
    finally:
        db.close()

    # ── Fallback: try daily K-line for historical dates ──
    return _get_kline_intraday_fallback(code, date)


def _get_kline_intraday_fallback(code: str, date: str) -> list:
    """Generate simplified intraday points from daily K-line data.

    Produces 4 timestamped price points:
      09:30 → open
      10:00 → high
      14:30 → low
      15:00 → close

    Returns empty list if no K-line data exists for that date.
    """
    db = get_db()
    try:
        row = db.execute(
            "SELECT open, close, high, low, volume "
            "FROM kline_daily WHERE code=? AND date=? LIMIT 1",
            [code, date]
        ).fetchone()
        if not row:
            return []
        open_p, close_p, high_p, low_p = row['open'], row['close'], row['high'], row['low']
        volume = row['volume'] or 0

        # Calculate rough change_pct relative to previous day's close
        prev = db.execute(
            "SELECT close FROM kline_daily WHERE code=? AND date<? "
            "ORDER BY date DESC LIMIT 1",
            [code, date]
        ).fetchone()
        prev_close = prev['close'] if prev else open_p
        chg_pct = round((close_p - prev_close) / prev_close * 100, 2) if prev_close else 0

        return [
            {'timestamp': f'{date} 09:30:00', 'price': open_p,  'change_pct': chg_pct, 'volume': 0,
             'is_kline_fallback': True},
            {'timestamp': f'{date} 10:00:00', 'price': high_p,  'change_pct': chg_pct, 'volume': 0,
             'is_kline_fallback': True},
            {'timestamp': f'{date} 14:30:00', 'price': low_p,   'change_pct': chg_pct, 'volume': 0,
             'is_kline_fallback': True},
            {'timestamp': f'{date} 15:00:00', 'price': close_p, 'change_pct': chg_pct, 'volume': volume,
             'is_kline_fallback': True},
        ]
    finally:
        db.close()


def insert_intraday_quotes(rows: list):
    """Insert or replace intraday quote rows.

    Args:
        rows: List of dicts with keys: code, timestamp, price, change_pct, volume
    """
    if not rows:
        return
    db = get_db()
    try:
        db.executemany(
            "INSERT OR REPLACE INTO intraday_quotes (code, timestamp, price, change_pct, volume) "
            "VALUES (?, ?, ?, ?, ?)",
            [[r['code'], r['timestamp'], r['price'], r.get('change_pct', 0), r.get('volume', 0)] for r in rows]
        )
        db.commit()
    finally:
        db.close()


def get_intraday_dates_for_code(code: str, limit: int = 90) -> list:
    """Get list of dates that have intraday data for a stock.

    Includes both actual minute-level data dates and dates where daily K-line
    fallback is available (e.g. June 3rd, which has K-line but no minute data).

    Args:
        code: Stock code
        limit: Max number of dates to return

    Returns:
        List of date strings 'YYYY-MM-DD'
    """
    db = get_db()
    try:
        # Minute data dates
        minute_rows = db.execute(
            "SELECT DISTINCT date(timestamp) as d FROM intraday_quotes "
            "WHERE code=? ORDER BY d DESC LIMIT ?",
            [code, limit]
        ).fetchall()
        minute_dates = set(r['d'] for r in minute_rows)

        # Also include dates with kline data (for K-line fallback)
        kline_rows = db.execute(
            "SELECT DISTINCT date FROM kline_daily "
            "WHERE code=? ORDER BY date DESC LIMIT ?",
            [code, limit * 2]
        ).fetchall()
        kline_dates = set(r['date'] for r in kline_rows)

        # Merge and sort desc
        all_dates = sorted(minute_dates | kline_dates, reverse=True)
        return all_dates[:limit]
    finally:
        db.close()


# ── K-line Pattern Rules ──────────────────────────────────────────────

def init_pattern_rules_tables():
    """Initialize pattern_rules table. Idempotent."""
    db = get_db()
    try:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS pattern_rules (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                rule_id     TEXT    NOT NULL UNIQUE,
                name        TEXT    NOT NULL,
                name_en     TEXT    DEFAULT '',
                category    TEXT    NOT NULL CHECK(category IN ('single','double','triple','multi','special')),
                direction   TEXT    NOT NULL CHECK(direction IN ('bullish','bearish','neutral')),
                strength    INTEGER NOT NULL DEFAULT 3,
                span_days   INTEGER NOT NULL,
                conditions  TEXT    NOT NULL,
                enabled     INTEGER NOT NULL DEFAULT 1,
                memo        TEXT    DEFAULT '',
                created_at  TEXT    DEFAULT (datetime('now','localtime')),
                updated_at  TEXT    DEFAULT (datetime('now','localtime'))
            );
            CREATE UNIQUE INDEX IF NOT EXISTS idx_pr_rule_id ON pattern_rules(rule_id);
            CREATE INDEX IF NOT EXISTS idx_pr_category ON pattern_rules(category);
            CREATE INDEX IF NOT EXISTS idx_pr_enabled ON pattern_rules(enabled);
        """)
        db.commit()
    finally:
        db.close()


def get_pattern_rules(enabled_only=False) -> list:
    """Get all pattern rules, optionally only enabled ones."""
    db = get_db()
    try:
        sql = "SELECT * FROM pattern_rules"
        if enabled_only:
            sql += " WHERE enabled=1"
        sql += " ORDER BY category, rule_id"
        return [dict(r) for r in db.execute(sql).fetchall()]
    finally:
        db.close()


def get_pattern_rule(rule_id: str) -> dict | None:
    """Get a single pattern rule by rule_id."""
    db = get_db()
    try:
        r = db.execute("SELECT * FROM pattern_rules WHERE rule_id=?", [rule_id]).fetchone()
        return dict(r) if r else None
    finally:
        db.close()


def insert_pattern_rule(rule: dict) -> int:
    """Insert a new pattern rule. Returns the new row id."""
    db = get_db()
    try:
        cur = db.execute(
            "INSERT INTO pattern_rules (rule_id, name, name_en, category, direction, "
            "strength, span_days, conditions, enabled, memo) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [rule['rule_id'], rule['name'], rule.get('name_en', ''),
             rule['category'], rule['direction'], rule['strength'],
             rule['span_days'], rule['conditions'], rule.get('enabled', 1),
             rule.get('memo', '')]
        )
        db.commit()
        return cur.lastrowid
    finally:
        db.close()


def update_pattern_rule(rule_id: str, updates: dict) -> bool:
    """Update a pattern rule. Returns True if any rows affected."""
    allowed = {'name', 'name_en', 'category', 'direction', 'strength',
               'span_days', 'conditions', 'enabled', 'memo'}
    sets = {}
    for k, v in updates.items():
        if k in allowed:
            sets[k] = v
    if not sets:
        return False
    sets['updated_at'] = 'datetime(\'now\',\'localtime\')'
    db = get_db()
    try:
        placeholders = ', '.join(f"{k}=?" for k in sets if k != 'updated_at')
        placeholders += ", updated_at=datetime('now','localtime')"
        values = [sets[k] for k in sets if k != 'updated_at']
        values.append(rule_id)
        db.execute(f"UPDATE pattern_rules SET {placeholders} WHERE rule_id=?", values)
        db.commit()
        return db.total_changes > 0
    finally:
        db.close()


def delete_pattern_rule(rule_id: str) -> bool:
    """Delete a pattern rule by rule_id."""
    db = get_db()
    try:
        db.execute("DELETE FROM pattern_rules WHERE rule_id=?", [rule_id])
        db.commit()
        return db.total_changes > 0
    finally:
        db.close()


def count_pattern_rules() -> int:
    """Count total pattern rules."""
    db = get_db()
    try:
        return db.execute("SELECT COUNT(*) as c FROM pattern_rules").fetchone()['c']
    finally:
        db.close()


# ═══════════════════════════════════════════════════════════════════════
# Company Relations Graph — tables init + CRUD
# ═══════════════════════════════════════════════════════════════════════

def init_company_relations_tables():
    """Create company_relations and company_business tables. Idempotent."""
    db = get_db()
    try:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS company_relations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL,
                related_code TEXT NOT NULL,
                related_name TEXT NOT NULL,
                relation_type TEXT NOT NULL,
                relation_subtype TEXT DEFAULT '',
                relation_detail TEXT DEFAULT '',
                weight REAL DEFAULT 1.0,
                direction TEXT DEFAULT '',
                extra_data TEXT DEFAULT '',
                source TEXT DEFAULT 'web',
                updated_at TEXT DEFAULT (datetime('now','localtime')),
                UNIQUE(code, related_code, relation_type, relation_subtype)
            );
            CREATE INDEX IF NOT EXISTS idx_cr_code ON company_relations(code);
            CREATE INDEX IF NOT EXISTS idx_cr_type ON company_relations(relation_type);
            CREATE INDEX IF NOT EXISTS idx_cr_relcode ON company_relations(related_code);

            CREATE TABLE IF NOT EXISTS company_business (
                code TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                industry TEXT DEFAULT '',
                business TEXT DEFAULT '',
                source TEXT DEFAULT 'web',
                updated_at TEXT DEFAULT (datetime('now','localtime'))
            );
        """)
        db.commit()
    finally:
        db.close()


def get_company_relations(code=None, type_filter=None):
    """Get company relations with optional filters.

    Args:
        code: Stock code to filter by (optional)
        type_filter: Relation type filter: equity/executive/supply/competition (optional)
    Returns:
        List of dict rows
    """
    db = get_db()
    try:
        sql = "SELECT * FROM company_relations WHERE 1=1"
        params = []
        if code:
            sql += " AND (code=? OR related_code=?)"
            params.extend([code, code])
        if type_filter:
            sql += " AND relation_type=?"
            params.append(type_filter)
        sql += " ORDER BY relation_type, weight DESC"
        return [dict(r) for r in db.execute(sql, params).fetchall()]
    finally:
        db.close()


def upsert_company_relation(record):
    """Insert or update a company relation record."""
    db = get_db()
    try:
        db.execute("""
            INSERT OR REPLACE INTO company_relations
                (code, related_code, related_name, relation_type, relation_subtype,
                 relation_detail, weight, direction, extra_data, source)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, [
            record.get('code'),
            record.get('related_code'),
            record.get('related_name', ''),
            record.get('relation_type'),
            record.get('relation_subtype', ''),
            record.get('relation_detail', ''),
            record.get('weight', 1.0),
            record.get('direction', ''),
            record.get('extra_data', ''),
            record.get('source', 'web'),
        ])
        db.commit()
    finally:
        db.close()


def clear_company_relations(type_filter=None):
    """Clear all company relations, optionally by type."""
    db = get_db()
    try:
        if type_filter:
            db.execute("DELETE FROM company_relations WHERE relation_type=?", [type_filter])
        else:
            db.execute("DELETE FROM company_relations")
        db.commit()
    finally:
        db.close()


def delete_company_relations_by_code(code, type_filter=None):
    """Delete all relations for a specific stock code."""
    db = get_db()
    try:
        sql = "DELETE FROM company_relations WHERE code=? OR related_code=?"
        params = [code, code]
        if type_filter:
            sql += " AND relation_type=?"
            params.append(type_filter)
        db.execute(sql, params)
        db.commit()
    finally:
        db.close()


def get_company_business(codes=None):
    """Get company business info.

    Args:
        codes: List of stock codes, or None for all
    Returns:
        Dict of {code: {name, industry, business}}
    """
    db = get_db()
    try:
        if codes:
            placeholders = ','.join('?' for _ in codes)
            rows = db.execute(
                f"SELECT * FROM company_business WHERE code IN ({placeholders})", codes
            ).fetchall()
        else:
            rows = db.execute("SELECT * FROM company_business").fetchall()
        return {r['code']: dict(r) for r in rows}
    finally:
        db.close()


def upsert_company_business(record):
    """Insert or update company business info."""
    db = get_db()
    try:
        db.execute("""
            INSERT OR REPLACE INTO company_business
                (code, name, industry, business, source)
            VALUES (?,?,?,?,?)
        """, [
            record.get('code'),
            record.get('name', ''),
            record.get('industry', ''),
            record.get('business', ''),
            record.get('source', 'web'),
        ])
        db.commit()
    finally:
        db.close()


def get_graph_data(code=None, type_filter=None):
    """Build graph nodes+edges data for the frontend.

    Args:
        code: Optional stock code to filter by (shows relations for a specific stock)
        type_filter: Optional relation type filter
    Returns:
        {nodes: [...], edges: [...]} compatible with G6
    """
    relations = get_company_relations(code=code, type_filter=type_filter)
    if not relations:
        return {'nodes': [], 'edges': []}

    # Collect unique node ids
    node_map = {}
    edges = []

    for r in relations:
        # Edge
        edge = {
            'source': r['code'],
            'target': r['related_code'],
            'type': r['relation_type'],
            'subtype': r['relation_subtype'],
            'label': r['relation_detail'] or '',
            'weight': r['weight'],
            'detail': r['relation_detail'] or '',
            'direction': r['direction'] or '',
        }
        edges.append(edge)

        # Source node
        if r['code'] not in node_map:
            if r['code'].startswith('person_'):
                ntype = 'person'
                label = r['code'].replace('person_', '')
            elif r['code'].startswith('holder_'):
                ntype = 'company'
                label = r['code'].replace('holder_', '')
            else:
                ntype = 'stock'
                label = r.get('related_name', r['code'])
            node_map[r['code']] = {
                'id': r['code'],
                'label': label,
                'type': ntype,
                'code': r['code'],
            }

        # Target node
        if r['related_code'] not in node_map:
            if r['related_code'].startswith('person_'):
                ntype = 'person'
                label = r['related_code'].replace('person_', '')
            elif r['related_code'].startswith('holder_'):
                ntype = 'company'
                label = r['related_code'].replace('holder_', '')
            else:
                ntype = 'company'
                label = r.get('related_name', r['related_code'])
            node_map[r['related_code']] = {
                'id': r['related_code'],
                'label': label,
                'type': ntype,
                'code': r['related_code'],
            }

    # Enrich stock/company nodes with business info
    stock_codes = [n['code'] for n in node_map.values()
                   if n['type'] in ('stock', 'company') and not n['code'].startswith(('person_', 'holder_'))]
    if stock_codes:
        biz = get_company_business(stock_codes)
        for n in node_map.values():
            if n['code'] in biz:
                n['industry'] = biz[n['code']].get('industry', '')
                n['business'] = biz[n['code']].get('business', '')

    return {'nodes': list(node_map.values()), 'edges': edges}
