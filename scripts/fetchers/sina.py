"""Sina Finance (新浪财经) data source fetcher.

Uses Sina's F10 pages and JSON API endpoints.
"""

import os
import sys
import re
import urllib.request
from html.parser import HTMLParser

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))

from fetchers.base import BaseFetcher


def _market_prefix(code):
    return ('sh' + code) if code.startswith('6') else ('sz' + code)


def _http_get_text(url, timeout=15):
    """HTTP GET returning text, handles gzip."""
    req = urllib.request.Request(
        url,
        headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept-Encoding': 'gzip, deflate',
        }
    )
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
        raw = resp.read()
        import gzip as _gzip
        try:
            text = _gzip.decompress(raw).decode('utf-8', errors='replace')
        except (_gzip.BadGzipFile, OSError):
            text = raw.decode('utf-8', errors='replace')
        return text
    except Exception:
        return None


def _extract_between(text, start, end):
    """Extract content between start and end markers."""
    idx = text.find(start)
    if idx == -1:
        return ''
    idx += len(start)
    end_idx = text.find(end, idx)
    if end_idx == -1:
        return text[idx:].strip()
    return text[idx:end_idx].strip()


class SinaFetcher(BaseFetcher):

    @property
    def source(self) -> str:
        return 'sina'

    def is_available(self) -> bool:
        text = _http_get_text(
            f'https://vip.stock.finance.sina.com.cn/corp/go.php/vCI_CorpInfo/stockid/601166.phtml',
            timeout=10
        )
        return text is not None and '兴业银行' in text

    def fetch_business(self, code: str) -> dict | None:
        url = f'https://vip.stock.finance.sina.com.cn/corp/go.php/vCI_CorpInfo/stockid/{code}.phtml'
        text = _http_get_text(url)
        if not text:
            return None

        result = {'code': code, 'name': '', 'industry': '', 'business': ''}

        # Extract stock name from page title
        title_m = re.search(r'<title>([^<]+?)\(', text)
        if title_m:
            result['name'] = title_m.group(1).strip()

        # Extract industry from the summary table
        # Look for "所属行业" row in the main table
        ind_m = re.search(r'所属行业[^<]*?<td[^>]*?>([^<]+)</td>', text)
        if ind_m:
            result['industry'] = ind_m.group(1).strip()

        # Extract main business from the business description section
        biz_m = re.search(r'经营范围[：:][^<]*?<td[^>]*?>([^<]+)</td>', text)
        if biz_m:
            result['business'] = biz_m.group(1).strip()
        else:
            biz_m2 = re.search(r'主营业务[：:][^<]*?<td[^>]*?>([^<]+)</td>', text)
            if biz_m2:
                result['business'] = biz_m2.group(1).strip()

        if result['name']:
            return result
        return None

    def fetch_shareholders(self, code: str) -> list[dict]:
        url = f'https://vip.stock.finance.sina.com.cn/corp/go.php/vCI_StockHolder/stockid/{code}.phtml'
        text = _http_get_text(url)
        if not text:
            return []

        results = []
        # Find the shareholder table - look for <td> containing shareholder names and ratios
        # Pattern: table rows with 股东名称 and 持股比例
        rows = re.findall(
            r'<tr[^>]*>(?:<td[^>]*>.*?</td>)*?<td[^>]*>.*?<a[^>]*>([^<]+)</a>.*?</td>'
            r'(?:<td[^>]*>.*?</td>)*?<td[^>]*>([\d.]+)%?.*?</td>'
            r'(?:<td[^>]*>.*?</td>)*?<td[^>]*>(\d+).*?</td>',
            text, re.DOTALL
        )
        for name, pct_str, rank_str in rows[:10]:
            try:
                pct = float(pct_str)
            except ValueError:
                pct = 0
            try:
                rank = int(rank_str)
            except ValueError:
                rank = 0
            results.append({'name': name.strip(), 'share_pct': round(pct, 2), 'rank': rank})

        return results

    def fetch_executives(self, code: str) -> list[dict]:
        """Fetch executives from Sina's manager page."""
        url = f'https://vip.stock.finance.sina.com.cn/corp/go.php/vCI_CorpManager/stockid/{code}.phtml'
        text = _http_get_text(url)
        if not text:
            return []

        results = []
        # Pattern: look for rows with name + position in the management table
        rows = re.findall(
            r'<tr[^>]*>.*?<td[^>]*>.*?<a[^>]*>([^<]+)</a>.*?</td>'
            r'(?:<td[^>]*>.*?</td>)*?<td[^>]*>([^<]+)</td>',
            text, re.DOTALL
        )
        for name, pos in rows[:20]:
            name = name.strip()
            pos = pos.strip()
            if name:
                results.append({'name': name, 'position': pos or '高管'})

        return results

    def fetch_supply_chain(self, code: str) -> dict:
        """Fetch supply chain from Sina's business analysis page."""
        url = f'https://vip.stock.finance.sina.com.cn/corp/go.php/vCI_Operate/stockid/{code}.phtml'
        text = _http_get_text(url)
        if not text:
            return {'suppliers': [], 'customers': []}

        suppliers = []
        customers = []

        # Try to find supplier/customer tables
        # Pattern: look for sections containing top suppliers/customers
        supp_section = re.search(r'前五大(?:供应商|供货商)[^<]*(.*?)(?=前五大客户|</table>)', text, re.DOTALL)
        if supp_section:
            supp_rows = re.findall(
                r'<td[^>]*>([^<]+)</td>.*?<td[^>]*>([\d.]+)%?.*?</td>',
                supp_section.group(1), re.DOTALL
            )
            for name, pct_str in supp_rows[:5]:
                try:
                    pct = float(pct_str)
                except ValueError:
                    pct = 0
                suppliers.append({'name': name.strip(), 'ratio': round(pct, 2)})

        cust_section = re.search(r'前五大客户[^<]*(.*?)(?=</table>|消失)', text, re.DOTALL)
        if cust_section:
            cust_rows = re.findall(
                r'<td[^>]*>([^<]+)</td>.*?<td[^>]*>([\d.]+)%?.*?</td>',
                cust_section.group(1), re.DOTALL
            )
            for name, pct_str in cust_rows[:5]:
                try:
                    pct = float(pct_str)
                except ValueError:
                    pct = 0
                customers.append({'name': name.strip(), 'ratio': round(pct, 2)})

        return {'suppliers': suppliers, 'customers': customers}
