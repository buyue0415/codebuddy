import json

with open('data/system_data.json', 'r', encoding='utf-8') as f:
    d = json.load(f)

print('=' * 60)
print('系统数据全面审计')
print('=' * 60)

# 1. 所有顶层字段
print('\n--- 顶层字段 ---')
for k, v in d.items():
    t = type(v).__name__
    sz = len(v) if isinstance(v, (list, dict)) else str(v)[:50]
    print(f'  {k}: {t} | {sz}')

# 2. 行情
print('\n--- quotes (行情) ---')
for code, q in d.get('quotes', {}).items():
    print(f'  {code}: price={q.get("price")} change={q.get("change")}%')

# 3. 持仓
print('\n--- current_positions ---')
for code, p in d.get('current_positions', {}).items():
    print(f'  {p["name"]}({code}): qty={p["qty"]} avg={p["avg_cost"]} trades={len(p.get("trades",[]))}')
    fee = p.get('total_commission', 0) + p.get('total_stamp_tax', 0) + p.get('total_other_fees', 0)
    print(f'    -> fees={fee:.2f}')

print('\n--- closed_positions ---')
for code, p in d.get('closed_positions', {}).items():
    fee = p.get('total_commission', 0) + p.get('total_stamp_tax', 0) + p.get('total_other_fees', 0)
    print(f'  {p["name"]}({code}): pnl={p["realized_pnl"]} div={p.get("dividends_total",0)} trades={len(p.get("trades",[]))}')
    print(f'    -> fees={fee:.2f}')

# 4. 预测
print('\n--- daily_predictions ---')
preds = d.get('daily_predictions', [])
for p in preds:
    has_act = p.get('actual', {}).get('close') is not None
    nd = p['next_day']
    print(f'  [{p["code"]}] {p["date"]}: dir={nd["direction"]} conf={nd["confidence"]} actual={"YES" if has_act else "no"}')

# 5. 新闻
print('\n--- news ---')
news = d.get('news', [])
print(f'  {len(news)} items')
if news:
    latest = sorted(news, key=lambda n: n.get('date', ''), reverse=True)
    print(f'  latest: {latest[0].get("date")} - {latest[0].get("title","?")[:50]}')

# 6. K线
print('\n--- kline (月度) ---')
kl = d.get('kline', {})
for code, data in kl.items():
    print(f'  {code}: {len(data)} bars, {data[-1][0]} -> {data[0][0]}')

print('\n--- kline_daily (日频) ---')
kld = d.get('kline_daily', {})
for code, data in kld.items():
    print(f'  {code}: {len(data)} bars, {data[-1][0]} -> {data[0][0]}')

# 7. 学习参数
print('\n--- learning_params ---')
for code, lp in d.get('learning_params', {}).items():
    w = lp.get('signal_weights', {})
    cb = lp.get('confidence_beta', {})
    bias = lp.get('hourly_bias', {})
    print(f'  {code}:')
    print(f'    signal_weights: {len(w)} signals x 5 blocks')
    print(f'    hourly_bias: {bias}')
    print(f'    confidence_beta: {cb}')
    print(f'    update_count: {lp.get("update_count", 0)}')

# 8. 准确率
print('\n--- accuracy_stats ---')
for code, ast in d.get('accuracy_stats', {}).items():
    l20 = ast.get('last_20', {})
    d20 = l20.get('direction', {})
    r20 = l20.get('range', {})
    print(f'  {code}: dir={d20.get("correct",0)}/{d20.get("total",0)}={d20.get("rate",0):.0%} range={r20.get("correct",0)}/{r20.get("total",0)}={r20.get("rate",0):.0%}')

# 9. 其他
print('\n--- 其他 ---')
print(f'  generated: {d.get("generated", "MISSING")}')
print(f'  all_trades: {len(d.get("all_trades", []))} trades')
print(f'  expert_reports: {len(d.get("expert_reports", []))} reports')
print(f'  predictions (旧): {len(d.get("predictions", []))}')

# 10. 数据时效性
from datetime import datetime
today = datetime.now().strftime('%Y-%m-%d')
print(f'\n--- 时效性检查 (today={today}) ---')

# 行情
if d.get('quotes', {}).get('601166', {}).get('price'):
    print('  quotes: OK (有行情数据)')
else:
    print('  quotes: STALE (无行情数据)')

# 日K
if d.get('kline_daily', {}).get('601166'):
    latest_date = d['kline_daily']['601166'][0][0]
    if latest_date == today:
        print(f'  kline_daily: CURRENT ({latest_date})')
    else:
        print(f'  kline_daily: STALE (latest={latest_date}, today={today})')
else:
    print('  kline_daily: MISSING')

# 日预测
today_preds = [p for p in preds if p['date'] == today]
if today_preds:
    for p in today_preds:
        has_act = p.get('actual', {}).get('close') is not None
        print(f'  prediction {p["code"]}: EXISTS, actual={"FILLED" if has_act else "PENDING"}')
else:
    print('  prediction: MISSING for today')

# 新闻
if news:
    latest_news_date = max(n.get('date', '') for n in news)
    print(f'  news: latest={latest_news_date}')
else:
    print('  news: EMPTY')

# 已存盘
with open('data/system_data.json', 'w', encoding='utf-8') as f:
    json.dump(d, f, ensure_ascii=False, indent=2)
