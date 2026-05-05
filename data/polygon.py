import os
import requests
from datetime import datetime, timedelta

POLYGON_BASE = "https://api.polygon.io"


def get_technical(ticker: str) -> dict:
    key = os.getenv("POLYGON_KEY")
    if not key:
        return {"status": "no_key"}

    to_date   = datetime.now().strftime("%Y-%m-%d")
    from_date = (datetime.now() - timedelta(days=210)).strftime("%Y-%m-%d")

    try:
        aggs = _get_aggs(ticker, from_date, to_date, key)
        if not aggs:
            return {"status": "no_data"}

        closes  = [r["c"] for r in aggs]
        volumes = [r["v"] for r in aggs]
        highs   = [r["h"] for r in aggs]
        lows    = [r["l"] for r in aggs]

        current_price = closes[-1] if closes else None
        w52_high = max(highs) if highs else None
        w52_low  = min(lows)  if lows  else None
        pct_vs_high = (
            round(((current_price - w52_high) / w52_high) * 100, 2)
            if current_price and w52_high else None
        )

        return {
            "status":               "ok",
            "price_history_6mo":    closes[-30:],
            "volume_history_6mo":   volumes[-30:],
            "ma_20":                _get_sma(ticker, 20,  key),
            "ma_50":                _get_sma(ticker, 50,  key),
            "ma_200":               _get_sma(ticker, 200, key),
            "rsi_14":               _get_rsi(ticker, key),
            "52w_high":             w52_high,
            "52w_low":              w52_low,
            "price_vs_52w_high_pct": pct_vs_high,
            "current_price":        current_price,
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}


# --- Helpers ---

def _get_aggs(ticker, from_date, to_date, key) -> list:
    resp = requests.get(
        f"{POLYGON_BASE}/v2/aggs/ticker/{ticker}/range/1/day/{from_date}/{to_date}",
        params={"adjusted": "true", "sort": "asc", "limit": 210, "apiKey": key},
        timeout=10,
    )
    data = resp.json()
    return data.get("results", []) if data.get("resultsCount", 0) > 0 else []


def _get_sma(ticker, window, key) -> float | None:
    resp = requests.get(
        f"{POLYGON_BASE}/v1/indicators/sma/{ticker}",
        params={
            "timespan": "day", "adjusted": "true", "window": window,
            "series_type": "close", "order": "desc", "limit": 1, "apiKey": key,
        },
        timeout=10,
    )
    try:
        return round(resp.json()["results"]["values"][0]["value"], 2)
    except (KeyError, IndexError, TypeError):
        return None


def _get_rsi(ticker, key) -> float | None:
    resp = requests.get(
        f"{POLYGON_BASE}/v1/indicators/rsi/{ticker}",
        params={
            "timespan": "day", "adjusted": "true", "window": 14,
            "series_type": "close", "order": "desc", "limit": 1, "apiKey": key,
        },
        timeout=10,
    )
    try:
        return round(resp.json()["results"]["values"][0]["value"], 2)
    except (KeyError, IndexError, TypeError):
        return None


