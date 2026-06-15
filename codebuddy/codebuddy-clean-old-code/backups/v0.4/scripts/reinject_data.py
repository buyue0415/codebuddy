import json, re

with open('data/system_data.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

with open('deliverables/bank-stock-system.html', 'r', encoding='utf-8') as f:
    html = f.read()

data_json = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
html = re.sub(r'const DATA = \{.*?\};\n', 'const DATA = ' + data_json + ';\n', html, flags=re.DOTALL)

with open('deliverables/bank-stock-system.html', 'w', encoding='utf-8') as f:
    f.write(html)
print('HTML updated successfully')
