import json
with open('data/broker_statement.json','r',encoding='utf-8') as f:
    d = json.load(f)
for code, pos in d['current_positions'].items():
    print(pos['name'], code)
    for dv in pos['dividends']:
        print('  ', dv)
    total = pos['total_commission'] + pos['total_stamp_tax'] + pos['total_other_fees']
    print(f'  佣金:{pos["total_commission"]} 印花税:{pos["total_stamp_tax"]} 其他:{pos["total_other_fees"]} 合计:{total:.2f}')
for code, pos in d['closed_positions'].items():
    print(pos['name'], code)
    print(f'  佣金:{pos["total_commission"]} 印花税:{pos["total_stamp_tax"]}')
