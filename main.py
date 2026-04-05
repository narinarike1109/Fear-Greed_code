import os
from datetime import datetime, timezone, timedelta
from typing import Optional

import requests
import yfinance as yf


# =========================
# Environment Variables
# =========================
DISCORD_WEBHOOK_URL = os.environ["DISCORD_WEBHOOK_URL"]
FRED_API_KEY = os.environ["FRED_API_KEY"]


# =========================
# Constants
# =========================
CNN_FNG_URL = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
FRED_URL = "https://api.stlouisfed.org/fred/series/observations"
TARGET_TICKERS = ["SPXL", "TECL", "SOXL"]

JST = timezone(timedelta(hours=9))

REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Referer": "https://edition.cnn.com/markets/fear-and-greed",
    "Origin": "https://edition.cnn.com"
}

# =========================
# Utilities
# =========================
def safe_float(value) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def now_jst_str() -> str:
    return datetime.now(JST).strftime("%Y/%m/%d %H:%M")


# =========================
# Fear & Greed
# =========================
def get_fear_greed_score() -> int:
    """
    CNN JSON endpoint から Fear & Greed score を取得
    """
    res = requests.get(CNN_FNG_URL, headers=REQUEST_HEADERS, timeout=15)
    res.raise_for_status()

    data = res.json()
    print(f"[DEBUG] F&G top-level keys: {list(data.keys())}")

    fear_and_greed = data.get("fear_and_greed")
    if not isinstance(fear_and_greed, dict):
        raise ValueError(f"fear_and_greed block not found: {data}")

    score = fear_and_greed.get("score")
    score = safe_float(score)

    if score is None:
        raise ValueError(f"fear_and_greed.score not found: {fear_and_greed}")

    return int(score)


def judge_fear_greed(score: int) -> str:
    if score <= 10:
        return "🚨 IMMEDIATE BUY NOW"
    elif score <= 20:
        return "🔥 PREPARE BUY SETUP"
    elif score <= 25:
        return "👀 BUY SIGNAL"
    elif score >= 80:
        return "🚨 STRONG EXIT NOW"
    elif score >= 75:
        return "💰 TAKE PROFIT ZONE"
    else:
        return "🙂 WAIT"


# =========================
# FRED
# =========================
def get_fred_latest_two(series_id: str):
    params = {
        "series_id": series_id,
        "api_key": FRED_API_KEY,
        "file_type": "json",
        "sort_order": "desc",
        "limit": 2,
    }

    res = requests.get(FRED_URL, params=params, headers=REQUEST_HEADERS, timeout=15)
    res.raise_for_status()
    data = res.json()

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


def judge_vix(vix: float) -> str:
    if vix >= 35:
        return "💀 BUY NOW"
    elif vix < 15:
        return "💰 SELL NOW"
    else:
        return "🙂 WAIT"


def get_nasdaq100():
    latest, market_date, previous = get_fred_latest_two("NASDAQ100")

    if previous is None or previous == 0:
        change_pct = 0.0
    else:
        change_pct = ((latest - previous) / previous) * 100

    return latest, change_pct, market_date


# =========================
# ETF / RSI
# =========================
def calculate_rsi(close_series, period: int = 14) -> Optional[float]:
    if len(close_series) < period + 1:
        return None

    delta = close_series.diff()
    gain = delta.where(delta > 0, 0.0).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(window=period).mean()

    last_gain = gain.iloc[-1]
    last_loss = loss.iloc[-1]

    if last_loss == 0:
        return 100.0

    rs = last_gain / last_loss
    rsi = 100 - (100 / (1 + rs))
    return float(rsi)


def get_etf_info(symbol: str):
    """
    yfinance.Ticker().history() を使って価格、前日比、RSI を取得
    """
    ticker = yf.Ticker(symbol)
    hist = ticker.history(period="1mo", interval="1d", auto_adjust=False)

    print(f"[DEBUG] {symbol} hist columns: {list(hist.columns)}")
    print(f"[DEBUG] {symbol} hist rows: {len(hist)}")

    if hist.empty or "Close" not in hist.columns:
        raise ValueError(f"No price data for {symbol}. columns={list(hist.columns)}")

    close = hist["Close"].dropna()

    if len(close) < 2:
        raise ValueError(f"Not enough close data for {symbol}. close_len={len(close)}")

    latest = float(close.iloc[-1])
    previous = float(close.iloc[-2])
    change_pct = 0.0 if previous == 0 else ((latest - previous) / previous) * 100
    rsi = calculate_rsi(close, period=14)

    return {
        "symbol": symbol,
        "price": latest,
        "change_pct": change_pct,
        "rsi": rsi,
    }


def judge_rsi(rsi: Optional[float]) -> str:
    if rsi is None:
        return "N/A"
    if rsi < 30:
        return "🔥 OVERSOLD"
    if rsi > 70:
        return "🥵 OVERBOUGHT"
    return "🙂 NORMAL"


# =========================
# Discord
# =========================
def send_discord(message: str) -> None:
    res = requests.post(
        DISCORD_WEBHOOK_URL,
        json={"content": message},
        timeout=15,
    )
    res.raise_for_status()


# =========================
# Report Builder
# =========================
def build_report() -> str:
    report_lines = [
        f"## 📊 Market Watch [{now_jst_str()} JST]",
        ""
    ]

    # VIX
    try:
        vix, vix_date = get_vix()
        vix_status = judge_vix(vix)
        report_lines.extend([
            "■VIX Monitor",
            f"time: {vix_date}",
            f"VIX: {vix:.2f}",
            f"{vix_status}",
            ""
        ])
    except Exception as e:
        print(f"[ERROR] VIX block failed: {e}")
        report_lines.extend([
            "■VIX Monitor",
            "取得失敗",
            f"⚠️ FETCH FAILED ({str(e)})",
            ""
        ])

    # Fear & Greed
    try:
        fg_score = get_fear_greed_score()
        fg_status = judge_fear_greed(fg_score)
        report_lines.extend([
            "■Fear & Greed Monitor",
            f"Fear & Greed: {fg_score}",
            f"{fg_status}",
            ""
        ])
    except Exception as e:
        print(f"[ERROR] Fear & Greed block failed: {e}")
        report_lines.extend([
            "■Fear & Greed Monitor",
            "Fear & Greed: 取得失敗",
            f"⚠️ FETCH FAILED ({str(e)})",
            ""
        ])

    # NASDAQ100
    try:
        _, nasdaq_change, market_date = get_nasdaq100()
        report_lines.extend([
            "■NASDAQ100 Monitor",
            f"change: {nasdaq_change:+.2f}%",
            f"market_date: {market_date}",
            ""
        ])
    except Exception as e:
        print(f"[ERROR] NASDAQ100 block failed: {e}")
        report_lines.extend([
            "■NASDAQ100 Monitor",
            "取得失敗",
            f"⚠️ FETCH FAILED ({str(e)})",
            ""
        ])

    # Leveraged ETFs
    report_lines.append("■Leveraged ETF Monitor")

    success_count = 0
    for symbol in TARGET_TICKERS:
        try:
            info = get_etf_info(symbol)
            success_count += 1

            rsi_label = judge_rsi(info["rsi"])
            rsi_str = "N/A" if info["rsi"] is None else f"{info['rsi']:.1f}"

            report_lines.append(
                f"{symbol}: {info['price']:.2f} ({info['change_pct']:+.2f}%) / RSI: {rsi_str} [{rsi_label}]"
            )
        except Exception as e:
            print(f"[ERROR] ETF block failed for {symbol}: {e}")
            report_lines.append(f"{symbol}: 取得失敗 ({str(e)})")

    if success_count == 0:
        report_lines.append("⚠️ ALL ETF FETCH FAILED")

    return "\n".join(report_lines)


# =========================
# Main
# =========================
def main() -> None:
    message = build_report()
    print("[DEBUG] Final message:")
    print(message)
    send_discord(message)


if __name__ == "__main__":
    main()
