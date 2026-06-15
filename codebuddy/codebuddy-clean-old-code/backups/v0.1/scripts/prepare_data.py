"""将NeoData月度K线数据整理为HTML程序所需的紧凑JSON格式"""
import json
import os

DATA_DIR = r"C:\Users\28312\WorkBuddy\2026-05-18-task-15\data"

# 分红数据（从NeoData查询结果提取）
DIVIDENDS = {
    "601166": [
        {"date": "2023-06-19", "amount": 1.188, "label": "10派11.88元"},
        {"date": "2024-07-09", "amount": 1.04, "label": "10派10.4元"},
        {"date": "2025-06-20", "amount": 1.06, "label": "10派10.6元"},
        {"date": "2026-02-06", "amount": 0.565, "label": "10派5.65元(中期)"},
        {"date": "2026-待定", "amount": 0.501, "label": "10派5.01元(预案)"},
    ],
    "600036": [
        {"date": "2023-07-13", "amount": 1.738, "label": "10派17.38元"},
        {"date": "2024-07-11", "amount": 1.972, "label": "10派19.72元"},
        {"date": "2025-07-11", "amount": 2.00, "label": "10派20元"},
        {"date": "2026-01-16", "amount": 1.013, "label": "10派10.13元(中期)"},
        {"date": "2026-待定", "amount": 1.003, "label": "10派10.03元(预案)"},
    ]
}

# 持仓信息
HOLDINGS = {
    "601166": {"shares": 6300, "name": "兴业银行", "code": "601166.SH"},
    "600036": {"shares": 2500, "name": "招商银行", "code": "600036.SH"},
}

def process_stock(code):
    """处理单只股票数据"""
    infile = os.path.join(DATA_DIR, f"{code}_kline_3y.json")
    with open(infile, 'r', encoding='utf-8') as f:
        raw = json.load(f)

    kline = raw['kline_data']

    # 计算月度涨跌幅统计
    monthly_stats = {}
    for item in kline:
        ym = item['date'][:7]  # YYYY-MM
        if ym not in monthly_stats:
            monthly_stats[ym] = {
                'open': item['open'],
                'close': item['close'],
                'high': item['high'],
                'low': item['low'],
                'volume': 0,
                'start_date': item['date'],
                'end_date': item['date'],
            }
        ms = monthly_stats[ym]
        ms['close'] = item['close']
        ms['end_date'] = item['date']
        ms['high'] = max(ms['high'], item['high'])
        ms['low'] = min(ms['low'], item['low'])
        ms['volume'] += item.get('volume', 0)
        if item['date'] < ms['start_date']:
            ms['start_date'] = item['date']
            ms['open'] = item['open']

    # 月度涨跌幅
    monthly_pct = {}
    for ym, ms in monthly_stats.items():
        if ms['open'] > 0:
            monthly_pct[ym] = round((ms['close'] - ms['open']) / ms['open'] * 100, 2)
        else:
            monthly_pct[ym] = 0

    # 季节性统计（按月份聚合）
    seasonal = {}
    for month in range(1, 13):
        pcts = []
        for ym, pct in monthly_pct.items():
            m = int(ym.split('-')[1])
            if m == month:
                pcts.append(pct)
        if pcts:
            seasonal[month] = {
                'avg': round(sum(pcts) / len(pcts), 2),
                'count': len(pcts),
                'values': pcts,
                'max': max(pcts),
                'min': min(pcts),
            }

    # 构建紧凑K线数据（日期,开,高,低,收,量,涨跌幅%）
    compact_kline = []
    for item in kline:
        compact_kline.append([
            item['date'],
            item['open'],
            item['high'],
            item['low'],
            item['close'],
            item.get('volume', 0),
            item.get('pct_change', 0),
        ])

    return {
        'code': code,
        'name': HOLDINGS[code]['name'],
        'shares': HOLDINGS[code]['shares'],
        'kline': compact_kline,
        'monthly_pct': monthly_pct,
        'seasonal': {str(k): v for k, v in seasonal.items()},
        'dividends': DIVIDENDS[code],
    }

def main():
    xy = process_stock("601166")
    zh = process_stock("600036")

    output = {
        'generated': '2026-05-20',
        'stocks': [xy, zh]
    }

    outpath = os.path.join(DATA_DIR, 'analysis_data.json')
    with open(outpath, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False)

    print(f"数据已保存到 {outpath}")
    print(f"兴业银行: {len(xy['kline'])} 条K线, {len(xy['monthly_pct'])} 个月度涨跌")
    print(f"招商银行: {len(zh['kline'])} 条K线, {len(zh['monthly_pct'])} 个月度涨跌")

if __name__ == '__main__':
    main()
