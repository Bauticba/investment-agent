"""
Datos de acciones del panel líder del MERVAL (BCBA).
Precios vía IOL API (mercado bCBA). Fallback: sin precio disponible.
Para acciones con ADR en USA, calcula el CCL implícito.
"""
import yfinance as yf
from data.argentina import get_macro_data
from data.fx import ccl_price

# Tickers BYMA/BCBA tal como los usa IOL.
# usd_adr: ticker NYSE/Nasdaq. adr_ratio: acciones locales por cada 1 ADR.
# CCL implícito = (precio_ARS × adr_ratio) / precio_ADR_USD
# Ratios verificados mayo 2026: GGAL×10, YPF×1, BMA×10, PAM×25, TEO×5, BBAR×3, LOMA×5
MERVAL_REGISTRY = {
    "GGAL":  {"name": "Grupo Financiero Galicia", "sector": "finance",        "usd_adr": "GGAL", "adr_ratio": 10},
    "YPFD":  {"name": "YPF S.A.",                 "sector": "energy",         "usd_adr": "YPF",  "adr_ratio": 1},
    "BMA":   {"name": "Banco Macro",              "sector": "finance",        "usd_adr": "BMA",  "adr_ratio": 10},
    "PAMP":  {"name": "Pampa Energía",            "sector": "energy",         "usd_adr": "PAM",  "adr_ratio": 25},
    "TECO2": {"name": "Telecom Argentina",        "sector": "communications", "usd_adr": "TEO",  "adr_ratio": 5},
    "BBAR":  {"name": "BBVA Argentina",           "sector": "finance",        "usd_adr": "BBAR", "adr_ratio": 3},
    "LOMA":  {"name": "Loma Negra",               "sector": "materials",      "usd_adr": "LOMA", "adr_ratio": 5},
    "TXAR":  {"name": "Ternium Argentina",        "sector": "materials",      "usd_adr": None,   "adr_ratio": None},
    "ALUA":  {"name": "Aluar Aluminio",           "sector": "materials",      "usd_adr": None,   "adr_ratio": None},
    "MIRG":  {"name": "Mirgor S.A.",              "sector": "consumer",       "usd_adr": None,   "adr_ratio": None},
}


def get_merval_data(ticker: str, price_ars_override: float = None, macro: dict = None) -> dict:
    """
    Devuelve datos de una acción MERVAL: precio ARS vía IOL, variación del día,
    CCL implícito (si tiene ADR), y contexto macro.
    Acepta macro pre-cargado para evitar llamadas redundantes en bulk.
    """
    ticker = ticker.upper()
    meta   = MERVAL_REGISTRY.get(ticker)
    if not meta:
        return {
            "status":  "unknown",
            "ticker":  ticker,
            "message": f"{ticker} no está en MERVAL_REGISTRY. Agregarlo en data/merval.py",
        }

    if macro is None:
        macro = get_macro_data()
    ccl = ccl_price(fallback=macro.get("usd_oficial") or 1400)

    if price_ars_override:
        market_price  = price_ars_override
        price_source  = "manual"
        variacion_pct = None
        apertura      = None
        maximo        = None
        minimo        = None
    else:
        iol = _iol_price(ticker)
        if iol:
            market_price  = float(iol["ultimo_precio"])
            variacion_pct = iol.get("variacion_pct")
            apertura      = iol.get("apertura")
            maximo        = iol.get("maximo")
            minimo        = iol.get("minimo")
            price_source  = "iol"
        else:
            market_price  = None
            variacion_pct = None
            apertura      = None
            maximo        = None
            minimo        = None
            price_source  = "unavailable"

    # CCL implícito = (precio_ARS × adr_ratio) / precio_ADR_USD
    ccl_implicit   = None
    usd_adr_price  = None
    adr_ticker     = meta.get("usd_adr")
    adr_ratio      = meta.get("adr_ratio")
    if adr_ticker and adr_ratio and market_price:
        usd_adr_price = _adr_price(adr_ticker)
        if usd_adr_price:
            ccl_implicit = round((market_price * adr_ratio) / usd_adr_price, 2)

    return {
        "status":         "ok" if market_price else "sin_precio",
        "ticker":         ticker,
        "name":           meta["name"],
        "asset_type":     "merval",
        "sector":         meta["sector"],
        "usd_adr":        adr_ticker,
        "adr_ratio":      adr_ratio,
        "market_price_ars": market_price,
        "variacion_pct":  variacion_pct,
        "apertura":       apertura,
        "maximo":         maximo,
        "minimo":         minimo,
        "price_source":   price_source,
        "usd_adr_price":  usd_adr_price,
        "ccl_implicit":   ccl_implicit,
        "ccl_oficial":    ccl,
        "macro":          macro,
    }


def get_all_merval_data() -> list[dict]:
    """Devuelve datos de todas las acciones del MERVAL registry con precio disponible."""
    macro   = get_macro_data()  # una sola llamada HTTP para todos
    results = []
    for ticker in MERVAL_REGISTRY:
        data = get_merval_data(ticker, macro=macro)
        if data.get("status") == "ok":
            results.append(data)
    return results


# --- helpers ---

def _iol_price(ticker: str) -> dict | None:
    try:
        from data.iol import get_price
        data = get_price(ticker)
        if data and data.get("ultimo_precio"):
            return data
    except Exception:
        pass
    return None


def _adr_price(adr_ticker: str) -> float | None:
    try:
        info = yf.Ticker(adr_ticker).info
        return info.get("currentPrice") or info.get("regularMarketPrice")
    except Exception:
        return None
