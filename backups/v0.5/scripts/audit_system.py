"""System audit - iterates over watchlist."""
import json
from datetime import datetime

with open('data/system_data.json', 'r', encoding='utf-8') as f:
    d = json.load(f)

wl = d.get('watchlist', [])
today = datetime.now().strftime('%Y-%m-%d')

print('='*60)
print('系统审计 v0.2 (watchlist驱动)')
print('='*60)
print(f'监控股票: {[(s["code"], s["name"]) for s in wl]}')
print(f'审计日期: {today}')
print(f'generated: {d.get("generated","MISSING")}')
print()

print('--- quotes ---')
for s in wl:
    q = d.get('quotes',{}).get(s['code'],{})
    print(f'  {s["name"]}({s["code"]}): price={q.get("price","?")} change={q.get("change","?")}%')

print('\n--- kline_daily ---')
for s in wl:
    kld = d.get('kline_daily',{}).get(s['code'],[])
    if kld:
        print(f'  {s["name"]}: {len(kld)} bars, {kld[-1][0]} -> {kld[0][0]}')
    else:
        print(f'  {s["name"]}: MISSING')

print('\n--- daily_predictions ---')
for s in wl:
    preds = [p for p in d.get('daily_predictions',[]) if p['code']==s['code']]
    latest = preds[-1] if preds else None
    if latest:
        has_act = latest.get('actual',{}).get('close') is not None
        print(f'  {s["name"]}: {len(preds)} preds, latest={latest["date"]} dir={latest["next_day"]["direction"]} actual={"YES" if has_act else "pending"}')
    else:
        print(f'  {s["name"]}: NO predictions')

print('\n--- learning_params ---')
for s in wl:
    lp = d.get('learning_params',{}).get(s['code'],{})
    if lp:
        print(f'  {s["name"]}: update_count={lp.get("update_count",0)} mw_beta={lp.get("mw_beta","?")} lr={lp.get("learning_rate","?")}')
    else:
        print(f'  {s["name"]}: MISSING')

print('\n--- accuracy_stats ---')
for s in wl:
    ast = d.get('accuracy_stats',{}).get(s['code'],{})
    l20 = ast.get('last_20',{})
    d20 = l20.get('direction',{})
    print(f'  {s["name"]}: dir={d20.get("correct",0)}/{d20.get("total",0)} rate={d20.get("rate",0):.0%}')

print('\n--- 其他 ---')
print(f'  positions: {len(d.get("current_positions",{}))} current + {len(d.get("closed_positions",{}))} closed')
print(f'  trades: {len(d.get("all_trades",[]))} total')
print(f'  news: {len(d.get("news",[]))} items')
print(f'  expert_reports: {len(d.get("expert_reports",[]))} reports')
print(f'  kline(月度): {sum(len(v) for v in d.get("kline",{}).values())} bars')
