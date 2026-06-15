import json
import os

# 加载所有数据
with open('data/analysis_data.json','r',encoding='utf-8') as f:
    analysis = json.load(f)
with open('data/broker_statement.json','r',encoding='utf-8') as f:
    broker = json.load(f)

# 当前行情
quotes = {
    '601166': {'price':17.33,'change':-0.97,'open':17.52,'high':17.52,'low':17.33,'pe':4.73,'pb':0.44,'dy':9.38},
    '600036': {'price':37.17,'change':-0.54,'open':37.37,'high':37.44,'low':37.17,'pe':6.22,'pb':0.83,'dy':8.11},
    '600900': {'price':26.90,'change':-1.28,'pe':18.24,'pb':2.89,'dy':3.51},
    '601939': {'price':9.85,'change':-0.81,'pe':7.54,'pb':0.73,'dy':1.89},
    '601398': {'price':7.13,'change':-1.79,'pe':6.84,'pb':0.65,'dy':4.35},
    '600050': {'price':4.74,'change':-4.24,'pe':17.12,'pb':0.87,'dy':3.66},
}

# 月度预测
predictions = {
    '601166': [
        {'month':'2026-06','pred':17.8,'hi':19.2,'lo':16.4},
        {'month':'2026-07','pred':18.6,'hi':20.4,'lo':16.8},
        {'month':'2026-08','pred':18.2,'hi':20.2,'lo':16.2},
        {'month':'2026-09','pred':19.0,'hi':21.2,'lo':16.8},
        {'month':'2026-10','pred':19.5,'hi':22.0,'lo':17.0},
        {'month':'2026-11','pred':19.1,'hi':21.7,'lo':16.5},
    ],
    '600036': [
        {'month':'2026-06','pred':38.2,'hi':41.0,'lo':35.5},
        {'month':'2026-07','pred':39.8,'hi':43.4,'lo':36.2},
        {'month':'2026-08','pred':39.1,'hi':42.7,'lo':35.5},
        {'month':'2026-09','pred':40.5,'hi':44.8,'lo':36.2},
        {'month':'2026-10','pred':41.2,'hi':45.6,'lo':36.8},
        {'month':'2026-11','pred':40.6,'hi':45.3,'lo':35.9},
    ]
}

# 季节性数据
seasonal = {
    '601166': [0.8,-2.5,1.2,0.5,-1.0,2.3,3.5,-1.8,1.5,2.8,-1.2,3.0],
    '600036': [1.0,-2.0,0.8,0.3,-0.5,2.0,3.0,-1.5,1.2,2.5,-1.0,2.5]
}

# 组装完整数据
output = {
    'generated': '2026-05-20',
    'account': broker['account'],
    'broker': broker['broker'],
    'quotes': quotes,
    'current_positions': broker['current_positions'],
    'closed_positions': broker['closed_positions'],
    'all_trades': broker['all_trades'],
    'predictions': predictions,
    'seasonal': seasonal,
}

# K线数据单独输出（数据量较大）
kline_data = {}
for stock in analysis['stocks']:
    kline_data[stock['code']] = stock['kline']
    output['dividends_' + stock['code']] = stock.get('dividends', [])
    output['monthly_changes_' + stock['code']] = stock.get('monthly_changes', [])

output['kline'] = kline_data

with open('data/system_data.json','w',encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False)

print(f"数据已整合: {len(kline_data['601166'])}条兴业K线, {len(kline_data['600036'])}条招行K线")
print(f"交易记录: {len(broker['all_trades'])}条")
