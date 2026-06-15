"""验证广发证券对账单数据的正确性"""
import json

with open('data/broker_statement.json', 'r', encoding='utf-8') as f:
    stmt = json.load(f)

print("=" * 70)
print("广发证券对账单 数据验证")
print("=" * 70)

# ===================== 当前持仓 =====================
print("\n## 当前持仓验证\n")
for code, pos in stmt['current_positions'].items():
    print(f"--- {pos['name']}({code}) ---")
    print(f"  持仓数量: {pos['qty']}")
    
    # 从交易记录验证持仓数量
    buy_qty = sum(int(t['qty']) for t in pos['trades'] if t['type'] == '证券买入')
    sell_qty = sum(abs(int(t['qty'])) for t in pos['trades'] if t['type'] == '证券卖出')
    calc_qty = buy_qty - sell_qty
    print(f"  交易验证: 买入{buy_qty} - 卖出{sell_qty} = {calc_qty}", end="")
    if calc_qty == pos['qty']:
        print(" ✅")
    else:
        print(f" ❌ 实际{pos['qty']}")
    
    # 验证总成本
    buy_cost = sum(abs(t['settlement']) for t in pos['trades'] if t['type'] == '证券买入')
    sell_proceeds = sum(t['settlement'] for t in pos['trades'] if t['type'] == '证券卖出')
    # 净投入 = 买入结算（含费用） - 卖出结算（含费用）
    net_invested = buy_cost - sell_proceeds
    print(f"  买入总金额(含费): {buy_cost:,.2f}")
    print(f"  卖出总金额(含费): {sell_proceeds:,.2f}")
    print(f"  净投入(买-卖): {net_invested:,.2f}")
    print(f"  记录总成本: {pos['total_cost']:,.2f}")
    
    # 验证均价
    calc_avg = pos['total_cost'] / pos['qty']
    print(f"  记录均价: {pos['avg_cost']:.3f}, 计算均价: {calc_avg:.3f}", end="")
    if abs(calc_avg - pos['avg_cost']) < 0.01:
        print(" ✅")
    else:
        print(" ⚠️ 差异")
    
    # 验证手续费合计
    calc_commission = sum(t['commission'] for t in pos['trades'])
    calc_stamp = sum(t['stamp_tax'] for t in pos['trades'])
    calc_other = sum(t.get('transfer_fee', 0) + t.get('regulatory_fee', 0) + t.get('handling_fee', 0) for t in pos['trades'])
    print(f"  佣金: 记录{pos['total_commission']:.2f} 计算{calc_commission:.2f}", end="")
    if abs(calc_commission - pos['total_commission']) < 0.1:
        print(" ✅")
    else:
        print(" ⚠️ 差异")
    print(f"  印花税: 记录{pos['total_stamp_tax']:.2f} 计算{calc_stamp:.2f}", end="")
    if abs(calc_stamp - pos['total_stamp_tax']) < 0.1:
        print(" ✅")
    else:
        print(" ⚠️ 差异")
    print(f"  其他费用: 记录{pos['total_other_fees']:.2f} 计算{calc_other:.2f}", end="")
    if abs(calc_other - pos['total_other_fees']) < 0.1:
        print(" ✅")
    else:
        print(" ⚠️ 差异")
    
    # 验证分红
    for d in pos['dividends']:
        print(f"  分红: {d['date']} 金额{d['amount']}")
    
    # 验证已实现盈亏（仅针对有卖出的）
    if sell_qty > 0:
        # 用移动加权平均法验证
        shares = 0
        avg_cost = 0
        realized = 0
        for t in sorted(pos['trades'], key=lambda x: x['date'] + x['time']):
            if t['type'] == '证券买入':
                qty = int(t['qty'])
                new_total = avg_cost * shares + qty * t['price']
                shares += qty
                avg_cost = new_total / shares if shares > 0 else 0
            elif t['type'] == '证券卖出':
                qty = abs(int(t['qty']))
                sell_rev = t['settlement']  # 已扣除费用
                cost_basis = qty * avg_cost
                trade_pnl = sell_rev - cost_basis
                realized += trade_pnl
                shares -= qty
                if shares == 0:
                    avg_cost = 0
        print(f"  已实现盈亏(移动加权平均): {realized:.2f}")
        print(f"  记录已实现盈亏: {pos['realized_pnl']:.2f}", end="")
        if abs(realized - pos['realized_pnl']) < 1:
            print(" ✅")
        else:
            print(f" ❌ 差异{abs(realized - pos['realized_pnl']):.2f}")

# ===================== 已清仓 =====================
print("\n\n## 已清仓股票验证\n")
for code, pos in stmt['closed_positions'].items():
    print(f"--- {pos['name']}({code}) ---")
    
    # 从all_trades找出该股票的所有交易
    trades = [t for t in stmt['all_trades'] if t['code'] == code]
    buy_trades = [t for t in trades if t['type'] == '证券买入']
    sell_trades = [t for t in trades if t['type'] == '证券卖出']
    div_trades = [t for t in trades if t['type'] == '股息入账']
    
    buy_qty = sum(t['qty'] for t in buy_trades)
    sell_qty = sum(abs(t['qty']) for t in sell_trades)
    print(f"  买入{buy_qty}股, 卖出{sell_qty}股, 余额{buy_qty-sell_qty}")
    
    buy_cost = sum(abs(t['settlement']) for t in buy_trades)
    sell_rev = sum(t['settlement'] for t in sell_trades)
    div_income = sum(t['settlement'] for t in div_trades)
    
    trading_pnl = sell_rev - buy_cost  # 纯交易盈亏（含手续费）
    total_pnl = trading_pnl + div_income  # 加分红
    
    print(f"  买入金额(含费): {buy_cost:,.2f}")
    print(f"  卖出金额(含费): {sell_rev:,.2f}")
    print(f"  分红收入: {div_income:,.2f}")
    print(f"  交易盈亏(不含分红): {trading_pnl:,.2f}")
    print(f"  总盈亏(含分红): {total_pnl:,.2f}")
    print(f"  记录realized_pnl: {pos['realized_pnl']:,.2f}")
    print(f"  记录dividends_total: {pos['dividends_total']:,.2f}")
    
    # 检查是否重复计算分红
    if abs(pos['realized_pnl'] - total_pnl) < 1:
        print("  ⚠️ realized_pnl包含了分红! 合计收益=realized_pnl+dividends_total会重复计算")
    elif abs(pos['realized_pnl'] - trading_pnl) < 1:
        print("  ✅ realized_pnl不含分红, 合计收益计算正确")
    else:
        print(f"  ❌ realized_pnl与两种算法都不匹配 (差交易{abs(pos['realized_pnl']-trading_pnl):.2f}, 差总计{abs(pos['realized_pnl']-total_pnl):.2f})")

# ===================== 总计 =====================
print("\n\n## 总计\n")
total_fees_current = sum(p['total_commission'] + p['total_stamp_tax'] + p['total_other_fees'] for p in stmt['current_positions'].values())
total_fees_closed = sum(p['total_commission'] + p['total_stamp_tax'] for p in stmt['closed_positions'].values())
print(f"当前持仓总费用: {total_fees_current:.2f}")
print(f"已清仓总费用: {total_fees_closed:.2f}")
print(f"全部费用: {total_fees_current + total_fees_closed:.2f}")

# 检查all_trades总数
print(f"\nall_trades总数: {len(stmt['all_trades'])}")
trades_from_pos = sum(len(p['trades']) for p in stmt['current_positions'].values())
div_count = sum(1 for t in stmt['all_trades'] if t['type'] == '股息入账')
closed_trade_count = len(stmt['all_trades']) - trades_from_pos - div_count + div_count  # all_trades包含所有
print(f"当前持仓trades数: {trades_from_pos}")
print(f"分红记录数: {div_count}")
