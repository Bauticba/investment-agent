import os
import requests

AV_BASE = "https://www.alphavantage.co/query"


def get_fundamental(ticker: str) -> dict:
    key = os.getenv("ALPHA_VANTAGE_KEY")
    if not key:
        return {"status": "no_key"}

    try:
        resp = requests.get(
            AV_BASE,
            params={"function": "OVERVIEW", "symbol": ticker, "apikey": key},
            timeout=10,
        )
        data = resp.json()
    except Exception as e:
        return {"status": "error", "message": str(e)}

    if "Note" in data or "Information" in data:
        return {"status": "rate_limited"}
    if not data.get("Symbol"):
        return {"status": "no_data"}

    return {
        "status": "ok",
        "company_name":    data.get("Name"),
        "sector":          data.get("Sector"),
        "industry":        data.get("Industry"),
        "description":     data.get("Description", "")[:500],
        "pe_ratio":        _f(data.get("PERatio")),
        "forward_pe":      _f(data.get("ForwardPE")),
        "eps":             _f(data.get("EPS")),
        "revenue_growth":  _f(data.get("QuarterlyRevenueGrowthYOY")),
        "earnings_growth": _f(data.get("QuarterlyEarningsGrowthYOY")),
        "profit_margin":   _f(data.get("ProfitMargin")),
        "return_on_equity":_f(data.get("ReturnOnEquityTTM")),
        "debt_to_equity":  _f(data.get("DebtToEquityRatio")),
        "current_ratio":   _f(data.get("CurrentRatioTTM")),
        "free_cashflow":   _f(data.get("OperatingCashflowTTM")),
        "dividend_yield":  _f(data.get("DividendYield")),
        "beta":            _f(data.get("Beta")),
        "analyst_target":  _f(data.get("AnalystTargetPrice")),
        "52w_high":        _f(data.get("52WeekHigh")),
        "52w_low":         _f(data.get("52WeekLow")),
    }


def _f(val) -> float | None:
    try:
        v = float(val)
        return None if v == 0 else v
    except (TypeError, ValueError):
        return None
