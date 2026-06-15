"""
NeoData (neodata-financial-search) data source fetcher.

Supplementary data source using the neodata-financial-search plugin.
Called via subprocess to query.py, requires valid token (12h cache).
Token must be initialized via connect_cloud_service before use.

Usage:
    from fetchers.neodata import NeoDataFetcher, neodata_query, init_token

    # Init token at server startup
    init_token("<temp_token>")

    # General query (for other project scripts)
    data = neodata_query("601166.SH 最新财报")

    # As fetcher
    fetcher = NeoDataFetcher()
    biz = fetcher.fetch_business('601166')
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))

from fetchers.base import BaseFetcher

NEODATA_DIR = r'C:\Users\28312\.workbuddy\plugins\marketplaces\cb_teams_marketplace\plugins\finance-data\skills\neodata-financial-search'
QUERY_SCRIPT = os.path.join(NEODATA_DIR, 'scripts', 'query.py')
TOKEN_FILE = Path(NEODATA_DIR).parent / '.neodata_token'
PYTHON = sys.executable


# ---------------------------------------------------------------------------
# 通用 API (供项目其他脚本导入使用)
# ---------------------------------------------------------------------------

def neodata_query(query: str, data_type: str = 'api', timeout: int = 30) -> dict | None:
    """通用 neodata 查询。

    Args:
        query: 自然语言查询，如 "601166.SH 最新财报 主营业务"
        data_type: 'api'(结构化数据，默认) / 'doc'(文章) / 'all'(全部)
        timeout: 超时秒数

    Returns:
        解析后的 JSON dict，或 None（失败/无有效 token）
    """
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

        # Token expired / missing
        if 'TOKEN_EXPIRED' in err or 'TOKEN_MISSING' in err:
            return None
        if result.returncode != 0:
            return None

        return json.loads(out)
    except (json.JSONDecodeError, subprocess.TimeoutExpired, Exception):
        return None


def init_token(token: str) -> bool:
    """保存 neodata token（在 server 启动时调用）。

    Args:
        token: 从 connect_cloud_service 获取的 tempToken

    Returns:
        是否保存成功
    """
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
    """检测 token 状态。"""
    if not os.path.exists(QUERY_SCRIPT):
        return 'NOT_INSTALLED'
    if not TOKEN_FILE.exists():
        return 'MISSING'
    return 'VALID'


# ---------------------------------------------------------------------------
# 内部工具
# ---------------------------------------------------------------------------

def _market_code(code: str) -> str:
    """6位代码 → 市场代码，如 '601166' → '601166.SH'"""
    return f'{code}.SH' if code.startswith('6') else f'{code}.SZ'


def _get_recalls(data: dict) -> list[dict]:
    """提取 neodata 响应中的 apiRecall 列表。"""
    if not data:
        return []
    return data.get('data', {}).get('apiData', {}).get('apiRecall', []) or []


def _get_entities(data: dict) -> list[dict]:
    """提取命中的标的列表。"""
    if not data:
        return []
    return data.get('data', {}).get('apiData', {}).get('entity', []) or []


def _get_content_texts(data: dict) -> list[str]:
    """提取所有 apiRecall 的 content 文本。"""
    return [r.get('content', '') for r in _get_recalls(data) if r.get('content')]


# ---------------------------------------------------------------------------
# BaseFetcher 实现
# ---------------------------------------------------------------------------

class NeoDataFetcher(BaseFetcher):

    @property
    def source(self) -> str:
        return 'neodata'

    def is_available(self) -> bool:
        """检查 neodata 脚本是否存在且 token 有效。"""
        if not os.path.exists(QUERY_SCRIPT):
            return False
        if not TOKEN_FILE.exists():
            return False
        # 轻量验证查询
        data = neodata_query('SH601166', data_type='api', timeout=10)
        return data is not None and data.get('suc') is True and data.get('code') == '200'

    def fetch_business(self, code: str) -> dict | None:
        """获取公司概况：名称、行业、主营业务。"""
        mkt = _market_code(code)
        data = neodata_query(f'{mkt} 公司概况 主营业务 所属行业')
        if not data:
            return None

        result = {'code': code, 'name': '', 'industry': '', 'business': ''}

        # 从 entity 列表取名称
        entities = _get_entities(data)
        if entities:
            result['name'] = entities[0].get('code', '')

        # 从 content 文本解析
        texts = _get_content_texts(data)
        full = '\n'.join(texts)

        m = re.search(r'(?:股票名称|证券简称|公司名称)[：:]\s*(\S+)', full)
        if m:
            result['name'] = m.group(1)

        m = re.search(r'(?:所属行业|所属申万行业|行业分类)[：:]\s*(.+?)(?:\n|$)', full)
        if m:
            result['industry'] = m.group(1).strip()

        m = re.search(r'(?:主营业务|经营范围|公司简介)[：:]\s*(.+?)(?:\n{2,}|\Z)', full, re.DOTALL)
        if m:
            result['business'] = m.group(1).strip()[:300]

        return result

    def fetch_shareholders(self, code: str) -> list[dict]:
        """获取前十大股东。"""
        mkt = _market_code(code)
        data = neodata_query(f'{mkt} 十大股东 股东持股信息')
        if not data:
            return []

        texts = _get_content_texts(data)
        results = []
        seen_ranks = set()

        for text in texts:
            for line in text.split('\n'):
                line = line.strip()
                # 表格行: | 1 | 股东名 | 10.5% |
                m = re.match(r'^\|\s*(\d+)\s*\|\s*(.+?)\s*\|\s*([\d.]+)\s*%?\s*\|', line)
                if m:
                    rank, name, pct = int(m.group(1)), m.group(2).strip(), float(m.group(3))
                    if name and rank not in seen_ranks:
                        seen_ranks.add(rank)
                        results.append({'name': name, 'share_pct': round(pct, 2), 'rank': rank})
                    continue

                # 列表行: "1. 股东名  10.50%"
                m = re.match(r'^\s*(\d+)[.、\s]\s*(\S{2,8})\s+([\d.]+)%', line)
                if m:
                    rank, name, pct = int(m.group(1)), m.group(2).strip(), float(m.group(3))
                    if rank not in seen_ranks:
                        seen_ranks.add(rank)
                        results.append({'name': name, 'share_pct': round(pct, 2), 'rank': rank})

        return results[:10]

    def fetch_executives(self, code: str) -> list[dict]:
        """获取高管/董事会成员。"""
        mkt = _market_code(code)
        data = neodata_query(f'{mkt} 高管信息 董事会成员')
        if not data:
            return []

        texts = _get_content_texts(data)
        results = []
        seen = set()

        for text in texts:
            for line in text.split('\n'):
                line = line.strip()
                # 表格行: | No | 姓名 | 职务 |
                m = re.match(r'^\|\s*\d+\s*\|\s*(\S{2,4})\s*\|\s*(.+?)\s*\|', line)
                if m:
                    name, pos = m.group(1).strip(), m.group(2).strip()
                    if name and re.match(r'^[\u4e00-\u9fff·]+$', name) and name not in seen:
                        seen.add(name)
                        results.append({'name': name, 'position': pos})

        return results

    def fetch_supply_chain(self, code: str) -> dict:
        """查询供应商/客户数据（neodata 覆盖 TOP5供应商/客户）。"""
        mkt = _market_code(code)
        data = neodata_query(f'{mkt} 前五大供应商 前五大客户 供应链')
        if not data:
            return {'suppliers': [], 'customers': []}

        texts = _get_content_texts(data)
        full = '\n'.join(texts)

        suppliers = []
        customers = []

        # 尝试从内容中提取供应商和客户
        in_supplier = False
        in_customer = False

        for line in full.split('\n'):
            line = line.strip()
            if not line:
                in_supplier = False
                in_customer = False
                continue

            # 识别段落标题
            if '供应商' in line and ('前五' in line or '前5' in line or '主要' in line or '占比' in line or '采购' in line):
                in_supplier = True
                in_customer = False
                continue
            if '客户' in line and ('前五' in line or '前5' in line or '主要' in line or '占比' in line or '销售' in line):
                in_supplier = False
                in_customer = True
                continue

            # 表格行: | Rank | 名称 | 占比% |
            m = re.match(r'^\|\s*\d+\s*\|\s*(.+?)\s*\|\s*([\d.]+)\s*%?\s*\|', line)
            if m:
                name = m.group(1).strip()
                ratio = float(m.group(2))
                if name and len(name) >= 2:
                    if in_supplier:
                        suppliers.append({'name': name, 'ratio': round(ratio, 2)})
                    elif in_customer:
                        customers.append({'name': name, 'ratio': round(ratio, 2)})

            # 列表行: "1. 名称 XXX.XX%"
            m = re.match(r'^\s*(\d+)[.、]\s*(\S+)\s+([\d.]+)%', line)
            if m:
                name = m.group(2).strip()
                ratio = float(m.group(3))
                if in_supplier:
                    suppliers.append({'name': name, 'ratio': round(ratio, 2)})
                elif in_customer:
                    customers.append({'name': name, 'ratio': round(ratio, 2)})

        return {
            'suppliers': suppliers[:5],
            'customers': customers[:5],
        }
