"""
股票投资管理系统 - FastAPI 本地API服务器
启动: python server_v2.py  (或 uvicorn server_v2:app --host 127.0.0.1 --port 8766)
端口: 8766

注意：本文件是对原 server.py (ThreadedHTTPServer) 的 FastAPI 完整迁移。
所有输入输出、业务逻辑、边界条件与原版完全一致。
"""
import json
import os
import sqlite3
import subprocess
import sys
import time
import traceback
import threading
from datetime import datetime
from typing import Optional, Dict, Any, List

from fastapi import FastAPI, Request, Query, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse, Response, HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# ─── Configuration ───────────────────────────────────────────────────────────
PORT = 8766
ROOT = os.path.dirname(os.path.abspath(__file__))
PYTHON = r"C:\Users\28312\AppData\Local\Programs\Python\Python312\python.exe"
NODE = r"C:\Users\28312\.workbuddy\binaries\node\versions\22.12.0\node.exe"

sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

# ─── Init cache (identical to original) ──────────────────────────────────────
_init_cache = None
_init_cache_time = 0
CACHE_TTL = 5

# ─── Analytical vs Broker tables (identical to original) ─────────────────────
_ANALYTICAL_TABLES = [
    "kline_daily", "kline_monthly", "daily_predictions",
    "seasonal", "learning_params", "accuracy_stats",
    "quotes", "news",
]
_BROKER_TABLES = [
    "positions", "closed_positions", "trades", "dividends",
]

# ─── Refresh lock (identical to original) ────────────────────────────────────
_refresh_lock = threading.Lock()
_refresh_in_progress = False

# ─── DB imports (identical to original) ──────────────────────────────────────
try:
    from db_helper import (get_stock_search, get_watchlist, get_watchlist_codes,
        add_watchlist, remove_watchlist, get_kline_daily, get_kline_monthly,
        get_quotes, get_positions, get_daily_predictions, get_learning_params,
        get_accuracy_stats, get_news, get_expert_reports, get_seasonal,
        get_config, _calc_fees, get_current_positions, get_closed_positions,
        get_trades, get_dividends, get_statement_dividends,
        get_all_kline_daily, get_all_kline_monthly,
        get_all_predictions, get_all_seasonal, get_all_accuracy_stats,
        get_all_monthly_changes, get_all_learning_params,
        get_dividend_yield_series,
        init_pattern_rules_tables, get_pattern_rules, get_pattern_rule,
        insert_pattern_rule, update_pattern_rule, delete_pattern_rule)
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False

# ─── Request log detail (identical to original) ──────────────────────────────

LOG_DETAIL_ENABLED = True
LOG_MAX_STR_LEN = 500
LOG_MAX_LIST_ITEMS = 5
LOG_SENSITIVE_KEYS = {
    'password', 'passwd', 'token', 'secret', 'api_key', 'apikey',
    'authorization', 'auth', 'credential', 'private_key', 'access_key',
    'sign', 'signature',
}


def _safe_log_data(obj, depth=0, max_depth=4):
    """Recursively sanitize data for safe logging (identical to original)."""
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


def _request_log_detail(method: str, path: str, query_params: dict,
                         body_params: Optional[dict],
                         resp_data: Optional[dict], status_code: int,
                         elapsed_ms: float):
    """Log request params + response body (identical to original detail logging)."""
    if not LOG_DETAIL_ENABLED:
        return

    RST = '\033[0m'
    DIM = '\033[2m'
    CYN = '\033[36m'
    GRN = '\033[32m'
    YLW = '\033[33m'
    RED = '\033[31m'

    lines = [f"{DIM}  ┌─ Detail{RST}"]

    # Query params
    if query_params:
        safe = _safe_log_data(query_params)
        try:
            j = json.dumps(safe, ensure_ascii=False, indent=2)
            for i, line in enumerate(j.split('\n')):
                prefix = f"{CYN}Query{RST} " if i == 0 else '     '
                lines.append(f"  {DIM}│{RST} {prefix}{line}")
        except Exception:
            lines.append(f"  {DIM}│{RST} {CYN}Query{RST} {str(safe)[:LOG_MAX_STR_LEN]}")

    # Body params
    if body_params:
        safe = _safe_log_data(body_params)
        try:
            j = json.dumps(safe, ensure_ascii=False, indent=2)
            for i, line in enumerate(j.split('\n')):
                prefix = f"{CYN}Body {RST}" if i == 0 else '      '
                lines.append(f"  {DIM}│{RST} {prefix}{line}")
        except Exception:
            lines.append(f"  {DIM}│{RST} {CYN}Body {RST} {str(safe)[:LOG_MAX_STR_LEN]}")

    # Response
    if resp_data is not None:
        safe = _safe_log_data(resp_data)
        try:
            j = json.dumps(safe, ensure_ascii=False, indent=2)
            for i, line in enumerate(j.split('\n')):
                if i > 30:
                    lines.append(f"  {DIM}│{RST}       ... ({len(j.split(chr(10))) - 30} more lines)")
                    break
                prefix = f"{GRN}Resp {RST}" if i == 0 else '      '
                lines.append(f"  {DIM}│{RST} {prefix}{line}")
        except Exception:
            lines.append(f"  {DIM}│{RST} {GRN}Resp {RST} {str(safe)[:LOG_MAX_STR_LEN]}")

    # Timing
    if elapsed_ms > 1000:    tc = RED
    elif elapsed_ms > 300:   tc = YLW
    else:                    tc = GRN
    lines.append(f"  {DIM}│{RST} {CYN}Time{RST}  {tc}{elapsed_ms:.1f}ms{RST}")

    lines.append(f"  {DIM}└{'─' * 52}{RST}")
    sys.stderr.write('\n'.join(lines) + '\n')
    sys.stderr.flush()


# ─── Data cleanup (identical to original) ─────────────────────────────────────

def _cleanup_stock_data(code):
    """删除自选股时，安全清除分析层数据，完整保留交易层数据 (identical to original)."""
    db = sqlite3.connect(os.path.join(ROOT, "data", "stock.db"), timeout=10)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=5000")
    db.execute("UPDATE stocks SET watchlist=0 WHERE code=?", [code])
    db.execute("DELETE FROM watchlist WHERE code=?", [code])

    for tbl in _ANALYTICAL_TABLES:
        db.execute(f"DELETE FROM {tbl} WHERE code=?", [code])
    db.execute(
        "DELETE FROM prediction_hourly WHERE pred_id IN "
        "(SELECT id FROM daily_predictions WHERE code=?)", [code])
    db.execute(
        "DELETE FROM prediction_signals WHERE pred_id IN "
        "(SELECT id FROM daily_predictions WHERE code=?)", [code])

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
                    db.execute("DELETE FROM expert_reports WHERE id=?", [row_id])
        except (json.JSONDecodeError, KeyError, TypeError):
            continue

    db.commit()
    db.close()
    _invalidate_init_cache()


def _invalidate_init_cache():
    """Invalidate the init data cache (identical to original)."""
    global _init_cache
    _init_cache = None


# ─── File utilities (identical to original) ──────────────────────────────────

def read_json(path):
    with open(os.path.join(ROOT, path), "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path, data):
    with open(os.path.join(ROOT, path), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ─── Stock search (identical to original) ────────────────────────────────────

def search_stocks(keyword):
    """Search stocks from SQLite stocks table. Falls back to JSON on DB error."""
    try:
        if DB_AVAILABLE:
            from db_helper import get_stock_search
            return get_stock_search(keyword)
    except Exception:
        pass
    try:
        stocks = read_json("data/a_stocks.json")
        if not stocks or not keyword:
            return []
        kw = keyword.lower().strip()
        return [s for s in stocks if kw in s.get('code', '') or kw in s.get('name', '').lower()
                or kw in s.get('py', '').lower()][:15]
    except:
        return []


# ─── Subprocess execution (identical to original) ────────────────────────────

def run_script(script_name, timeout=60):
    """Run a Python script in scripts/ directory (identical to original)."""
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


# ─── Init data builder (identical to original) ───────────────────────────────

def _build_init_data() -> dict:
    """Build full init data dict from SQLite (identical to original)."""
    global _init_cache, _init_cache_time

    now = time.time()
    if _init_cache and (now - _init_cache_time) < CACHE_TTL:
        return _init_cache

    try:
        cfg = get_config() if DB_AVAILABLE else {}
    except:
        cfg = {}
    init_data = {
        "account": cfg.get("account", ""),
        "broker": cfg.get("broker", ""),
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M")
    }
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
        if DB_AVAILABLE:
            mc = get_all_monthly_changes()
            for code, bars in mc.items():
                init_data[f"monthly_changes_{code}"] = bars
    except Exception:
        pass
    try:
        init_data["learning_params"] = get_all_learning_params() if DB_AVAILABLE else {}
    except Exception:
        init_data["learning_params"] = {}
    try:
        init_data["accuracy_stats"] = get_all_accuracy_stats() if DB_AVAILABLE else {}
    except Exception:
        init_data["accuracy_stats"] = {}

    if init_data.get("watchlist"):
        _init_cache = init_data
        _init_cache_time = now
    return init_data


# ─── File upload helpers (identical to original) ─────────────────────────────

def _detect_file_format(magic_bytes: bytes) -> str:
    """从文件头魔数识别真实文件格式（不是扩展名）."""
    if magic_bytes[:4] == b'PK\x03\x04':
        return "xlsx"
    if magic_bytes[:8] == b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1':
        return "xls_ole"
    if magic_bytes[:4] == b'\x50\x4b\x03\x04':
        return "xlsx"
    if magic_bytes[:2] == b'\xff\xfe':
        return "csv_utf16le"
    if magic_bytes[:2] == b'\xfe\xff':
        return "csv_utf16be"
    if magic_bytes[:3] == b'\xef\xbb\xbf':
        return "csv_utf8_bom"
    if magic_bytes[0:1] == b'{':
        return "json"
    if magic_bytes[0:1] == b'[':
        return "json_array"
    if magic_bytes[:5] == b'<?xml':
        return "xml"
    if magic_bytes[:4] == b'\x25\x50\x44\x46':
        return "pdf"
    try:
        text = magic_bytes.decode('utf-8', errors='strict')
        if ',' in text or '\t' in text:
            return "csv_utf8"
        return "text_utf8"
    except UnicodeDecodeError:
        pass
    return "unknown"


def _format_diagnostic(magic: bytes, data: bytes, detected: str) -> dict:
    """生成详细的格式诊断信息 (identical to original)."""
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


# ─── MIME types (identical to original) ──────────────────────────────────────

MIME_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".gif": "image/gif", ".svg": "image/svg+xml", ".ico": "image/x-icon",
    ".woff": "font/woff", ".woff2": "font/woff2", ".ttf": "font/ttf",
    ".pdf": "application/pdf", ".zip": "application/zip",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".xls": "application/vnd.ms-excel",
}


def _serve_file_content(path: str):
    """Serve a file from ROOT/path with proper MIME type detection."""
    full_path = os.path.join(ROOT, path)
    if not os.path.exists(full_path):
        return None
    _, ext = os.path.splitext(path.lower())
    content_type = MIME_TYPES.get(ext, "application/octet-stream")
    with open(full_path, "rb") as f:
        data = f.read()
    return Response(content=data, media_type=content_type,
                    headers={"Access-Control-Allow-Origin": "*"})


# ─── FastAPI App ─────────────────────────────────────────────────────────────

app = FastAPI(
    title="股票投资管理系统",
    description="银行股投资管理本地 API (FastAPI 迁移版)",
    version="0.8",
    docs_url="/docs",
    redoc_url=None,
)


@app.on_event("startup")
async def startup_init_tables():
    """Initialize paper-trading tables, pattern rules tables, and clean stale backtest records. Idempotent."""
    try:
        init_backtest_tables()
        _write("  [Startup] Paper-trading tables initialized\n")
    except Exception as e:
        _write(f"  [Startup] WARNING: init_backtest_tables failed: {e}\n")

    try:
        init_pattern_rules_tables()
        _write("  [Startup] Pattern rules table initialized\n")
    except Exception as e:
        _write(f"  [Startup] WARNING: init_pattern_rules_tables failed: {e}\n")

    # Clean up stale "running" records from previous server run
        try:
            db = get_db()
            stale = db.execute(
                "SELECT id FROM backtest_runs WHERE status='running'"
            ).fetchall()
            for row in stale:
                db.execute(
                    "UPDATE backtest_runs SET status='error', error_msg=?, finished_at=datetime('now','localtime') WHERE id=?",
                    ['服务重启，回测中断', row['id']]
                )
            if stale:
                db.commit()
                _write(f"  [Startup] Cleaned {len(stale)} stale backtest record(s)\n")
            db.close()
        except Exception as e:
            _write(f"  [Startup] WARNING: stale cleanup failed: {e}\n")
    except Exception as e:
        _write(f"  [Startup] WARNING: init_backtest_tables failed: {e}\n")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type"],
)


# ─── Middleware: request timing + ANSI color logging ─────────────────────────

def _write(text: str):
    """Write to stderr as UTF-8 bytes — readable Chinese in modern terminals."""
    sys.stderr.buffer.write(text.encode('utf-8') + b'\n')
    sys.stderr.buffer.flush()


def _format_json(val, max_len=2000):
    """Format JSON for logging. Chinese characters shown natively."""
    if val is None:
        return 'null'
    try:
        s = json.dumps(val, ensure_ascii=False, indent=2, default=str)
    except (TypeError, ValueError):
        s = str(val)
    if len(s) > max_len:
        s = s[:max_len] + f'\n  ...(truncated {len(s)} total chars)'
    return s


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log complete request params + response data with ANSI colors."""
    start_time = time.time()

    # ── Read request body (if any) ──
    req_body_raw = None
    if request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
        try:
            body_bytes = await request.body()
            if body_bytes:
                try:
                    req_body_raw = json.loads(body_bytes)
                except json.JSONDecodeError:
                    req_body_raw = f'<{len(body_bytes)} bytes non-JSON>'
        except Exception:
            req_body_raw = '<body read error>'

    response = await call_next(request)
    elapsed = (time.time() - start_time) * 1000

    # ── Read response body ──
    resp_body_raw = None
    content_type = response.headers.get('Content-Type', '')
    if 'application/json' in content_type:
        try:
            body_bytes = b''
            async for chunk in response.body_iterator:
                body_bytes += chunk
            resp_body_raw = json.loads(body_bytes)
            # Rebuild response with consumed body
            response = Response(
                content=body_bytes,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type,
            )
        except Exception:
            resp_body_raw = '<read error>'

    # ── Colors ──
    RST = '\033[0m'
    DIM = '\033[2m'
    BLD = '\033[1m'
    BLU = '\033[34m'
    GRN = '\033[32m'
    RED = '\033[31m'
    YLW = '\033[33m'
    CYN = '\033[36m'
    MAG = '\033[35m'
    BGW = '\033[41m\033[97m'

    METHOD_COLORS = {
        'GET': BLU, 'POST': GRN, 'DELETE': RED,
        'PUT': YLW, 'PATCH': MAG, 'OPTIONS': CYN,
    }
    mc = METHOD_COLORS.get(request.method, RST)

    ci = response.status_code
    if ci >= 500:   sc = BGW + BLD
    elif ci >= 400: sc = RED + BLD
    elif ci >= 300: sc = YLW
    else:           sc = GRN

    if elapsed > 1000:      tc = RED + BLD
    elif elapsed > 300:     tc = YLW
    else:                   tc = GRN

    path = request.url.path
    qs = request.url.query
    if qs:
        path_display = f"{path}?{qs}" if len(path + qs) <= 70 else f"{path[:60]}…?…"
    else:
        path_display = path if len(path) <= 70 else path[:67] + '...'

    m_pad = ' ' * (7 - len(request.method))
    ip = request.client.host if request.client else '-'

    timestamp = datetime.now().strftime('%H:%M:%S')

    # ── Log line 1: request method + path + status + timing ──
    line1 = (
        f"{DIM}[{timestamp}]{RST} "
        f"{BLD}{mc}{request.method}{RST}{m_pad}  "
        f"{path_display:<67}"
        f"→ {sc}{response.status_code}{RST}  "
        f"{tc}{elapsed:6.1f}ms{RST}  "
        f"{DIM}{ip}{RST}"
    )
    _write(line1)

    # ── Log line 2: request params ──
    if qs:
        params = dict(request.query_params)
        _write(f"  {CYN}▶ Query:{RST} {_format_json(params, 500)}")
    if req_body_raw is not None:
        _write(f"  {YLW}▶ Body:{RST} {_format_json(req_body_raw, 2000)}")

    # ── Log line 3: response data ──
    if resp_body_raw is not None:
        _write(f"  {GRN}◀ Response:{RST} {_format_json(resp_body_raw, 4000)}")
    return response


# ─── Response helper: preserves original format {success, data/error} ────────

def api_response(data: Any = None, success: bool = True,
                 status_code: int = 200, **extra) -> JSONResponse:
    """Build JSON response matching original server.py format exactly."""
    body = {"success": success}
    if data is not None:
        body["data"] = data
    elif not success:
        body["data"] = None
    body.update(extra)
    if not success and "error" not in body:
        body["error"] = str(body.get("message", "Unknown error"))
    return JSONResponse(content=body, status_code=status_code)


# ===========================================================================
# ROUTE HANDLERS — every endpoint mirrors the original server.py EXACTLY
# ===========================================================================

# ──────────────────────────────────────────────────────────────────────────
# Root / Static files / DB viewer
# ──────────────────────────────────────────────────────────────────────────

# ──────────────────────────────────────────────────────────────────────────
# V2 frontend static file serving
# ──────────────────────────────────────────────────────────────────────────

V2_DIST = os.path.join(ROOT, "deliverables", "v2", "dist")

@app.get("/")
@app.get("/index.html")
def root_page():
    """Serve main page (V2 frontend built with Vue)."""
    idx = os.path.join(V2_DIST, "index.html")
    if os.path.exists(idx):
        return HTMLResponse(content=open(idx, "r", encoding="utf-8").read())
    return HTMLResponse("<h1>前端构建文件缺失，请先构建 V2 前端</h1>", status_code=503)

@app.get("/assets/{rest_of_path:path}")
async def serve_v2_assets(rest_of_path: str):
    """Serve V2 dist assets (JS/CSS bundles)."""
    path = os.path.join(V2_DIST, "assets", rest_of_path)
    if not os.path.exists(path):
        raise HTTPException(status_code=404)
    return _serve_file_content(os.path.relpath(path, ROOT))

@app.get("/chart.umd.min.js")
async def serve_chart_umd():
    """Serve chart library from V2 dist."""
    path = os.path.join(V2_DIST, "chart.umd.min.js")
    if not os.path.exists(path):
        raise HTTPException(status_code=404)
    return _serve_file_content(os.path.relpath(path, ROOT))

@app.get("/chartjs-chart-financial.min.js")
async def serve_chart_financial():
    """Serve chart financial library from V2 dist."""
    path = os.path.join(V2_DIST, "chartjs-chart-financial.min.js")
    if not os.path.exists(path):
        raise HTTPException(status_code=404)
    return _serve_file_content(os.path.relpath(path, ROOT))


@app.get("/dbview")
def db_viewer(t: str = Query(default="")):
    """SQLite database viewer (identical to original /dbview handler)."""
    db_path = os.path.join(ROOT, "data", "stock.db")
    if not os.path.exists(db_path):
        raise HTTPException(status_code=404)
    db = sqlite3.connect(db_path)

    tables = [r[0] for r in db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()]

    html = """<!DOCTYPE html><html><head><meta charset='utf-8'><title>DB Viewer</title>
<style>body{font:13px monospace;background:#1e1e1e;color:#d4d4d4;margin:0;padding:16px}
h2{color:#569cd6;margin:0 0 8px}.tabs{display:flex;gap:4px;flex-wrap:wrap;margin-bottom:16px}
.tab{padding:6px 14px;border-radius:4px;cursor:pointer;color:#9cdcfe;border:1px solid #3c3c3c;font-size:12px}
.tab:hover{background:#2a2a2a}.tab.active{background:#569cd6;color:#fff;border-color:#569cd6}
table{border-collapse:collapse;width:100%}th{background:#333;padding:6px 10px;text-align:left;position:sticky;top:0}
td{padding:4px 10px;border-bottom:1px solid #333;max-width:400px;overflow:hidden;white-space:nowrap}
tr:hover td{background:#2a2a2a}.num{color:#b5cea8}.text{color:#ce9178}.null{color:#666}
</style></head><body><h2>DB Viewer - data/stock.db</h2><div class='tabs'>"""

    table = t
    for tb in tables:
        active = "active" if tb == table or (not table and tb == tables[0]) else ""
        html += "<a class='tab {}' href='/dbview?t={}'>{}</a>".format(active, tb, tb)
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
    return HTMLResponse(content=html)


# ──────────────────────────────────────────────────────────────────────────
# Init / System data
# ──────────────────────────────────────────────────────────────────────────

@app.get("/api/v2/init")
def api_v2_init():
    """Full init data (identical to original)."""
    try:
        return api_response(data=_build_init_data())
    except Exception as e:
        return api_response(success=False, error=str(e), status_code=500)


@app.get("/api/system-data")
def api_system_data():
    """Legacy system data endpoint (identical to original)."""
    try:
        data = _build_init_data()
        return api_response(data=data)
    except Exception as e:
        return api_response(success=False, error=str(e), status_code=500)


@app.get("/api/audit")
def api_audit():
    """System audit (identical to original)."""
    ok, out = run_script("audit_system.py")
    return api_response(success=ok, output=out)


# ──────────────────────────────────────────────────────────────────────────
# Watchlist (V2 + legacy exact match before prefix)
# ──────────────────────────────────────────────────────────────────────────

@app.get("/api/watchlist")
def api_watchlist_legacy():
    """Legacy watchlist endpoint (identical to original)."""
    try:
        wl = [dict(r) for r in get_watchlist()] if DB_AVAILABLE else []
        return api_response(data={"stocks": wl})
    except Exception as e:
        return api_response(success=False, error=str(e), status_code=500)


@app.get("/api/v2/watchlist")
def api_v2_watchlist_get():
    """V2 watchlist list (identical to original)."""
    try:
        data = [dict(r) for r in get_watchlist()] if DB_AVAILABLE else []
        return api_response(data=data, count=len(data))
    except Exception as e:
        return api_response(success=False, error=str(e), status_code=500)


@app.delete("/api/v2/watchlist/{code}")
def api_v2_watchlist_delete(code: str):
    """V2 RESTful watchlist delete with data cleanup (identical to original)."""
    try:
        _cleanup_stock_data(code)
        return api_response(message=f"已移除 {code}")
    except Exception as e:
        return api_response(success=False, error=str(e), status_code=500)


@app.post("/api/watchlist/add")
async def api_watchlist_add(request: Request):
    """Legacy watchlist add (identical to original)."""
    body = await request.json()
    code = body.get("code", "").strip()
    name = body.get("name", "").strip()
    market = body.get("market", "sh").strip()

    if not code or not name:
        return api_response(success=False, error="code and name required", status_code=400)

    if DB_AVAILABLE:
        wl_db = [dict(r) for r in get_watchlist()]
        if any(s["code"] == code for s in wl_db):
            return api_response(success=False, error=f"股票 {code} 已存在", status_code=409)
        add_watchlist(code, name, market)

    ok1, out1 = run_script("sync_all.py", 120)
    _invalidate_init_cache()
    if ok1:
        return api_response(
            message=f"已添加 {name}({code})，全模块数据同步完成",
            watchlist=[dict(r) for r in get_watchlist()] if DB_AVAILABLE else [],
            output=out1[-500:] if out1 else "",
        )
    else:
        return api_response(
            success=False,
            error=f"数据同步失败: {code}",
            message="股票已加自选，但数据同步失败。请手动点击'刷新数据'",
            output=out1[-500:] if out1 else "",
        )


@app.post("/api/watchlist/remove")
async def api_watchlist_remove(request: Request):
    """Legacy watchlist remove (identical to original)."""
    body = await request.json()
    code = body.get("code", "").strip()
    if not code:
        return api_response(success=False, error="code required", status_code=400)

    try:
        _cleanup_stock_data(code)
    except Exception as e:
        return api_response(success=False, error=f"删除失败: {e}", status_code=500)

    return api_response(message=f"已移除 {code}，数据已更新")


# ──────────────────────────────────────────────────────────────────────────
# Quotes
# ──────────────────────────────────────────────────────────────────────────

@app.get("/api/v2/quotes")
def api_v2_quotes_batch():
    """Batch quotes (identical to original)."""
    try:
        return api_response(data=get_quotes()) if DB_AVAILABLE else api_response(
            success=False, error="DB not available", status_code=500)
    except Exception as e:
        return api_response(success=False, error=str(e), status_code=500)


@app.get("/api/v2/quotes/{code}")
def api_v2_quotes_single(code: str):
    """Single stock quote by path (identical to original)."""
    try:
        quotes = get_quotes() if DB_AVAILABLE else {}
        data = quotes.get(code, {})
        return api_response(data=data)
    except Exception as e:
        return api_response(success=False, error=str(e), status_code=500)


# ──────────────────────────────────────────────────────────────────────────
# Positions
# ──────────────────────────────────────────────────────────────────────────

@app.get("/api/v2/positions")
def api_v2_positions():
    """All positions (identical to original)."""
    try:
        data = get_positions()
        return api_response(data=data) if DB_AVAILABLE else api_response(
            success=False, error="DB not available", status_code=500)
    except Exception as e:
        return api_response(success=False, error=str(e), status_code=500)


@app.get("/api/v2/positions/current")
def api_v2_positions_current():
    """Current positions (identical to original)."""
    try:
        data = get_current_positions() if DB_AVAILABLE else {}
        return api_response(data=data, count=len(data))
    except Exception as e:
        return api_response(success=False, error=str(e), status_code=500)


@app.get("/api/v2/positions/closed")
def api_v2_positions_closed():
    """Closed positions (identical to original)."""
    try:
        data = get_closed_positions() if DB_AVAILABLE else {}
        return api_response(data=data, count=len(data))
    except Exception as e:
        return api_response(success=False, error=str(e), status_code=500)


@app.get("/api/v2/trades")
def api_v2_trades_batch(code: str = Query(default="")):
    """Trades list, optionally filtered by code (identical to original)."""
    try:
        data = get_trades(code if code else None) if DB_AVAILABLE else []
        return api_response(data=data, count=len(data))
    except Exception as e:
        return api_response(success=False, error=str(e), status_code=500)


@app.get("/api/v2/trades/{code}")
def api_v2_trades_single(code: str):
    """Single stock trades by path (identical to original)."""
    try:
        data = get_trades(code) if DB_AVAILABLE else []
        return api_response(data=data, count=len(data))
    except Exception as e:
        return api_response(success=False, error=str(e), status_code=500)


@app.get("/api/v2/dividends")
def api_v2_dividends_batch(code: str = Query(default=""),
                           source: str = Query(default="statement")):
    """Dividends list with source filter (identical to original)."""
    try:
        code_arg = code if code else None
        if source == 'all':
            data = get_dividends(code_arg) if DB_AVAILABLE else []
        else:
            data = get_statement_dividends(code_arg) if DB_AVAILABLE else []
        return api_response(
            data=data, count=len(data), source=source,
            source_note="对账单实际到账数据 — date=派息日, amount=到账金额, per_share=公式计算值(到账金额÷持仓股数)"
        )
    except Exception as e:
        return api_response(success=False, error=str(e), status_code=500)


@app.get("/api/v2/dividends/{code}")
def api_v2_dividends_single(code: str):
    """Single stock dividends by path (identical to original)."""
    try:
        data = get_statement_dividends(code) if DB_AVAILABLE else []
        return api_response(
            data=data, count=len(data),
            source_note="对账单实际到账数据 — date=派息日, amount=到账金额, per_share=公式计算值(到账金额÷持仓股数)"
        )
    except Exception as e:
        return api_response(success=False, error=str(e), status_code=500)


@app.get("/api/v2/dividend-yield-series")
def api_v2_dividend_yield_series(code: str = Query(...)):
    """Dividend yield time series (identical to original)."""
    if not code:
        return api_response(success=False, error="code required", status_code=400)
    try:
        data = get_dividend_yield_series(code) if DB_AVAILABLE else {}
        has_data = bool(data.get("labels"))
        dy_series = data.get("dy_series", [])
        latest_dy = None
        for v in reversed(dy_series):
            if v is not None:
                latest_dy = v
                break
        return api_response(
            data=data, has_data=has_data, latest_dy=latest_dy,
            source_note="公式计算值（TTM滚动推算）— 基于最近12个月分红与股价推算，与公司实际公布股息率可能存在差异"
        )
    except Exception as e:
        return api_response(success=False, error=str(e), status_code=500)


# ──────────────────────────────────────────────────────────────────────────
# K-line (daily + monthly)
# ──────────────────────────────────────────────────────────────────────────

@app.get("/api/v2/kline/daily")
def api_v2_kline_daily_batch(code: str = Query(default=None),
                              codes: str = Query(default=None)):
    """Batch or single daily kline (identical to original)."""
    try:
        DB_AVAILABLE  # reference for linter
        if code:
            data = get_kline_daily(code) if DB_AVAILABLE else []
            return api_response(data=data)
        else:
            data = get_all_kline_daily(codes.split(",") if codes else None) if DB_AVAILABLE else {}
            return api_response(data=data)
    except Exception as e:
        return api_response(success=False, error=str(e), status_code=500)


@app.get("/api/v2/kline/daily/{code}")
def api_v2_kline_daily_single(code: str):
    """Single stock daily kline by path (identical to original)."""
    try:
        data = get_kline_daily(code) if code and DB_AVAILABLE else []
        return api_response(data=data)
    except Exception as e:
        return api_response(success=False, error=str(e), status_code=500)


@app.get("/api/v2/kline/monthly")
def api_v2_kline_monthly_batch(code: str = Query(default=None),
                                codes: str = Query(default=None)):
    """Batch or single monthly kline (identical to original)."""
    try:
        if code:
            data = get_kline_monthly(code) if DB_AVAILABLE else []
            return api_response(data=data)
        else:
            data = get_all_kline_monthly(codes.split(",") if codes else None) if DB_AVAILABLE else {}
            return api_response(data=data)
    except Exception as e:
        return api_response(success=False, error=str(e), status_code=500)


@app.get("/api/v2/kline/monthly/{code}")
def api_v2_kline_monthly_single(code: str):
    """Single stock monthly kline by path (identical to original)."""
    try:
        data = get_kline_monthly(code) if code and DB_AVAILABLE else []
        return api_response(data=data)
    except Exception as e:
        return api_response(success=False, error=str(e), status_code=500)


# ──────────────────────────────────────────────────────────────────────────
# Predictions
# ──────────────────────────────────────────────────────────────────────────

@app.get("/api/v2/predictions/daily")
def api_v2_predictions_daily_batch():
    """Batch daily predictions (identical to original)."""
    try:
        data = get_all_predictions() if DB_AVAILABLE else []
        return api_response(data=data, count=len(data))
    except Exception as e:
        return api_response(success=False, error=str(e), status_code=500)


@app.get("/api/v2/predictions/daily/{code}")
def api_v2_predictions_daily_single(code: str):
    """Single stock daily predictions by path (identical to original)."""
    try:
        data = get_daily_predictions(code) if code and DB_AVAILABLE else []
        return api_response(data=data)
    except Exception as e:
        return api_response(success=False, error=str(e), status_code=500)


# ──────────────────────────────────────────────────────────────────────────
# News
# ──────────────────────────────────────────────────────────────────────────

@app.get("/api/v2/news")
def api_v2_news(filter: str = Query(default="all")):
    """News with filter (identical to original)."""
    try:
        data = get_news(filter) if DB_AVAILABLE else []
        return api_response(data=data)
    except Exception as e:
        return api_response(success=False, error=str(e), status_code=500)


# ──────────────────────────────────────────────────────────────────────────
# Expert reports
# ──────────────────────────────────────────────────────────────────────────

@app.get("/api/v2/expert")
def api_v2_expert_get():
    """Expert reports list (identical to original)."""
    try:
        data = get_expert_reports() if DB_AVAILABLE else []
        return api_response(data=data)
    except Exception as e:
        return api_response(success=False, error=str(e), status_code=500)


@app.post("/api/v2/expert/import")
async def api_v2_expert_import(request: Request):
    """Import expert report JSON (identical to original)."""
    report_json = await request.json()
    try:
        from import_expert_report import import_report
        ok, msg, warnings = import_report(report_json)
        resp = {"success": ok, "message": msg, "warnings": warnings}
        if not ok:
            resp["error"] = msg
        return JSONResponse(content=resp)
    except Exception as e:
        return api_response(success=False, error=f"报告导入异常: {e}", message=str(e), status_code=500)


@app.post("/api/expert/import")
async def api_expert_import_legacy(request: Request):
    """Legacy expert import — redirects to V2 (identical to original)."""
    return await api_v2_expert_import(request)


# ──────────────────────────────────────────────────────────────────────────
# Learning & Accuracy
# ──────────────────────────────────────────────────────────────────────────

@app.get("/api/v2/learning")
def api_v2_learning(code: str = Query(default="")):
    """Learning params, batch or single (identical to original)."""
    try:
        if code:
            data = get_learning_params(code)
            return api_response(success=data is not None, data=data)
        else:
            data = get_all_learning_params() if DB_AVAILABLE else {}
            return api_response(data=data)
    except Exception as e:
        return api_response(success=False, error=str(e), status_code=500)


@app.get("/api/v2/accuracy")
def api_v2_accuracy_batch():
    """Batch accuracy stats (identical to original). Must come before prefix match."""
    try:
        data = get_all_accuracy_stats() if DB_AVAILABLE else {}
        return api_response(data=data)
    except Exception as e:
        return api_response(success=False, error=str(e), status_code=500)


@app.get("/api/v2/accuracy/{code}")
def api_v2_accuracy_single(code: str):
    """Single stock accuracy stats by path (identical to original)."""
    try:
        data = get_accuracy_stats(code) if code and DB_AVAILABLE else {}
        return api_response(data=data)
    except Exception as e:
        return api_response(success=False, error=str(e), status_code=500)


# ──────────────────────────────────────────────────────────────────────────
# Seasonal
# ──────────────────────────────────────────────────────────────────────────

@app.get("/api/v2/seasonal")
def api_v2_seasonal_batch():
    """Batch seasonal factors (identical to original)."""
    try:
        data = get_all_seasonal() if DB_AVAILABLE else {}
        return api_response(data=data)
    except Exception as e:
        return api_response(success=False, error=str(e), status_code=500)


@app.get("/api/v2/seasonal/{code}")
def api_v2_seasonal_single(code: str):
    """Single stock seasonal by path (identical to original)."""
    try:
        data = get_seasonal(code) if code and DB_AVAILABLE else []
        return api_response(data=data)
    except Exception as e:
        return api_response(success=False, error=str(e), status_code=500)


# ──────────────────────────────────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────────────────────────────────

@app.get("/api/v2/config")
def api_v2_config():
    """System config (identical to original)."""
    try:
        cfg = get_config()
        return api_response(data=cfg)
    except Exception as e:
        return api_response(success=False, error=str(e), status_code=500)


# ──────────────────────────────────────────────────────────────────────────
# Search
# ──────────────────────────────────────────────────────────────────────────

@app.get("/api/search/stocks")
def api_search_stocks(q: str = Query(default="")):
    """A-share stock search (identical to original)."""
    keyword = q.strip()
    result = search_stocks(keyword) if keyword else []
    return api_response(data=result)


# ──────────────────────────────────────────────────────────────────────────
# System snapshot
# ──────────────────────────────────────────────────────────────────────────

@app.get("/api/v2/snapshot")
def api_v2_snapshot():
    """System snapshot (identical to original)."""
    try:
        if DB_AVAILABLE:
            data = {
                "generated": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
                "watchlist": get_watchlist() if DB_AVAILABLE else [],
                "quotes": get_quotes() if DB_AVAILABLE else {},
                "daily_predictions": get_all_predictions() if DB_AVAILABLE else [],
                "seasonal": get_all_seasonal() if DB_AVAILABLE else {},
            }
            return api_response(
                data=data,
                tables_used=["watchlist", "quotes", "daily_predictions", "seasonal"],
                source="sqlite",
            )
        else:
            return api_response(success=False, error="Database not available", status_code=503)
    except Exception as e:
        return api_response(success=False, error=str(e), code="SNAPSHOT_FAILED", status_code=500)


# ──────────────────────────────────────────────────────────────────────────
# Statement import status
# ──────────────────────────────────────────────────────────────────────────

@app.get("/api/v2/statement/status")
def api_v2_statement_status():
    """Statement import status (identical to original)."""
    try:
        if DB_AVAILABLE:
            db = sqlite3.connect(os.path.join(ROOT, "data", "stock.db"), timeout=10)
            trade_count = db.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
            pos_count = db.execute("SELECT COUNT(*) FROM positions").fetchone()[0]
            db.close()
            return api_response(
                data={"current_stocks": pos_count, "total_trades": trade_count, "source": "sqlite"}
            )
        else:
            return api_response(success=False, error="Database not available", status_code=503)
    except Exception as e:
        return api_response(success=False, error=str(e), code="STATUS_FAILED", status_code=500)


# ──────────────────────────────────────────────────────────────────────────
# Triggers (POST)
# ──────────────────────────────────────────────────────────────────────────

@app.post("/api/trigger/news")
def api_trigger_news():
    """Trigger news fetch (identical to original)."""
    ok, out = run_script("fetch_news.py", 60)
    return api_response(
        success=ok,
        output=out[-1000:] if out else "",
        message="新闻已刷新" if ok else "新闻刷新失败",
    )


@app.post("/api/trigger/update_statement")
def api_trigger_update_statement():
    """Trigger statement update (identical to original)."""
    ok, out = run_script("update_from_statement.py", 60)
    if ok:
        return api_response(
            message="持仓数据已更新，刷新页面查看",
            output=out[-1000:] if out else "",
        )
    else:
        return api_response(
            success=False,
            error="解析失败",
            message="对账单更新失败，请检查文件格式或重新上传",
            output=out[-1000:] if out else "",
        )


@app.post("/api/trigger/predict")
def api_trigger_predict():
    """Trigger full sync (identical to original)."""
    global _refresh_in_progress
    if _refresh_in_progress:
        return api_response(success=False, error="刷新已在运行中，请稍候", status_code=429)

    _refresh_in_progress = True
    try:
        ok, out = run_script("sync_all.py", 180)
        if ok:
            try:
                fresh_data = _build_init_data()
                return api_response(
                    message="全模块同步完成，数据已刷新",
                    output=out[-1500:] if out else "",
                    data=fresh_data,
                )
            except Exception:
                return api_response(
                    message="全模块同步完成，刷新页面查看",
                    output=out[-1000:] if out else "",
                )
        else:
            return api_response(
                success=False,
                error="同步失败",
                output=out[-1000:] if out else "",
            )
    finally:
        _refresh_in_progress = False


@app.post("/api/trigger/expert")
async def api_trigger_expert(request: Request):
    """Trigger expert analysis (identical to original — returns message, does not execute)."""
    body = await request.json()
    code = body.get("code", "")
    name = body.get("name", "")
    return api_response(
        message=f"专家分析需通过WorkBuddy交易分析团队执行。请使用 trading-analysis skill 对{name or code}进行完整Workflow A分析。",
    )


@app.post("/api/v2/quotes/refresh")
def api_v2_quotes_refresh():
    """Lightweight quotes refresh (identical to original)."""
    global _refresh_in_progress
    if _refresh_in_progress:
        return api_response(success=False, error="刷新已在运行中，请稍候", status_code=429)

    _refresh_in_progress = True
    try:
        ok, out = run_script("refresh_quotes.py", 60)
        if ok and out:
            try:
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
                    return api_response(
                        message=f"股价已刷新 ({data.get('count', 0)}只股票)",
                        data=data.get("data", {}),
                        refreshed_at=data.get("refreshed_at", ""),
                        stats=data.get("stats", {}),
                    )
                else:
                    return api_response(
                        message="股价已刷新",
                        output=out[-500:] if out else "",
                    )
            except json.JSONDecodeError:
                return api_response(
                    message="股价已刷新",
                    output=out[-500:] if out else "",
                )
        else:
            return api_response(
                success=False,
                error="刷新失败",
                output=out[-500:] if out else "",
            )
    finally:
        _refresh_in_progress = False


# ──────────────────────────────────────────────────────────────────────────
# File Upload — identical logic to original _handle_statement_upload()
# ──────────────────────────────────────────────────────────────────────────

@app.post("/api/upload/statement")
async def api_upload_statement(file: UploadFile = File(...)):
    """Handle GF Securities statement upload (identical to original)."""
    import shutil

    # Read file bytes
    file_data = await file.read()

    # ── Layer 1: File size check ──
    if len(file_data) < 100:
        return api_response(
            success=False,
            error="文件过小（可能为空或损坏）",
            message=f"上传文件仅 {len(file_data)} 字节，请确认选择了正确的对账单文件",
            status_code=400,
        )

    # ── Layer 2: Magic byte detection ──
    magic = file_data[:8]
    detected_format = _detect_file_format(magic)

    if detected_format != "xlsx":
        detail = _format_diagnostic(magic, file_data, detected_format)
        return api_response(
            success=False,
            error=detail["error"],
            message=detail["message"],
            diagnostics=detail,
            status_code=400,
        )

    # ── Layer 3: Save with backup ──
    dest = os.path.join(ROOT, "广发易淘金PC版-普通对账单结果查询.xlsx")

    if os.path.exists(dest):
        with open(dest, 'rb') as check:
            old_magic = check.read(4)
        if old_magic == b'PK\x03\x04':
            bak = dest + f".bak_{int(time.time())}"
            shutil.copy2(dest, bak)
            bak_latest = dest + ".upload_bak"
            if os.path.exists(bak_latest):
                os.remove(bak_latest)
            shutil.copy2(dest, bak_latest)
        else:
            bak = dest + ".was_corrupted"
            shutil.copy2(dest, bak)

    with open(dest, "wb") as f:
        f.write(file_data)

    print(f"[INFO] 对账单已保存: {dest} ({len(file_data):,} bytes, magic OK)", file=sys.stderr)

    # ── Step 1: Parse Excel ──
    ok, out = run_script("update_from_statement.py", 60)
    if not ok:
        return api_response(
            success=False,
            error="对账单解析失败",
            message="Excel 文件可能损坏、列名不匹配或包含无效数据。详见输出日志。",
            output=out[-500:] if out else "",
        )



    return api_response(
        message="对账单已更新，刷新页面查看",
        output=out[-500:] if out else "",
    )


@app.get("/data/{rest_of_path:path}")
async def serve_data_files(rest_of_path: str):
    """Serve static files from data/ directory (identical to original)."""
    path = f"data/{rest_of_path}"
    if rest_of_path.endswith(".py"):
        return api_response(success=False, error="Forbidden", status_code=403)
    result = _serve_file_content(path)
    if result is None:
        raise HTTPException(status_code=404)
    return result


@app.get("/scripts/{rest_of_path:path}")
async def serve_scripts_files(rest_of_path: str):
    """Serve static files from scripts/ directory (identical to original)."""
    if rest_of_path.endswith(".py"):
        return api_response(success=False, error="Forbidden", status_code=403)
    path = f"scripts/{rest_of_path}"
    result = _serve_file_content(path)
    if result is None:
        raise HTTPException(status_code=404)
    return result


@app.post("/api/v2/watchlist")
async def api_v2_watchlist_post(request: Request):
    """POST /api/v2/watchlist (RESTful, identical to original)."""
    global _refresh_in_progress
    body = await request.json()
    code = body.get("code", "").strip()
    name = body.get("name", "").strip()
    market = body.get("market", "sh").strip()

    if not code or not name:
        return api_response(success=False, error="code and name required", status_code=400)

    if DB_AVAILABLE:
        wl = [dict(r) for r in get_watchlist()]
        if any(s["code"] == code for s in wl):
            return api_response(success=False, error=f"股票 {code} 已存在", status_code=409)
        add_watchlist(code, name, market)

    ok1, out1 = run_script("sync_all.py", 120)
    _invalidate_init_cache()
    if ok1:
        return api_response(
            message=f"已添加 {name}({code})，全模块数据同步完成",
            watchlist=wl if DB_AVAILABLE else [],
            output=out1[-500:] if out1 else "",
        )
    else:
        return api_response(
            success=False,
            error=f"数据同步失败: {code}",
            message=f"股票已添加到自选股，但数据同步失败。请手动点击'刷新数据'按钮",
            output=out1[-500:] if out1 else "",
        )


# ──────────────────────────────────────────────────────────────────────────
# V0.9: Backtest + Paper Trading API
# ──────────────────────────────────────────────────────────────────────────

_backtest_in_progress = False
_backtest_lock = threading.Lock()
_backtest_process = None      # subprocess.Popen handle for cancellation
_backtest_run_id = None       # current run_id for cancellation
_backtest_cancelled = False   # flag set by stop endpoint

from db_helper import (
    get_db, init_backtest_tables, get_backtest_runs as _get_backtest_runs,
    insert_backtest_run, update_backtest_run, get_paper_account,
    get_paper_positions, get_paper_trades, get_paper_suggestions,
    get_paper_daily_snapshots, reset_paper_account,
    get_intraday_quotes, get_intraday_dates_for_code,
)

# V0.9 TODAY import (fallback to datetime if signals not loaded)
try:
    from signals import TODAY
except ImportError:
    TODAY = datetime.now().strftime("%Y-%m-%d")

# Market utils
try:
    from market_utils import is_market_open, get_market_status
except ImportError:
    def is_market_open(): return True
    def get_market_status(): return 'open'


@app.post("/api/v2/backtest/run")
async def api_backtest_run(request: Request):
    """Trigger backtest engine (async subprocess with cancellation support)."""
    global _backtest_in_progress, _backtest_process, _backtest_run_id
    with _backtest_lock:
        if _backtest_in_progress:
            return api_response(success=False, error="回测已在运行中", status_code=429)
        _backtest_in_progress = True

    try:
        # Ensure tables exist
        init_backtest_tables()
        body = await request.json()
        codes = body.get("codes", "")
        train_win = body.get("train_window", 252)
        test_win = body.get("test_window", 21)

        # Create run record
        run_id = insert_backtest_run(
            status='running', train_window=train_win, test_window=test_win,
            stock_codes=codes, total_stocks=len(codes.split(',')) if codes else len(get_watchlist_codes())
        )
        _backtest_run_id = run_id

        # Build command
        cmd = [PYTHON, os.path.join(ROOT, 'scripts', 'backtest_engine.py'),
               '--train', str(train_win), '--test', str(test_win),
               '--run-id', str(run_id)]
        if codes:
            cmd += ['--codes', codes]

        # Run backtest in background thread with Popen for cancellation
        def _run():
            global _backtest_in_progress, _backtest_process, _backtest_run_id, _backtest_cancelled
            proc = None
            try:
                proc = subprocess.Popen(
                    cmd, cwd=ROOT,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
                )
                _backtest_process = proc

                # Wait for completion
                stdout, stderr = proc.communicate(timeout=600)  # 10-minute max timeout

                if proc.returncode != 0:
                    if _backtest_cancelled:
                        update_backtest_run(run_id, status='error',
                            error_msg='用户取消', finished_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                    else:
                        err = (stderr or stdout or 'Unknown error')[:500]
                        update_backtest_run(run_id, status='error',
                            error_msg=f'Exit code {proc.returncode}: {err}')
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.communicate()
                update_backtest_run(run_id, status='error',
                    error_msg='回测超时(10分钟)', finished_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            except FileNotFoundError:
                update_backtest_run(run_id, status='error',
                    error_msg=f'Python解释器未找到: {PYTHON}')
            except Exception as e:
                update_backtest_run(run_id, status='error', error_msg=str(e))
            finally:
                _backtest_in_progress = False
                _backtest_process = None
                _backtest_run_id = None
                _backtest_cancelled = False

        threading.Thread(target=_run, daemon=True).start()
        return api_response(data={
            'run_id': run_id, 'status': 'running',
            'started_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'config': {'train_window': train_win, 'test_window': test_win}
        })
    except Exception as e:
        _backtest_in_progress = False
        _backtest_process = None
        _backtest_run_id = None
        return api_response(success=False, error=str(e), status_code=500)


@app.get("/api/v2/backtest/status")
def api_backtest_status():
    """Get current backtest status with accurate progress from DB."""
    global _backtest_in_progress
    db_rows = _get_backtest_runs()
    current = db_rows[0] if db_rows else None

    if current is None:
        return api_response(data={
            'status': 'idle', 'run_id': None, 'progress': None
        })

    db_status = current.get('status', 'idle')

    # Determine status: prefer DB status over in-memory flag for done/error/cancelled
    if _backtest_in_progress and db_status == 'running':
        status = 'running'
    elif db_status == 'done':
        status = 'done'
    elif db_status == 'error':
        error_msg = current.get('error_msg', '')
        if '用户取消' in (error_msg or ''):
            status = 'cancelled'
        else:
            status = 'error'
    elif db_status == 'running' and not _backtest_in_progress:
        # Stale record: process died but DB not updated yet
        # Auto-clean it on first detection
        try:
            update_backtest_run(
                current['id'], status='error',
                error_msg='服务重启，回测中断',
                finished_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            )
        except Exception:
            pass
        status = 'error'
    else:
        status = 'idle'

    progress = {
        'current': current.get('completed_stocks', 0),
        'total': current.get('total_stocks', 0),
        'current_stock': current.get('current_stock'),
        'run_id': current['id'],
    }

    return api_response(data={
        'status': status,
        'run_id': current['id'],
        'progress': progress,
    })


@app.post("/api/v2/backtest/stop")
def api_backtest_stop():
    """Stop a running backtest task and release resources."""
    global _backtest_in_progress, _backtest_process, _backtest_run_id, _backtest_lock, _backtest_cancelled

    with _backtest_lock:
        if not _backtest_in_progress:
            return api_response(success=False, error="没有正在运行的回测", status_code=404)

        run_id = _backtest_run_id
        proc = _backtest_process
        _backtest_cancelled = True

        # Terminate the subprocess
        if proc and proc.poll() is None:
            try:
                proc.terminate()   # SIGTERM on Unix, TerminateProcess on Windows
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()    # Force kill if terminate didn't work
                    proc.wait(timeout=3)
            except Exception:
                pass

        _backtest_in_progress = False
        _backtest_process = None
        _backtest_run_id = None

    # Update DB record to indicate cancellation (may also be updated by _run thread)
    if run_id:
        try:
            update_backtest_run(
                run_id, status='error',
                error_msg='用户取消',
                finished_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            )
        except Exception:
            pass

    return api_response(data={
        'message': '回测已停止',
        'run_id': run_id
    })


@app.get("/api/v2/backtest/results/{run_id}")
def api_backtest_results(run_id: int):
    db_rows = _get_backtest_runs()
    run = next((r for r in db_rows if r['id'] == run_id), None)
    if not run:
        return api_response(success=False, error="回测记录不存在", status_code=404)
    summary = json.loads(run['summary_json']) if run.get('summary_json') else {}
    return api_response(data={
        'run_id': run['id'], 'status': run['status'],
        'started_at': run['started_at'], 'finished_at': run['finished_at'],
        'config': {'train_window': run['train_window'], 'test_window': run['test_window']},
        'overall_metrics': summary,
    })


@app.get("/api/v2/backtest/history")
def api_backtest_history():
    rows = _get_backtest_runs()
    return api_response(data=rows, count=len(rows))


@app.get("/api/v2/paper/account")
def api_paper_account():
    try:
        account = get_paper_account()
        if not account:
            return api_response(data={'initialized': False, 'message': '虚拟账户未初始化'})
        # Compute position value from LIVE quotes (consistent with get_paper_positions display)
        db = get_db()
        _kd = "(SELECT close FROM kline_daily WHERE code=pp.code ORDER BY date DESC LIMIT 1)"
        agg = db.execute(f"""
            SELECT COALESCE(SUM(pp.qty * COALESCE(q.price, {_kd}, pp.last_price, pp.avg_cost)), 0) as pos_val
            FROM paper_positions pp
            LEFT JOIN quotes q ON pp.code = q.code
            WHERE pp.qty > 0
        """).fetchone()
        db.close()
        pos_val = agg['pos_val'] if agg else 0
        total_val = account['cash'] + pos_val
        return api_response(data={
            'initialized': True,
            'cash': account['cash'], 'initial_capital': account['initial_capital'],
            'total_asset': round(total_val, 2),
            'position_value': round(pos_val, 2),
            'cumulative_return_pct': round((total_val / account['initial_capital'] - 1) * 100, 2),
            'created_at': account['created_at'], 'updated_at': account['updated_at'],
        })
    except Exception as e:
        return api_response(success=False, error=str(e), status_code=500)


@app.get("/api/v2/paper/positions")
def api_paper_positions():
    try:
        positions = get_paper_positions()
        return api_response(data=positions, count=len(positions))
    except Exception as e:
        return api_response(success=False, error=str(e), status_code=500)


@app.get("/api/v2/paper/trades")
def api_paper_trades(code: str = Query(default=''), limit: int = Query(default=50), offset: int = Query(default=0)):
    trades, total = get_paper_trades(code if code else None, limit, offset)
    return api_response(data=trades, count=len(trades), total=total)


@app.get("/api/v2/paper/suggestions")
def api_paper_suggestions(code: str = Query(default=''), date: str = Query(default=None)):
    if date is None:
        date = TODAY
    _market_status = get_market_status()
    suggestions = get_paper_suggestions(date=date, code=code if code else None)

    # Only generate fresh & auto-execute for TODAY (not historical dates)
    is_today = (date == TODAY)
    if is_today:
        # Generate fresh suggestions if none exist for today
        if not suggestions:
            try:
                from paper_trading import generate_suggestions as _gen_sug
                fresh = _gen_sug()
                if fresh:
                    from db_helper import upsert_paper_suggestion
                    for sug in fresh:
                        upsert_paper_suggestion(sug)
                    suggestions = get_paper_suggestions(date=date, code=code if code else None)
            except Exception:
                pass

        # Auto-execute any UNEXECUTED suggestions only when market is open
        unexecuted = [s for s in (suggestions or []) if s.get('executed') != 1]
        if unexecuted and is_market_open():
            try:
                import sys as _sys
                _sys.stderr.write(f"[Paper API] Found {len(unexecuted)} unexecuted suggestions, calling auto_execute...\n")
                from paper_trading import auto_execute as _auto_exec
                _auto_exec()
                suggestions = get_paper_suggestions(date=date, code=code if code else None)
            except Exception as _e:
                import traceback as _tb
                _sys.stderr.write(f"[Paper API] auto_execute ERROR: {_e}\n{_tb.format_exc()}\n")
        elif unexecuted:
            import sys as _sys
            _sys.stderr.write(f"[Paper API] {len(unexecuted)} unexecuted suggestions but market is {_market_status}. Skipping.\n")

    return api_response(
        data=suggestions, count=len(suggestions),
        market_status=_market_status,
        generated_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    )


@app.get("/api/v2/paper/intraday/{code}")
def api_intraday_quotes(code: str, date: str = Query(default=None)):
    """Get intraday minute-level quotes for a stock on a given date.
    
    Args:
        code: Stock code (e.g. '601166')
        date: Date string 'YYYY-MM-DD'. Defaults to today.
    """
    try:
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')
        data = get_intraday_quotes(code, date)
        available_dates = get_intraday_dates_for_code(code)
        return api_response(data={
            'code': code,
            'date': date,
            'data': data,
            'count': len(data),
            'available_dates': available_dates,
        })
    except Exception as e:
        return api_response(success=False, error=str(e), status_code=500)


@app.post("/api/v2/paper/reset")
async def api_paper_reset(request: Request):
    try:
        body = await request.json()
        capital = body.get('initial_capital', 100000.0)
        reset_paper_account(capital)
        return api_response(data={
            'cash': capital, 'initial_capital': capital,
            'total_asset': capital, 'position_value': 0.0,
            'message': '虚拟账户已重置'
        })
    except Exception as e:
        return api_response(success=False, error=str(e), status_code=500)


@app.get("/api/v2/paper/performance")
def api_paper_performance(days: int = Query(default=90)):
    snapshots = get_paper_daily_snapshots(days)
    if not snapshots:
        return api_response(data={'message': '暂无历史数据'})
    snapshots.sort(key=lambda x: x['date'])

    # Get initial_capital from paper_account for accurate baseline
    account = get_paper_account()
    initial_capital = account['initial_capital'] if account else 100000

    # Build equity curve starting from day before first snapshot (initial capital baseline)
    from datetime import datetime, timedelta
    first_date = snapshots[0]['date']
    try:
        dt = datetime.strptime(first_date, '%Y-%m-%d')
        baseline_date = (dt - timedelta(days=1)).strftime('%Y-%m-%d')
    except ValueError:
        baseline_date = first_date

    equity_curve = [{'date': baseline_date, 'value': initial_capital}]
    equity_curve += [{'date': s['date'], 'value': s['total_asset']} for s in snapshots]

    final = snapshots[-1]['total_asset'] if snapshots else initial_capital
    total_return = round((final / initial_capital - 1) * 100, 2) if initial_capital else 0

    # ── Compute additional statistics from trades ──
    trades, total_trades = get_paper_trades(None, 99999, 0)
    win_rate = 0.0
    profit_factor = 0.0
    max_single_win = 0.0
    max_drawdown = 0.0

    # Compute from equity_curve
    peak = equity_curve[0]['value']
    for pt in equity_curve:
        val = pt['value']
        if val > peak:
            peak = val
        dd = (peak - val) / peak * 100 if peak > 0 else 0
        if dd > max_drawdown:
            max_drawdown = dd

    # Compute from trades with realized_pnl (for win_rate, profit_factor, max_single_win)
    closed_trades = [t for t in trades if t.get('realized_pnl') is not None]
    if closed_trades:
        wins = [t for t in closed_trades if t['realized_pnl'] > 0]
        losses = [t for t in closed_trades if t['realized_pnl'] < 0]
        win_rate = round(len(wins) / len(closed_trades) * 100, 2) if closed_trades else 0.0
        total_wins = sum(t['realized_pnl'] for t in wins) if wins else 0
        total_losses = sum(abs(t['realized_pnl']) for t in losses) if losses else 0
        profit_factor = round(total_wins / total_losses, 2) if total_losses > 0 else (total_wins if total_wins > 0 else 0.0)
        max_single_win = round(max(t['realized_pnl'] for t in wins), 2) if wins else 0.0

    return api_response(data={
        'total_return_pct': total_return,
        'equity_curve': equity_curve,
        'latest': snapshots[-1] if snapshots else None,
        'initial_capital': initial_capital,
        'max_drawdown_pct': round(max_drawdown, 2),
        'win_rate_pct': win_rate,
        'profit_factor': profit_factor,
        'total_trades': total_trades,  # total transactions (buy + sell)
        'max_single_win': max_single_win,
    })


# ──────────────────────────────────────────────────────────────────────────
# K-line Pattern Rules API
# ──────────────────────────────────────────────────────────────────────────

@app.get("/api/v2/pattern-rules")
def api_pattern_rules_list(enabled: str = Query(default="")):
    """Get all pattern rules, optionally only enabled ones."""
    try:
        if enabled == '1':
            data = get_pattern_rules(enabled_only=True)
        else:
            data = get_pattern_rules()
        return api_response(data=data, count=len(data))
    except Exception as e:
        return api_response(success=False, error=str(e), status_code=500)


@app.get("/api/v2/pattern-rules/{rule_id}")
def api_pattern_rule_get(rule_id: str):
    """Get a single pattern rule by rule_id."""
    try:
        data = get_pattern_rule(rule_id)
        if not data:
            return api_response(success=False, error=f"规则 {rule_id} 不存在", status_code=404)
        return api_response(data=data)
    except Exception as e:
        return api_response(success=False, error=str(e), status_code=500)


@app.post("/api/v2/pattern-rules")
async def api_pattern_rule_create(request: Request):
    """Create a new pattern rule."""
    try:
        body = await request.json()
        rid = body.get('rule_id', '').strip()
        if not rid:
            return api_response(success=False, error="rule_id 不能为空", status_code=400)
        existing = get_pattern_rule(rid)
        if existing:
            return api_response(success=False, error=f"规则 {rid} 已存在", status_code=409)
        insert_pattern_rule(body)
        return api_response(message=f"规则 {rid} 已创建", data=get_pattern_rule(rid))
    except Exception as e:
        return api_response(success=False, error=str(e), status_code=500)


@app.put("/api/v2/pattern-rules/{rule_id}")
async def api_pattern_rule_update(rule_id: str, request: Request):
    """Update an existing pattern rule."""
    try:
        body = await request.json()
        existing = get_pattern_rule(rule_id)
        if not existing:
            return api_response(success=False, error=f"规则 {rule_id} 不存在", status_code=404)
        ok = update_pattern_rule(rule_id, body)
        if ok:
            return api_response(message=f"规则 {rule_id} 已更新", data=get_pattern_rule(rule_id))
        return api_response(message="无需更新")
    except Exception as e:
        return api_response(success=False, error=str(e), status_code=500)


@app.delete("/api/v2/pattern-rules/{rule_id}")
def api_pattern_rule_delete(rule_id: str):
    """Delete a pattern rule."""
    try:
        ok = delete_pattern_rule(rule_id)
        if not ok:
            return api_response(success=False, error=f"规则 {rule_id} 不存在", status_code=404)
        return api_response(message=f"规则 {rule_id} 已删除")
    except Exception as e:
        return api_response(success=False, error=str(e), status_code=500)


@app.post("/api/v2/pattern-rules/init")
def api_pattern_rules_init():
    """Initialize 33 default pattern rules (idempotent)."""
    try:
        import subprocess, sys as _sys
        python = _sys.executable or r"C:\Users\28312\AppData\Local\Programs\Python\Python312\python.exe"
        script = os.path.join(ROOT, "scripts", "init_pattern_rules.py")
        result = subprocess.run([python, script], cwd=ROOT, capture_output=True, text=True, timeout=30)
        output = result.stdout[-2000:] if result.stdout else ""
        if result.stderr:
            output += "\n[ERR] " + result.stderr[-1000:]
        return api_response(
            success=result.returncode == 0,
            message="规则初始化完成" if result.returncode == 0 else "初始化失败",
            output=output
        )
    except Exception as e:
        return api_response(success=False, error=str(e), status_code=500)


@app.get("/api/v2/pattern-scan/{code}")
def api_pattern_scan(code: str):
    """Scan daily kline for pattern matches."""
    try:
        kdata = get_kline_daily(code)
        if not kdata:
            return api_response(data={'patterns': [], 'summary': {
                'bullish': {'count': 0, 'max_strength': 0},
                'bearish': {'count': 0, 'max_strength': 0},
                'neutral': {'count': 0}, 'total': 0
            }})
        # kdata from db_helper is newest-first [(date,open,close,high,low), ...]
        from pattern_engine import scan_patterns
        result = scan_patterns(kdata, code=code)
        # 转换结果为前端友好格式
        patterns = result.get('patterns', [])
        frontend_result = {
            'bullish': [{'rule_id': p['rule_id'], 'name': p['name'],
                         'idx': p['idx'], 'price': p['price'],
                         'date': p['date'], 'strength': p['strength'], 'direction': p['direction']}
                        for p in patterns if p['direction'] == 'bullish'],
            'bearish': [{'rule_id': p['rule_id'], 'name': p['name'],
                         'idx': p['idx'], 'price': p['price'],
                         'date': p['date'], 'strength': p['strength'], 'direction': p['direction']}
                        for p in patterns if p['direction'] == 'bearish'],
            'neutral': [{'rule_id': p['rule_id'], 'name': p['name'],
                         'idx': p['idx'], 'price': p['price'],
                         'date': p['date'], 'strength': p['strength']}
                        for p in patterns if p['direction'] == 'neutral'],
            'summary': result.get('summary', {}),
            'code': code,
        }
        return api_response(data=frontend_result)
    except Exception as e:
        return api_response(success=False, error=str(e), status_code=500)


# ─── Main entry point ────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    print(f"[Stock] 股票投资管理系统 API 服务器 (FastAPI 迁移版)")
    print(f"   地址: http://localhost:{PORT}")
    print(f"   API文档: http://localhost:{PORT}/docs")
    print(f"   原版: http://localhost:8765")
    print(f"   目录: {ROOT}")
    print(f"   Ctrl+C 停止")
    print()
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")
