import os
import requests
from datetime import datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))
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
    valid = [o for o in observations if o.get("value") not in (".", None, "")]

    if len(valid) < 1:
        raise ValueError(f"No valid data for series: {series_id}")

    latest = valid[0]
    previous = valid[1] if len(valid) > 1 else None

    latest_value = float(latest["value"])
    latest_date = latest["date"]
    previous_value = float(previous["value"]) if previous else None

    return latest_value, latest_date, previous_value


def get_vix():
    vix, market_date, _ = get_fred_latest_two("VIXCLS")
    return vix, market_date


def get_nasdaq100():
    latest, market_date, previous = get_fred_latest_two("NASDAQ100")

    if previous is None or previous == 0:
        change_pct = 0.0
    else:
        change_pct = ((latest - previous) / previous) * 100

    return latest, change_pct, market_date


def get_fear_greed():
    url = "https://api.alternative.me/fng/"
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    data = r.json()

    value = int(data["data"][0]["value"])
    state = data["data"][0]["value_classification"]

    return value, state


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


def send_discord(msg: str):
    r = requests.post(
        WEBHOOK_URL,
        json={"content": msg},
        timeout=10,
    )
    r.raise_for_status()


def main():
    fg, fg_state = get_fear_greed()
    vix, vix_date = get_vix()
    nasdaq_price, nasdaq_change, nasdaq_date = get_nasdaq100()

    now = datetime.now(JST).strftime("%Y-%m-%d %H:%M")
    status = judge(fg)

    msg = f"""VIX Monitor (SOXL)

time: {now}

Fear & Greed: {fg} ({fg_state})

VIX: {vix:.2f}

NASDAQ100: {nasdaq_price:.2f}
change: {nasdaq_change:+.2f}%

{status}
"""

    send_discord(msg)


if __name__ == "__main__":
    main()
