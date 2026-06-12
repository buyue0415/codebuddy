"""Step 1: Create SQLite DB + migrate all existing JSON data"""
import sqlite3, json, os
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, 'data', 'stock.db')

# Load source data
with open(os.path.join(ROOT, 'data', 'system_data.json'), 'r', encoding='utf-8') as f:
    sd = json.load(f)
with open(os.path.join(ROOT, 'data', 'a_stocks.json'), 'r', encoding='utf-8') as f:
    stocks_list = json.load(f)
with open(os.path.join(ROOT, 'data', 'watchlist.json'), 'r', encoding='utf-8') as f:
    wl = json.load(f)
with open(os.path.join(ROOT, 'data', 'broker_statement.json'), 'r', encoding='utf-8') as f:
    bs = json.load(f)

if os.path.exists(DB):
    os.remove(DB)
db = sqlite3.connect(DB)
db.execute("PRAGMA journal_mode=WAL")
db.execute("PRAGMA foreign_keys=ON")

# ===== Create schema =====
db.executescript("""
CREATE TABLE stocks (code TEXT PRIMARY KEY, name TEXT NOT NULL, market TEXT, py TEXT, watchlist INTEGER DEFAULT 0);
CREATE INDEX idx_stocks_py ON stocks(py);
CREATE INDEX idx_stocks_name ON stocks(name);

CREATE TABLE kline_daily (id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT NOT NULL, date TEXT NOT NULL, open REAL, close REAL, high REAL, low REAL, volume REAL DEFAULT 0, pe REAL DEFAULT 0, pb REAL DEFAULT 0, dy REAL DEFAULT 0);
CREATE INDEX idx_kd_code_date ON kline_daily(code, date);

CREATE TABLE kline_monthly (id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT NOT NULL, date TEXT NOT NULL, open REAL, high REAL, low REAL, close REAL, volume REAL, change_pct REAL);
CREATE INDEX idx_km_code_date ON kline_monthly(code, date);

CREATE TABLE quotes (code TEXT PRIMARY KEY, price REAL, change REAL, open REAL, high REAL, low REAL, pe REAL, pb REAL, dy REAL, volume INTEGER DEFAULT 0);

CREATE TABLE daily_predictions (id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT NOT NULL, date TEXT NOT NULL, prev_close REAL, direction TEXT, confidence REAL, high REAL, low REAL, advice TEXT, entry_zone REAL, actual_open REAL, actual_high REAL, actual_low REAL, actual_close REAL, dir_hit INTEGER, range_hit INTEGER);
CREATE INDEX idx_dp_code_date ON daily_predictions(code, date);

CREATE TABLE prediction_hourly (id INTEGER PRIMARY KEY AUTOINCREMENT, pred_id INTEGER NOT NULL, block TEXT, pred_open REAL, pred_high REAL, pred_low REAL, pred_close REAL, direction TEXT, strength INTEGER, note TEXT, hit INTEGER, FOREIGN KEY(pred_id) REFERENCES daily_predictions(id));
CREATE INDEX idx_ph_pred ON prediction_hourly(pred_id);

CREATE TABLE prediction_signals (id INTEGER PRIMARY KEY AUTOINCREMENT, pred_id INTEGER NOT NULL, name TEXT, value TEXT, direction TEXT, raw_value REAL, extra TEXT, FOREIGN KEY(pred_id) REFERENCES daily_predictions(id));

CREATE TABLE learning_params (code TEXT PRIMARY KEY, signal_weights TEXT, hourly_bias TEXT, seasonal_adj TEXT, confidence_beta TEXT, learning_rate REAL, mw_beta REAL, update_count INTEGER);

CREATE TABLE accuracy_stats (code TEXT, period TEXT, dir_correct INTEGER, dir_total INTEGER, dir_rate REAL, range_correct INTEGER, range_total INTEGER, range_rate REAL, hourly_stats TEXT, PRIMARY KEY(code, period));

CREATE TABLE trades (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, time TEXT, code TEXT, name TEXT, type TEXT, qty INTEGER, price REAL, commission REAL, stamp_tax REAL, settlement REAL);
CREATE INDEX idx_trades_code ON trades(code);
CREATE INDEX idx_trades_date ON trades(date);

CREATE TABLE positions (code TEXT PRIMARY KEY, name TEXT, qty INTEGER, total_cost REAL, avg_cost REAL, realized_pnl REAL);
CREATE TABLE closed_positions (code TEXT PRIMARY KEY, name TEXT, realized_pnl REAL, dividends_total REAL, total_commission REAL, total_stamp_tax REAL, total_other_fees REAL);

CREATE TABLE dividends (id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT, date TEXT, amount REAL, price REAL, ex_date TEXT, source TEXT DEFAULT 'statement');
CREATE INDEX idx_div_code ON dividends(code);
CREATE UNIQUE INDEX IF NOT EXISTS idx_div_unique ON dividends(code, date, amount);

CREATE TABLE news (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, code TEXT, title TEXT, summary TEXT, source TEXT, sentiment TEXT, major INTEGER DEFAULT 0);
CREATE INDEX idx_news_date ON news(date);

CREATE TABLE expert_reports (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, report_data TEXT);

CREATE TABLE seasonal (code TEXT PRIMARY KEY, factors TEXT);

CREATE TABLE watchlist (code TEXT PRIMARY KEY, name TEXT, market TEXT, sort_order INTEGER);
""")

# ===== Migrate data =====
print("=== Migrating ===")

# Stocks (from a_stocks.json)
watchlist_codes = {s['code'] for s in wl.get('stocks', [])}
for s in stocks_list:
    db.execute("INSERT INTO stocks(code,name,market,py,watchlist) VALUES(?,?,?,?,?)",
               [s['code'], s['name'], s['market'], s.get('py',''), 1 if s['code'] in watchlist_codes else 0])
print(f"  stocks: {len(stocks_list)} rows")

# Watchlist
for i, s in enumerate(wl.get('stocks', [])):
    db.execute("INSERT OR REPLACE INTO watchlist(code,name,market,sort_order) VALUES(?,?,?,?)",
               [s['code'], s['name'], s.get('market','sh'), i])
print(f"  watchlist: {len(wl.get('stocks',[]))} rows")

# Kline daily
for code, bars in sd.get('kline_daily', {}).items():
    for b in bars:
        db.execute("INSERT INTO kline_daily(code,date,open,close,high,low) VALUES(?,?,?,?,?,?)",
                   [code, b[0], b[1], b[2], b[3], b[4]])
print(f"  kline_daily: {sum(len(v) for v in sd.get('kline_daily',{}).values())} rows")

# Kline monthly
for code, bars in sd.get('kline', {}).items():
    for b in bars:
        db.execute("INSERT INTO kline_monthly(code,date,open,high,low,close,volume,change_pct) VALUES(?,?,?,?,?,?,?,?)",
                   [code, b[0], b[1], b[2], b[3], b[4], b[5] if len(b)>5 else 0, b[6] if len(b)>6 else 0])
print(f"  kline_monthly: {sum(len(v) for v in sd.get('kline',{}).values())} rows")

# Quotes
for code, q in sd.get('quotes', {}).items():
    db.execute("INSERT INTO quotes(code,price,change,open,high,low,pe,pb,dy) VALUES(?,?,?,?,?,?,?,?,?)",
               [code, q.get('price'), q.get('change'), q.get('open'), q.get('high'), q.get('low'), q.get('pe'), q.get('pb'), q.get('dy')])
print(f"  quotes: {len(sd.get('quotes',{}))} rows")

# Daily predictions
for p in sd.get('daily_predictions', []):
    nd = p.get('next_day', {})
    act = p.get('actual', {})
    cur = db.execute("INSERT INTO daily_predictions(code,date,prev_close,direction,confidence,high,low,advice,entry_zone,actual_open,actual_high,actual_low,actual_close,dir_hit,range_hit) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        [p['code'], p['date'], p.get('prev_close'), nd.get('direction'), nd.get('confidence'), nd.get('high'), nd.get('low'), nd.get('advice'), nd.get('entry_zone'), act.get('open'), act.get('high'), act.get('low'), act.get('close'), 1 if act.get('next_day_direction_hit') else 0 if act.get('next_day_direction_hit') is not None else None, 1 if act.get('daily_range_hit') else 0 if act.get('daily_range_hit') is not None else None])
    pid = cur.lastrowid
    for hp in p.get('hourly', []):
        hits = act.get('hourly_hits', [None]*4)
        idx = ['09:30-10:30','10:30-11:30','13:00-14:00','14:00-15:00'].index(hp['block']) if hp['block'] in ['09:30-10:30','10:30-11:30','13:00-14:00','14:00-15:00'] else -1
        h = 1 if idx>=0 and hits[idx] else 0 if idx>=0 and hits[idx]==False else None
        db.execute("INSERT INTO prediction_hourly(pred_id,block,pred_open,pred_high,pred_low,pred_close,direction,strength,note,hit) VALUES(?,?,?,?,?,?,?,?,?,?)",
            [pid, hp['block'], hp.get('pred_open'), hp.get('pred_high'), hp.get('pred_low'), hp.get('pred_close'), hp.get('direction'), hp.get('strength'), hp.get('note'), h])
    for sn, sv in p.get('signals', {}).items():
        db.execute("INSERT INTO prediction_signals(pred_id,name,value,direction,raw_value) VALUES(?,?,?,?,?)",
            [pid, sn, str(sv.get('value','')), sv.get('direction'), sv.get('raw')])

print(f"  daily_predictions: {len(sd.get('daily_predictions',[]))} rows")

# Learning params
for code, lp in sd.get('learning_params', {}).items():
    db.execute("INSERT INTO learning_params(code,signal_weights,hourly_bias,seasonal_adj,confidence_beta,learning_rate,mw_beta,update_count) VALUES(?,?,?,?,?,?,?,?)",
        [code, json.dumps(lp.get('signal_weights',{})), json.dumps(lp.get('hourly_bias',{})), json.dumps(lp.get('seasonal_adj',{})), json.dumps(lp.get('confidence_beta',{})), lp.get('learning_rate'), lp.get('mw_beta'), lp.get('update_count')])
print(f"  learning_params: {len(sd.get('learning_params',{}))} rows")

# Accuracy stats
for code, ast in sd.get('accuracy_stats', {}).items():
    for period in ['last_20', 'last_60']:
        d = ast.get(period, {})
        db.execute("INSERT INTO accuracy_stats(code,period,dir_correct,dir_total,dir_rate,range_correct,range_total,range_rate,hourly_stats) VALUES(?,?,?,?,?,?,?,?,?)",
            [code, period, d.get('direction',{}).get('correct',0), d.get('direction',{}).get('total',0), d.get('direction',{}).get('rate',0), d.get('range',{}).get('correct',0), d.get('range',{}).get('total',0), d.get('range',{}).get('rate',0), json.dumps(d.get('hourly',{}))])
print(f"  accuracy_stats: {len(sd.get('accuracy_stats',{}))} stocks")

# Trades
for t in sd.get('all_trades', []):
    db.execute("INSERT INTO trades(date,time,code,name,type,qty,price,commission,stamp_tax,settlement) VALUES(?,?,?,?,?,?,?,?,?,?)",
        [t['date'], t.get('time',''), t['code'], t['name'], t['type'], int(t['qty']), t['price'], t.get('commission',0), t.get('stamp_tax',0), t['settlement']])
print(f"  trades: {len(sd.get('all_trades',[]))} rows")

# Positions
for code, p in sd.get('current_positions', {}).items():
    db.execute("INSERT INTO positions(code,name,qty,total_cost,avg_cost,realized_pnl) VALUES(?,?,?,?,?,?)",
        [code, p['name'], p['qty'], p['total_cost'], p['avg_cost'], p.get('realized_pnl',0)])
    for d in p.get('dividends', []):
        pay_date = d['date']
        ex_date = (datetime.strptime(pay_date[:10], '%Y-%m-%d') - timedelta(days=3)).strftime('%Y-%m-%d')
        db.execute("INSERT OR REPLACE INTO dividends(code,date,amount,price,ex_date,source) VALUES(?,?,?,?,?,?)",
            [code, pay_date, d['amount'], d['price'], ex_date, 'statement'])
for code, p in sd.get('closed_positions', {}).items():
    db.execute("INSERT INTO closed_positions(code,name,realized_pnl,dividends_total,total_commission,total_stamp_tax,total_other_fees) VALUES(?,?,?,?,?,?,?)",
        [code, p['name'], p.get('realized_pnl',0), p.get('dividends_total',0), p.get('total_commission',0), p.get('total_stamp_tax',0), p.get('total_other_fees',0)])
print(f"  positions: {len(sd.get('current_positions',{}))} open, {len(sd.get('closed_positions',{}))} closed")

# News
for n in sd.get('news', []):
    db.execute("INSERT INTO news(date,code,title,summary,source,sentiment,major) VALUES(?,?,?,?,?,?,?)",
        [n['date'], n['code'], n['title'], n.get('summary',''), n.get('source',''), n.get('sentiment',''), 1 if n.get('major') else 0])
print(f"  news: {len(sd.get('news',[]))} rows")

# Expert reports
for r in sd.get('expert_reports', []):
    db.execute("INSERT INTO expert_reports(date,report_data) VALUES(?,?)", [r['date'], json.dumps(r, ensure_ascii=False)])
print(f"  expert_reports: {len(sd.get('expert_reports',[]))} rows")

# Seasonal
for code, factors in sd.get('seasonal', {}).items():
    db.execute("INSERT INTO seasonal(code,factors) VALUES(?,?)", [code, json.dumps(factors)])
print(f"  seasonal: {len(sd.get('seasonal',{}))} stocks")

db.commit()
db.close()
print(f"\n=== Migration complete: {DB} ===")
