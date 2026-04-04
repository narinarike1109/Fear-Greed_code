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


def get_vix():
    vix, _, _ = get_fred_latest_two("VIXCLS")
    return vix


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

    patterns = [
        r"current value of the Fear & Greed Index.*?is\s+(\d+)\s*-\s*([A-Za-z ]+)",
        r"Fear & Greed Index.*?is\s+(\d+)\s*-\s*([A-Za-z ]+)",
        r"(\d+)\s*-\s*(Extreme Fear|Fear|Neutral|Greed|Extreme Greed)",
    ]

    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if m:
            value = int(m.group(1))
            state = m.group(2).strip().title()
            return value, state

    raise ValueError("Fear and Greed Value がページに見つからない")


def judge_vix(vix: float):
    if vix >= 35:
        return "💀 STRONG BUY"
    elif vix >= 28:
        return "🔥 BUY"
    elif vix <= 18:
        return "💰 TAKE PROFIT"
    else:
        return "🙂 NORMAL"


def judge_fear_greed(fg: int):
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
    now = datetime.now(JST).strftime("%Y-%m-%d %H:%M")

    # VIX
    try:
        vix = get_vix()
        vix_status = judge_vix(vix)
        vix_block = f"""■VIX Monitor
time: {now}
VIX: {vix:.2f}
{vix_status}"""
    except Exception as e:
        vix_block = f"""■VIX Monitor
time: {now}
VIX: 取得失敗
⚠️ FETCH FAILED ({str(e)})"""

    # Fear & Greed
    try:
        fg, fg_state = get_fear_greed()
        fg_status = judge_fear_greed(fg)
        fg_block = f"""■Fear & Greed Monitor
time: {now}
Fear & Greed: {fg} ({fg_state})
{fg_status}"""
    except Exception as e:
        fg_block = f"""■Fear & Greed Monitor
time: {now}
Fear & Greed: 取得失敗
⚠️ FETCH FAILED ({str(e)})"""

    # NASDAQ100
    try:
        _, nasdaq_change, market_date = get_nasdaq100()
        nasdaq_block = f"""■NASDAQ100 Monitor
change: {nasdaq_change:+.2f}%
market_date: {market_date}"""
    except Exception as e:
        nasdaq_block = f"""■NASDAQ100 Monitor
change: 取得失敗
market_date: unknown
⚠️ FETCH FAILED ({str(e)})"""

    msg = f"""{vix_block}

{fg_block}

{nasdaq_block}"""

    send_discord(msg)


if __name__ == "__main__":
    main()
