"""从东方财富公开API拉取所有自选股的历史分红数据，写入本地 dividends 表。

数据格式：
  - 上海: SH + code (如 SH601166)
  - 深圳: SZ + code (如 SZ002594)
  - 仅保留 ASSIGN_PROGRESS == '实施方案' 的已实施分红
  - 分红方案解析: "10派10.6元" → 每股分红 1.06 元
  - source='web', 与本地对账单 source='statement' 通过 UNIQUE(code,date,amount) 自动去重

用法:
  python scripts/fetch_dividends.py          # 拉取所有自选股
  python scripts/fetch_dividends.py 601166   # 拉取单只股票

模块导入:
  from fetch_dividends import fetch_all
  result = fetch_all()  # {'total': 45, 'stocks': {...}, 'errors': [...]}
"""

import os
import sys
import re
import json
import sqlite3
import gzip
import urllib.request
from datetime import datetime

# 项目根目录
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(ROOT, 'data', 'stock.db')

# 分红方案解析正则
# 格式: "10派10.6元" / "10送8转12派39.74元" / "10派1.05元"
_RE_BONUS = re.compile(r'(\d+)派([\d.]+)元')


def _get_watchlist_codes():
    """从数据库 watchlist 表读取所有自选股代码（与系统其他模块一致）。"""
    db = sqlite3.connect(DB_PATH, timeout=10)
    codes = [r[0] for r in db.execute("SELECT code FROM watchlist ORDER BY sort_order").fetchall()]
    db.close()
    return codes


def _market_prefix(code):
    """判断交易所前缀: 6开头→SH, 0/3开头→SZ。"""
    if code.startswith('6'):
        return 'SH' + code
    return 'SZ' + code


def _parse_per_share(plan_text):
    """从分红方案文字中提取每股分红金额。

    Args:
        plan_text: 如 "10派10.6元" / "10送8转12派39.74元" / "不分配不转增"

    Returns:
        float: 每股分红金额（元），无法解析时返回 0.0
    """
    if not plan_text or '不分配' in plan_text:
        return 0.0
    m = _RE_BONUS.search(plan_text)
    if m:
        per_10 = float(m.group(2))
        return round(per_10 / 10, 4)
    return 0.0


def fetch_dividend_history(code):
    """拉取单只股票的全部已实施分红记录。

    Args:
        code: 股票代码，如 '601166'

    Returns:
        list[dict]: 成功时返回 [{'date': '2025-06-20', 'per_share': 1.06, 'ex_date': '2025-06-20'}, ...]
                    失败时返回 []（网络错误、解析错误等）
    """
    market_code = _market_prefix(code)
    url = (
        'https://emweb.securities.eastmoney.com/PC_HSF10/'
        'BonusFinancing/PageAjax?code=' + market_code
    )

    req = urllib.request.Request(
        url,
        headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept-Encoding': 'gzip, deflate',
        }
    )

    try:
        resp = urllib.request.urlopen(req, timeout=10)
        raw = resp.read()
        # 尝试 gzip 解压
        try:
            text = gzip.decompress(raw).decode('utf-8')
        except (gzip.BadGzipFile, OSError):
            text = raw.decode('utf-8')
        data = json.loads(text)
    except Exception as e:
        print(f'  [fetch_dividends] {code} 网络请求失败: {e}')
        return []

    records = data.get('fhyx', [])
    if not records:
        return []

    result = []
    for item in records:
        # 只取已实施的
        if item.get('ASSIGN_PROGRESS') != '实施方案':
            continue

        per_share = _parse_per_share(item.get('IMPL_PLAN_PROFILE', ''))
        if per_share <= 0:
            continue

        ex_date = item.get('EX_DIVIDEND_DATE', '')
        if not ex_date:
            continue
        ex_date = ex_date[:10]  # '2025-06-20 00:00:00' → '2025-06-20'

        # 支付日优先，无支付日用除权日
        pay_date = item.get('PAY_CASH_DATE', '') or ex_date
        pay_date = pay_date[:10]

        result.append({
            'date': pay_date,
            'ex_date': ex_date,
            'per_share': per_share,
        })

    # 按日期倒序（最新在前）
    result.sort(key=lambda x: x['date'], reverse=True)
    return result


def upsert_dividends(code, records):
    """批量写入分红数据到 dividends 表。

    Web分红数据存储约定：
      - amount = per_share * 10000（大值避免与本地对账单记录冲突，用于UNIQUE去重）
      - price  = per_share（实际每股分红，get_dividends() 对 source='web' 直接取此值）
      - source = 'web'

    Args:
        code: 股票代码
        records: fetch_dividend_history() 的返回值

    Returns:
        int: 实际写入的记录数
    """
    if not records:
        return 0

    db = sqlite3.connect(DB_PATH, timeout=10)
    count = 0
    for r in records:
        per_share = r['per_share']
        # amount 用作唯一去重键（大量值避免与本地记录冲突）
        amount_key = round(per_share * 10000, 2)
        try:
            db.execute(
                "INSERT OR REPLACE INTO dividends(code, date, amount, price, ex_date, source) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                [code, r['date'], amount_key, per_share, r['ex_date'], 'web']
            )
            count += 1
        except Exception as e:
            print(f'  [fetch_dividends] {code} {r["date"]} 写入失败: {e}')

    db.commit()
    db.close()
    return count


def fetch_all():
    """遍历所有自选股，拉取分红数据并写入数据库。

    Returns:
        dict: {'total': N, 'stocks': {'601166': 5, ...}, 'errors': [...]}
    """
    codes = _get_watchlist_codes()
    print(f'[fetch_dividends] 开始拉取 {len(codes)} 只自选股的分红数据...')

    summary = {'total': 0, 'stocks': {}, 'errors': []}

    for code in codes:
        try:
            records = fetch_dividend_history(code)
            if records:
                count = upsert_dividends(code, records)
                summary['stocks'][code] = count
                summary['total'] += count
                # 显示最近2条分红信息
                latest = records[0]
                detail = f'每股{latest["per_share"]:.4f}元 ({latest["date"]})'
                if len(records) > 1:
                    detail += f' ...共{len(records)}条'
                print(f'  {code}: +{count}条  {detail}')
            else:
                print(f'  {code}: 无已实施分红记录')
        except Exception as e:
            summary['errors'].append({'code': code, 'error': str(e)})
            print(f'  [fetch_dividends] {code} 处理异常: {e}')

    print(f'[fetch_dividends] 完成: 共写入 {summary["total"]} 条分红记录')
    if summary['errors']:
        print(f'[fetch_dividends] 异常: {len(summary["errors"])} 只股票')
    return summary


if __name__ == '__main__':
    if len(sys.argv) > 1:
        # 拉取单只股票
        code = sys.argv[1]
        records = fetch_dividend_history(code)
        if records:
            count = upsert_dividends(code, records)
            print(f'{code}: 写入 {count} 条分红记录')
            for r in records:
                print(f"  {r['date']} 除权日={r['ex_date']} 每股={r['per_share']:.4f}元")
        else:
            print(f'{code}: 无已实施分红记录')
    else:
        fetch_all()
