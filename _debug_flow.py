"""Simulate the frontend API data flow for intraday chart."""
import urllib.request, json as j

BASE = 'http://127.0.0.1:8766'

def get(path):
    r = urllib.request.urlopen(BASE + path, timeout=5)
    return j.loads(r.read())

def check(step, ok, detail=''):
    print(f"  {'OK' if ok else 'FAIL'} {step}" + (f' - {detail}' if detail else ''))

print("=== Frontend data flow simulation ===")

# Step 1: Check server alive
try:
    d = get('/api/v2/paper/account')
    check("GET /paper/account", d.get('success'))
except Exception as e:
    check("Server reachable", False, str(e))

# Step 2: Check watchlist endpoint
d = get('/api/v2/watchlist')
check("GET /watchlist", d.get('success'))
codes = [x['code'] for x in (d.get('data') or [])]
check(f"  Watchlist codes", len(codes) > 0, f"{codes}")

# Step 3: Check intraday endpoint for first stock
if codes:
    code = codes[0]
    d = get(f'/api/v2/paper/intraday/{code}?date=2026-06-05')
    check(f"GET /paper/intraday/{code}", d.get('success'))
    if d.get('success') and d.get('data'):
        quotes = d['data'].get('data', [])
        check(f"  Response structure: success={d['success']}, has data.data", isinstance(quotes, list))
        check(f"  Data points count", len(quotes) > 0, f"{len(quotes)}")
        if quotes:
            sample = quotes[0]
            keys = list(sample.keys())
            check(f"  Has required keys: timestamp, price", 'timestamp' in keys and 'price' in keys, f"keys: {keys}")
            check(f"  Timestamp format HH:MM", ':' in sample['timestamp'][11:16], sample['timestamp'][11:16])
    else:
        check("  Data object exists", False, str(d))
else:
    check("  Skip intraday check - no watchlist", False)

print()
print("=== Frontend store loadIntraday result ===")
if codes:
    code = codes[0]
    d = get(f'/api/v2/paper/intraday/{code}?date=2026-06-05')
    # Simulate store.loadIntraday:
    r = d
    intradayData = r['data']['data'] if (r.get('success') and r.get('data')) else []
    print(f"  intradayData = {len(intradayData)} items")
    print(f"  intradayData[0] = {intradayData[0] if intradayData else 'EMPTY'}")
    print(f"  intradayData.length > 0 = {len(intradayData) > 0}")
    print(f"  Chart would render: {len(intradayData) > 0}")
