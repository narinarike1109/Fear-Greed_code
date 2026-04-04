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
    valid = [o for o in observations if o["value"] not in (".", "", None)]

    latest = valid[0]
    previous = valid[1] if len(valid) > 1 else None

    latest_value = float(latest["value"])
    latest_date = latest["date"]

    previous_value = float(previous["value"]) if previous else None

    return latest_value, latest_date, previous_value


def get_vix():

    vix, date, _ = get_fred_latest_two("VIXCLS")

    return vix


def get_nasdaq():

    latest, date, previous = get_fred_latest_two("NASDAQ100")

    if previous:
        change = (latest - previous) / previous * 100
    else:
        change = 0

    return latest, change


def judge(vix):

    if vix >= 35:
        return "💀 STRONG BUY"

    elif vix >= 28:
        return "🔥 BUY"

    elif vix <= 18:
        return "💰 TAKE PROFIT"

    else:
        return "🙂 NORMAL"


def send_discord(message):

    requests.post(
        WEBHOOK_URL,
        json={"content": message},
        timeout=10,
    )


def main():

    vix = get_vix()

    nasdaq_price, nasdaq_change = get_nasdaq()

    now = datetime.now(JST).strftime("%Y-%m-%d %H:%M")

    status = judge(vix)

    msg = f"""
VIX Monitor (SOXL)

time: {now}

VIX: {vix:.2f}

NASDAQ100: {nasdaq_price:.2f}
change: {nasdaq_change:+.2f}%

{status}
"""

    send_discord(msg)


if __name__ == "__main__":
    main()
