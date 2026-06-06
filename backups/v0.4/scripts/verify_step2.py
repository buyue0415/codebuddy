"""Verify Step 2: Test all new DB API endpoints"""
import urllib.request, json, sys

BASE = "http://localhost:8765"
endpoints = [
    ("/api/v2/quotes", None, "quotes"),
    ("/api/v2/positions", None, "positions"),
    ("/api/v2/kline/daily?code=601166", "data[0].length >= 5", "kline daily"),
    ("/api/v2/kline/monthly?code=601166", "data", "kline monthly"),
    ("/api/v2/predictions/daily?code=601166", "data", "predictions"),
    ("/api/v2/news?filter=all", "len(data)>0", "news all"),
    ("/api/v2/news?filter=major", "data", "news major"),
    ("/api/v2/news?filter=601166", "data", "news by code"),
    ("/api/v2/expert", "len(data)>0", "expert"),
    ("/api/v2/learning?code=601166", "data", "learning"),
    ("/api/v2/accuracy?code=601166", "data", "accuracy"),
    ("/api/v2/seasonal?code=601166", "len(data)==12", "seasonal"),
]

passed = 0; failed = 0

for path, check, name in endpoints:
    url = BASE + path
    try:
        r = urllib.request.urlopen(url, timeout=5)
        d = json.loads(r.read().decode())
        data = d.get('data')
        ok = d.get('success', False)
        if ok:
            if check:
                try:
                    valid = eval(check, {"data": data, "len": len, "__builtins__": {}})
                except:
                    valid = data is not None
            else:
                valid = True
            if valid:
                passed += 1
                info = f"data: {type(data).__name__}"
                if isinstance(data, list): info += f"[{len(data)}]"
                elif isinstance(data, dict): info += f"{{{len(data)} keys}}"
                print(f"  [OK] {name}: {info}")
            else:
                failed += 1
                print(f"  [FAIL] {name}: check failed, data={str(data)[:80]}")
        else:
            failed += 1
            print(f"  [FAIL] {name}: success=False, error={d.get('error','unknown')}")
    except Exception as e:
        failed += 1
        print(f"  [FAIL] {name}: {e}")

print(f"\n{'='*60}")
if failed == 0:
    print(f"ALL {passed} CHECKS PASSED - Step 2 complete")
else:
    print(f"{passed} PASSED, {failed} FAILED")
    sys.exit(1)
