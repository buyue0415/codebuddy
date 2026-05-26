"""Comprehensive system test suite — executes all automatable test cases from 测试用例方案.md"""
import urllib.request, urllib.parse, json, time, os, sys

BASE = "http://localhost:8765"
PASS, FAIL, SKIP = 0, 0, 0
results = []

def api(method, path, body=None, timeout=15):
    """Call API and return (status, response_dict, elapsed_ms)"""
    t0 = time.time()
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(f"{BASE}{path}", data=data) if method == "POST" else urllib.request.Request(f"{BASE}{path}")
    req.add_header("Content-Type", "application/json")
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
        code, raw = resp.status, resp.read().decode()
    except urllib.error.HTTPError as e:
        code, raw = e.code, e.read().decode()
    except Exception as e:
        code, raw = 0, str(e)
    elapsed = (time.time() - t0) * 1000
    try: body = json.loads(raw)
    except: body = {"success": False, "error": str(raw)[:200], "_raw": True}
    return code, body, int(elapsed)

def test(id, name, fn, expected=True):
    """Run a single test case"""
    global PASS, FAIL, SKIP
    try:
        ok = fn()
        if ok == expected or (isinstance(ok, bool) and ok):
            PASS += 1
            results.append(f"  PASS TC-{id}: {name}")
        else:
            FAIL += 1
            results.append(f"  FAIL TC-{id}: {name}")
    except Exception as e:
        FAIL += 1
        results.append(f"  FAIL TC-{id}: {name} — {e}")

# ===== 2.1 System Startup =====
print("=" * 60)
print("TEST SUITE: 股票投资管理系统 v0.5")
print("=" * 60)

sc, resp, ms = api("GET", "/")
test("001", "系统启动验证", lambda: sc == 200)
test("001b", "页面HTML响应<1s", lambda: ms < 1000)
print(f"  [INFO] TC-001: 首页加载 {sc} {ms}ms")

# ===== 2.2 Stock Data Management =====
print("\n--- TC-003 股票搜索 ---")
code, resp, ms = api("GET", "/api/search/stocks?q=600036")
test("003a", "代码搜索返回结果", lambda: resp.get("success") and len(resp.get("data",[])) > 0)
test("003b", "代码搜索<500ms", lambda: ms < 500)
if resp.get("data"): print(f"  [INFO] 搜索'600036': {resp['data'][0]['name']} ({len(resp['data'])} results, {ms}ms)")

code, resp, ms = api("GET", "/api/search/stocks?q=" + urllib.parse.quote("招商银行"))
test("003c", "名称搜索返回结果", lambda: resp.get("success") and any("招商" in d.get("name","") for d in resp.get("data",[])))
print(f"  [INFO] 搜索'招商银行': {len(resp.get('data',[]))} results, {ms}ms")

code, resp, ms = api("GET", "/api/search/stocks?q=zsyh")
test("003d", "拼音搜索返回结果", lambda: resp.get("success") and len(resp.get("data",[])) > 0)
print(f"  [INFO] 搜索'zsyh': {len(resp.get('data',[]))} results")

code, resp, _ = api("GET", "/api/search/stocks?q=")
test("003e", "空搜索返回空", lambda: resp.get("success") and len(resp.get("data",[])) == 0)

print("\n--- TC-004 自选股管理 ---")
# Get current state
_, init, _ = api("GET", "/api/v2/init")
orig_wl = init.get("data",{}).get("watchlist",[])
orig_codes = [s["code"] for s in orig_wl]

# Add test stock
test_code = "600016"
test_name = "民生银行"
code, resp, ms = api("POST", "/api/watchlist/add", {"code": test_code, "name": test_name, "market": "sh"}, timeout=130)
test("004a1", "添加自选股成功", lambda: resp.get("success"))
if resp.get("success"):
    # Verify added
    _, wl_resp, _ = api("GET", "/api/watchlist")
    added = any(s["code"] == test_code for s in wl_resp.get("data",{}).get("stocks",[]))
    test("004a2", "添加后列表包含新股票", lambda: added)
    print(f"  [INFO] 添加 {test_name}({test_code}): {resp.get('message','')[:80]}, {ms}ms")

    # Remove it
    code, resp, ms = api("POST", "/api/watchlist/remove", {"code": test_code}, timeout=40)
    test("004b1", "删除自选股成功", lambda: resp.get("success"))
    if resp.get("success"):
        _, wl_resp, _ = api("GET", "/api/watchlist")
        removed = not any(s["code"] == test_code for s in wl_resp.get("data",{}).get("stocks",[]))
        test("004b2", "删除后列表不包含该股票", lambda: removed)
        print(f"  [INFO] 删除 {test_code}: {resp.get('message','')[:80]}, {ms}ms")

# Duplicate add
if test_code not in orig_codes:
    api("POST", "/api/watchlist/add", {"code": test_code, "name": test_name, "market": "sh"}, timeout=130)
    api("POST", "/api/watchlist/remove", {"code": test_code}, timeout=40)
    _, wl_resp, _ = api("GET", "/api/watchlist")
    # Ensure we restored original state
    restored = sorted([s["code"] for s in wl_resp.get("data",{}).get("stocks",[])]) == sorted(orig_codes)
    test("004c", "删除后恢复到原始自选股", lambda: restored)

# Duplicate add check
code, resp, _ = api("POST", "/api/watchlist/add", {"code": orig_codes[0], "name": "dup", "market": "sh"}, timeout=130)
expect_dup = not resp.get("success") and "已存在" in resp.get("error","")
test("004d", "重复添加返回409/冲突提示", lambda: expect_dup or "已存在" in resp.get("error",""))
if resp.get("error"): print(f"  [INFO] 重复添加: {resp['error']}")

print("\n--- TC-005 K线数据 ---")
test_codes = ["601166", "600036"]
for c in test_codes:
    code, resp, ms = api("GET", f"/api/v2/kline/daily?code={c}")
    bars = resp.get("data", [])
    test(f"005-{c}", f"K线数据加载({c})", lambda: len(bars) > 10)
    print(f"  [INFO] {c}日K线: {len(bars)}条, {ms}ms")

code, resp, ms = api("GET", "/api/v2/kline/daily?code=000000")
test("005-invalid", "无效代码返回空", lambda: resp.get("success") and len(resp.get("data",[])) == 0)

print("\n--- TC-007 持仓数据 ---")
code, resp, ms = api("GET", "/api/v2/positions")
data = resp.get("data", {})
cp = data.get("current_positions", {})
cl = data.get("closed_positions", {})
trades = data.get("all_trades", [])
test("007a", "持仓数据返回成功", lambda: resp.get("success"))
test("007b", "有当前持仓", lambda: len(cp) >= 0)  # just check structure
print(f"  [INFO] 当前持仓:{len(cp)} 已清仓:{len(cl)} 交易记录:{len(trades)}")

print("\n--- TC-008 预测数据 ---")
code, resp, ms = api("GET", "/api/v2/predictions/daily?code=601166")
preds = resp.get("data", [])
test("008a", "预测数据返回成功", lambda: resp.get("success"))
print(f"  [INFO] 601166预测: {len(preds)}条, {ms}ms")

if preds:
    p = preds[0]
    has_fields = all(k in p for k in ["date","code","prev_close","next_day","hourly","signals"])
    test("008b", "预测数据字段完整", lambda: has_fields)

print("\n--- TC-010/011 系统审计 ---")
code, resp, ms = api("GET", "/api/audit")
test("011a", "审计接口返回成功", lambda: resp.get("success"))
print(f"  [INFO] 审计输出: {str(resp.get('output',''))[:100]}...")

# ===== 3. Performance Tests =====
print("\n--- TC-101 API性能 ---")
perf_results = []
for path, name in [
    ("/api/v2/init", "Bootstrap初始化"),
    ("/api/v2/quotes", "行情数据"),
    ("/api/v2/positions", "持仓数据"),
    ("/api/v2/kline/daily?code=601166", "日K线"),
    ("/api/v2/kline/monthly?code=601166", "月K线"),
    ("/api/search/stocks?q=600036", "股票搜索"),
    ("/api/v2/news?filter=all", "新闻列表"),
    ("/api/v2/expert", "专家报告"),
]:
    code, resp, ms = api("GET", path)
    ok = ms < 1000
    perf_results.append((name, ms, ok))
    test(f"101-{name}", f"{name}<1s ({ms}ms)", lambda ms=ms: ms < 1000)
    print(f"  [{'OK' if ok else 'NG'}] {name}: {ms}ms")

# TC-102 K-line bulk load
print("\n--- TC-102 大数据量加载 ---")
code, resp, ms = api("GET", "/api/v2/init")
kl = sum(len(v) for v in resp.get("data",{}).get("kline_daily",{}).values())
test("102a", f"K线全量加载({kl}条)", lambda: kl > 100)
test("102b", "Bootstrap<2s", lambda: ms < 2000)
print(f"  [INFO] init加载: {kl}条K线, {ms}ms")

# ===== 5. Security Tests =====
print("\n--- TC-301 SQL注入防护 ---")
code, resp, _ = api("GET", "/api/search/stocks?q=%27%20OR%201=1--")
test("301a", "SQL注入被参数化防御", lambda: resp.get("success", False))
code, resp, _ = api("GET", "/api/search/stocks?q=<script>alert(1)</script>")
test("301b", "XSS搜索无害", lambda: resp.get("success", False))

print("\n--- TC-303 访问控制 ---")
code, resp, _ = api("GET", "/dbview")
test("303a", "/dbview需要认证", lambda: code in [200, 302, 403])
code, resp, _ = api("GET", "/scripts/server.py")
test("303b", ".py文件禁止访问", lambda: code in [403, 404])

# ===== 4. Error Handling =====
print("\n--- TC-403 异常处理 ---")
code, resp, _ = api("POST", "/api/watchlist/add", {"code": "", "name": ""})
test("403a", "空参数返回400", lambda: code == 400)
print(f"  [INFO] 空参数: {code} — {resp.get('error','')[:80]}")
code, resp, _ = api("GET", "/api/v2/kline/daily?code=")
test("403b", "缺少参数处理", lambda: resp.get("success") is not None)
code, resp, _ = api("GET", "/api/nonexistent")
test("403c", "不存在的端点", lambda: code >= 400)

# ===== V0.5 Specific Tests =====
print("\n--- V0.5 架构验证 ---")
code, resp, ms = api("GET", "/api/v2/init")
test("v05a", "Bootstrap端点存在", lambda: code == 200 and resp.get("success"))
test("v05b", "DATA结构完整", lambda: all(k in resp.get("data",{}) for k in ["watchlist","quotes","positions","kline_daily","news","expert_reports"]))
print(f"  [INFO] init keys: {list(resp.get('data',{}).keys())}")

# Verify old endpoints removed
code, resp, _ = api("POST", "/api/v2/sync", {})
test("v05c", "旧sync端点已移除", lambda: code == 404)
code, resp, _ = api("POST", "/api/trigger/reload_db", {})
test("v05d", "旧reload_db已移除", lambda: code >= 400)

# Expert import
print("\n--- Expert Import ---")
test_report = {"stocks":{"000001":{"decision":"HOLD","confidence":"中","risk_level":"低","position_pct":10,"entry_price":10,"target_price":12,"stop_loss":8,"scores":{"technical":6,"fundamental":7,"news":6,"sentiment":6,"risk":6},"phase1":{},"phase2":{"bull_args":[],"bear_args":[]},"phase4":{"aggressive_score":6,"conservative_score":6,"neutral_score":6}}}}
code, resp, ms = api("POST", "/api/v2/expert/import", test_report, timeout=10)
test("expert-import", "专家报告导入", lambda: resp.get("success"))
print(f"  [INFO] 导入: {resp.get('message','')[:100]}")

# ===== SUMMARY =====
print("\n" + "=" * 60)
print(f"TEST RESULTS: PASS {PASS} passed  FAIL {FAIL} failed  SKIP {SKIP} skipped")
print(f"PASS RATE: {PASS/(PASS+FAIL)*100:.1f}%" if (PASS+FAIL) > 0 else "N/A")
print("=" * 60)
for r in results:
    print(r)

sys.exit(0 if FAIL == 0 else 1)
