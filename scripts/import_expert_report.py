"""导入专家分析报告 JSON 到 stock.db expert_reports 表。

兼容性处理委托给 report_compatibility 模块，支持：
  - v1 (旧版 stocks 格式)
  - v2 (圆桌讨论格式)
  - v3_flat (平面扁平结构)
  - v3_array (数组格式)
  - v3_wrapped (外层包裹格式)
  - 驼峰/中文混合字段名
  - 任意 dict/list 的模糊匹配

所有格式均归一化为统一内部模型后再存储。
"""
import json, os, sys, re
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from db_helper import get_db
from report_compatibility import (
    transform_report,
    normalize_to_v1,
    validate_report_structure,
    detect_format as detect_fmt,
    describe_format,
    UnifiedExpertReport,
)

# ============================================================
# v1 验证器 (保留向下兼容，供外部代码引用)
# ============================================================

VALID_DECISIONS = {"BUY", "HOLD", "SELL"}
VALID_CONFIDENCES = {"高", "中", "低"}
VALID_RISKS = {"高", "中", "低"}
REQUIRED_KEYS = ["decision", "confidence", "risk_level", "position_pct",
                 "entry_price", "target_price", "stop_loss", "scores", "phase1", "phase2", "phase4"]


def validate_v1_report(data):
    """Validate v1 report structure, return (is_valid, error_message, warnings)."""
    warnings = []
    if not isinstance(data, dict):
        return False, "根必须为 JSON 对象", []
    if "stocks" not in data or not isinstance(data["stocks"], dict):
        return False, "缺少 stocks 字段或格式错误", []
    stocks = data["stocks"]
    if not stocks:
        return False, "stocks 为空", []
    for code, sd in list(stocks.items()):
        if not isinstance(sd, dict):
            return False, f"股票 {code} 数据格式错误", warnings
        for key in REQUIRED_KEYS:
            if key not in sd:
                return False, f"股票 {code} 缺少必填字段: {key}", warnings
        if sd.get("decision") not in VALID_DECISIONS:
            return False, f"股票 {code} decision 必须为 BUY/HOLD/SELL, 当前: {sd.get('decision')}", warnings
        if sd.get("confidence") not in VALID_CONFIDENCES:
            warnings.append(f"股票 {code} confidence '{sd.get('confidence')}' 不在 高/中/低，已修正为'中'")
            sd["confidence"] = "中"
        if sd.get("risk_level") not in VALID_RISKS:
            warnings.append(f"股票 {code} risk_level '{sd.get('risk_level')}' 不在 高/中/低，已修正为'中'")
            sd["risk_level"] = "中"
        for sk in ["technical", "fundamental", "news", "sentiment", "risk"]:
            v = sd.get("scores", {}).get(sk, 0)
            if not (0 <= v <= 10):
                warnings.append(f"股票 {code} scores.{sk}={v} 超出 0-10 范围")
        for arg_type in ["bull_args", "bear_args"]:
            args = sd.get("phase2", {}).get(arg_type, [])
            if not isinstance(args, list):
                return False, f"股票 {code} phase2.{arg_type} 必须是数组", warnings
            for i, a in enumerate(args):
                if not isinstance(a, dict) or "point" not in a or "weight" not in a:
                    warnings.append(f"股票 {code} phase2.{arg_type}[{i}] 缺少 point/weight")
        for pk in ["aggressive_score", "conservative_score", "neutral_score"]:
            v = sd.get("phase4", {}).get(pk, 0)
            if not (0 <= v <= 10):
                warnings.append(f"股票 {code} phase4.{pk}={v} 超出 0-10 范围")
    return True, "", warnings


# ============================================================
# 旧版函数兼容性层 (外部代码可能直接引用这些函数)
# ============================================================

def detect_format(data):
    """旧版格式检测签名——返回 'v1'/'v2'/None。"""
    v, _ = detect_fmt(data)
    return v if v in ("v1", "v2") else None


def normalize_v2_to_unified(data):
    """v2 → v1 兼容格式（保留旧接口签名）。"""
    report = transform_report(data)
    return report.to_v1_like()


def _auto_add_to_watchlist(report_dict: dict) -> list:
    """导入报告后，将不在自选股中的股票自动添加到自选股。

    Returns 新添加的股票 code 列表。
    """
    if not isinstance(report_dict, dict) or "stocks" not in report_dict:
        return []
    stocks = report_dict["stocks"]
    added = []
    try:
        db = get_db()
        # 当前自选股
        wl = {r["code"] for r in db.execute("SELECT code FROM watchlist").fetchall()}
        for code, stock_data in stocks.items():
            if code in wl:
                continue
            if not isinstance(stock_data, dict):
                continue
            name = stock_data.get("name", "")
            market = stock_data.get("market", "A股")
            # 若名称仍为空，从 stocks 表查找
            if not name:
                row = db.execute(
                    "SELECT name, market FROM stocks WHERE code=?", [code]
                ).fetchone()
                if row:
                    name = row["name"]
                    market = market or row["market"]
            if not name:
                name = code  # fallback
            try:
                db.execute(
                    "INSERT OR REPLACE INTO watchlist(code, name, market, sort_order) "
                    "VALUES(?, ?, ?, COALESCE((SELECT MAX(sort_order) FROM watchlist),0)+1)",
                    [code, name, market],
                )
                db.execute("UPDATE stocks SET watchlist=1 WHERE code=?", [code])
                added.append(f"{name}({code})")
            except Exception:
                pass
        db.commit()
        db.close()
    except Exception:
        pass
    return added

def _fill_stock_info_from_db(report_dict: dict) -> dict:
    """从 stocks 表中补全报告里缺失的股票名称和市场信息。"""
    if not report_dict or "stocks" not in report_dict:
        return report_dict
    try:
        db = get_db()
        rows = db.execute(
            "SELECT code, name, market FROM stocks WHERE code IN ({})".format(
                ",".join("?" * len(report_dict["stocks"]))
            ),
            list(report_dict["stocks"].keys()),
        ).fetchall()
        name_map = {r["code"]: (r["name"], r["market"]) for r in rows}
        db.close()
    except Exception:
        return report_dict

    for code, stock_data in report_dict["stocks"].items():
        if isinstance(stock_data, dict):
            if not stock_data.get("name") and code in name_map:
                stock_data["name"] = name_map[code][0]
            if not stock_data.get("market") and code in name_map:
                stock_data["market"] = name_map[code][1]
    return report_dict


# ============================================================
# 主导入入口
# ============================================================

def import_report(json_data):
    """导入任意格式的报告到数据库。

    Returns (success: bool, message: str, warnings: list).
    """
    try:
        # 1. 归一化：任意格式 → UnifiedExpertReport
        unified = transform_report(json_data)

        # 2. 转换为 v1 兼容的存储格式
        report_to_store = unified.to_v1_like()
        report_to_store["_source_version"] = unified.source_version

        # 2.5 从数据库补全缺失的股票名称和市场信息
        report_to_store = _fill_stock_info_from_db(report_to_store)

        date = unified.date or datetime.now().strftime("%Y-%m-%d")
        stock_codes = ", ".join(unified.stocks.keys())
        warnings = list(unified.warnings)

        if not unified.stocks:
            fmt_desc = describe_format(json_data)
            return False, f"未能从输入数据中提取任何股票分析 (检测到格式: {fmt_desc})", warnings

        warnings.append(
            f"格式 '{unified.source_version}' 已自动转换为统一格式"
        )

        # 3. 可选的结构完整性验证
        issues = validate_report_structure(unified)
        for issue in issues:
            warnings.append(issue)

        # 4. 写入数据库（按 date 去重：同日期已存在则更新，不存在则插入）
        db = get_db()
        try:
            report_json = json.dumps(report_to_store, ensure_ascii=False)
            existing = db.execute(
                "SELECT id FROM expert_reports WHERE date=?", [date]
            ).fetchone()
            if existing:
                db.execute(
                    "UPDATE expert_reports SET report_data=? WHERE id=?",
                    [report_json, existing["id"]]
                )
                warnings.append(f"已更新 {date} 的已有报告")
            else:
                db.execute(
                    "INSERT INTO expert_reports(date, report_data) VALUES(?, ?)",
                    [date, report_json]
                )
            db.commit()
        except Exception as e:
            return False, f"数据库写入失败: {e}", warnings
        finally:
            db.close()

        # 5. 自动添加股票到自选股（若尚未在列表中）
        auto_added = _auto_add_to_watchlist(report_to_store)
        if auto_added:
            warnings.append(f"已自动添加到自选股: {', '.join(auto_added)}")

        msg = f"导入成功: {date} — {stock_codes}"
        return True, msg, warnings

    except Exception as e:
        return False, f"报告解析失败: {e}", []


# ============================================================
# CLI 入口
# ============================================================

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(
        description="导入专家分析报告 JSON，支持多种格式版本",
        epilog="自动检测 v1(stocks)/v2(圆桌)/v3(平面/数组/包裹) 等格式"
    )
    parser.add_argument("file", help="JSON 报告文件路径")
    parser.add_argument("--describe", action="store_true",
                        help="仅打印格式描述与内容摘要，不导入")
    args = parser.parse_args()

    with open(args.file, "r", encoding="utf-8") as f:
        text = f.read()

    # Try raw JSON first, then MD code block extraction
    data = None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
        if m:
            try:
                data = json.loads(m.group(1))
            except json.JSONDecodeError:
                print("JSON 解析失败：代码块内不是合法 JSON")
                sys.exit(1)
        else:
            print("JSON 解析失败：文件不是合法 JSON 且未找到 ```json 代码块")
            sys.exit(1)

    # --describe 模式：仅分析格式，不导入
    if args.describe:
        desc = describe_format(data)
        v, feats = detect_fmt(data)
        unified = transform_report(data)
        stock_count = len(unified.stocks)
        warnings = unified.warnings

        print(f"格式版本: {v}")
        print(f"格式描述: {desc}")
        print(f"检测特征: {feats}")
        print(f"股票数量: {stock_count}")
        if unified.stocks:
            print("股票列表:")
            for code, sa in unified.stocks.items():
                print(f"  {code} {sa.name}: {sa.decision} (confidence={sa.confidence}, risk={sa.risk_level})")
        if warnings:
            print(f"警告 ({len(warnings)}):")
            for w in warnings:
                print(f"  - {w}")
        sys.exit(0)

    ok, msg, warnings = import_report(data)
    print(msg)
    if warnings:
        print(f"警告 ({len(warnings)}):")
        for w in warnings:
            print(f"  - {w}")
    sys.exit(0 if ok else 1)
