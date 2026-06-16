from scripts.db_helper import get_db, get_watchlist
db = get_db()

# 当日新闻统计
today_news = db.execute("SELECT code, COUNT(cnt) as cnt FROM (SELECT code, 1 as cnt FROM news WHERE date = '2026-06-16') GROUP BY code ORDER BY cnt DESC").fetchall()
print('=== 今日(2026-06-16)抓取统计 ===')
for row in today_news:
    print(f'  {row[0]}: {row[1]} 条')
total_today = sum(r[1] for r in today_news)

# 总新闻数
total = db.execute("SELECT COUNT(rowid) FROM news").fetchone()[0]
print(f'\n数据库总新闻数: {total} 条')

# 监视列表
wl = get_watchlist()
print(f'\n监视股票: {len(wl)} 只')
for s in wl:
    print(f'  {s["code"]} {s["name"]}')
db.close()
