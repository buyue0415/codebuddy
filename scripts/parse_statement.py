import json, os, sys
import pandas as pd
from collections import defaultdict

ROOT = os.path.dirname(os.path.abspath(__file__))

if len(sys.argv) > 1:
    EXCEL_PATH = sys.argv[1]
else:
    EXCEL_PATH = os.environ.get(
        'BROKER_STATEMENT_PATH',
        os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'broker_statement.xlsx')
    )

df = pd.read_excel(EXCEL_PATH, header=0)
df.columns = ['date','time','seq','account','code','name','type','qty','price','commission','stamp_tax','transfer_fee','regulatory_fee','handling_fee','other_fee','settlement','currency','order_id','accrued_interest']

trades = []
for _, r in df.iterrows():
    trades.append({
        'date': str(r['date'])[:10],
        'time': str(r['time']),
        'code': str(r['code']),
        'name': str(r['name']),
        'type': str(r['type']),
        'qty': float(r['qty']),
        'price': float(r['price']),
        'commission': float(r['commission']),
        'stamp_tax': float(r['stamp_tax']),
        'transfer_fee': float(r['transfer_fee']),
        'regulatory_fee': float(r['regulatory_fee']),
        'handling_fee': float(r['handling_fee']),
        'settlement': float(r['settlement']),
    })

positions = defaultdict(lambda: {'code':'','name':'','qty':0,'total_cost':0.0,'trades':[],'dividends':[],'realized':0.0,'total_commission':0.0,'total_stamp_tax':0.0,'total_other_fees':0.0})

for t in trades:
    code = t['code']
    pos = positions[code]
    pos['code'] = code
    pos['name'] = t['name'].replace('XD','')
    fee = t['commission'] + t['stamp_tax'] + t['transfer_fee'] + t['regulatory_fee'] + t['handling_fee']
    pos['total_commission'] += t['commission']
    pos['total_stamp_tax'] += t['stamp_tax']
    pos['total_other_fees'] += t['transfer_fee'] + t['regulatory_fee'] + t['handling_fee']
    if t['type'] == '\u8bc1\u5238\u4e70\u5165':
        pos['qty'] += int(abs(t['qty']))
        pos['total_cost'] += abs(t['qty']) * t['price'] + fee
        pos['trades'].append(t)
    elif t['type'] == '\u8bc1\u5238\u5356\u51fa':
        sell_qty = int(abs(t['qty']))
        old_qty = pos['qty']
        if old_qty > 0:
            avg_cost = pos['total_cost'] / old_qty
            sell_cost = avg_cost * sell_qty
            pos['total_cost'] -= sell_cost
            realized = abs(t['qty']) * t['price'] - fee - sell_cost
            pos['realized'] += realized
        pos['qty'] -= sell_qty
        pos['trades'].append(t)
    elif t['type'] == '\u80a1\u606f\u5165\u8d26':
        pos['dividends'].append({'date':t['date'],'amount':t['settlement'],'price':t['price']})

result = {}
for code, pos in positions.items():
    if pos['qty'] <= 0 and code != '736435':
        continue
    avg_cost = pos['total_cost'] / pos['qty'] if pos['qty'] > 0 else 0
    result[code] = {
        'code': code, 'name': pos['name'], 'qty': pos['qty'],
        'total_cost': round(pos['total_cost'], 2), 'avg_cost': round(avg_cost, 3),
        'realized_pnl': round(pos['realized'], 2), 'dividends': pos['dividends'],
        'total_commission': round(pos['total_commission'], 2),
        'total_stamp_tax': round(pos['total_stamp_tax'], 2),
        'total_other_fees': round(pos['total_other_fees'], 2),
        'trades': pos['trades'],
    }

all_trades_out = []
for t in trades:
    if t['type'] in ('\u8bc1\u5238\u4e70\u5165','\u8bc1\u5238\u5356\u51fa','\u80a1\u606f\u5165\u8d26'):
        all_trades_out.append({
            'date': t['date'], 'time': t['time'], 'code': t['code'], 'name': t['name'],
            'type': t['type'], 'qty': int(t['qty']), 'price': t['price'],
            'commission': round(t['commission'], 2), 'stamp_tax': round(t['stamp_tax'], 2),
            'settlement': round(t['settlement'], 2),
        })

closed_positions = {}
for code, pos in positions.items():
    if pos['qty'] == 0 and code not in ('736435',):
        closed_positions[code] = {
            'code': code, 'name': pos['name'], 'realized_pnl': round(pos['realized'], 2),
            'dividends_total': round(sum(d['amount'] for d in pos['dividends']), 2),
            'dividends': pos['dividends'],
            'total_commission': round(pos['total_commission'], 2),
            'total_stamp_tax': round(pos['total_stamp_tax'], 2),
            'total_other_fees': round(pos['total_other_fees'], 2),
            'trades': pos['trades'],
        }

output = {
    'account': '51312640',
    'broker': '\u5e7f\u53d1\u8bc1\u5238',
    'current_positions': {k:v for k,v in result.items() if v['qty'] > 0},
    'closed_positions': closed_positions,
    'all_trades': all_trades_out,
}

with open(os.path.join(ROOT, '..', 'data', 'broker_statement.json'), 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)