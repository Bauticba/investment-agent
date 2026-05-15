import requests
import yfinance as yf
from datetime import datetime, timedelta, timezone

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
    Incluye '_sources' con metadata de calidad por dato (source, fetched_at, stale).
    """
    now_str = _now_art()

    inflation_item    = _last_item(f"{AD_BASE}/finanzas/indices/inflacion")
    inflation_monthly = inflation_item.get("valor") if inflation_item else None
    inflation_date    = inflation_item.get("fecha") if inflation_item else None

    inflation_annual_item = _last_item(f"{AD_BASE}/finanzas/indices/inflacionInteranual")
    inflation_annual      = inflation_annual_item.get("valor") if inflation_annual_item else None

    uva_item  = _last_item(f"{AD_BASE}/finanzas/indices/uva")
    uva       = uva_item.get("valor") if uva_item else None
    uva_date  = uva_item.get("fecha") if uva_item else None

    ofic_item   = _last_item(f"{AD_BASE}/cotizaciones/dolares/oficial")
    usd_oficial = (ofic_item.get("venta") or ofic_item.get("valor")) if ofic_item else None
    ofic_date   = ofic_item.get("fecha") if ofic_item else None

    # Stale: True si el fetch falló (valor None). El dato de inflación puede tener
    # 30-45 días de antigüedad (ciclo INDEC) pero eso es normal, no es stale.
    # UVA y oficial se publican diariamente — stale si la fecha del dato tiene >2 días.
    def _days_old(date_str):
        if not date_str:
            return 999
        try:
            d = datetime.strptime(date_str[:10], "%Y-%m-%d")
            return (datetime.now() - d).days
        except Exception:
            return 999

    return {
        "inflation_monthly": inflation_monthly,
        "inflation_date":    inflation_date,
        "inflation_annual":  inflation_annual,
        "uva":               uva,
        "usd_oficial":       usd_oficial,
        "_sources": {
            "inflation": {
                "source":          "argentinadatos→INDEC",
                "fetched_at":      now_str,
                "data_date":       inflation_date,
                "stale":           inflation_monthly is None,
            },
            "uva": {
                "source":          "argentinadatos→BCRA",
                "fetched_at":      now_str,
                "data_date":       uva_date,
                "stale":           uva is None or _days_old(uva_date) > 2,
            },
            "usd_oficial": {
                "source":          "argentinadatos",
                "fetched_at":      now_str,
                "data_date":       ofic_date,
                "stale":           usd_oficial is None or _days_old(ofic_date) > 2,
            },
        },
    }


# --- helpers ---

def _now_art() -> str:
    """Timestamp actual en hora Argentina (ART = UTC-3)."""
    art = timezone(timedelta(hours=-3))
    return datetime.now(art).strftime("%Y-%m-%dT%H:%M:%S-03:00")


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
