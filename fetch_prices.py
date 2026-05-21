import datetime
import os
import pandas as pd
import yfinance as yf

# 你要追蹤的台股標的（Yahoo Finance 代碼）
TICKERS = [
    "00772B.TW",  # 中信高評級公司債
    "00679B.TW",  # 元大美債20年
    "2890.TW",    # 永豐金
]

# TODO：境外基金這兩檔，暫時先留空，用其他資料源再補：
# 貝萊德世界健康科學基金 A2 美元
# 聯博-國際醫療基金 A 股美元
# 可以之後另外寫一支爬資料的函式，再合併到同一支報表。

LOOKBACK_DAYS = 40  # 抓約一個月多一點，避免假日

def fetch_history(tickers, lookback_days):
    end = datetime.date.today()
    start = end - datetime.timedelta(days=lookback_days)
    data = yf.download(
        tickers=tickers,
        start=start,
        end=end,
        group_by="ticker",
        auto_adjust=True
    )
    return data

def compute_returns(price_series):
    if len(price_series) < 2:
        return None

    latest = price_series.iloc[-1]

    def pct_vs_offset(offset):
        if len(price_series) <= offset:
            return None
        past = price_series.iloc[-1 - offset]
        if past == 0:
            return None
        return (latest / past - 1) * 100

    d1 = pct_vs_offset(1)   # 前一天
    w1 = pct_vs_offset(5)   # 約 1 週
    m1 = pct_vs_offset(21)  # 約 1 個月

    return latest, d1, w1, m1

def main():
    today = datetime.date.today().isoformat()
    raw = fetch_history(TICKERS, LOOKBACK_DAYS)

    records = []

    for ticker in TICKERS:
        try:
            close_series = raw[ticker]["Close"]
        except Exception:
            # 抓不到資料就略過
            continue

        result = compute_returns(close_series)
        if result is None:
            continue

        latest, d1, w1, m1 = result

        records.append({
            "date": today,
            "ticker": ticker,
            "price": round(float(latest), 4),
            "chg_1d_pct": None if d1 is None else round(float(d1), 2),
            "chg_1w_pct": None if w1 is None else round(float(w1), 2),
            "chg_1m_pct": None if m1 is None else round(float(m1), 2),
        })

    df = pd.DataFrame(records)

    # 建一個資料夾存每日一檔
    output_dir = "daily_reports"
    os.makedirs(output_dir, exist_ok=True)

    # 每日一檔，檔名帶日期
    output_filename = os.path.join(output_dir, f"prices_report_{today}.csv")
    df.to_csv(output_filename, index=False, encoding="utf-8-sig")

    # 同時更新一份最新檔
    latest_filename = os.path.join(output_dir, "prices_report_latest.csv")
    df.to_csv(latest_filename, index=False, encoding="utf-8-sig")

    print(f"Saved {output_filename} and {latest_filename}")

if __name__ == "__main__":
    main()
