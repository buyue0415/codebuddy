"""westock-data local Node.js plugin fetcher.

This is the PRIMARY data source — it runs locally and is always available,
unlike external HTTP APIs (EastMoney/Sina/Tencent) which may be blocked.
"""

import os
import sys
import subprocess
import re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))

from fetchers.base import BaseFetcher

NODE = r'C:\Users\28312\.workbuddy\binaries\node\versions\22.12.0\node.exe'
WESTOCK = r'C:\Users\28312\.workbuddy\plugins\marketplaces\cb_teams_marketplace\plugins\finance-data\skills\westock-data'
SCRIPT = 'scripts/index.js'


def _market_prefix(code):
    return f'sh{code}' if code.startswith('6') else f'sz{code}'


def _run_westock(args, timeout=30):
    """Run a westock-data command and return stdout text."""
    try:
        result = subprocess.run(
            [NODE, SCRIPT] + args,
            cwd=WESTOCK, capture_output=True, timeout=timeout,
        )
        out = result.stdout.decode('utf-8', errors='replace')
        err = result.stderr.decode('utf-8', errors='replace')
        if result.returncode != 0:
            return ''
        return out
    except Exception as e:
        return ''


def _parse_markdown_table(text):
    """Parse a simple markdown table into list of dicts.

    Handles the format from westock-data:
    | col1 | col2 | col3 |
    | --- | --- | --- |
    | val1 | val2 | val3 |
    """
    lines = text.strip().split('\n')
    if len(lines) < 3:
        return []

    # Find header row
    header_idx = None
    for i, line in enumerate(lines):
        if line.strip().startswith('|') and '---' not in line:
            header_idx = i
            break
    if header_idx is None:
        return []

    # Parse headers from header row
    headers = [h.strip() for h in lines[header_idx].strip('|').split('|')]

    # Skip separator row (|---|)
    data_start = header_idx + 2 if header_idx + 1 < len(lines) and '---' in lines[header_idx + 1] else header_idx + 1

    results = []
    for line in lines[data_start:]:
        stripped = line.strip()
        if not stripped.startswith('|'):
            continue
        cells = [c.strip() for c in stripped.strip('|').split('|')]
        if len(cells) != len(headers):
            continue
        row = {}
        for i, h in enumerate(headers):
            row[h.lower()] = cells[i] if i < len(cells) else ''
        results.append(row)

    return results


class WestockFetcher(BaseFetcher):

    @property
    def source(self) -> str:
        return 'westock'

    def is_available(self) -> bool:
        """Always available since it's a local Node.js plugin."""
        return os.path.exists(WESTOCK)

    def fetch_business(self, code: str) -> dict | None:
        mkt_code = _market_prefix(code)
        text = _run_westock(['profile', mkt_code])
        if not text:
            return None

        rows = _parse_markdown_table(text)
        if not rows:
            return None

        row = rows[0]
        return {
            'code': code,
            'name': row.get('name', ''),
            'industry': row.get('industry', row.get('sector', '')),
            'business': row.get('business', ''),
        }

    def fetch_shareholders(self, code: str) -> list[dict]:
        mkt_code = _market_prefix(code)
        text = _run_westock(['shareholder', mkt_code])
        if not text:
            return []

        results = []

        # Parse the first table (十大股东) — it's the first markdown table
        # The section starts with "**十大股东**" and has a markdown table
        lines = text.split('\n')
        in_table = False
        headers = []
        for i, line in enumerate(lines):
            if '十' in line and '股东' in line:
                # Next non-empty line after section header should be table header
                continue

            stripped = line.strip()

            # Find the table header row
            if stripped.startswith('|') and 'no' in stripped.lower() and 'name' in stripped.lower():
                headers = [h.strip() for h in stripped.strip('|').split('|')]
                in_table = True
                continue

            if in_table:
                if not stripped.startswith('|') or '---' in stripped:
                    continue  # skip separator
                # Check if this is still data or we hit another section
                cells = [c.strip() for c in stripped.strip('|').split('|')]
                if len(cells) != len(headers):
                    continue

                # Check for "十大流通股东" end marker
                # (next section header would stop the loop naturally)

                name = cells[1] if len(cells) > 1 else ''
                pct_str = cells[3] if len(cells) > 3 else '0'

                if not name:
                    continue

                try:
                    pct = float(pct_str) if pct_str else 0
                except ValueError:
                    pct = 0

                results.append({
                    'name': name,
                    'share_pct': round(pct, 2),
                    'rank': len(results) + 1,
                })

                if len(results) >= 10:
                    break

        return results

    def fetch_executives(self, code: str) -> list[dict]:
        """Fetch executives from westock-data profile (chairman field)."""
        mkt_code = _market_prefix(code)
        text = _run_westock(['profile', mkt_code])
        if not text:
            return []

        rows = _parse_markdown_table(text)
        if not rows:
            return []

        row = rows[0]
        chairman = row.get('chairman', '').strip()
        if chairman:
            return [{'name': chairman, 'position': '董事长'}]
        return []

    def fetch_supply_chain(self, code: str) -> dict:
        """westock-data doesn't directly provide supply chain data."""
        return {'suppliers': [], 'customers': []}
