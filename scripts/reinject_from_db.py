"""Build HTML inline DATA from SQLite DB — complete replacement for reinject_data.py"""
import json, re, sqlite3, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, 'data', 'stock.db')

db = sqlite3.connect(DB)
db.row_factory = sqlite3.Row

data = {"account": "51312640", "broker": "广发证券", "generated": ""}

# ===== Watchlist =====
wl = [dict(r) for r in db.execute("SELECT code, name, market FROM watchlist ORDER BY sort_order").fetchall()]
data["watchlist"] = wl

# ===== Quotes =====
quotes = {}
for r in db.execute("SELECT * FROM quotes").fetchall():
    quotes[r["code"]] = {"price": r["price"], "change": r["change"], "open": r["open"],
        "high": r["high"], "low": r["low"], "pe": r["pe"], "pb": r["pb"], "dy": r["dy"]}
data["quotes"] = quotes

# ===== Daily kline =====
kd = {}
for r in db.execute("SELECT code, date, open, close, high, low FROM kline_daily ORDER BY code, date DESC").fetchall():
    code = r["code"]
    if code not in kd: kd[code] = []
    kd[code].append([r["date"], r["open"], r["close"], r["high"], r["low"]])
data["kline_daily"] = kd

# ===== Monthly kline =====
km = {}
for r in db.execute("SELECT code, date, open, high, low, close, volume, change_pct FROM kline_monthly ORDER BY code, date DESC").fetchall():
    code = r["code"]
    if code not in km: km[code] = []
    km[code].append([r["date"], r["open"], r["high"], r["low"], r["close"], r["volume"], r["change_pct"]])
data["kline"] = km

# ===== Seasonal =====
seasonal = {}
for r in db.execute("SELECT code, factors FROM seasonal").fetchall():
    seasonal[r["code"]] = json.loads(r["factors"])
data["seasonal"] = seasonal

# ===== Trades (load once, shared across positions) =====
all_trades_raw = db.execute("SELECT id, date, time, code, name, type, qty, price, commission, stamp_tax, settlement FROM trades ORDER BY date, time").fetchall()
all_trades = []
for r in all_trades_raw:
    # compute additional fees: transfer_fee ~= qty/1000 (min 1), regulatory_fee ~= price*qty*0.002‰, handling_fee ~= price*qty*0.00487‰
    q = abs(r["qty"]); pr = r["price"]
    tf = max(1.0, round(q / 1000.0 * 1.0, 2))  # transfer fee ~1 yuan per 1000 shares
    rf = round(q * pr * 0.00002, 2)  # regulatory fee
    hf = round(q * pr * 0.0000487, 2)  # handling fee
    all_trades.append({
        "date": r["date"], "time": r["time"], "code": r["code"], "name": r["name"],
        "type": r["type"], "qty": int(r["qty"]), "price": r["price"],
        "commission": r["commission"], "stamp_tax": r["stamp_tax"],
        "transfer_fee": tf, "regulatory_fee": rf, "handling_fee": hf,
        "settlement": r["settlement"]
    })
data["all_trades"] = all_trades

# ===== Positions (current) =====
positions = {}
for r in db.execute("SELECT * FROM positions").fetchall():
    code = r["code"]
    # Dividends
    divs = [dict(r2) for r2 in db.execute("SELECT date, amount, price FROM dividends WHERE code=? ORDER BY date", [code]).fetchall()]
    # Trades for this stock
    stock_trades = [t for t in all_trades if t["code"] == code]
    # Fee totals
    total_comm = sum(t["commission"] for t in stock_trades)
    total_stamp = sum(t["stamp_tax"] for t in stock_trades)
    total_other = sum(t["transfer_fee"] + t["regulatory_fee"] + t["handling_fee"] for t in stock_trades)
    positions[code] = {
        "code": code, "name": r["name"], "qty": r["qty"],
        "total_cost": r["total_cost"], "avg_cost": r["avg_cost"],
        "realized_pnl": r["realized_pnl"],
        "dividends": divs,
        "total_commission": total_comm, "total_stamp_tax": total_stamp,
        "total_other_fees": total_other,
        "trades": stock_trades
    }
    # Also add flat dividends_XXX key
    data[f"dividends_{code}"] = divs
data["current_positions"] = positions

# ===== Closed positions =====
closed = {}
for r in db.execute("SELECT * FROM closed_positions").fetchall():
    code = r["code"]
    stock_trades = [t for t in all_trades if t["code"] == code]
    # Compute fee totals from actual trades
    total_comm = sum(t["commission"] for t in stock_trades)
    total_stamp = sum(t["stamp_tax"] for t in stock_trades)
    total_other = sum(t["transfer_fee"] + t["regulatory_fee"] + t["handling_fee"] for t in stock_trades)
    closed[code] = {
        "code": code, "name": r["name"],
        "realized_pnl": r["realized_pnl"], "dividends_total": r["dividends_total"],
        "total_commission": total_comm or r["total_commission"],
        "total_stamp_tax": total_stamp or r["total_stamp_tax"],
        "total_other_fees": total_other or r["total_other_fees"],
        "trades": stock_trades
    }
data["closed_positions"] = closed

# ===== Monthly changes (per stock) =====
for code, bars in km.items():
    mc = [[b[0], b[6]] for b in bars if b[6] != 0]  # [date, change_pct]
    data[f"monthly_changes_{code}"] = mc

# ===== Daily predictions =====
preds = []
for r in db.execute("SELECT * FROM daily_predictions ORDER BY date DESC, code").fetchall():
    pid = r["id"]
    hourly = [dict(h) for h in db.execute("SELECT * FROM prediction_hourly WHERE pred_id=? ORDER BY id", [pid]).fetchall()]
    sigs = {s["name"]: {"value": s["value"], "direction": s["direction"], "raw": s["raw_value"]}
            for s in db.execute("SELECT * FROM prediction_signals WHERE pred_id=?", [pid]).fetchall()}
    preds.append({
        "date": r["date"], "code": r["code"], "prev_close": r["prev_close"],
        "next_day": {"direction": r["direction"], "confidence": r["confidence"],
            "high": r["high"], "low": r["low"], "advice": r["advice"], "entry_zone": r["entry_zone"]},
        "hourly": [{"block": h["block"], "pred_open": h["pred_open"], "pred_high": h["pred_high"],
            "pred_low": h["pred_low"], "pred_close": h["pred_close"], "direction": h["direction"],
            "strength": h["strength"], "note": h["note"]} for h in hourly],
        "signals": sigs,
        "actual": {"open": r["actual_open"], "high": r["actual_high"], "low": r["actual_low"],
            "close": r["actual_close"],
            "next_day_direction_hit": bool(r["dir_hit"]) if r["dir_hit"] is not None else None,
            "daily_range_hit": bool(r["range_hit"]) if r["range_hit"] is not None else None,
            "hourly_hits": [h.get("hit") for h in hourly]}
    })
data["daily_predictions"] = preds

# ===== Learning params =====
lp = {}
for r in db.execute("SELECT * FROM learning_params").fetchall():
    lp[r["code"]] = {
        "signal_weights": json.loads(r["signal_weights"]),
        "hourly_bias": json.loads(r["hourly_bias"]),
        "seasonal_adj": json.loads(r["seasonal_adj"]),
        "confidence_beta": json.loads(r["confidence_beta"]),
        "learning_rate": r["learning_rate"], "mw_beta": r["mw_beta"],
        "update_count": r["update_count"]
    }
data["learning_params"] = lp

# ===== Accuracy stats =====
acc = {}
for r in db.execute("SELECT * FROM accuracy_stats ORDER BY code, period").fetchall():
    code = r["code"]
    if code not in acc: acc[code] = {}
    acc[code][r["period"]] = {
        "direction": {"correct": r["dir_correct"], "total": r["dir_total"], "rate": r["dir_rate"]},
        "range": {"correct": r["range_correct"], "total": r["range_total"], "rate": r["range_rate"]},
        "hourly": json.loads(r["hourly_stats"])
    }
data["accuracy_stats"] = acc

# ===== News =====
news = []
for r in db.execute("SELECT id, date, code, title, summary, source, sentiment, major FROM news ORDER BY date DESC").fetchall():
    news.append({"date": r["date"], "code": r["code"], "title": r["title"],
        "summary": r["summary"], "source": r["source"], "sentiment": r["sentiment"],
        "major": bool(r["major"])})
data["news"] = news

# ===== Expert reports =====
er = []
for r in db.execute("SELECT * FROM expert_reports ORDER BY date DESC").fetchall():
    er.append(json.loads(r["report_data"]))
data["expert_reports"] = er

db.close()

# ===== Inject into HTML =====
html_path = os.path.join(ROOT, 'deliverables', 'bank-stock-system.html')
with open(html_path, 'r', encoding='utf-8') as f:
    html = f.read()

data_json = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
html = re.sub(r'(let|const|var)( DATA = )\{.*?\};\n', r'\1\2' + data_json + ';\n', html, flags=re.DOTALL)

with open(html_path, 'w', encoding='utf-8') as f:
    f.write(html)

# Verify
m = re.search(r'(let|const|var) DATA = ({.*?});\s*', html, re.DOTALL)
if m:
    vdata = json.loads(m.group(2))
    keys = list(vdata.keys())
    print(f"HTML re-injected from SQLite: {len(keys)} top-level keys")
    print(f"  watchlist:{len(vdata.get('watchlist',[]))}  kline_daily:{sum(len(v) for v in vdata.get('kline_daily',{}).values())}")
    print(f"  positions:{len(vdata.get('current_positions',{}))}  closed:{len(vdata.get('closed_positions',{}))}")
    print(f"  trades:{len(vdata.get('all_trades',[]))}  preds:{len(vdata.get('daily_predictions',[]))}  news:{len(vdata.get('news',[]))}")
else:
    print("ERROR: DATA block not found in HTML!")
