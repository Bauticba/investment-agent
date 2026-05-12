import requests
import yfinance as yf
from datetime import datetime, timedelta

# API pública de Argentina (https://argentinadatos.com)
AD_BASE = "https://api.argentinadatos.com/v1"

# Metadata estática de bonos argentinos conocidos
BOND_REGISTRY = {
    "TX26": {
        "name":          "Bono del Tesoro CER 2026",
        "maturity":      "2026-11-09",
        "coupon_annual": 0.04,    # 4% anual (2% semestral sobre capital ajustado CER)
        "amortization":  "bullet",
        "adjusts_by":    "CER",
        "currency":      "ARS",
    },
    "TX28": {
        "name":          "Bono del Tesoro CER 2028",
        "maturity":      "2028-11-09",
        "coupon_annual": 0.04,
        "amortization":  "bullet",
        "adjusts_by":    "CER",
        "currency":      "ARS",
    },
    "TX30": {
        "name":          "Bono del Tesoro CER 2030",
        "maturity":      "2030-11-09",
        "coupon_annual": 0.05,
        "amortization":  "bullet",
        "adjusts_by":    "CER",
        "currency":      "ARS",
    },
    "DICP": {
        "name":          "Bono Descuento CER",
        "maturity":      "2033-12-31",
        "coupon_annual": 0.0583,
        "amortization":  "scheduled",
        "adjusts_by":    "CER",
        "currency":      "ARS",
    },
    "CUAP": {
        "name":          "Cuasipar CER",
        "maturity":      "2045-10-03",
        "coupon_annual": 0.0306,
        "amortization":  "scheduled",
        "adjusts_by":    "CER",
        "currency":      "ARS",
    },
}


def get_bond_data(ticker: str, price_override: float = None) -> dict:
    """
    Obtiene datos de un bono argentino.
    Precio: override manual > IOL API > unavailable.
    Macro: argentinadatos.com (inflación, UVA, dólar oficial).
    """
    ticker = ticker.upper()
    meta   = BOND_REGISTRY.get(ticker, {})
    macro  = get_macro_data()

    # Precio: override > IOL > unavailable
    if price_override:
        market_price = price_override
        price_source = "manual"
    else:
        try:
            from data.iol import get_price
            iol_data = get_price(ticker)
            if iol_data and iol_data.get("ultimo_precio"):
                market_price = iol_data["ultimo_precio"]
                price_source = "iol"
            else:
                market_price = None
                price_source = "unavailable"
        except Exception:
            market_price = None
            price_source = "unavailable"

    return {
        "status":        "ok" if market_price else "no_price",
        "ticker":        ticker,
        "name":          meta.get("name", ticker),
        "asset_type":    "bono_argentino",
        "adjusts_by":    meta.get("adjusts_by", "CER"),
        "maturity":      meta.get("maturity"),
        "coupon_annual": meta.get("coupon_annual"),
        "amortization":  meta.get("amortization", "bullet"),
        "currency":      meta.get("currency", "ARS"),
        "market_price":  market_price,
        "price_source":  price_source,
        **macro,
    }


def get_macro_data() -> dict:
    """
    Trae indicadores macro desde argentinadatos.com (API pública, sin key).
    Datos disponibles: inflación mensual/anual, UVA, tipos de cambio.
    """
    inflation_item     = _last_item(f"{AD_BASE}/finanzas/indices/inflacion")
    inflation_monthly  = inflation_item.get("valor") if inflation_item else None
    inflation_date     = inflation_item.get("fecha") if inflation_item else None  # "YYYY-MM-DD"
    inflation_annual   = _last_value(f"{AD_BASE}/finanzas/indices/inflacionInteranual")
    uva                = _last_value(f"{AD_BASE}/finanzas/indices/uva")
    usd_oficial        = _last_value(f"{AD_BASE}/cotizaciones/dolares/oficial", key="venta")

    return {
        "inflation_monthly":   inflation_monthly,   # IPC mensual %
        "inflation_date":      inflation_date,       # fecha del último dato IPC ("YYYY-MM-DD")
        "inflation_annual":    inflation_annual,     # IPC interanual %
        "uva":                 uva,                  # valor UVA en ARS
        "usd_oficial":         usd_oficial,          # tipo de cambio oficial venta
    }


# --- helpers ---

def _last_item(url: str) -> dict | None:
    """Llama a la API y devuelve el último ítem completo (con fecha y valor)."""
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        if isinstance(data, list) and data:
            return data[-1]
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return None


def _last_value(url: str, key: str = "valor") -> float | None:
    """Llama a la API y devuelve el último valor de la lista."""
    item = _last_item(url)
    if item:
        return item.get(key) or item.get("valor")
    return None
