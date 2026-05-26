"""从广发证券对账单解析交易记录，写入 SQLite 持仓表"""
import json, sys, os, shutil
from collections import defaultdict
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
from db_helper import upsert_positions

STMT_FILE = os.path.join(ROOT, '广发易淘金PC版-普通对账单结果查询.xlsx')

df = pd.read_excel(STMT_FILE, header=0)
df.columns = ['date','time','seq','account','code','name','type','qty','price','commission','stamp_tax','transfer_fee','regulatory_fee','handling_fee','other_fee','settlement','currency','order_id','accrued_interest']

# --- Step 1: Parse all trades ---
trades = []
for _, r in df.iterrows():
    trades.append({
        'date': str(r['date'])[:10], 'time': str(r['time']), 'code': str(r['code']),
        'name': str(r['name']), 'type': str(r['type']), 'qty': float(r['qty']),
        'price': float(r['price']), 'commission': float(r['commission']),
        'stamp_tax': float(r['stamp_tax']), 'transfer_fee': float(r['transfer_fee']),
        'regulatory_fee': float(r['regulatory_fee']), 'handling_fee': float(r['handling_fee']),
        'settlement': float(r['settlement']),
    })

# --- Step 2: Calculate positions ---
positions = defaultdict(lambda: {'code':'','name':'','qty':0,'total_cost':0.0,'trades':[],'dividends':[],'realized':0.0,'total_commission':0.0,'total_stamp_tax':0.0,'total_other_fees':0.0,'transfer_fee':0.0,'regulatory_fee':0.0,'handling_fee':0.0})

for t in trades:
    code = t['code']
    if code == '736435': continue  # skip IPO subscription tickets
    pos = positions[code]
    pos['code'] = code
    pos['name'] = t['name'].replace('XD', '')
    fee = t['commission'] + t['stamp_tax'] + t['transfer_fee'] + t['regulatory_fee'] + t['handling_fee']
    pos['total_commission'] += t['commission']
    pos['total_stamp_tax'] += t['stamp_tax']
    pos['transfer_fee'] += t['transfer_fee']
    pos['regulatory_fee'] += t['regulatory_fee']
    pos['handling_fee'] += t['handling_fee']
    pos['total_other_fees'] = pos['transfer_fee'] + pos['regulatory_fee'] + pos['handling_fee']

    if t['type'] == '证券买入':
        pos['qty'] += int(abs(t['qty']))
        pos['total_cost'] += abs(t['qty']) * t['price'] + fee
        pos['trades'].append(t)
    elif t['type'] == '证券卖出':
        sell_qty = int(abs(t['qty']))
        if pos['qty'] > 0 and pos['total_cost'] > 0:
            avg_cost = pos['total_cost'] / pos['qty']
            sell_cost = avg_cost * sell_qty
            pos['total_cost'] -= sell_cost
            pos['realized'] += abs(t['qty']) * t['price'] - fee - sell_cost
        pos['qty'] -= sell_qty
        pos['trades'].append(t)
    elif t['type'] == '股息入账':
        pos['dividends'].append({'date': t['date'], 'amount': t['settlement'], 'price': t['price']})

# --- Step 3: Build output structures ---
current = {}
for code, pos in positions.items():
    if pos['qty'] <= 0: continue
    current[code] = {
        'code': code, 'name': pos['name'], 'qty': pos['qty'],
        'total_cost': round(pos['total_cost'], 2),
        'avg_cost': round(pos['total_cost'] / pos['qty'], 3) if pos['qty'] > 0 else 0,
        'realized_pnl': round(pos['realized'], 2),
        'dividends': [{'date': d['date'], 'amount': round(d['amount'], 2), 'price': round(d['price'], 2)} for d in pos['dividends']],
        'total_commission': round(pos['total_commission'], 2),
        'total_stamp_tax': round(pos['total_stamp_tax'], 2),
        'total_other_fees': round(pos['total_other_fees'], 2),
        'trades': pos['trades'],
    }

closed = {}
for code, pos in positions.items():
    if pos['qty'] > 0: continue
    closed[code] = {
        'code': code, 'name': pos['name'],
        'realized_pnl': round(pos['realized'], 2),
        'dividends_total': round(sum(d['amount'] for d in pos['dividends']), 2),
        'total_commission': round(pos['total_commission'], 2),
        'total_stamp_tax': round(pos['total_stamp_tax'], 2),
        'total_other_fees': round(pos['total_other_fees'], 2),
        'trades': pos['trades'],
    }

all_trades_out = []
for t in trades:
    if t['type'] in ('证券买入','证券卖出','股息入账'):
        all_trades_out.append({
            'date': t['date'], 'time': t['time'], 'code': t['code'], 'name': t['name'],
            'type': t['type'], 'qty': int(t['qty']), 'price': t['price'],
            'commission': round(t['commission'], 2), 'stamp_tax': round(t['stamp_tax'], 2),
            'settlement': round(t['settlement'], 2),
        })

# Save broker_statement.json (canonical output)
stmt_path = os.path.join(ROOT, 'data', 'broker_statement.json')
stmt_backup = os.path.join(ROOT, 'data', 'broker_statement.json.bak')
if os.path.exists(stmt_path):
    shutil.copy2(stmt_path, stmt_backup)

broker = {
    'account': '51312640', 'broker': '广发证券',
    'current_positions': current, 'closed_positions': closed, 'all_trades': all_trades_out,
}
with open(stmt_path, 'w', encoding='utf-8') as f:
    json.dump(broker, f, ensure_ascii=False, indent=2)

# --- Step 4: Write to SQLite (replaces legacy system_data.json sync) ---
try:
    upsert_positions(current, closed, all_trades_out)
    print("  Positions written to SQLite")
except Exception as e:
    print(f"  SQLite write failed: {e}")

print("=== 当前持仓 ===")
for code, pos in current.items():
    print(f"  {pos['name']}({code}): {pos['qty']}股, 成本均价{pos['avg_cost']:.3f}, 总投入{pos['total_cost']:.2f}")

print("\n=== 已清仓 ===")
for code, pos in closed.items():
    print(f"  {pos['name']}({code}): 实现盈亏{pos['realized_pnl']:.2f}, 分红{pos['dividends_total']:.2f}")

total_fees = sum(v['total_commission']+v['total_stamp_tax']+v['total_other_fees'] for v in current.values())
print(f"\n总手续费: {total_fees:.2f}")
print(f"\nbroker_statement.json 已保存，SQLite 已更新")
