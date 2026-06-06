"""拉取兴业银行/招商银行3年日K线 + 复权因子，合并为前复权数据并保存"""
import json
import os
import sys

try:
    import requests
except ImportError:
    print("安装 requests...")
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "requests", "-q"])
    import requests

OUTPUT_DIR = r"C:\Users\28312\WorkBuddy\2026-05-18-task-15\data"

def fetch_api(api_name, params, fields=""):
    """调用finance-data-retrieval API"""
    payload = {
        "api_name": api_name,
        "params": params,
        "fields": fields
    }
    resp = requests.post(
        "https://www.codebuddy.cn/v2/tool/financedata",
        json=payload,
        timeout=60
    )
    resp.raise_for_status()
    return resp.json()

def process_stock(ts_code, stock_name, start_date, end_date):
    """拉取日线+复权因子，合并为前复权数据"""
    print(f"\n{'='*50}")
    print(f"拉取 {stock_name}({ts_code}) 日K线...")

    # 1. 拉日线
    raw = fetch_api("daily", {"ts_code": ts_code, "start_date": start_date, "end_date": end_date})
    if not raw or raw.get("code") != 0:
        print(f"  日线数据拉取失败: {raw.get('msg','unknown')}")
        return None

    fields = raw["data"]["fields"]
    items = raw["data"]["items"]
    print(f"  日线数据: {len(items)} 条")

    # 2. 拉复权因子
    adj_raw = fetch_api("adj_factor", {"ts_code": ts_code, "start_date": start_date, "end_date": end_date})
    if not adj_raw or adj_raw.get("code") != 0:
        print(f"  复权因子拉取失败: {adj_raw.get('msg','unknown')}")
        return None

    adj_fields = adj_raw["data"]["fields"]
    adj_items = adj_raw["data"]["items"]
    print(f"  复权因子: {len(adj_items)} 条")

    # 3. 构建复权因子字典 {date: factor}
    date_idx = adj_fields.index("trade_date")
    factor_idx = adj_fields.index("adj_factor")
    adj_map = {}
    for item in adj_items:
        adj_map[item[date_idx]] = float(item[factor_idx])

    # 4. 获取最新复权因子
    latest_factor = max(float(item[factor_idx]) for item in adj_items)
    if latest_factor == 0:
        latest_factor = 1.0

    # 5. 合并数据 - 前复权
    col_map = {name: i for i, name in enumerate(fields)}
    result_data = []
    for item in items:
        date = item[col_map["trade_date"]]
        raw_close = float(item[col_map["close"]])
        raw_open = float(item[col_map["open"]])
        raw_high = float(item[col_map["high"]])
        raw_low = float(item[col_map["low"]])

        factor = adj_map.get(date, latest_factor)
        adj_close = round(raw_close * factor / latest_factor, 2)
        adj_open = round(raw_open * factor / latest_factor, 2)
        adj_high = round(raw_high * factor / latest_factor, 2)
        adj_low = round(raw_low * factor / latest_factor, 2)

        result_data.append({
            "date": date,
            "open": adj_open,
            "high": adj_high,
            "low": adj_low,
            "close": adj_close,
            "volume": float(item[col_map["vol"]]),
            "amount": float(item[col_map["amount"]]),
            "pct_chg": float(item[col_map["pct_chg"]]),
            "adj_factor": factor,
        })

    # 按日期升序
    result_data.sort(key=lambda x: x["date"])

    # 6. 保存
    output = {
        "stock_code": ts_code,
        "stock_name": stock_name,
        "data_type": "前复权日K线",
        "start_date": start_date,
        "end_date": end_date,
        "total_records": len(result_data),
        "kline_data": result_data
    }

    fname = ts_code.replace(".", "") + "_daily.json"
    outpath = os.path.join(OUTPUT_DIR, fname)
    with open(outpath, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False)

    print(f"  已保存 {len(result_data)} 条到 {outpath}")
    print(f"  日期范围: {result_data[0]['date']} ~ {result_data[-1]['date']}")
    print(f"  收盘价范围: {min(r['close'] for r in result_data)} ~ {max(r['close'] for r in result_data)}")
    return result_data

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    process_stock("601166.SH", "兴业银行", "20230519", "20260520")
    process_stock("600036.SH", "招商银行", "20230519", "20260520")

    print("\n全部完成！")

if __name__ == "__main__":
    main()
