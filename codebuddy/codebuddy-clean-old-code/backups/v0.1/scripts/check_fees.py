import json
with open('data/system_data.json','r',encoding='utf-8') as f:
    d = json.load(f)

# 持仓总览里的累计手续费
for code, pos in d['current_positions'].items():
    total_fee = pos.get('total_commission',0) + pos.get('total_stamp_tax',0) + pos.get('total_other_fees',0)
    name = pos['name']
    print(f'{name}({code}):')
    print(f'  佣金={pos.get("total_commission",0):.2f} 印花税={pos.get("total_stamp_tax",0):.2f} 其他={pos.get("total_other_fees",0):.2f} = 合计{total_fee:.2f}')
    # 也看看每笔交易的手续费
    trade_fees = []
    for t in pos.get('trades',[]):
        fee = t.get('commission',0) + t.get('stamp_tax',0) + t.get('transfer_fee',0) + t.get('regulatory_fee',0) + t.get('handling_fee',0)
        trade_fees.append(fee)
    print(f'  逐笔交易费用合计: {sum(trade_fees):.2f} ({len(trade_fees)}笔)')
    print(f'  逐笔明细: {[round(f,2) for f in trade_fees]}')
    print()

# 已清仓
for code, pos in d.get('closed_positions',{}).items():
    total_fee = pos.get('total_commission',0) + pos.get('total_stamp_tax',0) + pos.get('total_other_fees',0)
    name = pos['name']
    print(f'{name}({code})[已清仓]:')
    print(f'  佣金={pos.get("total_commission",0):.2f} 印花税={pos.get("total_stamp_tax",0):.2f} 其他={pos.get("total_other_fees",0):.2f} = 合计{total_fee:.2f}')
    trade_fees = []
    for t in pos.get('trades',[]):
        fee = t.get('commission',0) + t.get('stamp_tax',0) + t.get('transfer_fee',0) + t.get('regulatory_fee',0) + t.get('handling_fee',0)
        trade_fees.append(fee)
    print(f'  逐笔交易费用合计: {sum(trade_fees):.2f} ({len(trade_fees)}笔)')
    print()

# 全部手续费总计
all_summary_fee = sum(
    pos.get('total_commission',0) + pos.get('total_stamp_tax',0) + pos.get('total_other_fees',0)
    for pos in d['current_positions'].values()
)
all_summary_fee += sum(
    pos.get('total_commission',0) + pos.get('total_stamp_tax',0) + pos.get('total_other_fees',0)
    for pos in d.get('closed_positions',{}).values()
)
print(f'=== 持仓总览侧（汇总字段）全部手续费: {all_summary_fee:.2f} ===')

all_trade_fee = 0
for code, pos in d['current_positions'].items():
    for t in pos.get('trades',[]):
        all_trade_fee += t.get('commission',0) + t.get('stamp_tax',0) + t.get('transfer_fee',0) + t.get('regulatory_fee',0) + t.get('handling_fee',0)
for code, pos in d.get('closed_positions',{}).items():
    for t in pos.get('trades',[]):
        all_trade_fee += t.get('commission',0) + t.get('stamp_tax',0) + t.get('transfer_fee',0) + t.get('regulatory_fee',0) + t.get('handling_fee',0)
print(f'=== 手续费分析侧（逐笔累加）全部手续费: {all_trade_fee:.2f} ===')
