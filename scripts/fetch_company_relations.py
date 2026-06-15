"""
采集公司关系数据（股权/高管/供应链/竞争/主营业务），写入 SQLite。

现在使用 fetchers 模块实现多数据源自动回退：
  东方财富(primary) → 新浪财经(fallback1) → 腾讯财经(fallback2)

用法:
  python scripts/fetch_company_relations.py
"""
import os
import sys
import json
import sqlite3

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
DB_PATH = os.path.join(ROOT, 'data', 'stock.db')

from fetchers import get_available_fetcher, clear_fetcher_cache, fetch_with_fallback

# ── 加载全量 A 股列表 ──────────────────────────────────────────────────
_A_STOCKS = None
_A_STOCKS_BY_NAME = None


def _load_a_stocks():
    """Load a_stocks.json and build name→code index."""
    global _A_STOCKS, _A_STOCKS_BY_NAME
    if _A_STOCKS is not None:
        return
    path = os.path.join(ROOT, 'data', 'a_stocks.json')
    if not os.path.exists(path):
        _A_STOCKS = []
        _A_STOCKS_BY_NAME = {}
        return
    with open(path, 'r', encoding='utf-8') as f:
        _A_STOCKS = json.load(f)
    _A_STOCKS_BY_NAME = {}
    for s in _A_STOCKS:
        name = s.get('name', '').strip()
        if name:
            _A_STOCKS_BY_NAME[name] = s


def _match_stock_code(company_name):
    """Try to match a company name to an A-share stock code.

    Returns (code, name) or (None, None) if no match.
    """
    _load_a_stocks()
    if not _A_STOCKS_BY_NAME:
        return None, None

    # 1. Exact match
    if company_name in _A_STOCKS_BY_NAME:
        s = _A_STOCKS_BY_NAME[company_name]
        return s['code'], s['name']

    # 2. Trim common suffixes and try again
    stripped = company_name
    for suffix in ['有限公司', '股份有限公司', '集团', '集团公司', '总公司', '股份']:
        if stripped.endswith(suffix):
            stripped = stripped[:-len(suffix)]
            break
    if stripped != company_name and stripped in _A_STOCKS_BY_NAME:
        s = _A_STOCKS_BY_NAME[stripped]
        return s['code'], s['name']

    # 3. Fuzzy: check if any stock name contains the company name
    for sname, s in _A_STOCKS_BY_NAME.items():
        if company_name in sname or sname in company_name:
            if len(company_name) >= 2 and len(sname) >= 2:
                return s['code'], s['name']

    return None, None


# ── DB helpers ──────────────────────────────────────────────────────────

def _get_db():
    db = sqlite3.connect(DB_PATH, timeout=10)
    db.execute("PRAGMA journal_mode=WAL")
    db.row_factory = sqlite3.Row
    return db


def _upsert_relation(db, record):
    db.execute("""
        INSERT OR REPLACE INTO company_relations
            (code, related_code, related_name, relation_type, relation_subtype,
             relation_detail, weight, direction, extra_data, source)
        VALUES (?,?,?,?,?,?,?,?,?,?)
    """, [
        record.get('code'),
        record.get('related_code'),
        record.get('related_name', ''),
        record.get('relation_type'),
        record.get('relation_subtype', ''),
        record.get('relation_detail', ''),
        record.get('weight', 1.0),
        record.get('direction', ''),
        json.dumps(record.get('extra_data', {}), ensure_ascii=False),
        'web',
    ])


def _upsert_business(db, record):
    """Upsert business info, protecting existing data from being overwritten
    by lower-quality sources.

    Rules:
      - Only overwrite industry/business if the new value is non-empty AND
        contains Chinese characters (reject numeric garbage codes)
      - Never replace real industry with empty string
      - Always update name (it's always available from any source)
    """
    existing = db.execute(
        "SELECT industry, business FROM company_business WHERE code=?",
        [record.get('code')]
    ).fetchone()

    def _has_real_industry(val):
        """Check if a value looks like a real Chinese industry name."""
        if not val:
            return False
        return any('\u4e00' <= c <= '\u9fff' for c in str(val))

    new_ind = record.get('industry', '')
    new_biz = record.get('business', '')

    if existing:
        # Preserve existing industry if new data has no real industry
        if not _has_real_industry(new_ind):
            new_ind = existing['industry']
        # Preserve existing business if new data has empty business
        if not new_biz and existing['business']:
            new_biz = existing['business']

    db.execute("""
        INSERT OR REPLACE INTO company_business
            (code, name, industry, business, source)
        VALUES (?,?,?,?,?)
    """, [
        record.get('code'),
        record.get('name', ''),
        new_ind,
        new_biz,
        'web',
    ])


def _get_existing_industry(db, code):
    """Get industry for a stock code from company_business table."""
    r = db.execute("SELECT industry FROM company_business WHERE code=?", [code]).fetchone()
    return r['industry'] if r and r['industry'] else None


# ── 关联方匹配补充 ──────────────────────────────────────────────────────

def _enrich_related_party(fetcher, related_names, summary):
    """For a list of related company names, try to match them to A-stock codes
    and fetch their business info. Only basic info, no recursive relations."""
    matched = 0
    for rname in related_names:
        # Remove holder_/person_ prefix if present
        clean_name = rname.replace('holder_', '').replace('person_', '')
        if not clean_name:
            continue

        code, name = _match_stock_code(clean_name)
        if not code:
            continue

        # Check if already have data
        db = _get_db()
        try:
            existing = db.execute(
                "SELECT industry FROM company_business WHERE code=?", [code]
            ).fetchone()
            if existing and existing['industry']:
                continue  # Already have data
        finally:
            db.close()

        # Fetch business info for this matched stock
        biz = fetcher.fetch_business(code)
        if not biz or not biz.get('name'):
            continue

        biz['code'] = code
        biz['name'] = name
        db = _get_db()
        try:
            _upsert_business(db, biz)
            db.commit()
            matched += 1
            print(f'    [补充] 关联方 {name} ({code}): 行业={biz.get("industry","")}')
        finally:
            db.close()

    return matched


# ── 竞争关系构建（全A股） ──────────────────────────────────────────────

def _build_competition_relations(db_path):
    """Build competition relations between watchlist stocks and their
    industry peers matched via a_stocks.json.

    Strategy:
    1. For each watchlist stock, get its industry from company_business
    2. For each industry, find ALL stocks in a_stocks.json with matching
       company names (since a_stocks.json lacks industry field, we rely
       on the industry from business descriptions)
    3. Create competition edges between watchlist stocks and their peers

    Note: Since a_stocks.json doesn't contain industry data, this function
    builds competition among stocks that have industry info in the
    company_business table (i.e., stocks that have been fetched).
    """
    db = sqlite3.connect(db_path, timeout=10)
    db.row_factory = sqlite3.Row
    try:
        # Get all watchlist codes
        watchlist_codes = [r['code'] for r in db.execute(
            "SELECT code FROM watchlist ORDER BY sort_order"
        ).fetchall()]

        if len(watchlist_codes) < 2:
            return 0

        # Get all company business data (industry info)
        biz_rows = db.execute(
            "SELECT code, name, industry FROM company_business WHERE industry != '' ORDER BY code"
        ).fetchall()

        # Build industry -> [stock] index from company_business
        industry_map = {}
        code_to_name = {}
        for r in biz_rows:
            ind = (r['industry'] or '').strip()
            if ind:
                if ind not in industry_map:
                    industry_map[ind] = []
                industry_map[ind].append(r['code'])
                code_to_name[r['code']] = r['name'] or r['code']

        # Also try to match a_stocks.json company names to industry peers
        _load_a_stocks()
        # For each watchlist stock, extend competition to all stocks in same industry
        count = 0
        for wl_code in watchlist_codes:
            # Get this stock's industry
            wl_ind = None
            for row in biz_rows:
                if row['code'] == wl_code:
                    wl_ind = (row['industry'] or '').strip()
                    break

            if not wl_ind or wl_ind not in industry_map:
                continue

            peers = industry_map[wl_ind]
            for peer_code in peers:
                if peer_code == wl_code:
                    continue
                peer_name = code_to_name.get(peer_code, peer_code)

                db.execute("""
                    INSERT OR IGNORE INTO company_relations
                        (code, related_code, related_name, relation_type, relation_subtype,
                         relation_detail, weight, direction, extra_data, source)
                    VALUES (?,?,?,?,?,?,?,?,?,?)
                """, [
                    wl_code, peer_code, peer_name, 'competition', 'competitor',
                    f'同行业({wl_ind})', 1.0, 'both',
                    json.dumps({'industry': wl_ind}, ensure_ascii=False), 'web',
                ])
                count += 1

        db.commit()
        return count
    finally:
        db.close()


# ── 主流程 ──────────────────────────────────────────────────────────────

def process_all_stocks():
    """遍历所有自选股，通过可用数据源采集关系数据并写入数据库。"""
    # Try to get an available fetcher
    fetcher = get_available_fetcher(force_refresh=True)
    if fetcher is None:
        print('[fetch_cr] 所有数据源均不可用，跳过采集')
        print('[fetch_cr] 提示: 当前已有的数据未被清除')
        return {'total': 0, 'stocks': {}, 'errors': [{'code': '*all*', 'error': 'no available data source'}]}

    print(f'[fetch_cr] 使用数据源: {fetcher.source}')

    # Read watchlist
    db = _get_db()
    codes = [r[0] for r in db.execute("SELECT code FROM watchlist ORDER BY sort_order").fetchall()]
    db.close()

    if not codes:
        print('[fetch_cr] 自选股列表为空，跳过采集')
        return {'total': 0, 'stocks': {}, 'errors': []}

    print(f'[fetch_cr] 开始采集 {len(codes)} 只自选股的企业关系数据...')

    summary = {'total_relations': 0, 'total_business': 0, 'stocks': {}, 'errors': []}
    all_related_names = []  # Collect all related party names for enrichment

    for code in codes:
        stock_result = {'code': code, 'relations': 0, 'business': False}
        try:
            # 1. 公司概况 → 主营业务
            business = fetcher.fetch_business(code)
            if business and business.get('name'):
                db = _get_db()
                try:
                    _upsert_business(db, business)
                    db.commit()
                    stock_result['business'] = True
                    summary['total_business'] += 1
                    print(f'  {code} {business["name"]}: 行业={business.get("industry","")}')
                finally:
                    db.close()
            else:
                print(f'  {code}: 未获取到公司概况数据')

            # 2. 前十大股东 → 股权关系
            shareholders = fetcher.fetch_shareholders(code)
            if shareholders:
                db = _get_db()
                try:
                    for sh in shareholders:
                        holder_id = f"holder_{sh['name']}"
                        _upsert_relation(db, {
                            'code': code,
                            'related_code': holder_id,
                            'related_name': sh['name'],
                            'relation_type': 'equity',
                            'relation_subtype': 'shareholder',
                            'relation_detail': f"持股{sh['share_pct']}%",
                            'weight': sh['share_pct'],
                            'direction': 'in',
                            'extra_data': {'share_pct': sh['share_pct'], 'rank': sh['rank']},
                        })
                        all_related_names.append(sh['name'])
                        stock_result['relations'] += 1
                        summary['total_relations'] += 1
                    db.commit()
                    print(f'  {code}: +{len(shareholders)}条股东关系')
                finally:
                    db.close()
            else:
                print(f'  {code}: 未获取到股东数据')

            # 3. 高管信息 → 高管关联
            executives = fetcher.fetch_executives(code)
            if executives:
                db = _get_db()
                try:
                    for exec_person in executives:
                        person_id = f"person_{exec_person['name']}"
                        _upsert_relation(db, {
                            'code': person_id,
                            'related_code': code,
                            'related_name': exec_person['name'],
                            'relation_type': 'executive',
                            'relation_subtype': 'executive',
                            'relation_detail': exec_person['position'],
                            'weight': 1.0,
                            'direction': 'both',
                            'extra_data': {'position': exec_person['position']},
                        })
                        stock_result['relations'] += 1
                        summary['total_relations'] += 1
                    db.commit()
                    print(f'  {code}: +{len(executives)}条高管关联')
                finally:
                    db.close()
            else:
                print(f'  {code}: 未获取到高管数据')

            # 4. 前五大供应商/客户 → 供应链关系（支持方法级回退到其他数据源）
            supply = fetch_with_fallback('fetch_supply_chain', code, default={'suppliers': [], 'customers': []})
            supply_count = 0
            if supply.get('suppliers'):
                db = _get_db()
                try:
                    for s in supply['suppliers']:
                        _upsert_relation(db, {
                            'code': s['name'],
                            'related_code': code,
                            'related_name': s['name'],
                            'relation_type': 'supply',
                            'relation_subtype': 'supplier',
                            'relation_detail': f"供应商 采购占比{s['ratio']}%",
                            'weight': s['ratio'],
                            'direction': 'in',
                            'extra_data': {'ratio': s['ratio']},
                        })
                        all_related_names.append(s['name'])
                        supply_count += 1
                    db.commit()
                finally:
                    db.close()
            if supply.get('customers'):
                db = _get_db()
                try:
                    for c in supply['customers']:
                        _upsert_relation(db, {
                            'code': code,
                            'related_code': c['name'],
                            'related_name': c['name'],
                            'relation_type': 'supply',
                            'relation_subtype': 'customer',
                            'relation_detail': f"客户 销售占比{c['ratio']}%",
                            'weight': c['ratio'],
                            'direction': 'out',
                            'extra_data': {'ratio': c['ratio']},
                        })
                        all_related_names.append(c['name'])
                        supply_count += 1
                    db.commit()
                finally:
                    db.close()
            if supply_count:
                stock_result['relations'] += supply_count
                summary['total_relations'] += supply_count
                print(f'  {code}: +{supply_count}条供应链关系')

        except Exception as e:
            summary['errors'].append({'code': code, 'error': str(e)})
            print(f'  [fetch_cr] {code} 处理异常: {e}')

        summary['stocks'][code] = stock_result

    # 5. 关联方补充：匹配股东/供应商/客户到 A 股代码并补充行业信息
    if all_related_names:
        print(f'  [关联方补充] 尝试匹配 {len(set(all_related_names))} 个关联方名称...')
        matched = _enrich_related_party(fetcher, list(set(all_related_names)), summary)
        if matched:
            print(f'  [关联方补充]: 成功匹配并补充 {matched} 个关联方')

    # 6. 竞争关系：全A股同行业
    try:
        competition_count = _build_competition_relations(DB_PATH)
        summary['total_relations'] += competition_count
        print(f'  [竞争关系]: +{competition_count}条同行业竞争关系')
    except Exception as e:
        print(f'  [fetch_cr] 竞争关系建立失败: {e}')
        summary['errors'].append({'code': '*competition*', 'error': str(e)})

    print(f'[fetch_cr] 完成: 关系{summary["total_relations"]}条, 主营业务{summary["total_business"]}条')
    if summary['errors']:
        print(f'[fetch_cr] 异常: {len(summary["errors"])} 个错误')
    return summary


if __name__ == '__main__':
    process_all_stocks()
