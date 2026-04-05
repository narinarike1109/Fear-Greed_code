import os
import re
import requests

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
    vix, date, _ = get_fred_latest_two("VIXCLS")
    return vix, date


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
        r"as of ([A-Za-z0-9 ,]+?) is (\d+)\s*-\s*([A-Za-z ]+)",
        r"current value of the Fear & Greed Index.*?is\s+(\d+)\s*-\s*([A-Za-z ]+)",
        r"Fear & Greed Index.*?is\s+(\d+)\s*-\s*([A-Za-z ]+)",
        r"(\d+)\s*-\s*(Extreme Fear|Fear|Neutral|Greed|Extreme Greed)",
    ]

    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if m:
            if len(m.groups()) == 3:
                return int(m.group(2)), m.group(3).strip().title(), m.group(1).strip()
            elif len(m.groups()) == 2:
                return int(m.group(1)), m.group(2).strip().title(), None

    raise ValueError("Fear and Greed Value not found")


def judge_vix(vix: float):
    if vix >= 35:
        return "💀 BUY NOW"
    elif vix < 15:
        return "💰 SELL NOW"
    else:
        return "🙂 WAIT"


def judge_fear_greed(fg: int):
    if fg <= 10:
        return "🚨 BUY NOW"
    elif fg <= 20:
        return "🔥 BUY SETUP"
    elif fg <= 25:
        return "👀 BUY SIGNAL"
    elif fg >= 80:
        return "🚨 STRONG EXIT NOW"
    elif fg >= 75:
        return "💰 SELL ZONE"
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

    # NASDAQ100
    _, nasdaq_change, market_date = get_nasdaq100()

    # Fear & Greed
    try:
        fg, fg_state, fg_date = get_fear_greed()
        fg_status = judge_fear_greed(fg)

        if fg_date:
            fg_block = f"""■Fear & Greed Monitor
time: {fg_date}
Fear & Greed: {fg} ({fg_state})
{fg_status}"""
        else:
            fg_block = f"""■Fear & Greed Monitor
Fear & Greed: {fg} ({fg_state})
{fg_status}"""
    except Exception:
        fg_block = """■Fear & Greed Monitor
Fear & Greed: 取得失敗
⚠️ FETCH FAILED"""

    msg = f"""■VIX Monitor
time: {vix_date}
VIX: {vix:.2f}
{vix_status}

{fg_block}

■NASDAQ100 Monitor
change: {nasdaq_change:+.2f}%
market_date: {market_date}
"""

    send_discord(msg)


if __name__ == "__main__":
    main()
