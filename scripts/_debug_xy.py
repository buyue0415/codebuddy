"""Debug 兴业银行 dividend yield chart data."""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from db_helper import get_dividend_yield_series

ds = get_dividend_yield_series('601166')
labels = ds['labels']
dy = ds['dy_series']
close = ds['close_prices']
events = ds['dividend_events']

print('=== 兴业银行 股息率走势 ===')
print(f'数据点数: {len(labels)}, 起止: {labels[0]} ~ {labels[-1]}')
print(f'分红事件数: {len(events)}')
for e in events:
    print(f'  ex={e.get("ex_date",e["date"])} ps={e["per_share"]:.4f} src={e["source"]}')

# 筛选 DY 高的区域
print('\n=== 高DY区域 (DY > 10%) ===')
for i, (d, c, y) in enumerate(zip(labels, close, dy)):
    if y and y > 10:
        print(f'  {d} close={c} dy={y}%')

print('\n=== 最高10个DY值 ===')
sorted_dy = sorted([(d, y, c) for d, y, c in zip(labels, dy, close) if y], key=lambda x: -x[1])
for d, y, c in sorted_dy[:10]:
    print(f'  {d} close={c} dy={y}%')

# 2026-03-09 附近
print('\n=== 2026-02 ~ 2026-03 数据 ===')
for i, (d, c, y) in enumerate(zip(labels, close, dy)):
    if d >= '2026-02-01' and d <= '2026-03-31':
        prev = dy[i-1] if i > 0 and dy[i-1] else None
        print(f'  {d} close={c} dy={y}  prev={prev}')

# 查看 Y 轴范围
non_null = [y for y in dy if y is not None]
if non_null:
    print(f'\nDY 范围: {min(non_null):.2f}% ~ {max(non_null):.2f}%')
