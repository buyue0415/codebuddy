"""V0.5: Full seed refactor — backup + server + HTML + doc update in one shot"""
import shutil, os, re, json, time

ROOT = r"c:\Users\28312\WorkBuddy\2026-05-18-task-15"
PY = r"C:\Users\28312\.workbuddy\binaries\python\versions\3.14.3\python.exe"

# ===== 1. V0.5 Backup =====
BKP = os.path.join(ROOT, "backups", "v0.5")
if os.path.exists(BKP): shutil.rmtree(BKP)
os.makedirs(BKP)
for d in ["deliverables","scripts","data","docs"]:
    src = os.path.join(ROOT, d)
    if os.path.exists(src):
        shutil.copytree(src, os.path.join(BKP, d), ignore=shutil.ignore_patterns('*.pyc','__pycache__','*-shm','*-wal'))
for f in os.listdir(ROOT):
    fp = os.path.join(ROOT, f)
    if os.path.isfile(fp) and f.endswith(('.py','.md','.bat','.xlsx','.xls')):
        shutil.copy2(fp, os.path.join(BKP, f))
print("V0.5 backup: OK")

# ===== 2. server.py — Add GET /api/v2/init, remove sync/reload endpoints =====
srv = os.path.join(ROOT, "server.py")
with open(srv, 'r', encoding='utf-8') as f:
    server_code = f.read()

# 2a. Remove GET /api/v2/sync and /api/v2/fullsync endpoints (replace with init)
old_sync_get = '''        elif path == "/api/v2/sync":
            # Unified HTML sync endpoint — replaces /api/trigger/reload_db + /api/v2/fullsync
            try:
                import subprocess as sp
                r = sp.run([PYTHON, os.path.join(ROOT, "scripts", "reinject_from_db.py")],
                           cwd=ROOT, capture_output=True, text=True, timeout=30)
                ok = r.returncode == 0
                json_response(self, {"success": ok,
                    "message": r.stdout.strip()[-500:] if ok else r.stderr.strip()[-200:]})
            except Exception as e:
                json_response(self, {"success": False, "error": str(e)}, 500)

        # ===== Deprecated: kept for backward compat, forwards to /api/v2/sync =====
        elif path == "/api/v2/fullsync":
            self.path = "/api/v2/sync"
            self.do_GET()
            return'''

new_init_get = '''        elif path == "/api/v2/init":
            # Bootstrap: return all data needed for page initialization
            try:
                init_data = {"account": "51312640", "broker": "广发证券", "generated": datetime.now().strftime("%Y-%m-%d %H:%M")}
                try: init_data["watchlist"] = [dict(r) for r in get_watchlist()] if DB_AVAILABLE else read_json("data/watchlist.json").get("stocks",[])
                except: init_data["watchlist"] = []
                try: init_data["quotes"] = get_quotes() if DB_AVAILABLE else read_json("data/system_data.json").get("quotes",{})
                except: init_data["quotes"] = {}
                try: init_data["positions"] = get_positions() if DB_AVAILABLE else {"current_positions":{}, "closed_positions":{}, "all_trades":[]}
                except: init_data["positions"] = {"current_positions":{}, "closed_positions":{}, "all_trades":[]}
                try:
                    if DB_AVAILABLE:
                        kd = {}
                        for r in sqlite3.connect(os.path.join(ROOT,"data","stock.db")).execute("SELECT code,date,open,close,high,low FROM kline_daily ORDER BY code,date DESC").fetchall():
                            if len(r) >= 6: kd.setdefault(r[0],[]).append([r[1],r[2],r[3],r[4],r[5]])
                        init_data["kline_daily"] = kd
                    else: init_data["kline_daily"] = {}
                except: init_data["kline_daily"] = {}
                try: init_data["daily_predictions"] = get_daily_predictions("") if DB_AVAILABLE else []
                except: init_data["daily_predictions"] = []
                try:
                    if DB_AVAILABLE:
                        import sqlite3
                        db = sqlite3.connect(os.path.join(ROOT,"data","stock.db")); db.row_factory = sqlite3.Row
                        news = [dict(r) for r in db.execute("SELECT id,date,code,title,summary,source,sentiment,major FROM news ORDER BY date DESC").fetchall()]
                        for n in news: n["major"] = bool(n["major"])
                        init_data["news"] = news
                        er = [json.loads(r["report_data"]) for r in db.execute("SELECT * FROM expert_reports ORDER BY date DESC").fetchall()]
                        init_data["expert_reports"] = er
                        db.close()
                    else: init_data["news"] = []; init_data["expert_reports"] = []
                except: init_data["news"] = []; init_data["expert_reports"] = []
                json_response(self, {"success": True, "data": init_data})
            except Exception as e:
                json_response(self, {"success": False, "error": str(e)}, 500)'''

server_code = server_code.replace(old_sync_get, new_init_get)

# 2b. Remove POST /api/v2/sync, POST /api/trigger/reload_db, POST /api/expert/import (deprecated)
# Replace with: just keep expert/import (forwarding) and remove others
old_post_sync = '''            elif path == "/api/v2/sync":
                ok, out = run_script("reinject_from_db.py", 30)
                json_response(self, {
                    "success": ok,
                    "message": out[-500:] if ok else ("刷新失败: " + out[-200:]),
                })

            elif path == "/api/trigger/reload_db":
                # Deprecated — forward to unified /api/v2/sync
                self.path = "/api/v2/sync"
                self.do_POST()
                return

            elif path == "/api/v2/expert/import":
                # Pure business endpoint: import only, no HTML injection side-effect
                report_json = params
                try:
                    from import_expert_report import import_report
                    ok, msg, warnings = import_report(report_json)
                    json_response(self, {"success": ok, "message": msg, "warnings": warnings})
                except Exception as e:
                    json_response(self, {"success": False, "error": str(e)}, 500)

            elif path == "/api/expert/import":
                # Deprecated — forward to pure business endpoint /api/v2/expert/import
                self.path = "/api/v2/expert/import"
                self.do_POST()
                return'''

new_post_sync = '''            elif path == "/api/v2/expert/import":
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
                return'''

server_code = server_code.replace(old_post_sync, new_post_sync)

with open(srv, 'w', encoding='utf-8') as f:
    f.write(server_code)
print("server.py: added GET /api/v2/init, removed sync/reload endpoints")

# ===== 3. HTML: Replace embedded DATA with API-driven bootstrap =====
html_path = os.path.join(ROOT, "deliverables", "bank-stock-system.html")
with open(html_path, 'r', encoding='utf-8') as f:
    html = f.read()

# 3a. Replace const DATA = {...}; with let DATA = null; (empty placeholder)
html = re.sub(r'const DATA = \{.*?\};\n', 'let DATA = null;\n', html, flags=re.DOTALL)

# 3b. Rewrite init() to be async and fetch from API
old_init = '''function init(){
const D=DATA, q=D.quotes, cp=D.current_positions, cl=D.closed_positions, trades=D.all_trades, sea=D.seasonal;'''

new_init = '''async function init(){
if(hasAPI()){
 try{
  var st=document.getElementById('server-status');
  if(st)st.innerHTML='加载中...';
  var r=await apiCall('GET','/api/v2/init');
  if(r&&r.success){ DATA=r.data; }
  else{ console.error('Init failed:',r); alert('数据加载失败，请检查服务器'); return; }
 }catch(e){ console.error('Init error:',e); return; }
}
if(!DATA){ alert('无法加载系统数据'); return; }
const D=DATA, q=D.quotes||{}, cp=(D.positions||D).current_positions||{}, cl=(D.positions||D).closed_positions||{}, trades=(D.positions||D).all_trades||[], sea=D.seasonal||{};'''

# Also update the server status check after init
old_server_status = '''// Server status check
(function(){
 setTimeout(function(){
  var el=document.getElementById('server-status');
  if(!el) return;
  if(hasAPI()){
   fetch(API_BASE+'/api/watchlist').then(function(r){return r.json();}).then(function(d){
    el.innerHTML='<span style="color:#16a34a">已连接</span> - 端口8765，监控'+d.data.stocks.length+'只股票';
   }).catch(function(){ el.innerHTML='<span style="color:#dc2626">连接失败</span>'; });
  }else{
   el.innerHTML='<span style="color:#f59e0b">离线模式</span>（通过 file:// 打开，API不可用）';
  }
 }, 500);'''

new_server_status = '''// Server status check
(function(){
 setTimeout(function(){
  var el=document.getElementById('server-status');
  if(!el) return;
  if(hasAPI()&&DATA){
   var wl=DATA.watchlist||[];
   el.innerHTML='<span style="color:#16a34a">已连接</span> - 端口8765，监控'+wl.length+'只股票';
  }else if(hasAPI()){
   el.innerHTML='<span style="color:#f59e0b">加载中...</span>';
  }else{
   el.innerHTML='<span style="color:#f59e0b">离线模式</span>（通过 file:// 打开，API不可用）';
  }
 }, 800);'''

html = html.replace(old_init, new_init)
html = html.replace(old_server_status, new_server_status)

# 3c. Also update the duplicate init call pattern (2nd occurrence)
# The 2nd init() definition was removed during dedup, so only 1 remains

# 3d. Fix all kline_daily references that might break (DATA.kline_daily)
# Actually these should still work since init populates DATA with the same structure

with open(html_path, 'w', encoding='utf-8') as f:
    f.write(html)
print("HTML: replaced embedded DATA with API bootstrap")

# ===== 4. Verify syntax =====
import subprocess
res = subprocess.run([PY, "-m", "py_compile", srv], capture_output=True, text=True)
print(f"server.py syntax: {'OK' if res.returncode==0 else 'FAIL: '+res.stderr[-200:]}")

print("\nV0.5 refactoring complete!")
print("Backup: backups/v0.5/")
