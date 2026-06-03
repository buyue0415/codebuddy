"""从广发证券对账单 xlsx 解析交易记录，写入 SQLite 持仓表。

v2.1 增强：
  - 纯Python标准库解析xlsx（无需pandas依赖）
  - 文件存在性 / 格式检查
  - 列名校验与自动适配
  - 逐行验证 + 隔离坏行不中断
  - 重复数据检测 (date+time+code+qty+price 去重)
  - 详细错误日志记录
  - 解析前后备份保护
"""
import json, sys, os, shutil, io
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Any, Tuple
import zipfile
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
from db_helper import upsert_positions, get_db

STMT_FILE = os.path.join(ROOT, '广发易淘金PC版-普通对账单结果查询.xlsx')
LOG_FILE = os.path.join(ROOT, 'data', 'statement_import.log')

# ── 期望的列名（版本兼容）──
EXPECTED_COLUMNS_V1 = [
    'date','time','seq','account','code','name','type','qty','price',
    'commission','stamp_tax','transfer_fee','regulatory_fee','handling_fee',
    'other_fee','settlement','currency','order_id','accrued_interest'
]
# 中文列名（广发证券原始导出格式）
CHINESE_COLUMN_MAP = {
    '业务日期': 'date', '发生时间': 'time', '流水序号': 'seq',
    '资金账号': 'account', '证券代码': 'code', '证券名称': 'name',
    '业务标志名称': 'type', '成交数量': 'qty', '成交价格': 'price',
    '净佣金': 'commission', '印花税': 'stamp_tax', '过户费': 'transfer_fee',
    '证管费': 'regulatory_fee', '经手费': 'handling_fee',
    '其他费': 'other_fee', '清算金额': 'settlement',
    '货币名称': 'currency', '委托编号': 'order_id', '应计利息': 'accrued_interest',
}
EXPECTED_COLUMNS_MINIMAL = ['date', 'code', 'name', 'type', 'qty', 'price',
                             'commission', 'stamp_tax', 'settlement']

# ── 日志 ──
_log_lines: List[str] = []

def log(msg: str, level: str = "INFO"):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] [{level}] {msg}"
    _log_lines.append(line)
    print(line)

def flush_log():
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write('\n'.join(_log_lines) + '\n')


# ── 文件检查 ──

def check_file(path: str) -> bool:
    if not os.path.exists(path):
        log(f"文件不存在: {path}", "ERROR")
        return False
    size = os.path.getsize(path)
    if size < 100:
        log(f"文件过小 ({size} bytes)，可能为空或损坏: {path}", "ERROR")
        return False
    log(f"文件检查通过: {path} ({size:,} bytes)")
    return True


# ── Excel 解析与校验 (纯Python标准库，无需pandas) ──

def _parse_xlsx_stdlib(path: str) -> Tuple[List[str], List[List[Any]]]:
    """使用zipfile+XML解析xlsx，返回(列名列表, 数据行列表)。"""
    NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
    
    with zipfile.ZipFile(path, 'r') as z:
        # 1. 读取共享字符串表
        sst = []
        if 'xl/sharedStrings.xml' in z.namelist():
            root = ET.fromstring(z.read('xl/sharedStrings.xml'))
            for si in root.findall(f'{NS}si'):
                text = si.findtext(f'{NS}t', '') or ''
                for r in si.findall(f'{NS}r'):
                    t = r.findtext(f'{NS}t', '') or ''
                    text += t
                sst.append(text)

        # 2. 读取第一个工作表
        sheet_xml = z.read('xl/worksheets/sheet1.xml')
        root = ET.fromstring(sheet_xml)

        rows_data = []
        for row_elem in root.findall(f'{NS}sheetData/{NS}row'):
            row_cells = {}
            for c in row_elem.findall(f'{NS}c'):
                ref = c.get('r', '')
                col_letter = ''.join(ch for ch in ref if ch.isalpha())
                col_idx = 0
                for ch in col_letter.upper():
                    col_idx = col_idx * 26 + (ord(ch) - ord('A') + 1)
                col_idx -= 1
                
                cell_type = c.get('t', '')
                v_elem = c.find(f'{NS}v')
                if v_elem is None or v_elem.text is None:
                    row_cells[col_idx] = ''
                elif cell_type == 's':
                    idx = int(v_elem.text)
                    row_cells[col_idx] = sst[idx] if idx < len(sst) else ''
                else:
                    row_cells[col_idx] = v_elem.text
            
            if row_cells:
                max_col = max(row_cells.keys())
                row_list = [row_cells.get(i, '') for i in range(max_col + 1)]
                rows_data.append(row_list)

    if not rows_data:
        return [], []

    # 第一行作为列名
    headers = [str(h).strip() for h in rows_data[0]]
    data_rows = rows_data[1:]
    return headers, data_rows


def parse_excel(path: str):
    """解析 Excel，返回 (success, list_of_dicts, warnings)。"""
    warnings: List[str] = []

    try:
        headers, data_rows = _parse_xlsx_stdlib(path)
    except Exception as e:
        return False, None, [f"Excel 读取失败: {e}"]

    if not headers:
        return False, None, ["Excel 文件为空"]

    first_col = headers[0] if headers else ""
    log(f"检测到 {len(headers)} 列，首列: '{first_col}', 数据行数: {len(data_rows)}")

    # 列名检测和适配（支持中/英文两种格式）
    if len(headers) >= len(EXPECTED_COLUMNS_MINIMAL):
        if first_col == 'date' or first_col in EXPECTED_COLUMNS_V1:
            # 已是英文列名 → 按位置对齐到 EXPECTED_COLUMNS_V1
            log("列名: 英文（按位置对齐）")
        elif first_col in CHINESE_COLUMN_MAP:
            # 中文列名 → 映射转换
            col_map = {}
            unmatched = []
            for idx, h in enumerate(headers):
                if h in CHINESE_COLUMN_MAP:
                    col_map[idx] = CHINESE_COLUMN_MAP[h]
                else:
                    unmatched.append(h)
            if unmatched:
                log(f"无法识别的列名: {unmatched}", "WARNING")
            # 重写 headers
            new_headers = [CHINESE_COLUMN_MAP.get(h, h) for h in headers]
            headers = new_headers
            log(f"列名: 中文→English (已映射)")
        else:
            return False, None, [
                f"无法识别列名。首列='{first_col}'，不支持此格式"
            ]
    else:
        return False, None, [
            f"列数不足: 期望 >= {len(EXPECTED_COLUMNS_MINIMAL)}，实际 {len(headers)}"
        ]

    # 补全缺失列（fill missing columns with empty）
    for col in EXPECTED_COLUMNS_V1:
        if col not in headers:
            # 在末尾追加
            pass  # 下面会处理

    # 将数据行转换为字典列表
    rows: List[Dict] = []
    for row in data_rows:
        d = {}
        for i, h in enumerate(headers):
            if i < len(row):
                d[h] = row[i]
            else:
                d[h] = ''
        # 补全缺失列
        for col in EXPECTED_COLUMNS_V1:
            if col not in d:
                d[col] = ''
        rows.append(d)

    # 检查必要列是否有数据
    for col in ['date', 'code', 'type', 'qty', 'price']:
        empty_count = sum(1 for r in rows if str(r.get(col, '')).strip() in ('', '0', 'nan'))
        if empty_count > len(rows) * 0.5:
            warnings.append(f"列 '{col}' 有 {empty_count}/{len(rows)} 空值，超过50%")

    log(f"成功解析 {len(rows)} 行数据")
    return True, rows, warnings


# ── 逐行验证 ──

VALID_TYPES = {'证券买入', '证券卖出', '股息入账', '申购中签', '新股申购', '配股缴款'}

def validate_row(row: Any, idx: int) -> Tuple[bool, Dict[str, Any], str]:
    """验证单行数据，返回 (valid, trade_dict, error_msg)。"""
    errors = []

    # 日期
    date_str = str(row.get('date', '')).strip()
    if not date_str or date_str == 'nan':
        errors.append("日期为空")
    elif len(date_str) < 8:
        errors.append(f"日期格式异常: {date_str}")

    # 代码
    code = str(row.get('code', '')).strip()
    if not code or code == 'nan':
        errors.append("代码为空")
    elif code == '736435':
        return True, {}, "skip_ipo"  # 跳过 IPO 申购代码

    # 类型
    trade_type = str(row.get('type', '')).strip()
    if trade_type not in VALID_TYPES and trade_type != 'nan':
        errors.append(f"未知交易类型: {trade_type}")

    # 数量
    try:
        qty = float(row.get('qty', 0))
    except (ValueError, TypeError):
        errors.append(f"数量无法解析: {row.get('qty')}")
        qty = 0

    # 价格
    try:
        price = float(row.get('price', 0))
    except (ValueError, TypeError):
        errors.append(f"价格无法解析: {row.get('price')}")
        price = 0

    # 费用字段容错
    def safe_f(val, default=0.0):
        try:
            return float(val)
        except (ValueError, TypeError):
            return default

    if errors:
        return False, {}, f"行 {idx+1}: " + "; ".join(errors)

    comm = safe_f(row.get('commission', 0))
    stamp = safe_f(row.get('stamp_tax', 0))
    tf = safe_f(row.get('transfer_fee', 0))
    rf = safe_f(row.get('regulatory_fee', 0))
    hf = safe_f(row.get('handling_fee', 0))
    sett = safe_f(row.get('settlement', 0))

    trade = {
        'date': date_str[:10],
        'time': str(row.get('time', '')),
        'code': code,
        'name': str(row.get('name', '')).strip().replace('XD', ''),
        'type': trade_type if trade_type != 'nan' else str(row.get('type', '')),
        'qty': qty,
        'price': price,
        'commission': comm,
        'stamp_tax': stamp,
        'transfer_fee': tf,
        'regulatory_fee': rf,
        'handling_fee': hf,
        'settlement': sett if sett != 0 else qty * price + comm + stamp,
    }
    return True, trade, ""


# ── 去重检测 ──

def dedup_trades(trades: List[Dict]) -> Tuple[List[Dict], int]:
    """基于 (date, time, code, qty, price, type) 去重。"""
    seen = set()
    unique = []
    dups = 0
    for t in trades:
        key = (t['date'], t['time'], t['code'], t['qty'], t['price'], t['type'])
        if key in seen:
            dups += 1
            continue
        seen.add(key)
        unique.append(t)
    return unique, dups


# ── 检查数据库中已有数据 ──

def check_existing_data() -> Tuple[int, int, int]:
    """返回 (existing_trades, existing_positions, existing_closed)。"""
    try:
        db = get_db()
        trades_cnt = db.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
        pos_cnt = db.execute("SELECT COUNT(*) FROM positions").fetchone()[0]
        closed_cnt = db.execute("SELECT COUNT(*) FROM closed_positions").fetchone()[0]
        db.close()
    except Exception:
        trades_cnt = pos_cnt = closed_cnt = 0
    return trades_cnt, pos_cnt, closed_cnt


# ── 主流程 ──

def main():
    log("========== 对账单导入开始 ==========")

    # Step 0: 文件检查
    if not check_file(STMT_FILE):
        flush_log()
        print("导入失败: 文件检查未通过")
        sys.exit(1)

    # 备份旧输出
    stmt_path = os.path.join(ROOT, 'data', 'broker_statement.json')
    stmt_backup = os.path.join(ROOT, 'data', 'broker_statement.json.bak')
    if os.path.exists(stmt_path):
        shutil.copy2(stmt_path, stmt_backup)
        log(f"已备份旧 broker_statement.json")

    old_trades, old_pos, old_closed = check_existing_data()
    log(f"数据库现有: {old_trades} 条交易, {old_pos} 持仓, {old_closed} 已清仓")

    # Step 1: 解析 Excel
    ok, rows, warnings = parse_excel(STMT_FILE)
    for w in warnings:
        log(w, "WARNING")
    if not ok or rows is None:
        flush_log()
        print(f"导入失败: 解析Excel失败")
        sys.exit(1)

    # Step 2: 逐行解析 + 验证
    trades: List[Dict] = []
    skipped = 0
    skip_reasons: List[str] = []
    error_count = 0

    for idx, row in enumerate(rows):
        valid, trade, err = validate_row(row, idx)
        if not valid:
            if err == "skip_ipo":
                skipped += 1
                continue
            error_count += 1
            if error_count <= 10:
                log(err, "ERROR")
                skip_reasons.append(err[:80])
            elif error_count == 11:
                log(f"... 还有更多错误（已省略），共 {len(rows) - idx + 10} 行待检查", "WARNING")
            continue
        # 验证成功，但做最终完整性检查
        required_keys = ['date', 'code', 'type', 'qty', 'price']
        missing = [k for k in required_keys if k not in trade]
        if missing:
            error_count += 1
            log(f"行 {idx+1}: 缺少键 {missing}, trade={trade}", "ERROR")
            continue
        trades.append(trade)

    if error_count > 0:
        log(f"共 {error_count} 行验证失败，已跳过", "WARNING")
    if skipped > 0:
        log(f"共 {skipped} 行 IPO 申购代码，已跳过")

    if not trades:
        log("无有效交易记录", "ERROR")
        flush_log()
        print("导入失败: 无有效交易记录")
        sys.exit(1)

    # 去重
    trades, dup_count = dedup_trades(trades)
    if dup_count > 0:
        log(f"检测到 {dup_count} 条重复交易，已去重", "WARNING")

    log(f"有效交易: {len(trades)} 条 (跳过{error_count}错误, {skipped}IPO, {dup_count}重复)")

    # Step 3: 计算持仓
    positions = defaultdict(lambda: {
        'code': '', 'name': '', 'qty': 0, 'total_cost': 0.0,
        'trades': [], 'dividends': [], 'realized': 0.0,
        'total_commission': 0.0, 'total_stamp_tax': 0.0, 'total_other_fees': 0.0,
        'transfer_fee': 0.0, 'regulatory_fee': 0.0, 'handling_fee': 0.0,
    })

    for t in trades:
        code = t['code']
        pos = positions[code]
        pos['code'] = code
        pos['name'] = t['name']
        fee = t['commission'] + t['stamp_tax'] + t['transfer_fee'] + t['regulatory_fee'] + t['handling_fee']
        pos['total_commission'] += t['commission']
        pos['total_stamp_tax'] += t['stamp_tax']
        pos['transfer_fee'] += t['transfer_fee']
        pos['regulatory_fee'] += t['regulatory_fee']
        pos['handling_fee'] += t['handling_fee']
        pos['total_other_fees'] = pos['transfer_fee'] + pos['regulatory_fee'] + pos['handling_fee']

        if t['type'] == '证券买入':
            pos['qty'] += int(abs(t['qty']))
            pos['total_cost'] += abs(t['qty']) * t['price'] + fee
            pos['trades'].append(t)
        elif t['type'] == '证券卖出':
            sell_qty = int(abs(t['qty']))
            if pos['qty'] > 0 and pos['total_cost'] > 0:
                avg_cost = pos['total_cost'] / pos['qty']
                sell_cost = avg_cost * sell_qty
                pos['total_cost'] -= sell_cost
                pos['realized'] += abs(t['qty']) * t['price'] - fee - sell_cost
            pos['qty'] -= sell_qty
            pos['trades'].append(t)
        elif t['type'] == '股息入账':
            pos['dividends'].append({
                'date': t['date'], 'amount': t['settlement'], 'price': t['price'],
            })

    # Step 4: 构建输出结构
    current = {}
    for code, pos in positions.items():
        if pos['qty'] <= 0:
            continue
        current[code] = {
            'code': code, 'name': pos['name'], 'qty': pos['qty'],
            'total_cost': round(pos['total_cost'], 2),
            'avg_cost': round(pos['total_cost'] / pos['qty'], 3) if pos['qty'] > 0 else 0,
            'realized_pnl': round(pos['realized'], 2),
            'dividends': [{'date': d['date'], 'amount': round(d['amount'], 2),
                          'price': round(d['price'], 2)} for d in pos['dividends']],
            'total_commission': round(pos['total_commission'], 2),
            'total_stamp_tax': round(pos['total_stamp_tax'], 2),
            'total_other_fees': round(pos['total_other_fees'], 2),
            'trades': pos['trades'],
        }

    closed = {}
    for code, pos in positions.items():
        if pos['qty'] > 0:
            continue
        closed[code] = {
            'code': code, 'name': pos['name'],
            'realized_pnl': round(pos['realized'], 2),
            'dividends_total': round(sum(d['amount'] for d in pos['dividends']), 2),
            'total_commission': round(pos['total_commission'], 2),
            'total_stamp_tax': round(pos['total_stamp_tax'], 2),
            'total_other_fees': round(pos['total_other_fees'], 2),
            'trades': pos['trades'],
        }

    all_trades_out = []
    for t in trades:
        if t['type'] in ('证券买入', '证券卖出', '股息入账'):
            all_trades_out.append({
                'date': t['date'], 'time': t['time'],
                'code': t['code'], 'name': t['name'],
                'type': t['type'], 'qty': int(t['qty']), 'price': t['price'],
                'commission': round(t['commission'], 2),
                'stamp_tax': round(t['stamp_tax'], 2),
                'settlement': round(t['settlement'], 2),
            })

    # 保存 broker_statement.json
    broker = {
        'account': '51312640', 'broker': '广发证券',
        'current_positions': current, 'closed_positions': closed,
        'all_trades': all_trades_out,
        'import_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'stats': {
            'total_trades': len(trades), 'valid_trades': len(all_trades_out),
            'current_stocks': len(current), 'closed_stocks': len(closed),
            'skipped_errors': error_count, 'duplicates_removed': dup_count,
        }
    }
    with open(stmt_path, 'w', encoding='utf-8') as f:
        json.dump(broker, f, ensure_ascii=False, indent=2)
    log(f"broker_statement.json 已保存")

    # Step 5: 写入 SQLite
    try:
        upsert_positions(current, closed, all_trades_out)
        log(f"SQLite 写入成功: {len(current)} 持仓 + {len(closed)} 已清仓 + {len(all_trades_out)} 交易")
    except Exception as e:
        log(f"SQLite 写入失败: {e}", "ERROR")
        flush_log()
        print(f"SQLite 写入失败: {e}")
        sys.exit(1)

    # 汇总输出
    print("\n=== 当前持仓 ===")
    for code, pos in current.items():
        pnl_str = f"  (已实现{pos['realized_pnl']:+.2f})" if pos['realized_pnl'] != 0 else ""
        print(f"  {pos['name']}({code}): {pos['qty']}股, 均价{pos['avg_cost']:.3f}, 投入{pos['total_cost']:.2f}{pnl_str}")

    print("\n=== 已清仓 ===")
    for code, pos in closed.items():
        print(f"  {pos['name']}({code}): 盈亏{pos['realized_pnl']:+.2f}, 分红{pos['dividends_total']:.2f}")

    total_fees = sum(v['total_commission'] + v['total_stamp_tax'] + v['total_other_fees']
                     for v in current.values())
    total_closed_fees = sum(v['total_commission'] + v['total_stamp_tax'] + v['total_other_fees']
                            for v in closed.values())
    print(f"\n总手续费: {total_fees + total_closed_fees:.2f}")
    print(f"解析统计: {len(all_trades_out)} 笔有效交易, {error_count} 行跳过, {dup_count} 条去重")

    log(f"========== 导入完成 (成功) ==========")
    flush_log()

    if skip_reasons:
        print(f"\n⚠ 以下行解析失败:")
        for reason in skip_reasons[:5]:
            print(f"  - {reason}")
        if len(skip_reasons) > 5:
            print(f"  ... 另有 {len(skip_reasons) - 5} 个错误，详见 {LOG_FILE}")


if __name__ == "__main__":
    main()
