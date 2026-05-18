"""
CRUD para my_portfolio.json.
Usado por main.py (comprar/vender) y la UI de Streamlit.
"""
import json
from datetime import date, datetime

PORTFOLIO_FILE = "my_portfolio.json"

_DEFAULTS = {
    "broker": "Invertir Online (IOL)",
    "positions": [],
    "cash": {"USD": 0, "ARS": 0},
}


def get_portfolio() -> dict:
    try:
        with open(PORTFOLIO_FILE) as f:
            return json.load(f)
    except FileNotFoundError:
        return dict(_DEFAULTS)


def save_portfolio(portfolio: dict):
    with open(PORTFOLIO_FILE, "w") as f:
        json.dump(portfolio, f, indent=2, ensure_ascii=False)


def add_position(
    ticker: str,
    shares: float,
    avg_price: float,
    currency: str = "USD",
    asset_type: str | None = None,
    notes: str = "",
) -> str:
    """
    Agrega una posición nueva o promedia con la existente (precio promedio ponderado).
    Retorna 'added' o 'updated'.
    """
    portfolio  = get_portfolio()
    positions  = portfolio.setdefault("positions", [])
    ticker     = ticker.upper()
    existing   = next((p for p in positions if p["ticker"] == ticker), None)

    if existing:
        old_shares    = existing["shares"]
        old_price     = existing["avg_buy_price"]
        total_shares  = old_shares + shares
        new_avg       = (old_shares * old_price + shares * avg_price) / total_shares
        existing["shares"]        = round(total_shares, 4)
        existing["avg_buy_price"] = round(new_avg, 4)
        if notes:
            existing["notes"] = notes
        action = "updated"
    else:
        pos = {
            "ticker":        ticker,
            "shares":        shares,
            "avg_buy_price": avg_price,
            "currency":      currency,
            "notes":         notes,
        }
        if asset_type:
            pos["asset_type"] = asset_type
        positions.append(pos)
        action = "added"

    save_portfolio(portfolio)
    return action


def sell_position(ticker: str, shares: float) -> tuple[bool, str]:
    """
    Reduce la posición. Si shares >= posición total, la elimina completa.
    Retorna (ok, mensaje).
    """
    portfolio = get_portfolio()
    positions = portfolio.setdefault("positions", [])
    ticker    = ticker.upper()
    existing  = next((p for p in positions if p["ticker"] == ticker), None)

    if not existing:
        return False, f"{ticker} no está en el portafolio."

    if shares >= existing["shares"]:
        portfolio["positions"] = [p for p in positions if p["ticker"] != ticker]
        save_portfolio(portfolio)
        return True, f"{ticker} eliminado del portafolio (posición cerrada)."

    existing["shares"] = round(existing["shares"] - shares, 4)
    save_portfolio(portfolio)
    return True, f"{ticker}: quedan {existing['shares']} unidades."


def remove_position(ticker: str) -> bool:
    """Elimina la posición completa. Retorna True si existía."""
    portfolio = get_portfolio()
    positions = portfolio.setdefault("positions", [])
    ticker    = ticker.upper()
    before    = len(positions)
    portfolio["positions"] = [p for p in positions if p["ticker"] != ticker]
    if len(portfolio["positions"]) < before:
        save_portfolio(portfolio)
        return True
    return False


def update_cash(usd: float | None = None, ars: float | None = None):
    portfolio = get_portfolio()
    cash      = portfolio.setdefault("cash", {"USD": 0, "ARS": 0})
    if usd is not None:
        cash["USD"] = usd
    if ars is not None:
        cash["ARS"] = ars
    save_portfolio(portfolio)


def sync_from_iol() -> dict | None:
    """
    Trae posiciones reales desde IOL API y las convierte al formato interno.
    Detecta tipo de activo (cedear/bono_argentino/bono_hard_dollar/on_usd/accion_merval)
    a partir de los registros internos. Retorna el portafolio listo para usar,
    o None si IOL no está disponible o no responde.
    """
    from data.iol import get_portfolio_iol, get_account_balance, is_available
    from data.cedears import CEDEAR_REGISTRY
    from data.argentina import BOND_REGISTRY
    from data.instruments_ar import HARD_DOLLAR_BOND_REGISTRY, ON_REGISTRY, MERVAL_STOCKS

    if not is_available():
        return None

    activos = get_portfolio_iol()
    if activos is None:
        return None

    positions = []
    for activo in activos:
        titulo   = activo.get("titulo") or {}
        ticker   = (titulo.get("simbolo") or "").upper().strip()
        if not ticker:
            continue

        cantidad        = float(activo.get("cantidad") or 0)
        precio_promedio = float(activo.get("ppc") or activo.get("precioPromedio") or 0)
        moneda_raw     = (titulo.get("moneda") or "").lower()

        # Moneda tal como la reporta IOL (siempre en ARS para instrumentos domésticos,
        # incluyendo ONs y bonos hard dollar que cotizan en ARS en BYMA).
        currency = "USD" if ("dolar" in moneda_raw or "usd" in moneda_raw) else "ARS"

        if ticker in CEDEAR_REGISTRY:
            asset_type = "cedear"
        elif ticker in BOND_REGISTRY:
            asset_type = "bono_argentino"
        elif ticker in HARD_DOLLAR_BOND_REGISTRY:
            asset_type = "bono_hard_dollar"
        elif ticker in ON_REGISTRY:
            asset_type = "on_usd"
        elif ticker in MERVAL_STOCKS:
            asset_type = "accion_merval"
        elif ticker.startswith("IOL"):
            # IOL money market / FCI funds (IOLCAMA, IOLCAMB, etc.)
            asset_type = "fci_mm"
        else:
            asset_type = None

        # IOL portfolio endpoint includes current price and total value
        ultimo_precio = float(activo.get("ultimoPrecio") or 0)
        valorizado    = float(activo.get("valorizado") or 0)

        pos = {
            "ticker":        ticker,
            "shares":        cantidad,
            "avg_buy_price": precio_promedio,
            "currency":      currency,
            "notes":         "sincronizado desde IOL",
        }
        if asset_type:
            pos["asset_type"] = asset_type
        # For FCIs, persist the IOL-reported value so analysis can use it without API calls
        if asset_type == "fci_mm" and (ultimo_precio or valorizado):
            pos["current_price_ars"] = ultimo_precio
            pos["current_value_ars"] = valorizado or round(cantidad * precio_promedio, 2)

        positions.append(pos)

    # IOL /cuenta/saldo devuelve 500 — preservar cash existente del archivo local
    existing_cash = get_portfolio().get("cash", {"USD": 0, "ARS": 0})

    return {
        "broker":          "Invertir Online (IOL)",
        "positions":       positions,
        "cash":            existing_cash,
        "synced_from_iol": True,
        "sync_timestamp":  datetime.now().isoformat(timespec="seconds"),
    }
