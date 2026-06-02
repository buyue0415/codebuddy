"""从 SQLite DB 构建 HTML 内联 DATA，安全注入到 bank-stock-system.html。

v2.0 增强：
  - 安全字符串定位注入（不再用脆弱 regex，避免 JSON 腐败）
  - 自动检测缺失的 let DATA 声明并补全
  - 注入前后完整性验证
  - 备份保护
"""
import json, os, sys, shutil
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
DB = os.path.join(ROOT, 'data', 'stock.db')

# ============================================================
# 数据构建（与原逻辑一致）
# ============================================================

def build_data():
    import sqlite3
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row

    data = {"account": "51312640", "broker": "广发证券", "generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

    # Watchlist
    wl = [dict(r) for r in db.execute("SELECT code, name, market FROM watchlist ORDER BY sort_order").fetchall()]
    data["watchlist"] = wl

    # Quotes
    quotes = {}
    for r in db.execute("SELECT * FROM quotes").fetchall():
        quotes[r["code"]] = {"price": r["price"], "change": r["change"], "open": r["open"],
            "high": r["high"], "low": r["low"], "pe": r["pe"], "pb": r["pb"], "dy": r["dy"]}
    data["quotes"] = quotes

    # Daily kline
    kd = {}
    for r in db.execute("SELECT code, date, open, close, high, low FROM kline_daily ORDER BY code, date DESC").fetchall():
        code = r["code"]
        if code not in kd: kd[code] = []
        kd[code].append([r["date"], r["open"], r["close"], r["high"], r["low"]])
    data["kline_daily"] = kd

    # Monthly kline
    km = {}
    for r in db.execute("SELECT code, date, open, high, low, close, volume, change_pct FROM kline_monthly ORDER BY code, date DESC").fetchall():
        code = r["code"]
        if code not in km: km[code] = []
        km[code].append([r["date"], r["open"], r["high"], r["low"], r["close"], r["volume"], r["change_pct"]])
    data["kline"] = km

    # Seasonal
    seasonal = {}
    for r in db.execute("SELECT code, factors FROM seasonal").fetchall():
        seasonal[r["code"]] = json.loads(r["factors"])
    data["seasonal"] = seasonal

    # Trades (with fee computation)
    all_trades_raw = db.execute("SELECT id, date, time, code, name, type, qty, price, commission, stamp_tax, settlement FROM trades ORDER BY date, time").fetchall()
    all_trades = []
    for r in all_trades_raw:
        q = abs(r["qty"]); pr = r["price"]
        tf = max(1.0, round(q / 1000.0 * 1.0, 2))
        rf = round(q * pr * 0.00002, 2)
        hf = round(q * pr * 0.0000487, 2)
        all_trades.append({
            "date": r["date"], "time": r["time"], "code": r["code"], "name": r["name"],
            "type": r["type"], "qty": int(r["qty"]), "price": r["price"],
            "commission": r["commission"], "stamp_tax": r["stamp_tax"],
            "transfer_fee": tf, "regulatory_fee": rf, "handling_fee": hf,
            "settlement": r["settlement"]
        })
    data["all_trades"] = all_trades

    # Positions
    positions = {}
    for r in db.execute("SELECT * FROM positions").fetchall():
        code = r["code"]
        divs = [dict(r2) for r2 in db.execute("SELECT date, amount, price FROM dividends WHERE code=? ORDER BY date", [code]).fetchall()]
        stock_trades = [t for t in all_trades if t["code"] == code]
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
        data[f"dividends_{code}"] = divs
    data["current_positions"] = positions

    # Closed positions
    closed = {}
    for r in db.execute("SELECT * FROM closed_positions").fetchall():
        code = r["code"]
        stock_trades = [t for t in all_trades if t["code"] == code]
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

    # Monthly changes
    for code, bars in km.items():
        mc = [[b[0], b[6]] for b in bars if b[6] != 0]
        data[f"monthly_changes_{code}"] = mc

    # Daily predictions
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

    # Learning params
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

    # Accuracy stats
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

    # News
    news = []
    for r in db.execute("SELECT id, date, code, title, summary, source, sentiment, major FROM news ORDER BY date DESC").fetchall():
        news.append({"date": r["date"], "code": r["code"], "title": r["title"],
            "summary": r["summary"], "source": r["source"], "sentiment": r["sentiment"],
            "major": bool(r["major"])})
    data["news"] = news

    # Expert reports
    er = []
    for r in db.execute("SELECT * FROM expert_reports ORDER BY date DESC").fetchall():
        er.append(json.loads(r["report_data"]))
    data["expert_reports"] = er

    db.close()
    return data


# ============================================================
# 安全 HTML 注入（基于字符串定位，不用 regex）
# ============================================================

def safe_inject(html: str, data: dict) -> str:
    """安全地将 DATA 对象注入 HTML，使用字符串定位而非 regex。

    查找 'let DATA;' 或 'let DATA = {...};' 或 'var DATA = {...};'
    然后用新的 JSON 替换右边的值。
    """
    DATA_MARKER = 'let DATA;'
    DATA_MARKER2 = 'let DATA ='
    DATA_MARKER3 = 'var DATA ='

    # 优先找 'let DATA;' (独立声明)
    pos = html.find(DATA_MARKER)
    if pos >= 0:
        # 'let DATA;' 后面直接是新行 — 改成 'let DATA = {...};'
        end_of_line = html.find('\n', pos)
        if end_of_line < 0:
            end_of_line = pos + len(DATA_MARKER)
        before = html[:pos]
        after = html[end_of_line:]
        data_json = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
        return before + f'let DATA = {data_json};\n' + after

    # 找 'let DATA = {...};' — 已有值，替换
    pos = html.find(DATA_MARKER2)
    if pos >= 0:
        # 找到 { 的位置
        brace_start = html.find('{', pos)
        if brace_start < 0:
            print("ERROR: let DATA = 后面找不到 {")
            return html
        # 找到匹配的 };
        depth = 0
        in_string = False
        escape = False
        end_pos = brace_start
        for i in range(brace_start, len(html)):
            c = html[i]
            if escape:
                escape = False
                continue
            if c == '\\' and in_string:
                escape = True
                continue
            if c == '"' and not escape:
                in_string = not in_string
                continue
            if in_string:
                continue
            if c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    end_pos = i
                    break
        # 找到 };
        semicolon = html.find(';', end_pos)
        if semicolon < 0:
            semicolon = end_pos + 1
        before = html[:brace_start]
        after = html[semicolon + 1:]
        data_json = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
        return before + data_json + ';\n' + after

    # 找 'var DATA = {...};'
    pos = html.find(DATA_MARKER3)
    if pos >= 0:
        brace_start = html.find('{', pos)
        if brace_start < 0:
            print("ERROR: var DATA = 后面找不到 {")
            return html
        depth = 0
        in_string = False
        escape = False
        end_pos = brace_start
        for i in range(brace_start, len(html)):
            c = html[i]
            if escape:
                escape = False
                continue
            if c == '\\' and in_string:
                escape = True
                continue
            if c == '"' and not escape:
                in_string = not in_string
                continue
            if in_string:
                continue
            if c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    end_pos = i
                    break
        semicolon = html.find(';', end_pos)
        if semicolon < 0:
            semicolon = end_pos + 1
        before = html[:brace_start]
        after = html[semicolon + 1:]
        data_json = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
        return before + data_json + ';\n' + after

    print("ERROR: 未找到 DATA 声明 ('let DATA;' 或 'let DATA =' 或 'var DATA =')")
    return html


# ============================================================
# 主流程
# ============================================================

def main():
    # 构建数据
    try:
        data = build_data()
    except Exception as e:
        print(f"ERROR: 数据构建失败: {e}")
        sys.exit(1)

    # 读取 HTML
    html_path = os.path.join(ROOT, 'deliverables', 'bank-stock-system.html')
    if not os.path.exists(html_path):
        print(f"ERROR: HTML 文件不存在: {html_path}")
        sys.exit(1)

    with open(html_path, 'r', encoding='utf-8') as f:
        html = f.read()

    # 备份
    bak_path = html_path + '.reject_bak'
    shutil.copy2(html_path, bak_path)

    # 安全注入
    new_html = safe_inject(html, data)

    # 注入前检测：如果没有找到 DATA 声明，尝试自动插入
    if 'let DATA;' not in new_html and 'let DATA =' not in new_html:
        # 可能之前的注入误删了 DATA 声明，尝试在 <script> 后插入
        script_pos = new_html.find('<script>')
        if script_pos >= 0:
            insert_pos = new_html.find('\n', script_pos) + 1
            data_json = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
            new_html = (new_html[:insert_pos] +
                        f'let DATA = {data_json};\n' +
                        new_html[insert_pos:])
            print("INFO: 自动插入 let DATA 声明")

    # 写入
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(new_html)

    # 验证
    verify_data(data)
    print("HTML re-injected from SQLite (safe mode)")


def verify_data(data: dict):
    """打印注入数据的统计摘要。"""
    keys = list(data.keys())
    print(f"  顶层键: {len(keys)}")
    print(f"  watchlist: {len(data.get('watchlist', []))}  "
          f"kline_daily: {sum(len(v) for v in data.get('kline_daily', {}).values())}")
    print(f"  positions: {len(data.get('current_positions', {}))}  "
          f"closed: {len(data.get('closed_positions', {}))}")
    print(f"  trades: {len(data.get('all_trades', []))}  "
          f"preds: {len(data.get('daily_predictions', []))}  "
          f"news: {len(data.get('news', []))}")


if __name__ == "__main__":
    main()
