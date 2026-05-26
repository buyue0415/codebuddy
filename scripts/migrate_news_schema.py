"""One-time migration: add url column + unique index to news table."""
import sqlite3, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, 'data', 'stock.db')

db = sqlite3.connect(DB)
c = db.cursor()

# Step 1: Add url column if it does not exist
column_exists = any(
    r[1] == 'url' for r in c.execute("PRAGMA table_info(news)").fetchall()
)
if not column_exists:
    c.execute("ALTER TABLE news ADD COLUMN url TEXT DEFAULT ''")
    print("[OK] Added 'url' column to news table")
else:
    print("[SKIP] 'url' column already exists")

# Step 2: Remove exact duplicates (based on code, date, title) keeping earliest id
# Need to drop existing index first if it exists with old definition
c.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_news_unique'")
if c.fetchone():
    c.execute("DROP INDEX idx_news_unique")
    print("[OK] Dropped old index idx_news_unique")

# Dedup on (code, date, title) — URL is stored for reference but not part of uniqueness
c.execute("""
    DELETE FROM news WHERE id NOT IN (
        SELECT MIN(id) FROM news GROUP BY code, date, title
    )
""")
removed = c.rowcount
if removed:
    print(f"[CLEAN] Removed {removed} duplicate news rows")
else:
    print("[OK] No duplicates found")

# Step 3: Create unique index on (code, date, title)
try:
    c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_news_unique ON news(code, date, title)")
    print("[OK] Created unique index idx_news_unique")
except Exception as e:
    print(f"[WARN] Index create: {e}")

db.commit()
db.close()
print("[DONE] News table migration complete")
