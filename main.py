import os
import requests
from datetime import datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))
WEBHOOK_URL = os.environ["DISCORD_WEBHOOK_URL"]

def get_vix():
    url = "https://query1.finance.yahoo.com/v7/finance/quote?symbols=%5EVIX"
    r = requests.get(url, timeout=10)
    r.raise_for_status()

    data = r.json()

    vix = data["quoteResponse"]["result"][0]["regularMarketPrice"]
    return vix


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

    vix = get_vix()

    state = judge(vix)

    now = datetime.now(JST).strftime("%Y-%m-%d %H:%M")

    msg = f"""
VIX Monitor

time: {now}
VIX: {vix}

{state}
"""

    send_discord(msg)


if __name__ == "__main__":
    main()
