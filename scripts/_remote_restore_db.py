import json, sqlite3, os, sys

ROOT = '/workspace'

db = sqlite3.connect(os.path.join(ROOT, 'data', 'stock.db'))

# Create tables
db.execute("CREATE TABLE IF NOT EXISTS watchlist (code TEXT PRIMARY KEY, name TEXT, market TEXT, sort_order INTEGER)")
db.execute("CREATE TABLE IF NOT EXISTS quotes (code TEXT PRIMARY KEY, price REAL, change REAL, open REAL, high REAL, low REAL, pe REAL, pb REAL, dy REAL)")
db.execute("CREATE TABLE IF NOT EXISTS positions (code TEXT PRIMARY KEY, name TEXT, qty INTEGER, total_cost REAL, avg_cost REAL, realized_pnl REAL)")
db.execute("CREATE TABLE IF NOT EXISTS closed_positions (code TEXT PRIMARY KEY, name TEXT, realized_pnl REAL, dividends_total REAL, total_commission REAL, total_stamp_tax REAL, total_other_fees REAL)")
db.execute("CREATE TABLE IF NOT EXISTS trades (id INTEGER PRIMARY KEY, date TEXT, time TEXT, code TEXT, name TEXT, type TEXT, qty INTEGER, price REAL, commission REAL, stamp_tax REAL, settlement REAL)")
db.execute("CREATE TABLE IF NOT EXISTS dividends (id INTEGER PRIMARY KEY, code TEXT, date TEXT, amount REAL, price REAL)")
db.execute("CREATE TABLE IF NOT EXISTS seasonal (code TEXT PRIMARY KEY, factors TEXT)")
db.execute("CREATE TABLE IF NOT EXISTS daily_predictions (id INTEGER PRIMARY KEY, code TEXT NOT NULL, date TEXT NOT NULL, prev_close REAL, direction TEXT, confidence REAL, high REAL, low REAL, advice TEXT, entry_zone TEXT, actual_open REAL, actual_high REAL, actual_low REAL, actual_close REAL, dir_hit INTEGER, range_hit INTEGER)")
db.execute("CREATE TABLE IF NOT EXISTS kline_daily (id INTEGER PRIMARY KEY, code TEXT NOT NULL, date TEXT NOT NULL, open REAL, close REAL, high REAL, low REAL)")
db.execute("CREATE TABLE IF NOT EXISTS news (id INTEGER PRIMARY KEY, date TEXT, code TEXT, title TEXT, summary TEXT, source TEXT, sentiment TEXT, major INTEGER)")
db.execute("CREATE TABLE IF NOT EXISTS expert_reports (id INTEGER PRIMARY KEY, date TEXT, report_data TEXT)")
db.commit()

# Load from JSON files
sd_path = os.path.join(ROOT, 'data', 'system_data.json')
bs_path = os.path.join(ROOT, 'data', 'broker_statement.json')

if os.path.exists(sd_path):
    sd = json.load(open(sd_path, 'r', encoding='utf-8'))
    for s in sd.get('watchlist', []):
        db.execute('INSERT OR IGNORE INTO watchlist VALUES(?,?,?,?)', [s['code'], s['name'], s.get('market', 'sh'), 0])
    for code, bars in sd.get('kline_daily', {}).items():
        for bar in bars:
            db.execute('INSERT OR IGNORE INTO kline_daily(code,date,open,close,high,low) VALUES(?,?,?,?,?,?)', [code, bar[0], bar[1], bar[2], bar[3], bar[4]])
    for code, f in sd.get('seasonal', {}).items():
        db.execute('INSERT OR REPLACE INTO seasonal(code,factors) VALUES(?,?)', [code, json.dumps(f)])
    for code, q in sd.get('quotes', {}).items():
        db.execute('INSERT OR REPLACE INTO quotes VALUES(?,?,?,?,?,?,?,?,?)', [code, q.get('price', 0), q.get('change', 0), q.get('open', 0), q.get('high', 0), q.get('low', 0), q.get('pe', 0), q.get('pb', 0), q.get('dy', 0)])
    db.commit()

if os.path.exists(bs_path):
    bs = json.load(open(bs_path, 'r', encoding='utf-8'))
    for code, p in bs.get('current_positions', {}).items():
        db.execute('INSERT OR REPLACE INTO positions VALUES(?,?,?,?,?,?)', [code, p['name'], p['qty'], p['total_cost'], p.get('avg_cost', 0), p.get('realized_pnl', 0)])
        for d in p.get('dividends', []):
            db.execute('INSERT OR IGNORE INTO dividends(code,date,amount,price) VALUES(?,?,?,?)', [code, d['date'], d['amount'], d['price']])
    for t in bs.get('all_trades', []):
        db.execute('INSERT OR IGNORE INTO trades(date,time,code,name,type,qty,price,commission,stamp_tax,settlement) VALUES(?,?,?,?,?,?,?,?,?,?)',
                   [t['date'], t.get('time', ''), t['code'], t['name'], t['type'], t['qty'], t['price'], t.get('commission', 0), t.get('stamp_tax', 0), t['settlement']])
    db.commit()

db.close()
print('DB restore complete')
