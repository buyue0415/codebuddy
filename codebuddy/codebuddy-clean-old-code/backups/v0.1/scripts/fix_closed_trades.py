import json

# 读取对账单数据（有all_trades完整列表）
with open('data/broker_statement.json', 'r', encoding='utf-8') as f:
    raw = json.load(f)

# 读取系统数据
with open('data/system_data.json', 'r', encoding='utf-8') as f:
    d = json.load(f)

# 从all_trades重建每只股票的trades
all_trades = raw.get('all_trades', [])
trades_by_code = {}
for t in all_trades:
    code = t['code']
    if code not in trades_by_code:
        trades_by_code[code] = []
    trades_by_code[code].append(t)

# 更新已清仓的positions
for code, pos in d.get('closed_positions', {}).items():
    if code in trades_by_code:
        pos['trades'] = trades_by_code[code]
        # 重新计算汇总
        pos['total_commission'] = round(sum(t.get('commission', 0) for t in pos['trades']), 2)
        pos['total_stamp_tax'] = round(sum(t.get('stamp_tax', 0) for t in pos['trades']), 2)
        # all_trades里没有transfer_fee/regulatory_fee/handling_fee，需要从原汇总字段扣除commission和stamp_tax后计算other
        summary_total = pos.get('total_commission', 0) + pos.get('total_stamp_tax', 0) + pos.get('total_other_fees', 0)
        new_comm_stamp = pos['total_commission'] + pos['total_stamp_tax']
        # 保留原有的total_other_fees（因为all_trades没有明细费用字段）
        print(f'{pos["name"]}({code}): {len(pos["trades"])} trades restored')
    else:
        print(f'{pos["name"]}({code}): no trades found in all_trades')

# 同时更新broker_statement.json的closed_positions
for code, pos in raw.get('closed_positions', {}).items():
    if code in trades_by_code:
        pos['trades'] = trades_by_code[code]

# 保存
with open('data/system_data.json', 'w', encoding='utf-8') as f:
    json.dump(d, f, ensure_ascii=False, indent=2)
with open('data/broker_statement.json', 'w', encoding='utf-8') as f:
    json.dump(raw, f, ensure_ascii=False, indent=2)

print('\nVerifying...')
# 验证
with open('data/system_data.json', 'r', encoding='utf-8') as f:
    d2 = json.load(f)

all_summary = 0
all_trade = 0
for section_name in ['current_positions', 'closed_positions']:
    for code, pos in d2.get(section_name, {}).items():
        summary = pos.get('total_commission', 0) + pos.get('total_stamp_tax', 0) + pos.get('total_other_fees', 0)
        trade_sum = sum(
            t.get('commission', 0) + t.get('stamp_tax', 0)
            for t in pos.get('trades', [])
        )
        # all_trades没有transfer_fee等，所以trade_sum只含commission+stamp_tax
        # 但有total_other_fees，所以 summary = trade_sum + total_other_fees
        all_summary += summary
        all_trade += trade_sum
        diff = summary - trade_sum
        print(f'{pos["name"]}({code}): summary={summary:.2f} trade_comm_stamp={trade_sum:.2f} other={pos.get("total_other_fees",0):.2f} diff={diff:.2f}')

print(f'\nTotal summary: {all_summary:.2f}')
