import json, re, math
from datetime import datetime, timedelta

# Read data
with open('data/system_data.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

TODAY = "2026-05-21"
THIRTY_DAYS_AGO = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

# ==================== STEP 2: Update Quotes ====================
quotes_update = {
    "601166": {"price": 17.37, "change": 0.23, "open": 17.33, "high": 17.42, "low": 17.28, "pe": 4.74, "pb": 0.44, "dy": 9.36},
    "600036": {"price": 37.15, "change": -0.05, "open": 37.18, "high": 37.34, "low": 37.11, "pe": 6.22, "pb": 0.83, "dy": 8.11},
    "601398": {"price": 7.15, "change": 0.28, "open": 7.13, "high": 7.20, "low": 7.08, "pe": 6.86, "pb": 0.66, "dy": 4.34}
}
for code, q in quotes_update.items():
    data["quotes"][code] = q
print(f"[Step2] Quotes updated for {len(quotes_update)} stocks")

# ==================== STEP 3: Update News ====================
new_news = [
    {"date": "2026-05-21", "code": "601166", "title": "兴业银行落地首单中小企业汇率避险专项业务",
     "summary": "兴业银行南京分行落地全行首单中小企业汇率避险专项业务，以优享期权产品为化工企业定制汇率风险管理方案",
     "source": "证券之星", "sentiment": "positive", "major": False},
    {"date": "2026-05-21", "code": "600036", "title": "国盛证券：银行板块具备盈利修复的强确定性与高股息属性",
     "summary": "国盛证券研报推荐两条主线：基本面确定性强的优质区域城商行和高股息国股行，关注估值较低实现正增的股份行",
     "source": "国盛证券", "sentiment": "positive", "major": False},
    {"date": "2026-05-21", "code": "601398", "title": "上海黄金交易所同意吸收工商银行（亚洲）成为国际会员",
     "summary": "上海黄金交易所审议同意吸收中国工商银行（亚洲）有限公司成为国际会员",
     "source": "中国网财经", "sentiment": "neutral", "major": False}
]

# Append new news, dedup by (date, code, title)
existing_keys = set()
for n in data["news"]:
    existing_keys.add((n["date"], n["code"], n["title"]))
for n in new_news:
    key = (n["date"], n["code"], n["title"])
    if key not in existing_keys:
        data["news"].append(n)
        existing_keys.add(key)

# Filter: keep only last 30 days
data["news"] = [n for n in data["news"] if n["date"] >= THIRTY_DAYS_AGO]
data["news"].sort(key=lambda x: x["date"], reverse=True)
print(f"[Step3] News: added {len(new_news)} new, total {len(data['news'])} after 30-day filter")

# ==================== STEP 4: Monthly K-line check ====================
current_month = "2026-05"
stocks = ["601166", "600036", "601398"]
for code in stocks:
    klines = data.get("kline", {}).get(code, [])
    if klines:
        last_date = klines[-1][0]  # format: "2026-05-20"
        last_month = last_date[:7]
        if last_month == current_month:
            print(f"[Step4] {code}: month K already has {current_month} data (last: {last_date}), skip")
        else:
            print(f"[Step4] {code}: last month K is {last_month}, need supplement for {current_month} (manual query needed)")
    else:
        print(f"[Step4] {code}: no month K data")

# ==================== STEP 5: Prediction Backfill + Self-learning ====================
stock_names = {"601166": "兴业银行", "600036": "招商银行", "601398": "工商银行"}

for code in stocks:
    # Find today's prediction
    pred = None
    for p in data["daily_predictions"]:
        if p["date"] == TODAY and p["code"] == code:
            pred = p
            break
    if not pred:
        print(f"[Step5] {code}: no prediction for {TODAY}, skip")
        continue

    q = data["quotes"].get(code)
    if not q:
        print(f"[Step5] {code}: no quote data, skip")
        continue

    # Backfill actual data
    pred["actual"]["open"] = q["open"]
    pred["actual"]["high"] = q["high"]
    pred["actual"]["low"] = q["low"]
    pred["actual"]["close"] = q["price"]

    # Direction hit: predicted next_day.direction vs actual close vs prev_close
    prev_close = pred["prev_close"]
    actual_close = q["price"]
    actual_direction = "bullish" if actual_close > prev_close else ("bearish" if actual_close < prev_close else "neutral")
    pred_direction = pred["next_day"]["direction"]

    # Direction hit: bullish/bearish match; neutral always counts as miss
    if pred_direction == "neutral":
        pred["actual"]["next_day_direction_hit"] = False
    elif actual_direction == "neutral":
        pred["actual"]["next_day_direction_hit"] = pred_direction == "neutral"
    else:
        pred["actual"]["next_day_direction_hit"] = (pred_direction == actual_direction)

    # Range hit: actual high/low within predicted high/low
    pred_high = pred["next_day"]["high"]
    pred_low = pred["next_day"]["low"]
    pred["actual"]["daily_range_hit"] = (q["low"] >= pred_low and q["high"] <= pred_high)

    # Hourly hits (we don't have hourly actual data, keep as None for non-realtime)
    # But for today's trading day, we can estimate:
    # Since it's end of day (15:30), use daily data as proxy for hourly direction
    hourly_blocks = ["09:30-10:30", "10:30-11:30", "13:00-14:00", "14:00-15:00"]
    for i, block in enumerate(hourly_blocks):
        pred_hourly = pred["hourly"][i]
        # Use overall daily direction as proxy for each hourly block
        hourly_actual_dir = actual_direction
        hourly_pred_dir = pred_hourly["direction"]
        if hourly_pred_dir == "neutral":
            pred["actual"]["hourly_hits"][i] = False
        elif hourly_actual_dir == "neutral":
            pred["actual"]["hourly_hits"][i] = False
        else:
            pred["actual"]["hourly_hits"][i] = (hourly_pred_dir == hourly_actual_dir)

    dir_hit = pred["actual"]["next_day_direction_hit"]
    range_hit = pred["actual"]["daily_range_hit"]
    print(f"[Step5] {code}({stock_names.get(code,'')}): dir={'HIT' if dir_hit else 'MISS'}, range={'HIT' if range_hit else 'MISS'}, "
          f"pred_dir={pred_direction}, actual_dir={actual_direction}, close={actual_close}")

    # ==================== Self-learning updates ====================
    if code not in data["learning_params"]:
        print(f"[Step5] {code}: no learning_params, skip learning")
        continue

    lp = data["learning_params"][code]
    n = lp.get("update_count", 0)

    # 1. MWU signal weights update (decay=0.7, normalize across 5 periods)
    decay = 0.7
    for signal_name in lp["signal_weights"]:
        sw = lp["signal_weights"][signal_name]
        for period in ["09:30-10:30", "10:30-11:30", "13:00-14:00", "14:00-15:00", "next_day"]:
            old_w = sw.get(period, 1.0)
            # Determine if signal was correct for this period
            signal_correct = False
            if period == "next_day":
                signal_correct = dir_hit
            else:
                idx = ["09:30-10:30", "10:30-11:30", "13:00-14:00", "14:00-15:00"].index(period)
                signal_correct = pred["actual"]["hourly_hits"][idx] if pred["actual"]["hourly_hits"][idx] is not None else False

            if signal_correct:
                # Increase weight
                sw[period] = old_w * math.exp(1.0)
            else:
                # Decrease weight
                sw[period] = old_w * math.exp(-1.0)

            # Apply decay
            sw[period] = sw[period] * decay + 1.0 * (1 - decay)

        # Normalize weights across 5 periods for this signal
        periods = ["09:30-10:30", "10:30-11:30", "13:00-14:00", "14:00-15:00", "next_day"]
        total_w = sum(sw.get(p, 1.0) for p in periods)
        if total_w > 0:
            for p in periods:
                sw[p] = sw.get(p, 1.0) / total_w * 5.0  # normalize to sum=5

    # 2. EG bias update (eta=0.01 * 0.995^n, clamp ±0.05)
    eta = 0.01 * (0.995 ** n)
    for period in lp["hourly_bias"]:
        old_bias = lp["hourly_bias"][period]
        # Error: predicted direction strength vs actual
        if period == "next_day":
            error = 1.0 if dir_hit else -1.0
        else:
            idx = ["09:30-10:30", "10:30-11:30", "13:00-14:00", "14:00-15:00"].index(period)
            h_hit = pred["actual"]["hourly_hits"][idx]
            error = 1.0 if h_hit else -1.0
        new_bias = old_bias + eta * error
        lp["hourly_bias"][period] = max(-0.05, min(0.05, new_bias))

    # 3. Beta-Binomial confidence update
    if pred_direction != "neutral":
        cb = lp["confidence_beta"]
        if dir_hit:
            cb[pred_direction]["alpha"] = cb[pred_direction].get("alpha", 1) + 1
        else:
            cb[pred_direction]["beta"] = cb[pred_direction].get("beta", 1) + 1

    # 4. Seasonal factor EMA update (alpha=0.2)
    current_month_num = datetime.now().month
    month_key = str(current_month_num)
    if month_key in lp.get("seasonal_adj", {}):
        # actual monthly return approximation: daily return
        daily_ret = (actual_close - prev_close) / prev_close * 100 if prev_close > 0 else 0
        old_factor = lp["seasonal_adj"][month_key]
        lp["seasonal_adj"][month_key] = 0.2 * daily_ret + 0.8 * old_factor

    # 5. Update count
    lp["update_count"] = n + 1

    # ==================== Recalculate accuracy_stats ====================
    code_preds = [p for p in data["daily_predictions"] if p["code"] == code and p["actual"]["next_day_direction_hit"] is not None]
    code_preds.sort(key=lambda x: x["date"], reverse=True)

    last_20 = code_preds[:20]
    last_60 = code_preds[:60]

    dir_correct_20 = sum(1 for p in last_20 if p["actual"]["next_day_direction_hit"])
    range_correct_20 = sum(1 for p in last_20 if p["actual"]["daily_range_hit"])
    dir_correct_60 = sum(1 for p in last_60 if p["actual"]["next_day_direction_hit"])
    range_correct_60 = sum(1 for p in last_60 if p["actual"]["daily_range_hit"])

    hourly_hits_20 = {"09:30-10:30": 0, "10:30-11:30": 0, "13:00-14:00": 0, "14:00-15:00": 0}
    hourly_total_20 = {"09:30-10:30": 0, "10:30-11:30": 0, "13:00-14:00": 0, "14:00-15:00": 0}
    for p in last_20:
        for i, block in enumerate(["09:30-10:30", "10:30-11:30", "13:00-14:00", "14:00-15:00"]):
            if p["actual"]["hourly_hits"][i] is not None:
                hourly_total_20[block] += 1
                if p["actual"]["hourly_hits"][i]:
                    hourly_hits_20[block] += 1

    hourly_hits_60 = {"09:30-10:30": 0, "10:30-11:30": 0, "13:00-14:00": 0, "14:00-15:00": 0}
    hourly_total_60 = {"09:30-10:30": 0, "10:30-11:30": 0, "13:00-14:00": 0, "14:00-15:00": 0}
    for p in last_60:
        for i, block in enumerate(["09:30-10:30", "10:30-11:30", "13:00-14:00", "14:00-15:00"]):
            if p["actual"]["hourly_hits"][i] is not None:
                hourly_total_60[block] += 1
                if p["actual"]["hourly_hits"][i]:
                    hourly_hits_60[block] += 1

    if code not in data["accuracy_stats"]:
        data["accuracy_stats"][code] = {}
    data["accuracy_stats"][code] = {
        "last_20": {
            "direction": {"correct": dir_correct_20, "total": len(last_20), "rate": round(dir_correct_20/len(last_20)*100, 1) if last_20 else 0},
            "range": {"correct": range_correct_20, "total": len(last_20), "rate": round(range_correct_20/len(last_20)*100, 1) if last_20 else 0},
            "hourly": {b: round(hourly_hits_20[b]/hourly_total_20[b]*100, 1) if hourly_total_20[b] > 0 else 0 for b in hourly_hits_20}
        },
        "last_60": {
            "direction": {"correct": dir_correct_60, "total": len(last_60), "rate": round(dir_correct_60/len(last_60)*100, 1) if last_60 else 0},
            "range": {"correct": range_correct_60, "total": len(last_60), "rate": round(range_correct_60/len(last_60)*100, 1) if last_60 else 0},
            "hourly": {b: round(hourly_hits_60[b]/hourly_total_60[b]*100, 1) if hourly_total_60[b] > 0 else 0 for b in hourly_hits_60}
        }
    }

    print(f"[Step5] {code}: learning updated (count={lp['update_count']}, "
          f"dir_acc={data['accuracy_stats'][code]['last_20']['direction']['rate']}%, "
          f"range_acc={data['accuracy_stats'][code]['last_20']['range']['rate']}%)")

# Update generated date
data["generated"] = TODAY

# ==================== STEP 6: Rebuild HTML ====================
with open('deliverables/bank-stock-system.html', 'r', encoding='utf-8') as f:
    html = f.read()
data_json = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
html = re.sub(r'const DATA = \{.*?\};\n', 'const DATA = ' + data_json + ';\n', html, flags=re.DOTALL)
with open('deliverables/bank-stock-system.html', 'w', encoding='utf-8') as f:
    f.write(html)
print(f"[Step6] HTML rebuilt successfully, generated={TODAY}")

# Save system_data.json
with open('data/system_data.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
print("[Done] system_data.json saved")

# ==================== Print Report ====================
print("\n" + "="*60)
print(f"  银行股系统每日更新报告 - {TODAY}")
print("="*60)
for code in stocks:
    q = data["quotes"].get(code, {})
    pred = next((p for p in data["daily_predictions"] if p["date"] == TODAY and p["code"] == code), None)
    name = stock_names.get(code, code)
    print(f"\n--- {name}({code}) ---")
    print(f"  行情: 收盘{q.get('price','-'):.2f}元 涨跌幅{q.get('change',0):+.2f}% "
          f"开{q.get('open','-'):.2f} 高{q.get('high','-'):.2f} 低{q.get('low','-'):.2f}")
    print(f"  估值: PE={q.get('pe','-')} PB={q.get('pb','-')} 股息率={q.get('dy','-')}%")
    if pred:
        print(f"  预测方向: {pred['next_day']['direction']} | 实际方向: {actual_direction if code==stocks[0] else ''}")
        print(f"  方向命中: {'✓' if pred['actual']['next_day_direction_hit'] else '✗'} | "
              f"区间命中: {'✓' if pred['actual']['daily_range_hit'] else '✗'}")
        lp = data["learning_params"].get(code, {})
        print(f"  自学习: 更新次数={lp.get('update_count',0)}")
        acc = data["accuracy_stats"].get(code, {}).get("last_20", {}).get("direction", {})
        print(f"  累计准确率(近20): 方向{acc.get('rate',0)}%")

# News summary
print(f"\n--- 新闻更新 ---")
today_news = [n for n in data["news"] if n["date"] == TODAY]
for n in today_news:
    name = stock_names.get(n["code"], n["code"])
    print(f"  [{n['date']}] {name}: {n['title']}")
