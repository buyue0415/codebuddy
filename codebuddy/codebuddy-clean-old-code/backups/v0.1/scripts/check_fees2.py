import json
with open('data/system_data.json','r',encoding='utf-8') as f:
    d = json.load(f)

# 查看已清仓的trades和整体结构
for code, pos in d.get('closed_positions',{}).items():
    print(f'{pos["name"]}({code}):')
    print(f'  trades count: {len(pos.get("trades",[]))}')
    print(f'  total_commission={pos.get("total_commission",0)}')
    print(f'  total_stamp_tax={pos.get("total_stamp_tax",0)}')
    print(f'  total_other_fees={pos.get("total_other_fees",0)}')
    print(f'  realized_pnl={pos.get("realized_pnl",0)}')
    print()

# 看看HTML里持仓总览的手续费怎么算的
print('=== 检查HTML中手续费显示逻辑 ===')
