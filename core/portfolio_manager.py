"""
CRUD para my_portfolio.json.
Usado por main.py (comprar/vender) y la UI de Streamlit.
"""
import json
from datetime import date

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
