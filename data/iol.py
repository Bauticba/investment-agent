"""
Cliente para la API de Invertir Online (IOL).
Documentación: https://api.invertironline.com

Credenciales en .env: IOL_USERNAME, IOL_PASSWORD
Token OAuth2 válido por 1200 segundos — se renueva automáticamente.
"""
import os
import time
import requests
from dotenv import load_dotenv

load_dotenv(override=True)

BASE_URL = "https://api.invertironline.com"
MERCADO  = "bCBA"

_token_cache = {"access_token": None, "expires_at": 0}


def get_price(simbolo: str) -> dict | None:
    """
    Devuelve el último precio de un activo disponible en BYMA (bCBA).
    Funciona para: acciones MERVAL, CEDEARs, bonos soberanos (TX26/GD30/AL30...),
    bonos hard dollar, y ONs disponibles.

    Retorna dict con: simbolo, ultimo_precio, variacion_pct, apertura, maximo,
    minimo, fecha, o None si no se encuentra.
    """
    token = _get_token()
    if not token:
        return None

    try:
        r = requests.get(
            f"{BASE_URL}/api/v2/titulos/{simbolo.upper()}/cotizacion",
            params={"mercado": MERCADO},
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        if not r.ok:
            return None

        d = r.json()
        precio = d.get("ultimoPrecio")
        if precio is None:
            return None

        return {
            "simbolo":       simbolo.upper(),
            "ultimo_precio": precio,
            "variacion_pct": d.get("variacion"),
            "apertura":      d.get("apertura"),
            "maximo":        d.get("maximo"),
            "minimo":        d.get("minimo"),
            "fecha":         str(d.get("fechaHora", ""))[:10],
            "fuente":        "iol",
        }
    except Exception:
        return None


def get_prices_bulk(simbolos: list[str]) -> dict[str, dict]:
    """
    Trae precios para una lista de símbolos.
    Retorna dict {simbolo: price_dict} — omite los que fallan.
    """
    results = {}
    for sym in simbolos:
        data = get_price(sym)
        if data:
            results[sym.upper()] = data
    return results


def is_available() -> bool:
    """Retorna True si las credenciales IOL están configuradas y funcionan."""
    return _get_token() is not None


# ─── helpers ──────────────────────────────────────────────────────────────────

def _get_token() -> str | None:
    """Devuelve un token válido, renovándolo si expiró."""
    if _token_cache["access_token"] and time.time() < _token_cache["expires_at"]:
        return _token_cache["access_token"]

    user = os.getenv("IOL_USERNAME")
    pwd  = os.getenv("IOL_PASSWORD")
    if not user or not pwd:
        return None

    try:
        r = requests.post(
            f"{BASE_URL}/token",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={"username": user, "password": pwd, "grant_type": "password"},
            timeout=10,
        )
        if not r.ok:
            return None

        data = r.json()
        _token_cache["access_token"] = data["access_token"]
        _token_cache["expires_at"]   = time.time() + data.get("expires_in", 1200) - 60
        return _token_cache["access_token"]
    except Exception:
        return None
