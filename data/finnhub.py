import os
import requests
from datetime import datetime, timedelta

FINNHUB_BASE = "https://finnhub.io/api/v1"


def get_fundamental(ticker: str) -> dict:
    key = os.getenv("FINNHUB_KEY")
    if not key:
        return {"status": "no_key"}

    try:
        resp = requests.get(
            f"{FINNHUB_BASE}/stock/metric",
            params={"symbol": ticker, "metric": "all", "token": key},
            timeout=10,
        )
        data = resp.json()
    except Exception as e:
        return {"status": "error", "message": str(e)}

    if "metric" not in data:
        return {"status": "no_data"}

    m = data["metric"]
    p = data.get("series", {}).get("annual", {})

    return {
        "status":          "ok",
        "pe_ratio":        m.get("peTTM"),
        "forward_pe":      m.get("peNormalizedAnnual"),
        "eps":             m.get("epsTTM"),
        "revenue_growth":  m.get("revenueGrowthTTMYoy"),
        "earnings_growth": m.get("epsGrowthTTMYoy"),
        "profit_margin":   m.get("netProfitMarginTTM"),
        "return_on_equity":m.get("roeTTM"),
        "debt_to_equity":  m.get("totalDebt/totalEquityAnnual"),
        "current_ratio":   m.get("currentRatioAnnual"),
        "free_cashflow":   m.get("freeCashFlowTTM"),
        "beta":            m.get("beta"),
        "52w_high":        m.get("52WeekHigh"),
        "52w_low":         m.get("52WeekLow"),
        "dividend_yield":  m.get("dividendYieldIndicatedAnnual"),
        "analyst_target":  None,
    }


def get_news(ticker: str, days: int = 7) -> list:
    key = os.getenv("FINNHUB_KEY")
    if not key:
        return []

    to_date   = datetime.now().strftime("%Y-%m-%d")
    from_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    try:
        resp = requests.get(
            f"{FINNHUB_BASE}/company-news",
            params={"symbol": ticker, "from": from_date, "to": to_date, "token": key},
            timeout=10,
        )
        articles = resp.json()
        if not isinstance(articles, list):
            return []
    except Exception:
        return []

    return [
        {
            "headline": a.get("headline", ""),
            "summary":  a.get("summary", "")[:300],
            "source":   a.get("source", ""),
            "date":     datetime.fromtimestamp(a.get("datetime", 0)).strftime("%Y-%m-%d"),
        }
        for a in articles[:10]
        if a.get("headline")
    ]
