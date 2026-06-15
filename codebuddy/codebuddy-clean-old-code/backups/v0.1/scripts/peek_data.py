import json
d = json.load(open('data/601166_kline_3y.json', 'r', encoding='utf-8'))
print(f"总记录: {len(d['kline_data'])}")
for r in d['kline_data'][:15]:
    print(r)
print("---")
for r in d['kline_data'][-5:]:
    print(r)
