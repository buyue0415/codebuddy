import json, copy, os

ROOT = os.path.dirname(os.path.abspath(__file__))
statement_path = os.path.join(ROOT, '..', 'data', 'broker_statement.json')
d = json.load(open(statement_path, 'r', encoding='utf-8'))

# \u9a8c\u8bc1\u62db\u5546\u94f6\u884c(\u65e0\u5356\u51fa)
print("=== \u62db\u5546\u94f6\u884c\u9a8c\u8bc1 ===")
total = 97250.0
divs = 405.20
qty = 2500
print(f"  (\u7cfb\u7edf\u603b\u6210\u672c{total} - \u80a1\u606f{divs}) / {qty} = {(total-divs)/qty:.4f}")
print(f"  \u7528\u6237\u5238\u5546\u503c: 38.7379")
print()

print("=== \u5174\u4e1a\u94f6\u884c\u6a21\u62df ===")
trades = [
    ('buy', 200, 21.03, 5.00),
    ('buy', 200, 19.16, 5.00),
    ('buy', 500, 18.52, 5.00),
    ('buy', 600, 18.07, 5.00),
    ('div', 0, 0, 226.0),
    ('sell', 1100, 18.55, 15.30),
    ('buy', 700, 18.97, 5.00),
    ('buy', 500, 17.95, 5.00),
    ('buy', 1200, 17.94, 5.38),
    ('buy', 600, 17.77, 5.00),
    ('buy', 1600, 17.63, 5.00),
    ('buy', 1300, 17.40, 5.00),
    ('div', 0, 0, 3156.30),
]

cost, qty = 0, 0
for t in trades:
    if t[0] == 'buy':
        cost += t[1] * t[2] + t[3]
        qty += t[1]
    elif t[0] == 'div':
        cost -= t[3]
    elif t[0] == 'sell':
        avg = cost / qty
        cost -= avg * abs(t[1])
        qty -= abs(t[1])
print(f"  \u65b9\u6848A(\u80a1\u606f\u5728\u5356\u51fa\u524d\u6263): cost={cost:.2f}, qty={qty}, avg={cost/qty:.4f}")

cost, qty = 0, 0
div_total = 0
for t in trades:
    if t[0] == 'buy':
        cost += t[1] * t[2] + t[3]
        qty += t[1]
    elif t[0] == 'div':
        div_total += t[3]
    elif t[0] == 'sell':
        avg = cost / qty
        cost -= avg * abs(t[1])
        qty -= abs(t[1])
cost -= div_total
print(f"  \u65b9\u6848B(\u6700\u540e\u5168\u6263\u80a1\u606f): cost={cost:.2f}, qty={qty}, avg={cost/qty:.4f}")

total_buy = sum(t[1]*t[2]+t[3] for t in trades if t[0]=='buy')
sell_proceeds = 1100*18.55 - 15.30
total_div = 226 + 3156.30
final = (total_buy - sell_proceeds - total_div) / 6300
print(f"  \u65b9\u6848C(\u7b80\u5316\u516c\u5f0f):({total_buy}-{sell_proceeds}-{total_div})/6300 = {final:.4f}")

print(f"\n  \u7528\u6237\u5238\u5546\u503c: 17.4148")
