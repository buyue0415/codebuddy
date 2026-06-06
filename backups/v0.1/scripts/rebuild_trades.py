import json

with open('data/broker_statement.json', 'r', encoding='utf-8') as f:
    raw = json.load(f)

with open('data/system_data.json', 'r', encoding='utf-8') as f:
    d = json.load(f)

# 从对账单提取所有交易记录，按股票分组
all_trades = {}  # code -> [trade, ...]

for section in ['current_positions', 'closed_positions']:
    positions = raw.get(section, {})
    for code, pos in positions.items():
        if code not in all_trades:
            all_trades[code] = []
        for t in pos.get('trades', []):
            all_trades[code].append(t)

# 重建每只股票的trades
for section_name in ['current_positions', 'closed_positions']:
    positions = d.get(section_name, {})
    for code, pos in positions.items():
        if code in all_trades and all_trades[code]:
            pos['trades'] = all_trades[code]
            # 重新计算汇总字段
            total_commission = sum(t.get('commission', 0) for t in pos['trades'])
            total_stamp_tax = sum(t.get('stamp_tax', 0) for t in pos['trades'])
            total_other = sum(
                t.get('transfer_fee', 0) + t.get('regulatory_fee', 0) + t.get('handling_fee', 0)
                for t in pos['trades']
            )
            pos['total_commission'] = round(total_commission, 2)
            pos['total_stamp_tax'] = round(total_stamp_tax, 2)
            pos['total_other_fees'] = round(total_other, 2)
            print(f'{pos["name"]}({code}): {len(pos["trades"])} trades, '
                  f'commission={pos["total_commission"]}, stamp={pos["total_stamp_tax"]}, other={pos["total_other_fees"]}')
        else:
            print(f'{pos["name"]}({code}): no trades in broker_statement, keeping existing data')

with open('data/system_data.json', 'w', encoding='utf-8') as f:
    json.dump(d, f, ensure_ascii=False, indent=2)

print('\nDone. Verifying...')

# 验证
with open('data/system_data.json', 'r', encoding='utf-8') as f:
    d2 = json.load(f)

all_summary = 0
all_trade = 0
for section_name in ['current_positions', 'closed_positions']:
    for code, pos in d2.get(section_name, {}).items():
        summary = pos.get('total_commission', 0) + pos.get('total_stamp_tax', 0) + pos.get('total_other_fees', 0)
        trade_sum = sum(
            t.get('commission', 0) + t.get('stamp_tax', 0) + t.get('transfer_fee', 0) + t.get('regulatory_fee', 0) + t.get('handling_fee', 0)
            for t in pos.get('trades', [])
        )
        all_summary += summary
        all_trade += trade_sum
        match = '✓' if abs(summary - trade_sum) < 0.02 else '✗'
        print(f'{pos["name"]}({code}): summary={summary:.2f} trade_sum={trade_sum:.2f} {match}')

print(f'\nTotal: summary={all_summary:.2f} trade_sum={all_trade:.2f}')
