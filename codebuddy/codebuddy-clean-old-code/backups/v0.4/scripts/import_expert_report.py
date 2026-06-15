"""Import expert report JSON into stock.db expert_reports table"""
import json, os, sys, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from db_helper import get_db

VALID_DECISIONS = {"BUY", "HOLD", "SELL"}
VALID_CONFIDENCES = {"高", "中", "低"}
VALID_RISKS = {"高", "中", "低"}
REQUIRED_KEYS = ["decision", "confidence", "risk_level", "position_pct",
                 "entry_price", "target_price", "stop_loss", "scores", "phase1", "phase2", "phase4"]

def validate_report(data):
    """Validate report structure, return (is_valid, error_message, warnings)"""
    warnings = []
    if not isinstance(data, dict):
        return False, "根必须为 JSON 对象", []
    if "stocks" not in data or not isinstance(data["stocks"], dict):
        return False, "缺少 stocks 字段或格式错误", []
    stocks = data["stocks"]
    if not stocks:
        return False, "stocks 为空", []
    # Check each stock
    for code, sd in list(stocks.items()):
        if not isinstance(sd, dict):
            return False, f"股票 {code} 数据格式错误", warnings
        for key in REQUIRED_KEYS:
            if key not in sd:
                return False, f"股票 {code} 缺少必填字段: {key}", warnings
        if sd.get("decision") not in VALID_DECISIONS:
            return False, f"股票 {code} decision 必须为 BUY/HOLD/SELL，当前: {sd.get('decision')}", warnings
        if sd.get("confidence") not in VALID_CONFIDENCES:
            warnings.append(f"股票 {code} confidence '{sd.get('confidence')}' 不在 高/中/低，已修正为'中'")
            sd["confidence"] = "中"
        if sd.get("risk_level") not in VALID_RISKS:
            warnings.append(f"股票 {code} risk_level '{sd.get('risk_level')}' 不在 高/中/低，已修正为'中'")
            sd["risk_level"] = "中"
        # Check scores range
        for sk in ["technical", "fundamental", "news", "sentiment", "risk"]:
            v = sd.get("scores", {}).get(sk, 0)
            if not (0 <= v <= 10):
                warnings.append(f"股票 {code} scores.{sk}={v} 超出 0-10 范围")
        # Ensure bull_args/bear_args have correct structure
        for arg_type in ["bull_args", "bear_args"]:
            args = sd.get("phase2", {}).get(arg_type, [])
            if not isinstance(args, list):
                return False, f"股票 {code} phase2.{arg_type} 必须是数组", warnings
            for i, a in enumerate(args):
                if not isinstance(a, dict) or "point" not in a or "weight" not in a:
                    warnings.append(f"股票 {code} phase2.{arg_type}[{i}] 缺少 point/weight")
        # Check phase4 scores
        for pk in ["aggressive_score", "conservative_score", "neutral_score"]:
            v = sd.get("phase4", {}).get(pk, 0)
            if not (0 <= v <= 10):
                warnings.append(f"股票 {code} phase4.{pk}={v} 超出 0-10 范围")
    return True, "", warnings

def import_report(json_data):
    """Import a report into the database. Returns (success, message, warnings)"""
    # Auto-fill date
    if "date" not in json_data:
        from datetime import datetime
        json_data["date"] = datetime.now().strftime("%Y-%m-%d")
    
    # Validate
    ok, err, warnings = validate_report(json_data)
    if not ok:
        return False, err, warnings
    
    # Insert
    db = get_db()
    try:
        db.execute("INSERT INTO expert_reports(date, report_data) VALUES(?, ?)",
                   [json_data["date"], json.dumps(json_data, ensure_ascii=False)])
        db.commit()
        stock_list = ", ".join(f"{code}({sd.get('decision','?')})" for code, sd in json_data["stocks"].items())
        msg = f"导入成功: {json_data['date']} — {stock_list}"
        return True, msg, warnings
    except Exception as e:
        return False, f"数据库写入失败: {e}", warnings
    finally:
        db.close()

# CLI entry point
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("file", help="JSON report file path")
    args = parser.parse_args()
    
    with open(args.file, "r", encoding="utf-8") as f:
        text = f.read()
    
    # Try raw JSON first, then try MD extraction
    data = None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r'```json\s*([\s\S]*?)```', text)
        if m:
            try:
                data = json.loads(m.group(1))
            except json.JSONDecodeError:
                print("JSON 解析失败：代码块内不是合法 JSON")
                sys.exit(1)
        else:
            print("JSON 解析失败：文件不是合法 JSON 且未找到 ```json 代码块")
            sys.exit(1)
    
    ok, msg, warnings = import_report(data)
    print(msg)
    if warnings:
        print(f"警告 ({len(warnings)}):")
        for w in warnings:
            print(f"  - {w}")
    sys.exit(0 if ok else 1)
