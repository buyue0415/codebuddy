import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))

from fetchers.base import BaseFetcher
from env_paths import get_neodata

NEODATA_DIR = get_neodata()
QUERY_SCRIPT = os.path.join(NEODATA_DIR, 'scripts', 'query.py')
TOKEN_FILE = Path(NEODATA_DIR).parent / '.neodata_token'
PYTHON = sys.executable


def neodata_query(query: str, data_type: str = 'api', timeout: int = 30) -> dict | None:
    if not os.path.exists(QUERY_SCRIPT):
        return None
    try:
        cmd = [PYTHON, QUERY_SCRIPT, '--query', query]
        if data_type != 'all':
            cmd += ['--data-type', data_type]
        result = subprocess.run(
            cmd, cwd=NEODATA_DIR, capture_output=True, timeout=timeout,
        )
        out = result.stdout.decode('utf-8', errors='replace')
        err = result.stderr.decode('utf-8', errors='replace')
        if 'TOKEN_EXPIRED' in err or 'TOKEN_MISSING' in err:
            return None
        if result.returncode != 0:
            return None
        return json.loads(out)
    except (json.JSONDecodeError, subprocess.TimeoutExpired, Exception):
        return None


def init_token(token: str) -> bool:
    if not os.path.exists(QUERY_SCRIPT):
        return False
    try:
        result = subprocess.run(
            [PYTHON, QUERY_SCRIPT, '--save-token', token],
            cwd=NEODATA_DIR, capture_output=True, timeout=15,
        )
        return result.returncode == 0
    except Exception:
        return False


def check_token() -> str:
    if not os.path.exists(QUERY_SCRIPT):
        return 'NOT_INSTALLED'
    if not TOKEN_FILE.exists():
        return 'MISSING'
    return 'VALID'


class NeoDataFetcher(BaseFetcher):
    @property
    def source(self) -> str:
        return 'neodata'

    def is_available(self) -> bool:
        if not os.path.exists(QUERY_SCRIPT):
            return False
        if not TOKEN_FILE.exists():
            return False
        data = neodata_query('SH601166', data_type='api', timeout=10)
        return data is not None and data.get('suc') is True and data.get('code') == '200'

    def fetch_business(self, code: str) -> dict | None:
        mkt = f'{code}.SH' if code.startswith('6') else f'{code}.SZ'
        data = neodata_query(f'{mkt} \u516c\u53f8\u6982\u51b5 \u4e3b\u8425\u4e1a\u52a1 \u6240\u5c5e\u884c\u4e1a')
        if not data:
            return None
        result = {'code': code, 'name': '', 'industry': '', 'business': ''}
        from fetchers.neodata import _get_entities, _get_content_texts
        texts = _get_content_texts(data)
        full = '\n'.join(texts)
        m = re.search(r'(?:\u80a1\u7968\u540d\u79f0|\u8bc1\u5238\u7b80\u79f0|\u516c\u53f8\u540d\u79f0)[\uff1a:]\s*(\S+)', full)
        if m:
            result['name'] = m.group(1)
        m = re.search(r'(?:\u6240\u5c5e\u884c\u4e1a|\u6240\u5c5e\u7533\u4e07\u884c\u4e1a|\u884c\u4e1a\u5206\u7c7b)[\uff1a:]\s*(.+?)(?:\n|$)', full)
        if m:
            result['industry'] = m.group(1).strip()
        m = re.search(r'(?:\u4e3b\u8425\u4e1a\u52a1|\u7ecf\u8425\u8303\u56f4|\u516c\u53f8\u7b80\u4ecb)[\uff1a:]\s*(.+?)(?:\n{2,}|\Z)', full, re.DOTALL)
        if m:
            result['business'] = m.group(1).strip()[:300]
        return result

    def fetch_shareholders(self, code: str) -> list[dict]:
        return []

    def fetch_executives(self, code: str) -> list[dict]:
        return []

    def fetch_supply_chain(self, code: str) -> dict:
        return {'suppliers': [], 'customers': []}
