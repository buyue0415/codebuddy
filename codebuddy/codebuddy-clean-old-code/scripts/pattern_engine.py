"""K线形态检测引擎 — 从DB加载规则，扫描日K线数据匹配，返回检测结果。

使用方式：
    from pattern_engine import scan_patterns
    result = scan_patterns(kline_data, code="601166")

kline_data 格式 (newest-first):
    [[date, open, close, high, low], ...]
    date: str 'YYYY-MM-DD'
    open/close/high/low: float
"""
import json
import sys
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))


def _load_rules(enabled_only=True):
    """从DB加载规则列表，返回解析后的 dict 列表。"""
    import db_helper
    try:
        rows = db_helper.get_pattern_rules(enabled_only=enabled_only)
        rules = []
        for r in rows:
            try:
                r['conditions_obj'] = json.loads(r['conditions']) if isinstance(r['conditions'], str) else r['conditions']
            except (json.JSONDecodeError, TypeError):
                r['conditions_obj'] = {}
            rules.append(r)
        return rules
    except Exception as e:
        print(f"[PatternEngine] 加载规则失败: {e}", file=sys.stderr)
        return []


def _get_field(candle, field):
    """从K线数据元组中提取字段值。
    candle: (date, open, close, high, low)
    """
    o, c, h, l = candle[1], candle[2], candle[3], candle[4]
    body = abs(c - o)
    tr = h - l
    body_ratio = body / tr if tr > 0 else 0
    upper_shadow = h - max(o, c)
    lower_shadow = min(o, c) - l
    midpoint = (o + c) / 2

    field_map = {
        'open': o, 'close': c, 'high': h, 'low': l,
        'body': body, 'body_ratio': body_ratio,
        'upper_shadow': upper_shadow, 'lower_shadow': lower_shadow,
        'midpoint': midpoint,
    }
    return field_map.get(field)


def _eval_condition(candle, condition, prev_candles_map):
    """评估单条条件。返回 True/False。
    condition: {"field": "...", "op": "...", "ref": ...,
                "type": "self"|"value"|"prev"|"field_factor"}
    """
    field = condition.get('field', '')
    op = condition.get('op', '==')
    ctype = condition.get('type', 'self')

    # 先获取当前字段值
    val = _get_field(candle, field)
    if val is None:
        return False

    # 计算参考值
    if ctype == 'self':
        ref_val = _get_field(candle, condition.get('ref', ''))
    elif ctype == 'value':
        ref_val = condition.get('ref', 0)
    elif ctype == 'prev':
        ref_key = condition.get('ref', '')
        ref_val = prev_candles_map.get(ref_key)
    elif ctype == 'field_factor':
        base = _get_field(candle, condition.get('ref_field', 'body'))
        factor = condition.get('ref_factor', 1)
        ref_val = base * factor if base is not None else None
    else:
        return False

    if ref_val is None:
        return False

    # 特殊字段处理
    if field == 'gap_up':
        return ref_val == 1  # 由引擎逻辑判断
    if field == 'gap_down':
        return ref_val == 1
    if field == 'gap_pct':
        return True  # gap_pct由引擎计算，这里做占位
    if field == 'close_ascend':
        return True  # 由引擎判断
    if field == 'close_descend':
        return True
    if field == 'close_diff_1':
        # 当前收与前日收的差值比
        prev_close = prev_candles_map.get('close_1')
        if prev_close and prev_close > 0:
            return abs(val - prev_close) / prev_close <= condition.get('ref', 0.01)
        return False
    if field in ('tower_bottom', 'tower_top', 'double_bottom', 'double_top'):
        return True  # 由引擎的复合形态函数检测

    # 比较操作
    try:
        if op == '>':    return val > ref_val
        if op == '>=':   return val >= ref_val
        if op == '<':    return val < ref_val
        if op == '<=':   return val <= ref_val
        if op == '==':   return abs(val - ref_val) < 1e-9
    except (TypeError, ValueError):
        return False
    return False


def _build_prev_map(kdata, idx, span_days):
    """构建前N天参考值映射，供条件评估使用。"""
    pmap = {}
    for offset in range(1, span_days + 1):
        if idx - offset >= 0:
            c = kdata[idx - offset]
            o, c_, h, l = c[1], c[2], c[3], c[4]
            body = abs(c_ - o)
            tr = h - l
            body_ratio = body / tr if tr > 0 else 0
            midpoint = (o + c_) / 2
            pmap[f'open_{offset}'] = o
            pmap[f'close_{offset}'] = c_
            pmap[f'high_{offset}'] = h
            pmap[f'low_{offset}'] = l
            pmap[f'body_{offset}'] = body
            pmap[f'body_ratio_{offset}'] = body_ratio
            pmap[f'midpoint_{offset}'] = midpoint
    return pmap


def _check_close_ascend(kdata, idx, count):
    """检查连续 count 根K线收盘价是否逐日上升。"""
    for i in range(1, count):
        if idx - i < 0 or idx - i + 1 < 0:
            return False
        if kdata[idx - i + 1][2] <= kdata[idx - i][2]:
            return False
    return True


def _check_close_descend(kdata, idx, count):
    """检查连续 count 根K线收盘价是否逐日下降。"""
    for i in range(1, count):
        if idx - i < 0 or idx - i + 1 < 0:
            return False
        if kdata[idx - i + 1][2] >= kdata[idx - i][2]:
            return False
    return True


def _check_rule(kdata, idx, rule):
    """检查 idx 位置是否匹配 rule 规则。"""
    conds = rule.get('conditions_obj', {})
    candles = conds.get('candles', [])
    span_days = rule.get('span_days', 1)

    # 确保有足够的历史数据
    if idx < span_days - 1:
        return False

    # 为复合形态调用专用检测函数
    first_candle_rules = candles[0]['rules'] if candles else []
    first_field = first_candle_rules[0].get('field', '') if first_candle_rules else ''

    if first_field == 'tower_bottom':
        return _detect_tower_bottom(kdata, idx)
    if first_field == 'tower_top':
        return _detect_tower_top(kdata, idx)
    if first_field == 'double_bottom':
        return _detect_double_bottom(kdata, idx)
    if first_field == 'double_top':
        return _detect_double_top(kdata, idx)
    if first_field == 'gap_up':
        return _detect_gap_up(kdata, idx, conds)
    if first_field == 'gap_down':
        return _detect_gap_down(kdata, idx, conds)

    for candle_def in candles:
        cidx = candle_def.get('idx', 0)
        target_idx = idx - cidx
        if target_idx < 0:
            return False
        candle = kdata[target_idx]
        pmap = _build_prev_map(kdata, target_idx, span_days)
        rules = candle_def.get('rules', [])

        # 特殊处理逐日涨跌检查
        has_ascend = any(r.get('field') == 'close_ascend' for r in rules)
        has_descend = any(r.get('field') == 'close_descend' for r in rules)
        has_close_diff = any(r.get('field') == 'close_diff_1' for r in rules)

        if has_ascend and not _check_close_ascend(kdata, idx, 3):
            return False
        if has_descend and not _check_close_descend(kdata, idx, 3):
            return False
        if has_close_diff:
            prev_close = kdata[idx - 1][2] if idx > 0 else None
            curr_close = kdata[idx][2]
            if prev_close and prev_close > 0:
                diff = abs(curr_close - prev_close) / prev_close
                cond = next(r.get('ref', 0.01) for r in rules if r.get('field') == 'close_diff_1')
                if diff > cond:
                    return False

        # 标准条件评估
        for condition in rules:
            f = condition.get('field', '')
            if f in ('close_ascend', 'close_descend', 'close_diff_1', 'gap_up', 'gap_down', 'gap_pct',
                     'tower_bottom', 'tower_top', 'double_bottom', 'double_top'):
                continue
            if not _eval_condition(candle, condition, pmap):
                return False

    return True


def _detect_gap_up(kdata, idx, conds):
    """检测向上跳空缺口。"""
    if idx < 1:
        return False
    curr = kdata[idx]
    prev = kdata[idx - 1]
    gap = curr[4] - prev[3]  # curr.low - prev.high
    if gap <= 0 or prev[3] <= 0:
        return False
    gap_pct = gap / prev[3]
    # 检查条件中的最小跳空幅度
    candles = conds.get('candles', [])
    if candles:
        for r in candles[0].get('rules', []):
            if r.get('field') == 'gap_pct' and r.get('type') == 'value':
                if gap_pct < r['ref']:
                    return False
    return True


def _detect_gap_down(kdata, idx, conds):
    """检测向下跳空缺口。"""
    if idx < 1:
        return False
    curr = kdata[idx]
    prev = kdata[idx - 1]
    gap = prev[4] - curr[3]  # prev.low - curr.high
    if gap <= 0 or prev[4] <= 0:
        return False
    gap_pct = gap / prev[4]
    candles = conds.get('candles', [])
    if candles:
        for r in candles[0].get('rules', []):
            if r.get('field') == 'gap_pct' and r.get('type') == 'value':
                if gap_pct < r['ref']:
                    return False
    return True


def _detect_tower_bottom(kdata, idx):
    """塔形底：左侧跌≥3天→中间小实体横盘≥3天→右侧涨≥3天。"""
    n = len(kdata)
    min_leg = 3
    min_consolidation = 3
    total_min = min_leg * 2 + min_consolidation
    if idx < total_min or n < total_min:
        return False

    # 从 idx 向左扫描
    # 右侧上涨段
    right_start = idx - min_leg + 1
    for i in range(right_start, idx + 1):
        if kdata[i][2] <= kdata[i - 1][2]:
            right_start = i + 1
    if idx - right_start + 1 < min_leg:
        return False

    # 横盘段
    flat_end = right_start - 1
    flat_start = flat_end
    for i in range(flat_end, max(0, flat_end - 10), -1):
        body_r = abs(kdata[i][2] - kdata[i][1]) / (kdata[i][3] - kdata[i][4]) if (kdata[i][3] - kdata[i][4]) > 0 else 0
        if body_r > 0.5:
            flat_start = i + 1
            break
        flat_start = i
    if flat_end - flat_start + 1 < min_consolidation:
        return False

    # 左侧下跌段
    left_end = flat_start - 1
    left_start = left_end
    for i in range(left_end, max(0, left_end - 10), -1):
        if kdata[i][2] >= kdata[i - 1][2]:
            left_start = i + 1
            break
        left_start = i
    if left_end - left_start + 1 < min_leg:
        return False

    return True


def _detect_tower_top(kdata, idx):
    """塔形顶：左侧涨≥3天→中间小实体横盘≥3天→右侧跌≥3天。"""
    n = len(kdata)
    min_leg = 3
    min_consolidation = 3
    total_min = min_leg * 2 + min_consolidation
    if idx < total_min or n < total_min:
        return False

    right_start = idx - min_leg + 1
    for i in range(right_start, idx + 1):
        if kdata[i][2] >= kdata[i - 1][2]:
            right_start = i + 1
    if idx - right_start + 1 < min_leg:
        return False

    flat_end = right_start - 1
    flat_start = flat_end
    for i in range(flat_end, max(0, flat_end - 10), -1):
        body_r = abs(kdata[i][2] - kdata[i][1]) / (kdata[i][3] - kdata[i][4]) if (kdata[i][3] - kdata[i][4]) > 0 else 0
        if body_r > 0.5:
            flat_start = i + 1
            break
        flat_start = i
    if flat_end - flat_start + 1 < min_consolidation:
        return False

    left_end = flat_start - 1
    left_start = left_end
    for i in range(left_end, max(0, left_end - 10), -1):
        if kdata[i][2] <= kdata[i - 1][2]:
            left_start = i + 1
            break
        left_start = i
    if left_end - left_start + 1 < min_leg:
        return False

    return True


def _detect_double_bottom(kdata, idx):
    """W底：两个相近低点→突破颈线。"""
    n = len(kdata)
    if idx < 4 or n < 5:
        return False
    # 简化检测：最近5根K线内有两个相近低点
    window = kdata[max(0, idx - 5):idx + 1]
    if len(window) < 5:
        return False
    low1 = min(w[4] for w in window[:3])
    low2 = min(w[4] for w in window[-3:])
    diff = abs(low1 - low2) / low1 if low1 > 0 else 999
    if diff > 0.02:  # 差≤2%
        return False
    # 当前阳线收盘突破
    return kdata[idx][2] > kdata[idx][1] and kdata[idx][2] > max(w[2] for w in window[-3:])


def _detect_double_top(kdata, idx):
    """M顶：两个相近高点→跌破颈线。"""
    n = len(kdata)
    if idx < 4 or n < 5:
        return False
    window = kdata[max(0, idx - 5):idx + 1]
    if len(window) < 5:
        return False
    high1 = max(w[3] for w in window[:3])
    high2 = max(w[3] for w in window[-3:])
    diff = abs(high1 - high2) / high1 if high1 > 0 else 999
    if diff > 0.02:
        return False
    # 当前阴线跌破
    return kdata[idx][2] < kdata[idx][1] and kdata[idx][2] < min(w[2] for w in window[-3:])


def scan_patterns(kdata, code="", rules=None):
    """扫描K线数据，检测所有已启用形态规则。

    Args:
        kdata: newest-first K线列表 [(date, open, close, high, low), ...]
        code: 股票代码，仅用于结果标记
        rules: 规则列表，None则自动从DB加载已启用规则

    Returns:
        dict: {
            'patterns': [
                {'rule_id': 'C3-05', 'name': '三绿一红', 'direction': 'bullish',
                 'strength': 3, 'idx': trigger_index, 'date': '2026-01-15',
                 'price': 18.56, 'rule_name': '三绿一红'},
            ],
            'summary': {
                'bullish': {'count': int, 'max_strength': int},
                'bearish': {'count': int, 'max_strength': int},
                'neutral': {'count': int},
                'total': int,
            }
        }
    """
    if not kdata or len(kdata) < 2:
        return {'patterns': [], 'summary': {
            'bullish': {'count': 0, 'max_strength': 0},
            'bearish': {'count': 0, 'max_strength': 0},
            'neutral': {'count': 0}, 'total': 0
        }}

    if rules is None:
        rules = _load_rules(enabled_only=True)

    # 确保kdata是oldest-first格式便于索引
    if kdata[0][0] > kdata[-1][0]:
        kdata = list(reversed(kdata))

    total = len(kdata)
    patterns = []

    for rule in rules:
        rule_id = rule.get('rule_id', '')
        name = rule.get('name', '')
        direction = rule.get('direction', 'neutral')
        strength = rule.get('strength', 3)
        span = rule.get('span_days', 1)

        # 从触发日（最新）开始扫描
        for idx in range(total - 1, span - 2, -1):
            if _check_rule(kdata, idx, rule):
                candle = kdata[idx]
                date = candle[0]
                price = candle[2]  # close price
                patterns.append({
                    'rule_id': rule_id,
                    'name': name,
                    'direction': direction,
                    'strength': strength,
                    'idx': idx,
                    'date': date,
                    'price': price,
                    'rule_name': name,
                })

    # 按idx降序排序（最新在前）
    patterns.sort(key=lambda p: p['idx'], reverse=True)

    # 汇总
    bullish = [p for p in patterns if p['direction'] == 'bullish']
    bearish = [p for p in patterns if p['direction'] == 'bearish']
    neutral = [p for p in patterns if p['direction'] == 'neutral']

    summary = {
        'bullish': {'count': len(bullish), 'max_strength': max((p['strength'] for p in bullish), default=0)},
        'bearish': {'count': len(bearish), 'max_strength': max((p['strength'] for p in bearish), default=0)},
        'neutral': {'count': len(neutral)},
        'total': len(patterns),
    }

    return {'patterns': patterns, 'summary': summary}


def load_rules_from_db():
    """从 pattern_rules 表加载所有已启用规则。"""
    return _load_rules(enabled_only=True)
