import json, re

with open('deliverables/bank-stock-system.html', 'r', encoding='utf-8') as f:
    html = f.read()

match = re.search(r'const DATA = (\{.*?\});\n', html, re.DOTALL)
data = json.loads(match.group(1))

cp = data.get('current_positions', {})
cl = data.get('closed_positions', {})

# 模拟持仓总览
totalFees = 0
for code, p in cp.items():
    totalFees += p.get('total_commission', 0) + p.get('total_stamp_tax', 0) + p.get('total_other_fees', 0)
for code, p in cl.items():
    totalFees += p.get('total_commission', 0) + p.get('total_stamp_tax', 0) + (p.get('total_other_fees') or 0)
print(f'持仓总览 累计手续费 = {totalFees:.2f}')

# 模拟手续费分析
allC = sum(p.get('total_commission', 0) for p in list(cp.values()) + list(cl.values()))
allS = sum(p.get('total_stamp_tax', 0) for p in list(cp.values()) + list(cl.values()))
allO = sum(p.get('total_other_fees', 0) or 0 for p in list(cp.values()) + list(cl.values()))
print(f'手续费分析: 佣金={allC:.2f} 印花税={allS:.2f} 其他={allO:.2f} 合计={allC+allS+allO:.2f}')

match = '✓ 一致' if abs(totalFees - (allC+allS+allO)) < 0.02 else '✗ 不一致！'
print(f'结论: {match}')
