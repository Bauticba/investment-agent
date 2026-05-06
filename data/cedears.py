import json
import os
import yfinance as yf
from data.argentina import get_macro_data

# Ratio = cantidad de CEDEARs necesarios para equivaler a 1 acción del subyacente USA.
# Precio paridad ARS = precio_USD / ratio × CCL
# Fuente: BYMA / Bull Market. Verificar periódicamente ante splits o cambios corporativos.
CEDEAR_REGISTRY = {
    "AAPL":  {"us_ticker": "AAPL",  "ratio": 10,  "name": "Apple Inc."},
    "MSFT":  {"us_ticker": "MSFT",  "ratio": 8,   "name": "Microsoft Corp."},
    "NVDA":  {"us_ticker": "NVDA",  "ratio": 35,  "name": "NVIDIA Corp."},
    "GOOGL": {"us_ticker": "GOOGL", "ratio": 20,  "name": "Alphabet Inc."},
    "AMZN":  {"us_ticker": "AMZN",  "ratio": 7,   "name": "Amazon.com Inc."},
    "META":  {"us_ticker": "META",  "ratio": 3,   "name": "Meta Platforms Inc."},
    "TSLA":  {"us_ticker": "TSLA",  "ratio": 10,  "name": "Tesla Inc."},
    "JPM":   {"us_ticker": "JPM",   "ratio": 2,   "name": "JPMorgan Chase & Co."},
    "V":     {"us_ticker": "V",     "ratio": 2,   "name": "Visa Inc."},
    "MA":    {"us_ticker": "MA",    "ratio": 2,   "name": "Mastercard Inc."},
    "COST":  {"us_ticker": "COST",  "ratio": 2,   "name": "Costco Wholesale Corp."},
    "XOM":   {"us_ticker": "XOM",   "ratio": 2,   "name": "ExxonMobil Corp."},
    "CVX":   {"us_ticker": "CVX",   "ratio": 2,   "name": "Chevron Corp."},
    "JNJ":   {"us_ticker": "JNJ",   "ratio": 2,   "name": "Johnson & Johnson"},
    "ABBV":  {"us_ticker": "ABBV",  "ratio": 2,   "name": "AbbVie Inc."},
    "UNH":   {"us_ticker": "UNH",   "ratio": 5,   "name": "UnitedHealth Group Inc."},
}


def get_cedear_data(ticker: str, price_ars_override: float = None) -> dict:
    """
    Devuelve datos completos de un CEDEAR:
    precio en ARS (override > BYMA > paridad estimada),
    paridad teórica, premium/discount y CCL implícito.
    """
    ticker = ticker.upper()
    meta   = CEDEAR_REGISTRY.get(ticker)
    if not meta:
        return {
            "status":  "unknown",
            "ticker":  ticker,
            "message": f"{ticker} no está en el registro de CEDEARs. Agregarlo en data/cedears.py",
        }

    macro    = get_macro_data()
    ccl      = macro.get("usd_oficial") or 1400  # CCL ≈ oficial (mercado unificado desde abr 2025)
    ratio    = meta["ratio"]

    # Precio subyacente en USD
    us_price = _us_price(ticker)

    # Precio de paridad teórica en ARS
    parity = round(us_price / ratio * ccl, 2) if us_price else None

    # Precio de mercado en ARS: override > BYMA > paridad estimada
    if price_ars_override:
        market_price = price_ars_override
        price_source = "manual"
    else:
        byma_price = _byma_price(ticker)
        if byma_price:
            market_price = byma_price
            price_source = "iol_byma"
        else:
            market_price = parity
            price_source = "estimated_parity"

    # Métricas de paridad
    premium_pct  = round((market_price - parity) / parity * 100, 1) if (market_price and parity) else None
    ccl_implicit = round(market_price * ratio / us_price, 2)         if (market_price and us_price) else None

    return {
        "status":               "ok",
        "ticker":               ticker,
        "name":                 meta["name"],
        "asset_type":           "cedear",
        "us_ticker":            meta["us_ticker"],
        "ratio":                ratio,
        "us_price_usd":         us_price,
        "parity_price_ars":     parity,
        "market_price_ars":     market_price,
        "price_source":         price_source,
        "premium_discount_pct": premium_pct,
        "ccl_implicit":         ccl_implicit,
        "ccl_oficial":          ccl,
        "macro":                macro,
    }


def get_top_cedears(max_count: int = 3, min_score: float = 6.0) -> list[dict]:
    """
    Carga los análisis cacheados del storage y devuelve los mejores CEDEARs
    ordenados por score CEO. Usado por invest_ars.py para dar picks específicos.
    """
    macro = get_macro_data()
    ccl   = macro.get("usd_oficial") or 1400
    picks = []

    for ticker, meta in CEDEAR_REGISTRY.items():
        cache_file = f"storage/{ticker}_analysis.json"
        if not os.path.exists(cache_file):
            continue

        with open(cache_file) as f:
            analysis = json.load(f)

        if analysis.get("status") != "ok":
            continue

        ceo     = analysis.get("ceo_thesis", {})
        score   = ceo.get("ceo_score") or 0
        verdict = ceo.get("final_verdict", "")

        if score < min_score:
            continue

        us_price = analysis.get("price", {}).get("current_price")
        parity   = round(us_price / meta["ratio"] * ccl, 2) if us_price else None

        picks.append({
            "ticker":           ticker,
            "name":             meta["name"],
            "ratio":            meta["ratio"],
            "verdict":          verdict,
            "score":            score,
            "conviction":       ceo.get("conviction"),
            "us_price_usd":     us_price,
            "parity_price_ars": parity,
            "analysis_date":    analysis.get("date"),
            "thesis":           ceo.get("thesis", "")[:200],
            "how_to_buy":       f"Bull Market > Cotizaciones > CEDEARs > {ticker} > Comprar",
        })

    picks.sort(key=lambda x: x.get("score", 0), reverse=True)
    return picks[:max_count]


# --- helpers ---

def _us_price(ticker: str) -> float | None:
    try:
        info = yf.Ticker(ticker).info
        return info.get("currentPrice") or info.get("regularMarketPrice")
    except Exception:
        return None


def _byma_price(ticker: str) -> float | None:
    # Intentar IOL primero (precio real BYMA)
    try:
        from data.iol import get_price
        data = get_price(ticker)
        if data and data.get("ultimo_precio"):
            return round(float(data["ultimo_precio"]), 2)
    except Exception:
        pass

    # Fallback: yfinance .BA
    try:
        info = yf.Ticker(f"{ticker}.BA").info
        price = info.get("currentPrice") or info.get("regularMarketPrice") or info.get("previousClose")
        if price:
            return round(float(price), 2)
        hist = yf.Ticker(f"{ticker}.BA").history(period="5d")
        if not hist.empty:
            return round(float(hist["Close"].iloc[-1]), 2)
    except Exception:
        pass
    return None
