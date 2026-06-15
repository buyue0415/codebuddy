"""验证持仓成本计算"""
import json, copy

d = json.load(open(r'data/broker_statement.json', 'r', encoding='utf-8'))

# 验证招商银行(无卖出)
print("=== 招商银行验证 ===")
total = 97250.0
divs = 405.20
qty = 2500
print(f"  (系统总成本{total} - 股息{divs}) / {qty} = {(total-divs)/qty:.4f}")
print(f"  用户券商值: 38.7379")
print()

# 模拟兴业银行完整交易过程(含卖出摊薄 + 股息扣减)
print("=== 兴业银行模拟 ===")
trades = [
    ('buy', 200, 21.03, 5.00),
    ('buy', 200, 19.16, 5.00),
    ('buy', 500, 18.52, 5.00),
    ('buy', 600, 18.07, 5.00),
    ('div', 0, 0, 226.0),      # 2026-02-05 股息
    ('sell', 1100, 18.55, 15.30),  # 2026-03-06 卖出
    ('buy', 700, 18.97, 5.00),
    ('buy', 500, 17.95, 5.00),
    ('buy', 1200, 17.94, 5.38),
    ('buy', 600, 17.77, 5.00),
    ('buy', 1600, 17.63, 5.00),
    ('buy', 1300, 17.40, 5.00),
    ('div', 0, 0, 3156.30),   # 2026-06-11 股息
]

# 方案A: 股息在卖之前扣减
cost, qty = 0, 0
for t in trades:
    if t[0] == 'buy':
        cost += t[1] * t[2] + t[3]
        qty += t[1]
    elif t[0] == 'div':
        cost -= t[3]  # 股息扣减成本
    elif t[0] == 'sell':
        avg = cost / qty
        cost -= avg * abs(t[1])
        qty -= abs(t[1])
print(f"  方案A(股息在卖出前扣): cost={cost:.2f}, qty={qty}, avg={cost/qty:.4f}")

# 方案B: 所有股息在最后一起扣(先处理卖出)
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
print(f"  方案B(最后全扣股息): cost={cost:.2f}, qty={qty}, avg={cost/qty:.4f}")

# 方案C: 券商全量公式(买入总额-卖出净收入-股息)/剩余股数
total_buy = sum(t[1]*t[2]+t[3] for t in trades if t[0]=='buy')
sell_proceeds = 1100*18.55 - 15.30
total_div = 226 + 3156.30
final = (total_buy - sell_proceeds - total_div) / 6300
print(f"  方案C(简化公式):({total_buy}-{sell_proceeds}-{total_div})/6300 = {final:.4f}")

print(f"\n  用户券商值: 17.4148")
