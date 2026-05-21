# fetch_prices.py
import os
from datetime import datetime, date
import requests
from bs4 import BeautifulSoup
import pandas as pd
import yfinance as yf


# ---------- 你要設定的部分：股票 & 基金清單 ----------

# 這裡填你要追蹤的三支股票（用 Yahoo 的 ticker 寫）
STOCK_TICKERS = [
    "2890.TW",
    "00679B.TWO",
    "00772B.TWO",
]

# 兩檔基金：MoneyDJ 淨值表網址
FUND_CONFIGS = [
    {
        "code": "ALZ02",
        "ticker": "ALZ02.FUND",
        "url": "https://www.moneydj.com/funddj/ya/yp010001.djhtm?a=ALZ02",
    },
    {
        "code": "SHZB0",
        "ticker": "SHZB0.FUND",
        "url": "https://www.moneydj.com/funddj/ya/yp010001.djhtm?a=SHZB0",
    },
]


# ---------- 共用的小工具 ----------

def pct_change(base, now):
    if base is None or base == 0:
        return None
    return round((now - base) / base * 100, 2)


def calc_returns_from_series(series):
    """
    series: list[(date, price)]，由新到舊
    回傳: today_date, today_price, chg_1d, chg_1w, chg_1m
    """
    if not series:
        return None

    today_date, today_price = series[0]

    price_1d = series[1][1] if len(series) > 1 else None
    price_1w = series[5][1] if len(series) > 5 else None   # 約 1 週前
    price_1m = series[20][1] if len(series) > 20 else None # 約 1 個月前

    chg_1d = pct_change(price_1d, today_price) if price_1d is not None else None
    chg_1w = pct_change(price_1w, today_price) if price_1w is not None else None
    chg_1m = pct_change(price_1m, today_price) if price_1m is not None else None

    return today_date, today_price, chg_1d, chg_1w, chg_1m


# ---------- 一、抓股票價格（用 yfinance） ----------

def fetch_stock_history(ticker: str, days: int = 30):
    """
    用 yfinance 抓最近約 2 個月的日資料，取最後 N 天。
    回傳：list[(date, close)]，由新到舊排序。
    """
    obj = yf.Ticker(ticker)
    hist = obj.history(period="2mo")
    hist = hist.dropna(subset=["Close"])

    hist = hist.tail(days)

    records = []
    for idx, row in hist.iterrows():
        d = idx.date()
        close = float(row["Close"])
        records.append((d, close))

    records.sort(reverse=True, key=lambda x: x[0])
    return records


def fetch_stock_rows():
    rows = []
    for ticker in STOCK_TICKERS:
        series = fetch_stock_history(ticker, days=30)
        result = calc_returns_from_series(series)
        if result is None:
            continue
        today_date, today_price, chg_1d, chg_1w, chg_1m = result
        rows.append({
            "date": today_date.strftime("%Y-%m-%d"),
            "ticker": ticker,
            "price": today_price,
            "chg_1d_pct": chg_1d if chg_1d is not None else "",
            "chg_1w_pct": chg_1w if chg_1w is not None else "",
            "chg_1m_pct": chg_1m if chg_1m is not None else "",
        })
    return rows


# ---------- 二、抓基金 NAV（MoneyDJ「近30日淨值」） ----------

def fetch_fund_nav_last_30days(url: str):
    """
    從 MoneyDJ 淨值頁抓「近30日淨值」三個表格。
    回傳 list[(date, nav)]，由新到舊。
    """
    resp = requests.get(url)
    resp.encoding = resp.apparent_encoding
    soup = BeautifulSoup(resp.text, "html.parser")

    # 1. 找「淨值日期」那列，拿最新完整日期
    nav_date_cell = soup.find("td", string=lambda s: s and "淨值日期" in s)
    if not nav_date_cell:
        raise ValueError("找不到淨值日期欄位")
    latest_row = nav_date_cell.find_parent("tr").find_next_sibling("tr")
    latest_date_str = latest_row.find_all("td")[0].get_text(strip=True)  # 例如 "2026/05/20"
    latest_date = datetime.strptime(latest_date_str, "%Y/%m/%d").date()

    # 2. 找「近30日淨值」標題
    header_tag = soup.find(string=lambda s: s and "近30日淨值" in s)
    if not header_tag:
        raise ValueError("找不到『近30日淨值』")
    node = header_tag.parent
    tables = []
    # 向後尋找 table，通常有 3 個
    for _ in range(20):
        node = node.find_next()
        if not node:
            break
        if node.name == "table":
            tables.append(node)
        if len(tables) >= 3:
            break

    records = []
    for tbl in tables:
        trs = tbl.find_all("tr")
        if len(trs) <= 1:
            continue
        for tr in trs[1:]:  # 跳過表頭
            tds = tr.find_all("td")
            if len(tds) < 2:
                continue
            d_str = tds[0].get_text(strip=True)  # "05/20"
            nav_str = tds[1].get_text(strip=True)
            if not d_str or not nav_str:
                continue
            month, day = map(int, d_str.split("/"))
            year = latest_date.year
            candidate = date(year, month, day)
            if candidate > latest_date:
                candidate = date(year - 1, month, day)
            nav = float(nav_str)
            records.append((candidate, nav))

    # 去重、排序（由新到舊）
    records = list({(d, v) for d, v in records})
    records.sort(reverse=True, key=lambda x: x[0])

    return records[:30]


def fetch_fund_rows():
    rows = []
    for cfg in FUND_CONFIGS:
        nav_records = fetch_fund_nav_last_30days(cfg["url"])
        result = calc_returns_from_series(nav_records)
        if result is None:
            continue
        today_date, today_nav, chg_1d, chg_1w, chg_1m = result
        rows.append({
            "date": today_date.strftime("%Y-%m-%d"),
            "ticker": cfg["ticker"],
            "price": today_nav,
            "chg_1d_pct": chg_1d if chg_1d is not None else "",
            "chg_1w_pct": chg_1w if chg_1w is not None else "",
            "chg_1m_pct": chg_1m if chg_1m is not None else "",
        })
    return rows


# ---------- 三、組合股票 + 基金，輸出 CSV ----------

def main():
    stock_rows = fetch_stock_rows()
    fund_rows = fetch_fund_rows()

    all_rows = stock_rows + fund_rows
    if not all_rows:
        print("No data fetched.")
        return

    df = pd.DataFrame(all_rows, columns=[
        "date",
        "ticker",
        "price",
        "chg_1d_pct",
        "chg_1w_pct",
        "chg_1m_pct",
    ])

    # 用今天日期命名：prices_report_YYYY-MM-DD.csv
    report_date = df["date"].iloc[0]
    out_dir = "daily_reports"
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"prices_report_{report_date}.csv")
    df.to_csv(out_path, index=False)
    print(f"saved to {out_path}")


if __name__ == "__main__":
    main()
