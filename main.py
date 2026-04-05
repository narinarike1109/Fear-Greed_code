import os
import requests
import yfinance as yf
from playwright.sync_api import sync_playwright

WEBHOOK_URL = os.environ["DISCORD_WEBHOOK_URL"]
FRED_API_KEY = os.environ["FRED_API_KEY"]

FRED_URL = "https://api.stlouisfed.org/fred/series/observations"


def get_fred_latest_two(series_id: str):
    params = {
        "series_id": series_id,
        "api_key": FRED_API_KEY,
        "file_type": "json",
        "sort_order": "desc",
        "limit": 2,
    }

    r = requests.get(FRED_URL, params=params, timeout=15)
    r.raise_for_status()
    data = r.json()

    observations = data.get("observations", [])
    valid = [o for o in observations if o.get("value") not in (".", "", None)]

    if len(valid) < 1:
        raise ValueError(f"No valid data for series: {series_id}")

    latest = valid[0]
    previous = valid[1] if len(valid) > 1 else None

    latest_value = float(latest["value"])
    latest_date = latest["date"]
    previous_value = float(previous["value"]) if previous else None

    return latest_value, latest_date, previous_value


def get_vix():
    vix, date, _ = get_fred_latest_two("VIXCLS")
    return vix, date


def get_nasdaq100():
    latest, market_date, previous = get_fred_latest_two("NASDAQ100")

    if previous is None or previous == 0:
        change_pct = 0.0
    else:
        change_pct = ((latest - previous) / previous) * 100

    return latest, change_pct, market_date


# CNN Fear & Greed 取得
def get_fear_greed():

    url = "https://edition.cnn.com/markets/fear-and-greed"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        page = browser.new_page(
            user_agent="Mozilla/5.0"
        )

        page.goto(url, wait_until="domcontentloaded")

        fg_text = page.locator(
            ".market-fng-gauge__dial-number-value"
        ).inner_text()

        browser.close()

    return int(fg_text)


def get_etf_change(symbol: str):
    ticker = yf.Ticker(symbol)
    hist = ticker.history(period="5d", interval="1d", auto_adjust=False)

    hist = hist.dropna(subset=["Close"])

    if len(hist) < 2:
        raise ValueError(f"Not enough price data for {symbol}")

    latest = float(hist["Close"].iloc[-1])
    previous = float(hist["Close"].iloc[-2])

    if previous == 0:
        change_pct = 0.0
    else:
        change_pct = ((latest - previous) / previous) * 100

    return latest, change_pct


def judge_vix(vix: float):

    if vix >= 35:
        return "💀 BUY NOW"
    elif vix < 15:
        return "💰 SELL NOW"
    else:
        return "🙂 WAIT"


def judge_fear_greed(fg: int):

    if fg <= 10:
        return "🚨 IMMEDIATE BUY NOW"
    elif fg <= 20:
        return "🔥 PREPARE BUY SETUP"
    elif fg <= 25:
        return "👀 BUY SIGNAL"
    elif fg >= 80:
        return "🚨 STRONG EXIT NOW"
    elif fg >= 75:
        return "💰 TAKE PROFIT ZONE"
    else:
        return "🙂 WAIT"


def send_discord(message: str):

    r = requests.post(
        WEBHOOK_URL,
        json={"content": message},
        timeout=10,
    )

    r.raise_for_status()


def main():

    # VIX
    vix, vix_date = get_vix()
    vix_status = judge_vix(vix)

    # Fear & Greed
    try:

        fg = get_fear_greed()
        fg_status = judge_fear_greed(fg)

        fg_block = f"""■Fear & Greed Monitor
Fear & Greed: {fg}
{fg_status}"""

    except Exception as e:

        fg_block = f"""■Fear & Greed Monitor
Fear & Greed: 取得失敗
⚠️ FETCH FAILED ({str(e)})"""

    # NASDAQ100
    _, nasdaq_change, market_date = get_nasdaq100()

    # Leveraged ETFs
    try:

        spxl_price, spxl_change = get_etf_change("SPXL")
        soxl_price, soxl_change = get_etf_change("SOXL")
        tecl_price, tecl_change = get_etf_change("TECL")

        etf_block = f"""■Leveraged ETF Monitor
SPXL: {spxl_price:.2f} ({spxl_change:+.2f}%)
SOXL: {soxl_price:.2f} ({soxl_change:+.2f}%)
TECL: {tecl_price:.2f} ({tecl_change:+.2f}%)"""

    except Exception as e:

        etf_block = f"""■Leveraged ETF Monitor
取得失敗
⚠️ FETCH FAILED ({str(e)})"""

    msg = f"""■VIX Monitor
time: {vix_date}
VIX: {vix:.2f}
{vix_status}

{fg_block}

■NASDAQ100 Monitor
change: {nasdaq_change:+.2f}%
market_date: {market_date}

{etf_block}
"""

    send_discord(msg)


if __name__ == "__main__":
    main()
