"""Tencent Finance (腾讯财经) data source fetcher.

Uses Tencent's qt.gtimg.cn quote API for basic company info.
The API returns: v_sh601166="1~name~601166~price~..."
Field [86] = numeric industry code.
"""

import os
import sys
import re
import urllib.request
import gzip as _gzip

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))

from fetchers.base import BaseFetcher

def _http_get_text(url, timeout=15):
    """HTTP GET, auto-detect gzip, return GBK-decoded text."""
    req = urllib.request.Request(
        url,
        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'},
    )
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
        raw = resp.read()
        # Try gzip decompress, fallback to raw
        try:
            raw = _gzip.decompress(raw)
        except Exception:
            pass
        return raw.decode('gbk', errors='replace')
    except Exception:
        return None


def _parse_qt_fields(text):
    """Parse the 88 fields from gtimg response.
    
    Known fields (0-based):
      [0]  market (1=SH, 0=SZ)
      [1]  name
      [2]  code
      [3]  current price
      [86] industry code (numeric, e.g. 9144=银行)
    """
    if not text:
        return {}
    m = re.search(r'"([^"]*)"', text)
    if not m:
        return {}
    parts = m.group(1).split('~')
    return {
        'name': parts[1].strip() if len(parts) > 1 else '',
        'code': parts[2].strip() if len(parts) > 2 else '',
        'industry_code': parts[86].strip() if len(parts) > 86 else '',
    }


# Common Tencent industry code → name mapping
_INDUSTRY_MAP = {
    '9144': '银行', '9145': '证券', '9146': '保险', '9147': '多元金融',
    '9150': '房地产', '9151': '建筑装饰', '9152': '建筑材料',
    '9160': '汽车', '9161': '汽车零部件', '9162': '交通运输', '9163': '物流',
    '9170': '计算机', '9171': '电子', '9172': '通信', '9173': '传媒',
    '9180': '医药生物', '9181': '医疗器械', '9182': '中药',
    '9190': '食品饮料', '9191': '白酒', '9192': '乳制品',
    '9200': '电力设备', '9201': '电力', '9202': '环保',
    '9210': '机械设备', '9211': '专用设备', '9212': '通用设备',
    '9220': '国防军工', '9221': '航空航天',
    '9230': '农林牧渔', '9231': '种植业', '9232': '养殖业',
    '9240': '商贸零售', '9241': '百货', '9242': '连锁',
    '9250': '社会服务', '9251': '旅游', '9252': '酒店餐饮',
    '9260': '纺织服装', '9261': '服装家纺',
    '9270': '轻工制造', '9271': '造纸', '9272': '包装印刷',
    '9280': '化工', '9281': '化学制品', '9282': '化学原料',
    '9290': '有色金属', '9291': '钢铁', '9292': '煤炭',
    '9300': '石油石化', '9301': '采掘',
    '9310': '公用事业', '9311': '燃气', '9312': '水务',
    '9320': '综合',
}


def _qt_api(code):
    """Return the correct Tencent qt API URL for a stock code."""
    prefix = 'sh' if code.startswith('6') else 'sz'
    return f'https://qt.gtimg.cn/q={prefix}{code}'


class TencentFetcher(BaseFetcher):

    @property
    def source(self) -> str:
        return 'tencent'

    def is_available(self) -> bool:
        text = _http_get_text(_qt_api('601166'), timeout=10)
        fields = _parse_qt_fields(text)
        return bool(fields.get('name'))

    def fetch_business(self, code: str) -> dict | None:
        text = _http_get_text(_qt_api(code))
        fields = _parse_qt_fields(text)
        if not fields.get('name'):
            return None

        # Only use industry code if it maps to a known Chinese name
        ind_code = fields.get('industry_code', '')
        industry = _INDUSTRY_MAP.get(ind_code, '') if ind_code else ''

        return {
            'code': code,
            'name': fields.get('name', ''),
            'industry': industry,
            'business': '',
        }

    def fetch_shareholders(self, code: str) -> list[dict]:
        return []

    def fetch_executives(self, code: str) -> list[dict]:
        return []

    def fetch_supply_chain(self, code: str) -> dict:
        return {'suppliers': [], 'customers': []}
