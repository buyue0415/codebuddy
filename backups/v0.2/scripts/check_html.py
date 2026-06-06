import re

with open("deliverables/bank-stock-system.html", "r", encoding="utf-8") as f:
    html = f.read()

issues = []

# Brace check
o, c = html.count("{"), html.count("}")
issues.append(f"Braces: {o} open vs {c} close {'MISMATCH!' if o!=c else 'OK'}")

# Script tags
s_open = html.count("<script") + html.count("<script>")
s_close = html.count("</script>")
issues.append(f"Script tags: {s_open} open vs {s_close} close")

# Backtick check
bt = html.count("`")
issues.append(f"Backticks: {bt} {'MISMATCH!' if bt%2!=0 else 'OK'}")

# init() calls
inits = len(re.findall(r"init\s*\(\s*\)", html))
issues.append(f"init() calls: {inits}")

# showPage
if "function showPage" in html:
    issues.append("showPage: FOUND")
else:
    issues.append("showPage: MISSING")

# Duplicate functions
funcs = re.findall(r"function (\w+)\(", html)
dups = {f for f in funcs if funcs.count(f) > 1}
issues.append(f"Duplicate functions: {dups if dups else 'NONE'}")

# refreshWatchlistUI
rw = len(re.findall(r"function refreshWatchlistUI", html))
issues.append(f"refreshWatchlistUI defs: {rw}")

# genStockTabs
gs = len(re.findall(r"function genStockTabs", html))
issues.append(f"genStockTabs defs: {gs}")

# switchToKline
sk = len(re.findall(r"function switchToKline", html))
issues.append(f"switchToKline defs: {sk}")

# Check if DATA is defined before use
data_def_idx = html.find("const DATA")
if data_def_idx > 0:
    # Check what's before DATA
    before = html[max(0, data_def_idx-100):data_def_idx]
    issues.append(f"DATA defined at offset {data_def_idx}, script scope: {'<script>' in before}")

# Check for common JS errors
if "getStockName(" in html and "function getStockName" not in html:
    issues.append("getStockName CALLED but not DEFINED!")
else:
    issues.append("getStockName: OK")

if "getWatchlist()" in html and "function getWatchlist" not in html:
    issues.append("getWatchlist CALLED but not DEFINED!")
else:
    issues.append("getWatchlist: OK")

# Check genStockTabs called in init
if "genStockTabs(" in html:
    gs_calls = re.findall(r"genStockTabs\([^)]+\)", html)
    issues.append(f"genStockTabs calls: {len(gs_calls)}")

# Check refreshWatchlistUI called
if "refreshWatchlistUI" in html:
    rwc = re.findall(r"refreshWatchlistUI", html)
    issues.append(f"refreshWatchlistUI refs: {len(rwc)}")

for i in issues:
    print(f"  {i}")
print(f"\nTotal: {len(html)} chars, ~{html.count(chr(10))} lines")
