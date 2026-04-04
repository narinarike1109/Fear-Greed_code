import os
import requests
from datetime import datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))
WEBHOOK_URL = os.environ["DISCORD_WEBHOOK_URL"]
FRED_API_KEY = os.environ["FRED_API_KEY"]

def get_vix():
    url = "https://api.stlouisfed.org/fred/series/observations"
    params = {
        "series_id": "VIXCLS",
        "api_key": FRED_API_KEY,
        "file_type": "json",
        "sort_order": "desc",
        "limit": 1,
    }

    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    data = r.json()

    obs = data["observations"][0]
    value = obs["value"]
    date = obs["date"]

    if value == ".":
        raise ValueError("VIX data is not available yet")

    return float(value), date


def judge(vix):
    if vix >= 45:
        return "💀 PANIC BUY (SOXL)"
    elif vix >= 35:
        return "🔥 STRONG BUY (SOXL)"
    elif vix >= 25:
        return "⚠️ BUY ZONE (SOXL)"
    elif vix <= 15:
        return "💰 TAKE PROFIT ZONE"
    else:
        return "🙂 NORMAL"


def send_discord(msg):
    r = requests.post(
        WEBHOOK_URL,
        json={"content": msg},
        timeout=10
    )
    r.raise_for_status()


def main():
    vix, market_date = get_vix()
    state = judge(vix)
    now = datetime.now(JST).strftime("%Y-%m-%d %H:%M")

    msg = f"""VIX Monitor (SOXL)

time: {now}
market_date: {market_date}
VIX: {vix:.2f}

{state}
"""
    send_discord(msg)


if __name__ == "__main__":
    main()
