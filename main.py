import os
import requests
from datetime import datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))
WEBHOOK_URL = os.environ["DISCORD_WEBHOOK_URL"]

URL = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

def get_fear_greed():
    r = requests.get(URL, headers=HEADERS, timeout=10)
    r.raise_for_status()
    data = r.json()

    score = data["fear_and_greed"]["score"]
    rating = data["fear_and_greed"]["rating"]

    return score, rating

def send_discord(msg):
    r = requests.post(
        WEBHOOK_URL,
        json={"content": msg},
        timeout=10
    )
    r.raise_for_status()

def main():
    score, rating = get_fear_greed()
    now = datetime.now(JST).strftime("%Y-%m-%d %H:%M")

    msg = f"""Fear & Greed Daily

time: {now}
score: {score}
state: {rating}
"""
    send_discord(msg)

if __name__ == "__main__":
    main()
