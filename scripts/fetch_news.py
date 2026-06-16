import json, os, re, subprocess, sys, time
from datetime import datetime, date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from env_paths import get_node, get_westock
NODE = get_node()
WESTOCK = get_westock()
SCRIPT = 'scripts/index.js'
from db_helper import get_watchlist, get_db
MAX_NEWS_PER_STOCK = 20
MAX_RETRIES = 3
TIMEOUT_SEC = 60

A_SHARE_HOLIDAYS_2026 = {
    date(2026, 1, 1),
    date(2026, 2, 16), date(2026, 2, 17), date(2026, 2, 18),
    date(2026, 2, 19), date(2026, 2, 20),
    date(2026, 4, 6),
    date(2026, 5, 1),
    date(2026, 6, 22),
    date(2026, 10, 1), date(2026, 10, 2), date(2026, 10, 5),
    date(2026, 10, 6), date(2026, 10, 7),
}

def is_trading_day(d=None):
    if d is None:
        d = date.today()
    if d.weekday() >= 5:
        return False
    if d in A_SHARE_HOLIDAYS_2026:
        return False
    return True

def fetch_news_node(market_code, limit=MAX_NEWS_PER_STOCK):
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            result = subprocess.run(
                [NODE, SCRIPT, 'news', market_code, '--limit', str(limit)],
                cwd=WESTOCK, capture_output=True, timeout=TIMEOUT_SEC,
            )
            if result.returncode != 0:
                stderr_text = result.stderr.decode('gbk', errors='replace') if result.stderr else ''
                raise RuntimeError(f"exit code {result.returncode}: {stderr_text[:200]}")
            stdout = result.stdout
            if not stdout:
                return []
            try:
                text = stdout.decode('gbk')
            except (UnicodeDecodeError, LookupError):
                text = stdout.decode('utf-8', errors='replace')
            return _parse_news_table(text)
        except subprocess.TimeoutExpired:
            last_error = f"TimeoutExpired ({TIMEOUT_SEC}s)"
        except Exception as e:
            last_error = str(e)
        if attempt < MAX_RETRIES:
            backoff = 2 ** attempt
            time.sleep(backoff)
    return []

def _parse_news_table(text):
    lines = text.strip().split('\n')
    news_items = []
    data_start = 0
    for i, line in enumerate(lines):
        if line.startswith('| --- |') or line.startswith('|---'):
            data_start = i + 1
            break
    if data_start == 0 or data_start >= len(lines):
        return []
    for row in lines[data_start:]:
        row = row.strip()
        if not row or not row.startswith('|') or row.startswith('| ---'):
            continue
        item = _parse_news_row(row)
        if item:
            news_items.append(item)
    return news_items

def _parse_news_row(row):
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
    date_str = time_str[:10] if len(time_str) >= 10 else ''
    sentiment = _detect_sentiment(title, summary)
    return {
        'date': date_str,
        'code': _extract_code(symbol),
        'title': title,
        'summary': summary or '',
        'source': source or '\u7efc\u5408',
        'url': url,
        'sentiment': sentiment,
        'major': 1 if _is_major(title, summary) else 0,
        'news_id': news_id,
    }

def _extract_code(symbol):
    m = re.search(r'(\d{6})', symbol)
    return m.group(1) if m else symbol

def _detect_sentiment(title, summary):
    text = (title + ' ' + summary).lower()
    positive_kw = ['\u4e0a\u6da8', '\u51c0\u6d41\u5165', '\u4e70\u5165', '\u5229\u597d', '\u589e\u6301', '\u76c8\u5229', '\u5206\u7ea2', '\u770b\u597d',
                   '\u589e\u957f', '\u56de\u5347', '\u7a81\u7834', '\u65b0\u9ad8', '\u53d7\u6367', '\u8d44\u91d1\u51c0\u6d41\u5165']
    negative_kw = ['\u4e0b\u8dcc', '\u51c0\u6d41\u51fa', '\u5356\u51fa', '\u5229\u7a7a', '\u51cf\u6301', '\u4e8f\u635f', '\u98ce\u9669', '\u770b\u8dcc',
                   '\u4e0b\u6ed1', '\u627f\u538b', '\u8dcc\u7834', '\u629b\u538b', '\u8d44\u91d1\u51c0\u6d41\u51fa', '\u878d\u8d44\u51c0\u5356\u51fa']
    pos_score = sum(1 for kw in positive_kw if kw in text)
    neg_score = sum(1 for kw in negative_kw if kw in text)
    if pos_score > neg_score:
        return 'positive'
    elif neg_score > pos_score:
        return 'negative'
    return 'neutral'

def _is_major(title, summary):
    major_kw = ['\u91cd\u5927', '\u91cd\u78c5', '\u653f\u7b56', '\u5229\u7387', '\u964d\u51c6', '\u52a0\u606f', '\u76d1\u7ba1', '\u592e\u884c', '\u56fd\u52a1\u9662']
    text = title + ' ' + summary
    return any(kw in text for kw in major_kw)

def main():
    if not is_trading_day():
        return
    watchlist = get_watchlist()
    today = datetime.now().strftime('%Y-%m-%d')
    all_news = []
    for stock in watchlist:
        code, name, mkt = stock['code'], stock['name'], stock.get('market', 'sh')
        items = fetch_news_node(f'{mkt}{code}')
        if items:
            all_news.extend(items)
    if not all_news:
        return
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
    from db_helper import upsert_news
    upsert_news(deduped)
    db = get_db()
    total = db.execute("SELECT COUNT(*) FROM news").fetchone()[0]
    db.close()

if __name__ == '__main__':
    main()
