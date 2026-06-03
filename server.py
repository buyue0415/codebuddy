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
PYTHON = r"C:\Users\28312\.workbuddy\binaries\python\versions\3.12.6\python.exe"
NODE = r"C:\Users\28312\.workbuddy\binaries\node\versions\22.12.0\node.exe"

# Cache for init data (Category B optimization)
_init_cache = None
_init_cache_time = 0
CACHE_TTL = 5

# No global DB connection — each db_helper function opens its own
# connection with WAL mode and busy_timeout for thread safety.

# ─── 安全删除机制：分析层 / 交易层 隔离 ───
# 分析层（可清理）：自选股删除时，这些缓存/分析数据可安全清除
_ANALYTICAL_TABLES = [
    "kline_daily", "kline_monthly", "daily_predictions",
    "seasonal", "learning_params", "accuracy_stats",
    "quotes", "news",
]
# 交易层（受保护）：对账单导入模块的历史/持仓数据，NEVER 随自选股删除而清除
# 包括: positions, closed_positions, trades, dividends
# 这些数据来自券商对账单，代表真实资金流水，必须在整个生命周期中保持完整
_BROKER_TABLES = [
    "positions", "closed_positions", "trades", "dividends",
]

def _cleanup_stock_data(code):
    """删除自选股时，安全清除分析层数据，完整保留交易层数据。

    安全隔离机制：
      - 分析层（kline / predictions / seasonal / quotes / news / expert）：可清除
      - 交易层（positions / trades / dividends）：永不删除，保障对账单数据完整
      - expert_reports: JSON blob 单股清理（report_data 内移除该股票的 entries）
    """
    import sqlite3, json
    db = sqlite3.connect(os.path.join(ROOT, "data", "stock.db"), timeout=10)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=5000")
    db.execute("UPDATE stocks SET watchlist=0 WHERE code=?", [code])
    db.execute("DELETE FROM watchlist WHERE code=?", [code])

    # ── 分析层清理 ──
    for tbl in _ANALYTICAL_TABLES:
        db.execute(f"DELETE FROM {tbl} WHERE code=?", [code])
    # prediction_hourly / prediction_signals 使用 pred_id（无 code 列）
    db.execute(
        "DELETE FROM prediction_hourly WHERE pred_id IN "
        "(SELECT id FROM daily_predictions WHERE code=?)", [code])
    db.execute(
        "DELETE FROM prediction_signals WHERE pred_id IN "
        "(SELECT id FROM daily_predictions WHERE code=?)", [code])

    # ── expert_reports 单股清理（JSON blob 格式） ──
    rows = db.execute("SELECT id, report_data FROM expert_reports").fetchall()
    for row_id, report_data in rows:
        try:
            data = json.loads(report_data)
            stocks = data.get("stocks", {})
            if code in stocks:
                del stocks[code]
                if stocks:
                    db.execute("UPDATE expert_reports SET report_data=? WHERE id=?",
                               [json.dumps(data, ensure_ascii=False), row_id])
                else:
                    # 这是该报告唯一的股票 → 删除整条报告
                    db.execute("DELETE FROM expert_reports WHERE id=?", [row_id])
        except (json.JSONDecodeError, KeyError, TypeError):
            continue

    db.commit()
    db.close()

    # ── 交易层数据：不做任何修改，保留完整 ──
    # positions / closed_positions / trades / dividends 保留不动

    _invalidate_init_cache()


def _invalidate_init_cache():
    """Invalidate the init data cache so next request rebuilds from DB."""
    global _init_cache
    _init_cache = None


# ─── Request / Response Detail Logger ───
# Usage: set LOG_DETAIL_ENABLED = True/False to toggle.
# Automatically intercepts request params and response body via
# json_response(), do_GET, and do_POST — no changes needed in
# individual endpoint handlers.

LOG_DETAIL_ENABLED = True          # Global toggle switch
LOG_MAX_STR_LEN = 500              # Max chars per string value
LOG_MAX_LIST_ITEMS = 5             # Truncate lists longer than this
LOG_SENSITIVE_KEYS = {
    'password', 'passwd', 'token', 'secret', 'api_key', 'apikey',
    'authorization', 'auth', 'credential', 'private_key', 'access_key',
    'sign', 'signature',
}

def _safe_log_data(obj, depth=0, max_depth=4):
    """Recursively sanitize data for safe logging:
    - Filter sensitive keys (password, token, secret, etc.)
    - Truncate long strings
    - Cap list items
    - Limit nesting depth
    """
    if depth >= max_depth:
        if isinstance(obj, dict):
            return {'__truncated__': f'max depth {max_depth}'}
        if isinstance(obj, list):
            return [f'<{len(obj)} items, depth limit>']
        return '<max depth>'

    if isinstance(obj, dict):
        result = {}
        for k, v in obj.items():
            key_norm = k.lower().replace('_', '').replace('-', '')
            if any(s in key_norm for s in LOG_SENSITIVE_KEYS):
                result[k] = '***FILTERED***'
                continue
            result[k] = _safe_log_data(v, depth + 1, max_depth)
            # Truncate oversized dict
            try:
                if len(json.dumps(result, ensure_ascii=False)) > LOG_MAX_STR_LEN * 2:
                    result['__truncated__'] = f'... {len(obj) - len(result) + 1} more keys'
                    break
            except Exception:
                break
        return result

    if isinstance(obj, list):
        if len(obj) > LOG_MAX_LIST_ITEMS:
            shown = [_safe_log_data(item, depth + 1, max_depth) for item in obj[:LOG_MAX_LIST_ITEMS]]
            shown.append(f'... ({len(obj) - LOG_MAX_LIST_ITEMS} more items)')
            return shown
        return [_safe_log_data(item, depth + 1, max_depth) for item in obj]

    if isinstance(obj, str):
        if len(obj) > LOG_MAX_STR_LEN:
            return obj[:LOG_MAX_STR_LEN] + f'… [{len(obj)} total]'
        return obj

    if isinstance(obj, bytes):
        return f'<bytes:{len(obj)}B>'

    return obj


def _request_log_detail(handler, resp_data, status_code):
    """Log request params + response body in a color-coded detail block.
    Called automatically from json_response() after the response is written.
    Reads captured params from handler._req_query / handler._req_body.
    """
    if not LOG_DETAIL_ENABLED:
        return

    RST = '\033[0m'
    DIM = '\033[2m'
    CYN = '\033[36m'
    GRN = '\033[32m'
    YLW = '\033[33m'
    RED = '\033[31m'

    # Compute elapsed time
    start = getattr(handler, '_request_start_time', time.time())
    elapsed = (time.time() - start) * 1000

    lines = [f"{DIM}  ┌─ Detail{RST}"]

    # ── Query params (GET) ──
    query = getattr(handler, '_req_query', None)
    if query:
        safe = _safe_log_data(query)
        try:
            j = json.dumps(safe, ensure_ascii=False, indent=2)
            for i, line in enumerate(j.split('\n')):
                prefix = f"{CYN}Query{RST} " if i == 0 else '     '
                lines.append(f"  {DIM}│{RST} {prefix}{line}")
        except Exception:
            lines.append(f"  {DIM}│{RST} {CYN}Query{RST} {str(safe)[:LOG_MAX_STR_LEN]}")

    # ── Body params (POST) ──
    body = getattr(handler, '_req_body', None)
    if body:
        safe = _safe_log_data(body)
        try:
            j = json.dumps(safe, ensure_ascii=False, indent=2)
            for i, line in enumerate(j.split('\n')):
                prefix = f"{CYN}Body {RST}" if i == 0 else '      '
                lines.append(f"  {DIM}│{RST} {prefix}{line}")
        except Exception:
            lines.append(f"  {DIM}│{RST} {CYN}Body {RST} {str(safe)[:LOG_MAX_STR_LEN]}")

    # ── Response ──
    if resp_data is not None:
        safe = _safe_log_data(resp_data)
        try:
            j = json.dumps(safe, ensure_ascii=False, indent=2)
            for i, line in enumerate(j.split('\n')):
                # Truncate response lines if too many
                if i > 30:
                    lines.append(f"  {DIM}│{RST}       ... ({len(j.split(chr(10))) - 30} more lines)")
                    break
                prefix = f"{GRN}Resp {RST}" if i == 0 else '      '
                lines.append(f"  {DIM}│{RST} {prefix}{line}")
        except Exception:
            lines.append(f"  {DIM}│{RST} {GRN}Resp {RST} {str(safe)[:LOG_MAX_STR_LEN]}")

    # ── Timing ──
    if elapsed > 1000:    tc = RED
    elif elapsed > 300:   tc = YLW
    else:                 tc = GRN
    lines.append(f"  {DIM}│{RST} {CYN}Time{RST}  {tc}{elapsed:.1f}ms{RST}")

    lines.append(f"  {DIM}└{'─' * 52}{RST}")

    sys.stderr.write('\n'.join(lines) + '\n')
    sys.stderr.flush()

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
        get_all_monthly_changes, get_all_learning_params,
        get_dividend_yield_series)
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False


def json_response(handler, data, status=200):
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.end_headers()
    handler.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))
    # Auto-log request params + response body (non-invasive detail logging)
    _request_log_detail(handler, data, status)


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
            init_data["kline_daily"] = get_all_kline_daily()
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
            news = get_news('all')
            for n in news:
                n["major"] = bool(n["major"])
            init_data["news"] = news
            init_data["expert_reports"] = get_expert_reports()
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
        init_data["learning_params"] = get_all_learning_params() if DB_AVAILABLE else {}
    except Exception:
        init_data["learning_params"] = {}
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
        # Capture query params for detail logging (non-invasive, 1 line)
        self._req_query = dict(urllib.parse.parse_qsl(parsed.query)) if parsed.query else {}
        self._req_body = None

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
                json_response(self, {
                    "success": True,
                    "data": data,
                    "count": len(data),
                    "source_note": "对账单实际到账数据 — date=派息日, amount=到账金额, per_share=公式计算值(到账金额÷持仓股数)"
                })
            except Exception as e:
                json_response(self, {"success": False, "error": str(e)}, 500)

        elif path.startswith("/api/v2/dividends/") and len(path) > len("/api/v2/dividends/"):
            code = path.split("/api/v2/dividends/")[1]
            try:
                data = get_dividends(code) if DB_AVAILABLE else []
                json_response(self, {
                    "success": True,
                    "data": data,
                    "count": len(data),
                    "source_note": "对账单实际到账数据 — date=派息日, amount=到账金额, per_share=公式计算值(到账金额÷持仓股数)"
                })
            except Exception as e:
                json_response(self, {"success": False, "error": str(e)}, 500)

        elif path == "/api/v2/dividend-yield-series":
            q = urllib.parse.parse_qs(parsed.query)
            code = q.get("code", [None])[0]
            if not code:
                json_response(self, {"success": False, "error": "code required"}, 400)
            else:
                try:
                    data = get_dividend_yield_series(code) if DB_AVAILABLE else {}
                    has_data = bool(data.get("labels"))
                    # Extract latest valid DY for cross-verification with quotes.dy
                    dy_series = data.get("dy_series", [])
                    latest_dy = None
                    for v in reversed(dy_series):
                        if v is not None:
                            latest_dy = v
                            break
                    json_response(self, {
                        "success": True,
                        "data": data,
                        "has_data": has_data,
                        "latest_dy": latest_dy,
                        "source_note": "公式计算值（TTM滚动推算）— 基于最近12个月分红与股价推算，与公司实际公布股息率可能存在差异"
                    })
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
                _cleanup_stock_data(code)
                json_response(self, {"success": True, "message": f"已移除 {code}"})
            except Exception as e:
                json_response(self, {"success": False, "error": str(e)}, 500)
        else:
            json_response(self, {"success": False, "error": "Unknown DELETE endpoint"}, 404)

    def do_POST(self):
        global _refresh_in_progress
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

        # Capture request body for detail logging (non-invasive, 1 line)
        self._req_query = None
        self._req_body = params

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
                _invalidate_init_cache()
                if ok1:
                    json_response(self, {
                        "success": True,
                        "message": f"已添加 {name}({code})，全模块数据同步完成",
                        "watchlist": wl if DB_AVAILABLE else [],
                        "output": out1[-500:] if out1 else "",
                    })
                else:
                    json_response(self, {
                        "success": False,
                        "error": f"数据同步失败: {code}",
                        "message": f"股票已添加到自选股，但数据同步失败。请手动点击'刷新数据'按钮",
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
                _invalidate_init_cache()
                if ok1:
                    json_response(self, {
                        "success": True,
                        "message": f"已添加 {name}({code})，全模块数据同步完成",
                        "watchlist": [dict(r) for r in get_watchlist()] if DB_AVAILABLE else [],
                        "output": out1[-500:] if out1 else "",
                    })
                else:
                    json_response(self, {
                        "success": False,
                        "error": f"数据同步失败: {code}",
                        "message": "股票已加自选，但数据同步失败。请手动点击'刷新数据'",
                        "output": out1[-500:] if out1 else "",
                    })

            elif path == "/api/watchlist/remove":
                code = params.get("code", "").strip()
                if not code:
                    json_response(self, {"success": False, "error": "code required"}, 400)
                    return

                try:
                    _cleanup_stock_data(code)
                except Exception as e:
                    json_response(self, {"success": False, "error": f"删除失败: {e}"}, 500)
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
                ok, out = run_script("update_from_statement.py", 60)
                ok2, out2 = run_script("reinject_from_db.py", 30)
                if ok and ok2:
                    json_response(self, {
                        "success": True,
                        "message": "持仓数据已更新，刷新页面查看",
                        "output": out[-1000:] if out else "",
                    })
                else:
                    err_msg = "解析失败" if not ok else "HTML注入失败"
                    json_response(self, {
                        "success": False,
                        "error": err_msg + (" (update)" if not ok else " (reinject)"),
                        "message": "对账单更新失败，请检查文件格式或重新上传",
                        "output": out[-1000:] if out else "",
                    })

            elif path == "/api/v2/quotes/refresh":
                # Lightweight quotes-only refresh (no full sync)
                if _refresh_in_progress:
                    json_response(self, {"success": False, "error": "刷新已在运行中，请稍候"}, 429)
                    return
                _refresh_in_progress = True
                try:
                    ok, out = run_script("refresh_quotes.py", 60)
                    if ok and out:
                        try:
                            # Parse JSON output from refresh_quotes.py
                            # Find the last JSON object in the output
                            lines = out.strip().split('\n')
                            json_line = None
                            for line in reversed(lines):
                                line = line.strip()
                                if line.startswith('{') and line.endswith('}'):
                                    json_line = line
                                    break
                            if json_line:
                                data = json.loads(json_line)
                                _invalidate_init_cache()
                                json_response(self, {
                                    "success": True,
                                    "message": f"股价已刷新 ({data.get('count', 0)}只股票)",
                                    "data": data.get("data", {}),
                                    "refreshed_at": data.get("refreshed_at", ""),
                                    "stats": data.get("stats", {}),
                                })
                            else:
                                json_response(self, {
                                    "success": True,
                                    "message": "股价已刷新",
                                    "output": out[-500:] if out else "",
                                })
                        except json.JSONDecodeError:
                            json_response(self, {
                                "success": True,
                                "message": "股价已刷新",
                                "output": out[-500:] if out else "",
                            })
                    else:
                        json_response(self, {
                            "success": False,
                            "error": "刷新失败",
                            "output": out[-500:] if out else "",
                        })
                finally:
                    _refresh_in_progress = False

            elif path == "/api/trigger/predict":
                # Prevent concurrent refresh runs
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
                    resp = {"success": ok, "message": msg, "warnings": warnings}
                    if not ok:
                        resp["error"] = msg  # duplicate as error for frontend compatibility
                    json_response(self, resp)
                except Exception as e:
                    json_response(self, {"success": False, "error": f"报告导入异常: {e}", "message": str(e)}, 500)

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
        """Receive uploaded GF Securities statement xlsx, validate, save and process.

        Multi-layer format validation:
          1. Content-Type header check (multipart/form-data)
          2. Magic byte detection (true file type, not extension)
          3. File size sanity check
          4. Detailed diagnostics on failure
        """
        import shutil, email, sys, traceback, time

        content_type = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in content_type:
            json_response(self, {
                "success": False,
                "error": "需要 multipart/form-data",
                "message": "请通过页面上传按钮选择对账单文件，不要直接调用API",
            }, 400)
            return

        try:
            raw = self.rfile.read(content_length)
            boundary = content_type.split("boundary=")[1].strip()
            boundary_bytes = boundary.encode()
        except Exception as e:
            json_response(self, {"success": False, "error": f"请求解析失败: {e}"}, 400)
            return

        found_file = False
        for part in raw.split(b"--" + boundary_bytes):
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

            # ── 层1: 文件大小检查 ──
            if len(file_data) < 100:
                json_response(self, {
                    "success": False,
                    "error": "文件过小（可能为空或损坏）",
                    "message": f"上传文件仅 {len(file_data)} 字节，请确认选择了正确的对账单文件",
                }, 400)
                return

            # ── 层2: 魔数检测（真实文件类型，非扩展名） ──
            magic = file_data[:8]
            magic_hex = magic.hex()
            detected_format = self._detect_file_format(magic)

            if detected_format != "xlsx":
                # 构建详细诊断信息
                detail = self._format_diagnostic(magic, file_data, detected_format)
                json_response(self, {
                    "success": False,
                    "error": detail["error"],
                    "message": detail["message"],
                    "diagnostics": detail,
                }, 400)
                return

            # ── 层3: 无损坏——安全保存 ──
            found_file = True
            dest = os.path.join(ROOT, "广发易淘金PC版-普通对账单结果查询.xlsx")

            # 备份现有文件（仅在它是有效xlsx时保留）
            if os.path.exists(dest):
                with open(dest, 'rb') as check:
                    old_magic = check.read(4)
                if old_magic == b'PK\x03\x04':
                    # 现有文件是有效xlsx → 安全备份
                    bak = dest + f".bak_{int(time.time())}"
                    shutil.copy2(dest, bak)
                    bak_latest = dest + ".upload_bak"
                    if os.path.exists(bak_latest):
                        os.remove(bak_latest)
                    shutil.copy2(dest, bak_latest)
                else:
                    # 现有文件已损坏 → 仅做一次性备份
                    bak = dest + ".was_corrupted"
                    shutil.copy2(dest, bak)

            with open(dest, "wb") as f:
                f.write(file_data)

            print(f"[INFO] 对账单已保存: {dest} ({len(file_data):,} bytes, magic OK)", file=sys.stderr)

            # ── Step 1: 解析 Excel ──
            ok, out = run_script("update_from_statement.py", 60)
            if not ok:
                json_response(self, {
                    "success": False,
                    "error": "对账单解析失败",
                    "message": "Excel 文件可能损坏、列名不匹配或包含无效数据。详见输出日志。",
                    "output": out[-500:] if out else "",
                })
                return

            # ── Step 2: 注入 HTML ──
            ok2, out2 = run_script("reinject_from_db.py", 30)
            if not ok2:
                # HTML注入失败，但SQLite已更新 → 部分成功
                json_response(self, {
                    "success": False,
                    "error": "HTML 注入失败",
                    "message": "持仓数据已解析并写入数据库，但页面未能自动更新。请手动运行 reinject_from_db.py。",
                    "output": out2[-500:] if out2 else "",
                })
                return

            json_response(self, {
                "success": True,
                "message": "对账单已更新，刷新页面查看",
                "output": out[-500:] if out else "",
            })
            return

        if not found_file:
            json_response(self, {
                "success": False,
                "error": "未找到上传文件",
                "message": "请选择广发对账单 .xlsx 文件后点击上传",
            }, 400)

    @staticmethod
    def _detect_file_format(magic_bytes: bytes) -> str:
        """从文件头魔数识别真实文件格式（不是扩展名）。"""
        if magic_bytes[:4] == b'PK\x03\x04':
            # 进一步检查是否是 Office Open XML
            return "xlsx"  # 也可能是 docx/pptx，但在本例中只接受xlsx
        if magic_bytes[:8] == b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1':
            return "xls_ole"  # 旧版Excel格式
        if magic_bytes[:4] == b'\x50\x4b\x03\x04':
            return "xlsx"
        if magic_bytes[:2] == b'\xff\xfe':
            return "csv_utf16le"
        if magic_bytes[:2] == b'\xfe\xff':
            return "csv_utf16be"
        if magic_bytes[:3] == b'\xef\xbb\xbf':
            return "csv_utf8_bom"
        if magic_bytes[0:1] == b'{':
            # JSON — 可能是专家报告误上传
            return "json"
        if magic_bytes[0:1] == b'[':
            return "json_array"
        if magic_bytes[:5] == b'<?xml':
            return "xml"
        if magic_bytes[:4] == b'\x25\x50\x44\x46':  # %PDF
            return "pdf"
        # 尝试检测纯文本/CSV
        try:
            text = magic_bytes.decode('utf-8', errors='strict')
            if ',' in text or '\t' in text:
                return "csv_utf8"
            return "text_utf8"
        except UnicodeDecodeError:
            pass
        return "unknown"

    @staticmethod
    def _format_diagnostic(magic: bytes, data: bytes, detected: str) -> dict:
        """生成详细的格式诊断信息。"""
        magic_hex = magic[:8].hex()
        preview = data[:200].decode('utf-8', errors='replace')

        format_names = {
            "xlsx": "Excel 2007+ (.xlsx)",
            "xls_ole": "旧版 Excel 97-2003 (.xls)",
            "json": "JSON 文本",
            "json_array": "JSON 数组",
            "csv_utf8": "CSV UTF-8",
            "csv_utf8_bom": "CSV UTF-8 BOM",
            "csv_utf16le": "CSV UTF-16 LE",
            "csv_utf16be": "CSV UTF-16 BE",
            "xml": "XML",
            "pdf": "PDF",
            "text_utf8": "纯文本 UTF-8",
            "unknown": "未知二进制格式",
        }
        detected_name = format_names.get(detected, detected)

        suggestions = {
            "json": "您上传的是 JSON 文件（可能是专家分析报告），而非广发对账单。请从广发易淘金PC版导出对账单（.xlsx格式）后重新上传。",
            "csv_utf8": "您上传的是 CSV/文本文件。请从广发易淘金PC版导出为 .xlsx 格式。",
            "csv_utf8_bom": "您上传的是 CSV/文本文件（含 BOM 头）。请从广发易淘金PC版导出为 .xlsx 格式。",
            "csv_utf16le": "您上传的是 UTF-16 编码的 CSV 文件。请从广发易淘金PC版导出为 .xlsx 格式。",
            "xls_ole": "您上传的是旧版 .xls 格式（Excel 97-2003）。请另存为 .xlsx 格式后上传。",
            "pdf": "您上传的是 PDF 文件，不是对账单。请上传.xlsx格式。",
        }

        return {
            "error": f"文件格式不匹配: 检测到 {detected_name}，需要 .xlsx",
            "message": suggestions.get(detected,
                      f"上传文件的实际格式为 {detected_name}，但系统需要广发对账单 .xlsx 格式。请检查文件选择是否正确。"),
            "detected_format": detected,
            "detected_format_name": detected_name,
            "expected_format": "xlsx",
            "magic_hex": magic_hex,
            "file_size": len(data),
            "preview": preview[:100],
        }

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

    def handle_one_request(self):
        """Override to track request start time for detailed logging."""
        self._request_start_time = time.time()
        try:
            super().handle_one_request()
        except Exception:
            if not hasattr(self, '_request_start_time'):
                self._request_start_time = time.time()
            raise

    def log_message(self, format, *args):
        """Enhanced request logging: method, full path, query params, status,
        response time (ms), client IP, and User-Agent — with ANSI colors.

        Color legend:
          GET=Blue  POST=Green  DELETE=Red  PUT=Yellow  OPTIONS=Cyan
          Status 2xx=Green  3xx=Yellow  4xx=Red  5xx=White-on-Red
          Timing <300ms=Green  300ms-1s=Yellow  >1s=Red
        """
        # ── Calculate response time ──
        start = getattr(self, '_request_start_time', time.time())
        elapsed = (time.time() - start) * 1000

        # ── Status code from base class log_request(code) ──
        status_code = str(args[0]) if args else "???"

        # ── ANSI escape codes ──
        RST = '\033[0m'           # Reset
        DIM = '\033[2m'           # Dim
        BLD = '\033[1m'           # Bold
        BLU = '\033[34m'          # Blue
        GRN = '\033[32m'          # Green
        RED = '\033[31m'          # Red
        YLW = '\033[33m'          # Yellow
        CYN = '\033[36m'          # Cyan
        MAG = '\033[35m'          # Magenta
        BGW = '\033[41m\033[97m'  # White on red background (5xx)

        # ── Method → color mapping ──
        METHOD_COLORS = {
            'GET': BLU, 'POST': GRN, 'DELETE': RED,
            'PUT': YLW, 'PATCH': MAG, 'OPTIONS': CYN,
        }
        mc = METHOD_COLORS.get(self.command, RST)

        # ── Status → color ──
        try:
            ci = int(status_code)
            if ci >= 500:   sc = BGW + BLD
            elif ci >= 400: sc = RED + BLD
            elif ci >= 300: sc = YLW
            else:           sc = GRN
        except ValueError:
            sc = RST

        # ── Timing → color ──
        if elapsed > 1000:      tc = RED + BLD
        elif elapsed > 300:     tc = YLW
        else:                   tc = GRN

        # ── Truncate overly long paths ──
        path = self.path
        if len(path) > 65:
            path = path[:62] + '...'

        # ── Padding for method alignment ──
        m_pad = ' ' * (7 - len(self.command))

        # ── Client info ──
        ip = self.client_address[0] if self.client_address else '-'
        ua = self.headers.get('User-Agent', '-')
        if len(ua) > 60:
            ua = ua[:57] + '...'

        timestamp = datetime.now().strftime('%H:%M:%S')

        # ── Assemble log line ──
        line = (
            f"{DIM}[{timestamp}]{RST} "
            f"{BLD}{mc}{self.command}{RST}{m_pad}  "
            f"{path:<67}"
            f"→ {sc}{status_code}{RST}  "
            f"{tc}{elapsed:6.1f}ms{RST}  "
            f"{DIM}{ip}{RST}  "
            f"{DIM}{ua}{RST}"
        )

        sys.stderr.write(line + '\n')
        sys.stderr.flush()


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
