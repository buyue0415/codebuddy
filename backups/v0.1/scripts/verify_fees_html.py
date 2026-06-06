import json, re

with open('deliverables/bank-stock-system.html', 'r', encoding='utf-8') as f:
    html = f.read()

# 提取注入的DATA
match = re.search(r'const DATA = (\{.*?\});\n', html, re.DOTALL)
if match:
    data = json.loads(match.group(1))
    print("=== DATA loaded successfully ===")
else:
    print("ERROR: Could not find DATA constant")
    exit(1)

# 模拟持仓总览页计算
print("\n=== 持仓总览页 (遍历cp) ===")
cp = data.get('current_positions', {})
totalFees = 0
for code, p in cp.items():
    fee = p.get('total_commission', 0) + p.get('total_stamp_tax', 0) + p.get('total_other_fees', 0)
    totalFees += fee
    print(f'{p["name"]}: commission={p.get("total_commission",0)} stamp={p.get("total_stamp_tax",0)} other={p.get("total_other_fees",0)} = {fee:.2f}')
print(f'>>> 持仓总览累计手续费: {totalFees:.2f}')

# 模拟手续费分析页计算
print("\n=== 手续费分析页 (遍历cp+cl) ===")
cl = data.get('closed_positions', {})
allCommission = 0
allStamp = 0
allOther = 0

for code, p in cp.items():
    c = p.get('total_commission', 0)
    s = p.get('total_stamp_tax', 0)
    o = p.get('total_other_fees', 0)
    allCommission += c
    allStamp += s
    allOther += o
    print(f'CP {p["name"]}: comm={c} stamp={s} other={o}')

for code, p in cl.items():
    c = p.get('total_commission', 0)
    s = p.get('total_stamp_tax', 0)
    o = p.get('total_other_fees', 0)
    allCommission += c
    allStamp += s
    allOther += o
    print(f'CL {p["name"]}: comm={c} stamp={s} other={o}')

total = allCommission + allStamp + allOther
print(f'>>> 手续费分析: commission={allCommission:.2f} stamp={allStamp:.2f} other={allOther:.2f} total={total:.2f}')

# 检查cl是否缺失total_other_fees字段
print("\n=== 已清仓字段检查 ===")
for code, p in cl.items():
    has_trades = 'trades' in p and p['trades']
    has_other = 'total_other_fees' in p
    print(f'{p["name"]}: has_trades={has_trades}({len(p.get("trades",[]))}), has_total_other_fees={has_other}({p.get("total_other_fees",0)})')
