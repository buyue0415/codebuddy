"""East Money (东方财富) data source fetcher.

Extracted from the original fetch_company_relations.py.
API base: https://emweb.securities.eastmoney.com/PC_HSF10
"""

import json
import gzip
import urllib.request
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))

from fetchers.base import BaseFetcher

EM_API = 'https://emweb.securities.eastmoney.com/PC_HSF10'


def _market_prefix(code):
    return ('SH' + code) if code.startswith('6') else ('SZ' + code)


def _http_get(url, timeout=15):
    req = urllib.request.Request(
        url,
        headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept-Encoding': 'gzip, deflate',
            'Referer': 'https://emweb.securities.eastmoney.com/',
        }
    )
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
        raw = resp.read()
        try:
            text = gzip.decompress(raw).decode('utf-8')
        except (gzip.BadGzipFile, OSError):
            text = raw.decode('utf-8', errors='replace')
        return json.loads(text)
    except Exception as e:
        return None


class EastMoneyFetcher(BaseFetcher):

    @property
    def source(self) -> str:
        return 'eastmoney'

    def is_available(self) -> bool:
        """Test by fetching a lightweight company page."""
        url = f'{EM_API}/Company/PageAjax?code=SH601166'
        data = _http_get(url, timeout=10)
        return data is not None

    def fetch_business(self, code: str) -> dict | None:
        url = f'{EM_API}/Company/PageAjax?code={_market_prefix(code)}'
        data = _http_get(url)
        if not data:
            return None

        result = {'code': code, 'name': '', 'industry': '', 'business': ''}
        company = data.get('CompanyInfoDetail', {}) or data.get('jyzq', {}) or {}
        if isinstance(company, dict):
            result['name'] = company.get('SECURITY_NAME_ABBR', '') or company.get('ZQJC', '') or ''
            result['industry'] = company.get('INDUSTRY', '') or company.get('SSHY', '') or ''
            result['business'] = company.get('MAIN_BUSINESS', company.get('ZY', ''))

        if not result['business']:
            main_op = data.get('MainOperationProductList', []) or data.get('zygcfx', [])
            if main_op and isinstance(main_op, list):
                products = [item.get('PRODUCT', item.get('CP', '')) for item in main_op[:5]]
                result['business'] = '、'.join(filter(None, products))

        return result

    def fetch_shareholders(self, code: str) -> list[dict]:
        url = f'{EM_API}/ShareholderResearch/PageAjax?code={_market_prefix(code)}'
        data = _http_get(url)
        if not data:
            return []

        holders = data.get('sdltgd', []) or data.get('SDLTGD', [])
        if not holders or not isinstance(holders, list):
            return []

        results = []
        for item in holders[:10]:
            name = item.get('HOLDER_NAME', item.get('GDMC', '')).strip()
            pct = item.get('HOLD_NUM_RATIO', item.get('ZGBL', 0))
            rank = item.get('HOLDER_RANK', item.get('PM', 0))
            if not name:
                continue
            try:
                pct = float(pct) if pct else 0
            except (ValueError, TypeError):
                pct = 0
            try:
                rank = int(rank) if rank else 0
            except (ValueError, TypeError):
                rank = 0
            results.append({'name': name, 'share_pct': round(pct, 2), 'rank': rank})
        return results

    def fetch_executives(self, code: str) -> list[dict]:
        url = f'{EM_API}/Manager/PageAjax?code={_market_prefix(code)}'
        data = _http_get(url)
        if not data:
            return []

        managers = data.get('manager', []) or data.get('Manager', []) or data.get('dsjb', [])
        if not managers or not isinstance(managers, list):
            return []

        results = []
        for item in managers:
            name = item.get('NAME', item.get('XM', '')).strip()
            pos = item.get('POSITION', item.get('ZW', '')).strip()
            if not name:
                continue
            results.append({'name': name, 'position': pos or '高管'})
        return results

    def fetch_supply_chain(self, code: str) -> dict:
        url = f'{EM_API}/Business/PageAjax?code={_market_prefix(code)}'
        data = _http_get(url)
        if not data:
            return {'suppliers': [], 'customers': []}

        suppliers = []
        customers = []

        def _extract_list(key, name_key, pct_key, max_items=5):
            items = []
            lst = data.get(key, [])
            if isinstance(lst, list):
                for item in lst[:max_items]:
                    n = item.get(name_key, '').strip()
                    p = item.get(pct_key, 0)
                    if not n:
                        continue
                    try:
                        p = float(p) if p else 0
                    except (ValueError, TypeError):
                        p = 0
                    items.append({'name': n, 'ratio': round(p, 2)})
            elif isinstance(lst, dict):
                for item in lst.get('list', [])[:max_items]:
                    n = item.get(name_key, '').strip()
                    p = item.get(pct_key, 0)
                    if not n:
                        continue
                    try:
                        p = float(p) if p else 0
                    except (ValueError, TypeError):
                        p = 0
                    items.append({'name': n, 'ratio': round(p, 2)})
            return items

        suppliers = _extract_list('gys', 'SUPPLIER_NAME', 'PROCUREMENT_RATIO') or \
                    _extract_list('supplier', 'SUPPLIER_NAME', 'PROCUREMENT_RATIO')
        customers = _extract_list('kh', 'CUSTOMER_NAME', 'SALES_RATIO') or \
                    _extract_list('customer', 'CUSTOMER_NAME', 'SALES_RATIO')

        return {'suppliers': suppliers, 'customers': customers}
