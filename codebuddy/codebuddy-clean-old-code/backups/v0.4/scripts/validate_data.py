"""Validate HTML DATA injection"""
import re, json

with open("deliverables/bank-stock-system.html", "r", encoding="utf-8") as f:
    html = f.read()

# Find DATA
match = re.search(r"const DATA = (\{.*?\});", html, re.DOTALL)
if not match:
    print("ERROR: No DATA found in HTML!")
    exit(1)

try:
    d = json.loads(match.group(1))
    print("JSON valid!")
    print(f"  quotes: {len(d.get('quotes',{}))} stocks")
    for code, q in d.get('quotes',{}).items():
        print(f"    {code}: price={q.get('price')}")
    print(f"  current_positions: {len(d.get('current_positions',{}))}")
    print(f"  closed_positions: {len(d.get('closed_positions',{}))}")
    print(f"  all_trades: {len(d.get('all_trades',[]))} trades")
    print(f"  news: {len(d.get('news',[]))} items")
    print(f"  watchlist: {[s['name'] for s in d.get('watchlist',[])]}")
    print(f"  kline_daily: {len(d.get('kline_daily',{}).get('601166',[]))} bars")
    print(f"  seasonal: {len(d.get('seasonal',{}).get('601166',[]))} entries")
    print(f"  expert_reports: {len(d.get('expert_reports',[]))}")
    print(f"  daily_predictions: {len(d.get('daily_predictions',[]))}")
    print(f"  generated: {d.get('generated')}")
except json.JSONDecodeError as e:
    print(f"INVALID JSON: {e}")
    # Find the bad spot
    raw = match.group(1)
    print(f"First 500 chars: {raw[:500]}")
