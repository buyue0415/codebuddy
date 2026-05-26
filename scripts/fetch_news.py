"""
Fetch news for all watchlist stocks from NeoData and persist to SQLite.
Run daily via scheduler to keep news data current.

Usage: python scripts/fetch_news.py
Or via automation: POST /api/trigger/news (via server.py trigger endpoint)
"""
import json, os, re, subprocess, sys
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from db_helper import get_watchlist, get_db

NODE = r'C:\Users\28312\.workbuddy\binaries\node\versions\22.12.0\node.exe'
WESTOCK = r'C:\Users\28312\.workbuddy\plugins\marketplaces\cb_teams_marketplace\plugins\finance-data\skills\westock-data'
SCRIPT = 'scripts/index.js'
MAX_NEWS_PER_STOCK = 20

def fetch_news_node(market_code: str, limit: int = MAX_NEWS_PER_STOCK) -> list[dict]:
    """Fetch news for one stock via Node.js CLI. Returns list of parsed news items."""
    try:
        result = subprocess.run(
            [NODE, SCRIPT, 'news', market_code, '--limit', str(limit)],
            cwd=WESTOCK, capture_output=True, timeout=30,
        )
        stdout = result.stdout
        if not stdout:
            return []
        # Decode: try gbk first, fallback to utf-8
        try:
            text = stdout.decode('gbk')
        except (UnicodeDecodeError, LookupError):
            text = stdout.decode('utf-8', errors='replace')

        return _parse_news_table(text)
    except Exception as e:
        print(f"  NEWS fetch error for {market_code}: {e}")
        return []

def _parse_news_table(text: str) -> list[dict]:
    """Parse the markdown table output from the news CLI command."""
    lines = text.strip().split('\n')
    news_items = []

    # Find separator line to know where data rows start
    data_start = 0
    for i, line in enumerate(lines):
        if line.startswith('| --- |') or line.startswith('|---'):
            data_start = i + 1
            break

    if data_start == 0 or data_start >= len(lines):
        return []

    # Parse the header line to get column positions
    header_line = ''
    for line in lines:
        if line.startswith('| time | id |'):
            header_line = line
            break

    if not header_line:
        # Try data rows directly
        for row in lines[data_start:]:
            row = row.strip()
            if not row or not row.startswith('|'):
                continue
            item = _parse_news_row(row)
            if item:
                news_items.append(item)
    else:
        for row in lines[data_start:]:
            row = row.strip()
            if not row or not row.startswith('|') or row.startswith('| ---'):
                continue
            item = _parse_news_row(row)
            if item:
                news_items.append(item)

    return news_items

def _parse_news_row(row: str) -> dict | None:
    """Parse a single markdown table row into a news dict."""
    # Split by | but handle content carefully
    # Remove leading/trailing | and split
    content = row.strip()
    if content.startswith('|'):
        content = content[1:]
    if content.endswith('|'):
        content = content[:-1]
    parts = [p.strip() for p in content.split('|')]

    if len(parts) < 10:
        return None

    time_str = parts[0] if len(parts) > 0 else ''
    news_id = parts[1] if len(parts) > 1 else ''
    symbol = parts[3] if len(parts) > 3 else ''
    title = parts[4] if len(parts) > 4 else ''
    url = parts[5] if len(parts) > 5 else ''
    source = parts[9] if len(parts) > 9 else ''
    summary = parts[13] if len(parts) > 13 else ''

    # Extract date from time string
    date_str = time_str[:10] if len(time_str) >= 10 else ''

    # Determine sentiment from title keywords
    sentiment = _detect_sentiment(title, summary)

    return {
        'date': date_str,
        'code': _extract_code(symbol),
        'title': title,
        'summary': summary or '',
        'source': source or '综合',
        'url': url,
        'sentiment': sentiment,
        'major': 1 if _is_major(title, summary) else 0,
        'news_id': news_id,
    }

def _extract_code(symbol: str) -> str:
    """Extract 6-digit stock code from symbol like 'sh601166' -> '601166'."""
    m = re.search(r'(\d{6})', symbol)
    return m.group(1) if m else symbol

def _detect_sentiment(title: str, summary: str) -> str:
    """Detect news sentiment by keyword matching."""
    text = (title + ' ' + summary).lower()
    positive_kw = ['上涨', '净流入', '买入', '利好', '增持', '盈利', '分红', '看好',
                   '增长', '回升', '突破', '新高', '受捧', '资金净流入']
    negative_kw = ['下跌', '净流出', '卖出', '利空', '减持', '亏损', '风险', '看跌',
                   '下滑', '承压', '跌破', '抛压', '资金净流出', '融资净卖出']

    pos_score = sum(1 for kw in positive_kw if kw in text)
    neg_score = sum(1 for kw in negative_kw if kw in text)

    if pos_score > neg_score:
        return 'positive'
    elif neg_score > pos_score:
        return 'negative'
    return 'neutral'

def _is_major(title: str, summary: str) -> bool:
    """Determine if news is a major event."""
    major_kw = ['重大', '重磅', '政策', '利率', '降准', '加息', '监管', '央行', '国务院']
    text = title + ' ' + summary
    return any(kw in text for kw in major_kw)

def main():
    watchlist = get_watchlist()
    print(f"[fetch_news] Watchlist: {len(watchlist)} stocks")

    today = datetime.now().strftime('%Y-%m-%d')
    all_news = []
    codes = [s['code'] for s in watchlist]

    for stock in watchlist:
        code, name, mkt = stock['code'], stock['name'], stock.get('market', 'sh')
        market_code = f'{mkt}{code}'
        print(f"  Fetching news for {name}({code})...", end=' ')
        items = fetch_news_node(market_code)
        if items:
            print(f"{len(items)} items")
            all_news.extend(items)
        else:
            print("no data")

    if not all_news:
        print("[fetch_news] No news fetched. Check network connectivity.")
        return

    # Stronger in-memory dedup: prefer URL as unique key, fallback to (title, date, code)
    seen_url = set()
    seen_fallback = set()
    deduped = []
    for n in all_news:
        url_key = n.get('url', '')
        fallback_key = (n['title'], n['date'], n['code'])
        if url_key and url_key not in seen_url:
            seen_url.add(url_key)
            deduped.append(n)
        elif not url_key and fallback_key not in seen_fallback:
            seen_fallback.add(fallback_key)
            deduped.append(n)

    # Persist via upsert which uses INSERT OR IGNORE + unique index
    from db_helper import upsert_news
    upsert_news(deduped)

    # Count total after write
    db = get_db()
    total = db.execute("SELECT COUNT(*) FROM news").fetchone()[0]
    db.close()

    print(f"\n[fetch_news] Done. Fetched {len(all_news)} items, "
          f"deduped to {len(deduped)}, saved via upsert.")
    print(f"[fetch_news] DB now has {total} total news.")

if __name__ == '__main__':
    main()
