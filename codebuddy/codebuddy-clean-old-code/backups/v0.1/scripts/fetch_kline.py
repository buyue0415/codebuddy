#!/usr/bin/env python3
"""按月分段拉取兴业银行/招商银行3年日K线数据，合并保存为JSON"""

import json
import re
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
NEODATA_SCRIPT = r"C:\Users\28312\.workbuddy\plugins\marketplaces\cb_teams_marketplace\plugins\finance-data\skills\neodata-financial-search\scripts\query.py"
PYTHON = r"C:\Users\28312\.workbuddy\binaries\python\versions\3.13.12\python.exe"
OUTPUT_DIR = SCRIPT_DIR.parent / "data"

import subprocess

def run_query(query: str) -> dict:
    """调用neodata查询脚本"""
    result = subprocess.run(
        [PYTHON, NEODATA_SCRIPT, "--query", query, "--data-type", "api"],
        capture_output=True, text=True, timeout=30
    )
    if result.returncode != 0:
        print(f"查询失败: {result.stderr}", file=sys.stderr)
        return {}
    return json.loads(result.stdout)

def parse_kline_table(content: str) -> list:
    """从markdown表格中解析K线数据"""
    rows = []
    lines = content.split('\n')
    in_table = False
    for line in lines:
        line = line.strip()
        if line.startswith('|') and '日期' in line:
            in_table = True
            continue
        if line.startswith('| :---') or line.startswith('|---'):
            continue
        if in_table and line.startswith('|'):
            cells = [c.strip() for c in line.split('|')[1:-1]]
            if len(cells) >= 7 and cells[0] not in ('', '日期'):
                date_str = cells[0]
                if '未开盘' in date_str or '省略' in date_str:
                    continue
                try:
                    rows.append({
                        'date': date_str,
                        'open': float(cells[1]) if cells[1] else None,
                        'close': float(cells[2]) if cells[2] else None,
                        'pct_change': float(cells[3].replace('%','')) if cells[3] and cells[3] != '-' else None,
                        'volume': int(cells[4].replace(',','')) if cells[4] and cells[4] != '-' else None,
                        'amount': float(cells[5].replace(',','')) if cells[5] and cells[5] != '-' else None,
                        'high': float(cells[6]) if cells[6] else None,
                        'low': float(cells[7]) if cells[7] and cells[7] != '-' else None,
                    })
                except (ValueError, IndexError):
                    continue
        elif in_table and not line.startswith('|'):
            in_table = False
    return rows

def fetch_monthly_kline(stock_code: str, stock_name: str, year: int, month: int) -> list:
    """查询指定月份的K线数据"""
    from datetime import date
    if month == 12:
        end_date = f"{year}-12-31"
    else:
        end_date = f"{year}-{month+1:02d}-01"
    start_date = f"{year}-{month:02d}-01"

    query = f"{stock_name}{stock_code} {year}年{month}月日K线数据 从{start_date}到{end_date} 包括日期、开盘价、收盘价、最高价、最低价、成交量"
    print(f"  查询 {stock_name} {year}-{month:02d} ...", end=" ", flush=True)
    result = run_query(query)
    if not result or result.get('code') != '200':
        print("失败")
        return []

    api_recall = result.get('data', {}).get('apiData', {}).get('apiRecall', [])
    all_rows = []
    for item in api_recall:
        content = item.get('content', '')
        rows = parse_kline_table(content)
        all_rows.extend(rows)
    print(f"获取 {len(all_rows)} 条")
    return all_rows

def fetch_stock_3years(stock_code: str, stock_name: str) -> list:
    """拉取3年月度数据并合并"""
    all_data = []
    seen_dates = set()

    # 从2023-06到2026-05, 按月查询
    months = []
    for y in range(2023, 2027):
        for m in range(1, 13):
            if y == 2023 and m < 6:
                continue
            if y == 2026 and m > 5:
                continue
            months.append((y, m))

    for y, m in months:
        rows = fetch_monthly_kline(stock_code, stock_name, y, m)
        for row in rows:
            if row['date'] not in seen_dates:
                seen_dates.add(row['date'])
                all_data.append(row)
        time.sleep(0.8)  # 避免限流

    # 按日期排序
    all_data.sort(key=lambda x: x['date'])
    return all_data

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    stocks = [
        ("601166", "兴业银行"),
        ("600036", "招商银行"),
    ]

    for code, name in stocks:
        print(f"\n{'='*50}")
        print(f"开始拉取 {name}({code}) 3年K线数据")
        print(f"{'='*50}")

        data = fetch_stock_3years(code, name)

        # 保存为JSON
        output_file = OUTPUT_DIR / f"{code}_kline_3y.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                'stock_code': code,
                'stock_name': name,
                'data_range': '2023-06 至 2026-05',
                'total_records': len(data),
                'kline_data': data
            }, f, ensure_ascii=False, indent=2)

        print(f"\n{name} 共 {len(data)} 条数据, 已保存到 {output_file}")

if __name__ == '__main__':
    main()
