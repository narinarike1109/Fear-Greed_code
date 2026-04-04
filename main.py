import os
import re
import requests
from datetime import datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))

WEBHOOK_URL = os.environ["DISCORD_WEBHOOK_URL"]
FRED_API_KEY = os.environ["FRED_API_KEY"]

FRED_URL = "https://api.stlouisfed.org/fred/series/observations"
FG_URL = "https://www.finhacker.cz/en/fear-and-greed-index-historical-data-and-chart/"


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


def get_nasdaq100():
    latest, market_date, previous = get_fred_latest_two("NASDAQ100")

    if previous is None or previous == 0:
        change_pct = 0.0
    else:
        change_pct = ((latest - previous) / previous) * 100

    return latest, change_pct, market_date


def get_fear_greed():
    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    r = requests.get(FG_URL, headers=headers, timeout=15)
    r.raise_for_status()
    text = r.text

    # 例:
    # "The current value of the Fear & Greed Index as of April 2, 2026 is 15 - extreme fear."
    pattern = r"The current value of the Fear & Greed Index as of (.*?) is (\d+)\s*-\s*([a-zA-Z ]+)\."
    m = re.search(pattern, text, re.IGNORECASE)

    if not m:
        raise ValueError("Fear & Greed value not found on page")

    market_date = m.group(1).strip()
    value = int(m.group(2))
    state = m.group(3).strip().title()

    return value, state, market_date


def judge(fg: int):
    if fg < 20:
        return "💀 STRONG BUY"
    elif fg < 30:
        return "🔥 BUY"
    elif fg >= 85:
        return "🚨 EXIT MARKET"
    elif fg >= 70:
        return "💰 TAKE PROFIT"
    else:
        return "🙂 NORMAL"


def send_discord(message: str):
    r = requests.post(
        WEBHOOK_URL,
        json={"content": message},
        timeout=10,
    )
    r.raise_for_status()


def main():
    fg, fg_state, fg_date = get_fear_greed()
    nasdaq_price, nasdaq_change, nasdaq_date = get_nasdaq100()

    now = datetime.now(JST).strftime("%Y-%m-%d %H:%M")
    status = judge(fg)

    msg = f"""Fear & Greed Monitor (SOXL)

time: {now}

Fear & Greed: {fg} ({fg_state})
fg_date: {fg_date}

NASDAQ100: {nasdaq_price:.2f}
change: {nasdaq_change:+.2f}%
market_date: {nasdaq_date}

{status}
"""

    send_discord(msg)


if __name__ == "__main__":
    main()
