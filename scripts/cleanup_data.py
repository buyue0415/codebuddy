"""清理僵尸数据 + 修复字段"""
import json, os
from datetime import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(ROOT, '..', 'data', 'system_data.json')

with open(DATA_PATH, 'r', encoding='utf-8') as f:
    d = json.load(f)

today = datetime.now().strftime('%Y-%m-%d')
changes = []

# 1. 清理 quotes 中非持仓股票（保留 601166 + 600036）
old_quotes = list(d['quotes'].keys())
d['quotes'] = {k: v for k, v in d['quotes'].items() if k in ('601166', '600036')}
removed = set(old_quotes) - set(d['quotes'].keys())
changes.append(f'quotes: 保留 601166/600036, 移除 {removed}')

# 2. 删除旧 predictions 字段（已被 daily_predictions 替代）
if 'predictions' in d:
    del d['predictions']
    changes.append("删除旧 'predictions' 字段")

# 3. 删除顶层孤儿 dividends_*/monthly_changes_*（已在持仓内）
for key in list(d.keys()):
    if key.startswith('dividends_') or key.startswith('monthly_changes_'):
        del d[key]
        changes.append(f"删除顶层孤儿 '{key}'（已在持仓内）")

# 4. 更新 generated
d['generated'] = today
changes.append(f"generated -> {today}")

# 5. 验证 mw_beta 存在
for code, lp in d.get('learning_params', {}).items():
    if 'mw_beta' not in lp:
        lp['mw_beta'] = 0.7
        changes.append(f"learning_params.{code}.mw_beta = 0.7 (补)")

# 6. 补充 learning_params 里面的 learning_rate 字段（如果缺失）
for code, lp in d.get('learning_params', {}).items():
    if 'learning_rate' not in lp:
        lp['learning_rate'] = 0.01
        changes.append(f"learning_params.{code}.learning_rate = 0.01 (补)")

with open(DATA_PATH, 'w', encoding='utf-8') as f:
    json.dump(d, f, ensure_ascii=False, indent=2)

print('=== 清理完成 ===')
for c in changes:
    print(f'  {c}')

print(f'\n当前顶层字段: {list(d.keys())}')
print(f'总字段数: {len(d)}')