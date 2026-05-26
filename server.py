"""
股票投资管理系统 - 本地API服务器
启动: python server.py
端口: 8765
"""
import http.server
import json
import os
import sqlite3
import subprocess
import sys
import time
import traceback
import urllib.parse
import threading
from datetime import datetime
from socketserver import ThreadingMixIn

PORT = 8765
ROOT = os.path.dirname(os.path.abspath(__file__))
PYTHON = r"C:\Users\28312\.workbuddy\binaries\python\versions\3.14.3\python.exe"
NODE = r"C:\Users\28312\.workbuddy\binaries\node\versions\22.12.0\node.exe"

# Cache for init data (Category B optimization)
_init_cache = None
_init_cache_time = 0
CACHE_TTL = 5

# Reusable DB connection (Category B optimization)
_server_db = None

def get_server_db():
    global _server_db
    if _server_db is None:
        _server_db = sqlite3.connect(os.path.join(ROOT, "data", "stock.db"))
        _server_db.row_factory = sqlite3.Row
    return _server_db

sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

try:
    from db_helper import (get_stock_search, get_watchlist, get_watchlist_codes,
        add_watchlist, remove_watchlist, get_kline_daily, get_kline_monthly,
        get_quotes, get_positions, get_daily_predictions, get_learning_params,
        get_accuracy_stats, get_news, get_expert_reports, get_seasonal,
        get_config, _calc_fees, get_current_positions, get_closed_positions,
        get_trades, get_dividends, get_all_kline_daily, get_all_kline_monthly,
        get_all_predictions, get_all_seasonal, get_all_accuracy_stats,
        get_all_monthly_changes, get_all_learning_params)
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False


def json_response(handler, data, status=200):
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.end_headers()
    handler.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))


def read_json(path):
    with open(os.path.join(ROOT, path), "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path, data):
    with open(os.path.join(ROOT, path), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# --- Stock Search ---
_stock_cache = None

def _load_stocks():
    global _stock_cache
    if _stock_cache is None:
        try:
            _stock_cache = read_json("data/a_stocks.json")
        except:
            _stock_cache = []
    return _stock_cache

def search_stocks(keyword):
    stocks = _load_stocks()
    if not stocks or not keyword:
        return []
    kw = keyword.lower().strip()
    # Category D: Normalize full-width characters for Chinese name matching
    kw = kw.replace('\u3000', ' ').replace('\uff41', 'a').replace('\uff42', 'b')
    results = []
    for s in stocks:
        score = 0
        code = s.get("code", "")
        name = s.get("name", "")
        py = s.get("py", "")
        if code.startswith(kw):
            score += 100
        elif code.find(kw) > 0:
            score += 60
        if name.find(kw) >= 0:
            score += 80 - name.find(kw) * 0.5
        if kw.isalpha() and py.find(kw) >= 0:
            # Also try partial pinyin matching for multi-character queries
            if py.startswith(kw):
                score += 50
            else:
                score += 30
        if score == 0 and len(kw) > 1:
            match_all = all(ch in py for ch in kw if ch.isalpha())
            if match_all:
                score += 10
        if score > 0:
            results.append({"code": code, "name": name, "market": s.get("market", "sh"), "py": py, "score": score})
    results.sort(key=lambda x: -x["score"])
    return results[:15]


# Refresh status tracking — prevents concurrent runs
_refresh_lock = threading.Lock()
_refresh_in_progress = False

def run_script(script_name, timeout=60):
    """Run a Python script in scripts/ directory, return success and output"""
    script_path = os.path.join(ROOT, "scripts", script_name)
    if not os.path.exists(script_path):
        return False, f"Script not found: {script_path}"
    try:
        result = subprocess.run(
            [PYTHON, script_path],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = result.stdout[-3000:] if len(result.stdout) > 3000 else result.stdout
        if result.stderr:
            err = result.stderr[-1000:] if len(result.stderr) > 1000 else result.stderr
            output += "\n[STDERR]\n" + err
        return result.returncode == 0, output.strip()
    except subprocess.TimeoutExpired:
        return False, f"Script timed out after {timeout}s"
    except Exception as e:
        return False, str(e)


def _build_init_data() -> dict:
    """Build full init data dict from SQLite (same as /api/v2/init).
    
    Category B: Implements response caching with TTL to avoid
    redundant DB queries within CACHE_TTL seconds.
    """
    global _init_cache, _init_cache_time
    import json

    now = time.time()
    if _init_cache and (now - _init_cache_time) < CACHE_TTL:
        return _init_cache

    init_data = {"account": "51312640", "broker": "广发证券", "generated": datetime.now().strftime("%Y-%m-%d %H:%M")}
    try:
        init_data["watchlist"] = [dict(r) for r in get_watchlist()] if DB_AVAILABLE else []
    except Exception:
        init_data["watchlist"] = []
    try:
        init_data["quotes"] = get_quotes() if DB_AVAILABLE else {}
    except Exception:
        init_data["quotes"] = {}
    try:
        init_data["positions"] = get_positions() if DB_AVAILABLE else {"current_positions": {}, "closed_positions": {}, "all_trades": []}
    except Exception:
        init_data["positions"] = {"current_positions": {}, "closed_positions": {}, "all_trades": []}
    try:
        if DB_AVAILABLE:
            db = get_server_db()
            kd = {}
            for r in db.execute("SELECT code,date,open,close,high,low FROM kline_daily ORDER BY code,date DESC").fetchall():
                kd.setdefault(r[0], []).append([r[1], r[2], r[3], r[4], r[5]])
            init_data["kline_daily"] = kd
        else:
            init_data["kline_daily"] = {}
    except Exception:
        init_data["kline_daily"] = {}
    try:
        init_data["daily_predictions"] = get_all_predictions() if DB_AVAILABLE else []
    except Exception:
        init_data["daily_predictions"] = []
    try:
        if DB_AVAILABLE:
            db = get_server_db()
            news = [dict(r) for r in db.execute("SELECT id,date,code,title,summary,source,sentiment,major FROM news ORDER BY date DESC").fetchall()]
            for n in news:
                n["major"] = bool(n["major"])
            init_data["news"] = news
            er = [json.loads(r["report_data"]) for r in db.execute("SELECT * FROM expert_reports ORDER BY date DESC").fetchall()]
            init_data["expert_reports"] = er
        else:
            init_data["news"] = []
            init_data["expert_reports"] = []
    except Exception:
        init_data["news"] = []
        init_data["expert_reports"] = []
    try:
        init_data["kline"] = get_all_kline_monthly() if DB_AVAILABLE else {}
    except Exception:
        init_data["kline"] = {}
    try:
        init_data["seasonal"] = get_all_seasonal() if DB_AVAILABLE else {}
    except Exception:
        init_data["seasonal"] = {}
    try:
        init_data["learning_params"] = {}
        if DB_AVAILABLE:
            db = get_server_db()
            codes = tuple(s["code"] for s in init_data.get("watchlist", []))
            if codes:
                for r in db.execute(
                    f"SELECT * FROM learning_params WHERE code IN ({','.join('?' * len(codes))})",
                    codes
                ).fetchall():
                    lp = {
                        'signal_weights': json.loads(r['signal_weights']),
                        'hourly_bias': json.loads(r['hourly_bias']),
                        'seasonal_adj': json.loads(r['seasonal_adj']),
                        'confidence_beta': json.loads(r['confidence_beta']),
                        'learning_rate': r['learning_rate'], 'mw_beta': r['mw_beta'],
                        'update_count': r['update_count'],
                    }
                    init_data["learning_params"][r["code"]] = lp
    except Exception:
        pass
    try:
        init_data["accuracy_stats"] = get_all_accuracy_stats() if DB_AVAILABLE else {}
    except Exception:
        init_data["accuracy_stats"] = {}

    # Only cache if watchlist is non-empty (prevent caching incomplete data)
    if init_data.get("watchlist"):
        _init_cache = init_data
        _init_cache_time = now
    return init_data


class APIHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/" or path == "/index.html":
            self.serve_file("deliverables/bank-stock-system.html", "text/html")
        elif path == "/dbview":
            self._serve_db_viewer()
        elif path == "/api/watchlist":
            """Return watchlist from SQLite (migrated from JSON)."""
            try:
                wl = [dict(r) for r in get_watchlist()] if DB_AVAILABLE else []
                json_response(self, {"success": True, "data": {"stocks": wl}})
            except Exception as e:
                json_response(self, {"success": False, "error": str(e)}, 500)
        elif path == "/api/system-data":
            # 替换为 SQLite 全量数据（兼容旧版前端调用）
            try:
                data = _build_init_data()
                json_response(self, {"success": True, "data": data})
            except Exception as e:
                json_response(self, {"success": False, "error": str(e)}, 500)
        elif path == "/api/v2/init":
            try:
                json_response(self, {"success": True, "data": _build_init_data()})
            except Exception as e:
                json_response(self, {"success": False, "error": str(e)}, 500)

        elif path == "/api/audit":
            ok, out = run_script("audit_system.py")
            json_response(self, {"success": ok, "output": out})

        # ===== DB-based API endpoints (new) =====
        elif path == "/api/v2/quotes":
            try:
                json_response(self, {"success": True, "data": get_quotes()}) if DB_AVAILABLE else json_response(self, {"success": False, "error": "DB not available"}, 500)
            except Exception as e:
                json_response(self, {"success": False, "error": str(e)}, 500)

        elif path == "/api/v2/positions":
            try:
                data = get_positions()
                json_response(self, {"success": True, "data": data}) if DB_AVAILABLE else json_response(self, {"success": False, "error": "DB not available"}, 500)
            except Exception as e:
                json_response(self, {"success": False, "error": str(e)}, 500)

        # K-line endpoints: single stock (?code=) and batch (?codes=)
        # Category A fix: check ?code= before assuming batch request
        elif path == "/api/v2/kline/daily":
            q = urllib.parse.parse_qs(parsed.query)
            code = q.get("code", [None])[0]
            if code:
                try:
                    data = get_kline_daily(code) if DB_AVAILABLE else []
                    json_response(self, {"success": True, "data": data})
                except Exception as e:
                    json_response(self, {"success": False, "error": str(e)}, 500)
            else:
                codes = q.get("codes", [None])[0]
                try:
                    data = get_all_kline_daily(codes.split(",") if codes else None) if DB_AVAILABLE else {}
                    json_response(self, {"success": True, "data": data})
                except Exception as e:
                    json_response(self, {"success": False, "error": str(e)}, 500)

        elif path == "/api/v2/kline/monthly":
            q = urllib.parse.parse_qs(parsed.query)
            code = q.get("code", [None])[0]
            if code:
                try:
                    data = get_kline_monthly(code) if DB_AVAILABLE else []
                    json_response(self, {"success": True, "data": data})
                except Exception as e:
                    json_response(self, {"success": False, "error": str(e)}, 500)
            else:
                codes = q.get("codes", [None])[0]
                try:
                    data = get_all_kline_monthly(codes.split(",") if codes else None) if DB_AVAILABLE else {}
                    json_response(self, {"success": True, "data": data})
                except Exception as e:
                    json_response(self, {"success": False, "error": str(e)}, 500)

        # V0.6: Batch predictions (exact match, before startswith)
        elif path == "/api/v2/predictions/daily":
            try:
                data = get_all_predictions() if DB_AVAILABLE else []
                json_response(self, {"success": True, "data": data, "count": len(data)})
            except Exception as e:
                json_response(self, {"success": False, "error": str(e)}, 500)

        # V0.6: Single stock predictions with /{code} path (before startswith)
        elif path.startswith("/api/v2/predictions/daily/") and len(path) > len("/api/v2/predictions/daily/"):
            code = path.split("/api/v2/predictions/daily/")[1]
            try:
                data = get_daily_predictions(code) if code and DB_AVAILABLE else []
                json_response(self, {"success": True, "data": data})
            except Exception as e:
                json_response(self, {"success": False, "error": str(e)}, 500)

        elif path.startswith("/api/v2/news"):
            q = urllib.parse.parse_qs(parsed.query)
            filt = q.get("filter", ["all"])[0]
            try:
                data = get_news(filt) if DB_AVAILABLE else []
                json_response(self, {"success": True, "data": data})
            except Exception as e:
                json_response(self, {"success": False, "error": str(e)}, 500)

        elif path.startswith("/api/v2/expert"):
            try:
                data = get_expert_reports() if DB_AVAILABLE else []
                json_response(self, {"success": True, "data": data})
            except Exception as e:
                json_response(self, {"success": False, "error": str(e)}, 500)

        elif path == "/api/v2/learning":
            # Batch: GET /api/v2/learning (no query) returns all watchlist stocks
            # Single: GET /api/v2/learning?code=XXXX returns one stock
            q = urllib.parse.parse_qs(parsed.query)
            code = q.get("code", [""])[0]
            try:
                if code:
                    data = get_learning_params(code)
                    json_response(self, {"success": data is not None, "data": data})
                else:
                    data = get_all_learning_params() if DB_AVAILABLE else {}
                    json_response(self, {"success": True, "data": data})
            except Exception as e:
                json_response(self, {"success": False, "error": str(e)}, 500)

        # V0.6: Batch accuracy stats (exact path, before startswith)
        elif path == "/api/v2/accuracy":
            try:
                data = get_all_accuracy_stats() if DB_AVAILABLE else {}
                json_response(self, {"success": True, "data": data})
            except Exception as e:
                json_response(self, {"success": False, "error": str(e)}, 500)

        elif path.startswith("/api/v2/accuracy"):
            q = urllib.parse.parse_qs(parsed.query)
            code = q.get("code", [""])[0]
            try:
                data = get_accuracy_stats(code) if code and DB_AVAILABLE else {}
                json_response(self, {"success": True, "data": data})
            except Exception as e:
                json_response(self, {"success": False, "error": str(e)}, 500)

        # V0.6: Batch seasonal (exact match, must come BEFORE startswith)
        elif path == "/api/v2/seasonal":
            try:
                data = get_all_seasonal() if DB_AVAILABLE else {}
                json_response(self, {"success": True, "data": data})
            except Exception as e:
                json_response(self, {"success": False, "error": str(e)}, 500)

        # V0.6: Single stock seasonal (path /{code}, before startswith)
        elif path.startswith("/api/v2/seasonal/") and len(path) > len("/api/v2/seasonal/"):
            code = path.split("/api/v2/seasonal/")[1]
            try:
                data = get_seasonal(code) if code and DB_AVAILABLE else []
                json_response(self, {"success": True, "data": data})
            except Exception as e:
                json_response(self, {"success": False, "error": str(e)}, 500)

        # Legacy: Single stock seasonal with ?code= query param (path.startswith fallback)
        elif path.startswith("/api/v2/seasonal"):
            q = urllib.parse.parse_qs(parsed.query)
            code = q.get("code", [""])[0]
            try:
                data = get_seasonal(code) if code and DB_AVAILABLE else []
                json_response(self, {"success": True, "data": data})
            except Exception as e:
                json_response(self, {"success": False, "error": str(e)}, 500)

        # ===== V0.6 New independent RESTful endpoints =====

        elif path == "/api/v2/config":
            try:
                cfg = get_config()
                json_response(self, {"success": True, "data": cfg})
            except Exception as e:
                json_response(self, {"success": False, "error": str(e)}, 500)

        elif path == "/api/v2/watchlist":
            try:
                data = [dict(r) for r in get_watchlist()] if DB_AVAILABLE else []
                json_response(self, {"success": True, "data": data, "count": len(data)})
            except Exception as e:
                json_response(self, {"success": False, "error": str(e)}, 500)

        elif path.startswith("/api/v2/quotes/") and len(path) > len("/api/v2/quotes/"):
            # Single stock quote: /api/v2/quotes/{code}
            code = path.split("/api/v2/quotes/")[1]
            try:
                quotes = get_quotes() if DB_AVAILABLE else {}
                data = quotes.get(code, {})
                json_response(self, {"success": True, "data": data})
            except Exception as e:
                json_response(self, {"success": False, "error": str(e)}, 500)

        elif path == "/api/v2/positions/current":
            try:
                data = get_current_positions() if DB_AVAILABLE else {}
                json_response(self, {"success": True, "data": data, "count": len(data)})
            except Exception as e:
                json_response(self, {"success": False, "error": str(e)}, 500)

        elif path == "/api/v2/positions/closed":
            try:
                data = get_closed_positions() if DB_AVAILABLE else {}
                json_response(self, {"success": True, "data": data, "count": len(data)})
            except Exception as e:
                json_response(self, {"success": False, "error": str(e)}, 500)

        elif path == "/api/v2/trades":
            q = urllib.parse.parse_qs(parsed.query)
            code = q.get("code", [""])[0] or None
            try:
                data = get_trades(code) if DB_AVAILABLE else []
                json_response(self, {"success": True, "data": data, "count": len(data)})
            except Exception as e:
                json_response(self, {"success": False, "error": str(e)}, 500)

        elif path.startswith("/api/v2/trades/") and len(path) > len("/api/v2/trades/"):
            code = path.split("/api/v2/trades/")[1]
            try:
                data = get_trades(code) if DB_AVAILABLE else []
                json_response(self, {"success": True, "data": data, "count": len(data)})
            except Exception as e:
                json_response(self, {"success": False, "error": str(e)}, 500)

        elif path == "/api/v2/dividends":
            q = urllib.parse.parse_qs(parsed.query)
            code = q.get("code", [""])[0] or None
            try:
                data = get_dividends(code) if DB_AVAILABLE else []
                json_response(self, {"success": True, "data": data, "count": len(data)})
            except Exception as e:
                json_response(self, {"success": False, "error": str(e)}, 500)

        elif path.startswith("/api/v2/dividends/") and len(path) > len("/api/v2/dividends/"):
            code = path.split("/api/v2/dividends/")[1]
            try:
                data = get_dividends(code) if DB_AVAILABLE else []
                json_response(self, {"success": True, "data": data, "count": len(data)})
            except Exception as e:
                json_response(self, {"success": False, "error": str(e)}, 500)

        # Batch kline endpoints (no code = all watchlist stocks)
        elif path == "/api/v2/kline/daily":
            q = urllib.parse.parse_qs(parsed.query)
            codes = q.get("codes", [None])[0]
            try:
                data = get_all_kline_daily(codes.split(",") if codes else None) if DB_AVAILABLE else {}
                json_response(self, {"success": True, "data": data})
            except Exception as e:
                json_response(self, {"success": False, "error": str(e)}, 500)

        elif path == "/api/v2/kline/monthly":
            q = urllib.parse.parse_qs(parsed.query)
            codes = q.get("codes", [None])[0]
            try:
                data = get_all_kline_monthly(codes.split(",") if codes else None) if DB_AVAILABLE else {}
                json_response(self, {"success": True, "data": data})
            except Exception as e:
                json_response(self, {"success": False, "error": str(e)}, 500)

        # Single stock endpoints with /{code} URL path
        elif path.startswith("/api/v2/kline/daily/") and len(path) > len("/api/v2/kline/daily/"):
            code = path.split("/api/v2/kline/daily/")[1]
            try:
                data = get_kline_daily(code) if code and DB_AVAILABLE else []
                json_response(self, {"success": True, "data": data})
            except Exception as e:
                json_response(self, {"success": False, "error": str(e)}, 500)

        elif path.startswith("/api/v2/kline/monthly/") and len(path) > len("/api/v2/kline/monthly/"):
            code = path.split("/api/v2/kline/monthly/")[1]
            try:
                data = get_kline_monthly(code) if code and DB_AVAILABLE else []
                json_response(self, {"success": True, "data": data})
            except Exception as e:
                json_response(self, {"success": False, "error": str(e)}, 500)

        elif path.startswith("/api/v2/predictions/daily/") and len(path) > len("/api/v2/predictions/daily/"):
            code = path.split("/api/v2/predictions/daily/")[1]
            try:
                data = get_daily_predictions(code) if code and DB_AVAILABLE else []
                json_response(self, {"success": True, "data": data})
            except Exception as e:
                json_response(self, {"success": False, "error": str(e)}, 500)

        elif path.startswith("/api/v2/seasonal/") and len(path) > len("/api/v2/seasonal/"):
            code = path.split("/api/v2/seasonal/")[1]
            try:
                data = get_seasonal(code) if code and DB_AVAILABLE else []
                json_response(self, {"success": True, "data": data})
            except Exception as e:
                json_response(self, {"success": False, "error": str(e)}, 500)

        # ===== Existing JSON-based endpoints =====
        elif path == "/api/search/stocks":
            q = parsed.query
            params = urllib.parse.parse_qs(q)
            keyword = params.get("q", [""])[0].strip()
            result = search_stocks(keyword) if keyword else []
            json_response(self, {"success": True, "data": result})
        elif path.startswith("/deliverables/") or path.startswith("/data/") or path.startswith("/scripts/"):
            # Serve static files but block .py execution
            if path.endswith(".py"):
                json_response(self, {"error": "Forbidden"}, 403)
            else:
                self.serve_file(path.lstrip("/"))
        else:
            super().do_GET()

    def do_DELETE(self):
        """Handle DELETE requests (V0.6 RESTful)"""
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        # DELETE /api/v2/watchlist/{code}
        if path.startswith("/api/v2/watchlist/") and len(path) > len("/api/v2/watchlist/"):
            code = path.split("/api/v2/watchlist/")[1]
            try:
                from db_helper import remove_watchlist
                remove_watchlist(code)
                # Also clean up related tables
                import sqlite3
                db = sqlite3.connect(os.path.join(ROOT, "data", "stock.db"))
                for tbl in ["kline_daily", "kline_monthly", "daily_predictions",
                             "prediction_hourly", "prediction_signals",
                             "seasonal", "learning_params", "accuracy_stats",
                             "dividends", "quotes"]:
                    db.execute(f"DELETE FROM {tbl} WHERE code=?", [code])
                db.commit(); db.close()

                json_response(self, {"success": True, "message": f"已移除 {code}"})
            except Exception as e:
                json_response(self, {"success": False, "error": str(e)}, 500)
        else:
            json_response(self, {"success": False, "error": "Unknown DELETE endpoint"}, 404)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        content_length = int(self.headers.get("Content-Length", 0))

        # File upload endpoint — parse multipart before JSON
        if path == "/api/upload/statement":
            self._handle_statement_upload(content_length)
            return

        # Regular JSON body
        body = self.rfile.read(content_length) if content_length else b"{}"
        try:
            params = json.loads(body) if body else {}
        except json.JSONDecodeError:
            params = {}

        try:
            # === WATCHLIST CRUD (V0.6 RESTful + legacy compat) ===

            # NEW: POST /api/v2/watchlist (RESTful)
            if path == "/api/v2/watchlist":
                code = params.get("code", "").strip()
                name = params.get("name", "").strip()
                market = params.get("market", "sh").strip()
                if not code or not name:
                    json_response(self, {"success": False, "error": "code and name required"}, 400)
                    return

                if DB_AVAILABLE:
                    wl = [dict(r) for r in get_watchlist()]
                    if any(s["code"] == code for s in wl):
                        json_response(self, {"success": False, "error": f"股票 {code} 已存在"}, 409)
                        return
                    add_watchlist(code, name, market)

                ok1, out1 = run_script("sync_all.py", 120)
                json_response(self, {
                    "success": ok1,
                    "message": f"已添加 {name}({code})，全模块数据同步完成" if ok1 else "添加失败",
                    "watchlist": wl_json,
                    "output": out1[-500:] if out1 else "",
                })

            elif path == "/api/watchlist/add":
                code = params.get("code", "").strip()
                name = params.get("name", "").strip()
                market = params.get("market", "sh").strip()
                if not code or not name:
                    json_response(self, {"success": False, "error": "code and name required"}, 400)
                    return

                if DB_AVAILABLE:
                    wl_db = [dict(r) for r in get_watchlist()]
                    if any(s["code"] == code for s in wl_db):
                        json_response(self, {"success": False, "error": f"股票 {code} 已存在"}, 409)
                        return
                    add_watchlist(code, name, market)

                # Initialize data for new stock — sync ALL modules
                ok1, out1 = run_script("sync_all.py", 120)

                json_response(self, {
                    "success": ok1,
                    "message": f"已添加 {name}({code})，全模块数据同步完成" if ok1 else "添加失败",
                    "watchlist": [dict(r) for r in get_watchlist()] if DB_AVAILABLE else [],
                    "output": out1[-500:] if out1 else "",
                })

            elif path == "/api/watchlist/remove":
                code = params.get("code", "").strip()
                if not code:
                    json_response(self, {"success": False, "error": "code required"}, 400)
                    return

                sql_cleaned = False
                try:
                    from db_helper import remove_watchlist
                    remove_watchlist(code)
                    import sqlite3
                    db = sqlite3.connect(os.path.join(ROOT, "data", "stock.db"))
                    for tbl in ["kline_daily", "kline_monthly", "daily_predictions",
                                 "prediction_hourly", "prediction_signals",
                                 "seasonal", "learning_params", "accuracy_stats",
                                 "dividends", "quotes"]:
                        db.execute(f"DELETE FROM {tbl} WHERE code=?", [code])
                    db.commit()
                    db.close()
                    sql_cleaned = True
                except Exception as e:
                    print(f"[cleanup] SQLite cleanup warning: {e}")

                if not sql_cleaned:
                    json_response(self, {"success": False, "error": f"股票 {code} 不存在"}, 404)
                    return

                json_response(self, {
                    "success": True,
                    "message": f"已移除 {code}，数据已更新",
                })

            # === TRIGGERS ===
            elif path == "/api/trigger/news":
                ok, out = run_script("fetch_news.py", 60)
                json_response(self, {
                    "success": ok,
                    "output": out[-1000:] if out else "",
                    "message": "新闻已刷新" if ok else "新闻刷新失败",
                })

            elif path == "/api/trigger/update_statement":
                ok, out = run_script("update_from_statement.py", 30)
                ok2, out2 = run_script("reinject_from_db.py", 15)
                json_response(self, {
                    "success": ok and ok2,
                    "output": out[-1000:] if out else "",
                    "message": "持仓数据已更新，刷新页面查看" if ok else "更新失败",
                })

            elif path == "/api/trigger/predict":
                # Prevent concurrent refresh runs
                global _refresh_in_progress
                if _refresh_in_progress:
                    json_response(self, {"success": False, "error": "刷新已在运行中，请稍候"}, 429)
                    return
                _refresh_in_progress = True
                try:
                    ok, out = run_script("sync_all.py", 180)
                    if ok:
                        try:
                            fresh_data = _build_init_data()
                            json_response(self, {
                                "success": True,
                                "message": "全模块同步完成，数据已刷新",
                                "output": out[-1500:] if out else "",
                                "data": fresh_data,
                            })
                        except Exception:
                            json_response(self, {
                                "success": True,
                                "message": "全模块同步完成，刷新页面查看",
                                "output": out[-1000:] if out else "",
                            })
                    else:
                        json_response(self, {
                            "success": False,
                            "error": "同步失败",
                            "output": out[-1000:] if out else "",
                        })
                finally:
                    _refresh_in_progress = False

            elif path == "/api/v2/expert/import":
                report_json = params
                try:
                    from import_expert_report import import_report
                    ok, msg, warnings = import_report(report_json)
                    json_response(self, {"success": ok, "message": msg, "warnings": warnings})
                except Exception as e:
                    json_response(self, {"success": False, "error": str(e)}, 500)

            elif path == "/api/expert/import":
                self.path = "/api/v2/expert/import"
                self.do_POST()
                return

            elif path == "/api/trigger/expert":
                code = params.get("code", "")
                name = params.get("name", "")
                # Expert analysis requires trading-analysis skill (multi-agent workflow)
                # Cannot be run from subprocess - needs WorkBuddy context
                json_response(self, {
                    "success": True,
                    "message": f"专家分析需通过WorkBuddy交易分析团队执行。请使用 trading-analysis skill 对{name or code}进行完整Workflow A分析。",
                })

            else:
                json_response(self, {"success": False, "error": f"Unknown endpoint: {path}"}, 404)

        except Exception as e:
            json_response(self, {"success": False, "error": str(e), "trace": traceback.format_exc()[-500:]}, 500)

    def _handle_statement_upload(self, content_length):
        """Receive uploaded GF Securities statement xlsx, save and process"""
        import shutil, email

        content_type = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in content_type:
            json_response(self, {"success": False, "error": "需要 multipart/form-data"}, 400)
            return

        raw = self.rfile.read(content_length)
        boundary = content_type.split("boundary=")[1].strip()
        boundary_bytes = boundary.encode()

        parts = raw.split(b"--" + boundary_bytes)
        for part in parts:
            if b"filename=" not in part:
                continue
            header_end = part.find(b"\r\n\r\n")
            if header_end == -1:
                continue
            file_data = part[header_end + 4:]
            end = file_data.rfind(b"\r\n--" + boundary_bytes)
            if end >= 0:
                file_data = file_data[:end]
            else:
                file_data = file_data.rstrip(b"\r\n-")

            if len(file_data) < 100:
                continue

            dest = os.path.join(ROOT, "广发易淘金PC版-普通对账单结果查询.xlsx")
            bak = dest + ".bak"
            if os.path.exists(dest):
                shutil.copy2(dest, bak)
            with open(dest, "wb") as f:
                f.write(file_data)

            ok, out = run_script("update_from_statement.py", 30)
            ok2, out2 = run_script("reinject_from_db.py", 15)
            json_response(self, {
                "success": ok and ok2,
                "message": "对账单已更新，刷新页面查看" if ok else "解析失败",
                "output": out[-500:] if out else "",
            })
            return

        json_response(self, {"success": False, "error": "未找到上传文件"}, 400)

    def _serve_db_viewer(self):
        import sqlite3
        db_path = os.path.join(ROOT, "data", "stock.db")
        if not os.path.exists(db_path):
            self.send_response(404); self.end_headers(); return
        db = sqlite3.connect(db_path)

        table = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get("t", [""])[0]
        tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name").fetchall()]

        html = """<!DOCTYPE html><html><head><meta charset='utf-8'><title>DB Viewer</title>
<style>body{font:13px monospace;background:#1e1e1e;color:#d4d4d4;margin:0;padding:16px}
h2{color:#569cd6;margin:0 0 8px}.tabs{display:flex;gap:4px;flex-wrap:wrap;margin-bottom:16px}
.tab{padding:6px 14px;border-radius:4px;cursor:pointer;color:#9cdcfe;border:1px solid #3c3c3c;font-size:12px}
.tab:hover{background:#2a2a2a}.tab.active{background:#569cd6;color:#fff;border-color:#569cd6}
table{border-collapse:collapse;width:100%}th{background:#333;padding:6px 10px;text-align:left;position:sticky;top:0}
td{padding:4px 10px;border-bottom:1px solid #333;max-width:400px;overflow:hidden;white-space:nowrap}
tr:hover td{background:#2a2a2a}.num{color:#b5cea8}.text{color:#ce9178}.null{color:#666}
</style></head><body><h2>DB Viewer - data/stock.db</h2><div class='tabs'>"""

        for t in tables:
            active = "active" if t == table or (not table and t == tables[0]) else ""
            html += "<a class='tab {}' href='/dbview?t={}'>{}</a>".format(active, t, t)
        html += "</div>"

        if not table:
            table = tables[0] if tables else ""

        if table:
            cols = [c[1] for c in db.execute("PRAGMA table_info(" + table + ")")]
            html += "<h3>{}</h3><table><tr>".format(table)
            for c in cols:
                html += "<th>{}</th>".format(c)
            html += "</tr>"
            rows = db.execute("SELECT * FROM {} LIMIT 1000".format(table)).fetchall()
            for row in rows:
                html += "<tr>"
                for i, val in enumerate(row):
                    cls = "num" if isinstance(val, (int, float)) else "null" if val is None else "text"
                    display = str(val)[:200] if val is not None else "NULL"
                    html += "<td class='{}'>{}</td>".format(cls, display)
                html += "</tr>"
            html += "</table>"

        db.close()
        html += "</body></html>"
        data = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", len(data))
        self.end_headers()
        self.wfile.write(data)

    def serve_file(self, path, content_type=None):
        full_path = os.path.join(ROOT, path)
        if not os.path.exists(full_path):
            self.send_response(404)
            self.end_headers()
            return
        ct = content_type or "application/octet-stream"
        with open(full_path, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ct)
        self.send_header("Content-Length", len(data))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format, *args):
        # Quieter logging
        if "/api/" in self.path:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {self.command} {self.path}")


class ThreadedHTTPServer(ThreadingMixIn, http.server.HTTPServer):
    """Multi-threaded server that doesn't block on long requests."""
    daemon_threads = True


if __name__ == "__main__":
    print(f"[Stock] 股票投资管理系统 API 服务器")
    print(f"   地址: http://localhost:{PORT}")
    print(f"   目录: {ROOT}")
    print(f"   Ctrl+C 停止")
    print()
    server = ThreadedHTTPServer(("127.0.0.1", PORT), APIHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n服务器已停止")
        server.server_close()
