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
from core.ttl_cache import ttl_cache

load_dotenv(override=True)

BASE_URL = "https://api.invertironline.com"
MERCADO  = "bCBA"

_token_cache = {"access_token": None, "expires_at": 0}


@ttl_cache(seconds=300)  # 5 min — precios BYMA cambian durante el mercado
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


def get_portfolio_iol() -> list[dict]:
    """
    Trae las posiciones del portafolio real desde IOL.
    Retorna lista de activos. Cada activo tiene:
      titulo.simbolo, titulo.tipo, titulo.moneda,
      cantidad, ppc (precio promedio de compra), ultimoPrecio, valorizado.
    Usa el endpoint flat /api/v2/portafolio como primario (trae bCBA + nYSE).
    Si devuelve vacío, reintenta por mercado individual.
    """
    token = _get_token()
    if not token:
        return []

    def _extract_activos(data) -> list:
        if isinstance(data, dict) and "activos" in data:
            return data["activos"] or []
        if isinstance(data, list):
            result = []
            for item in data:
                if isinstance(item, dict) and "activos" in item:
                    result.extend(item["activos"] or [])
                elif isinstance(item, dict) and "titulo" in item:
                    result.append(item)
            return result
        return []

    headers = {"Authorization": f"Bearer {token}"}

    # Primero intentamos el endpoint flat (trae todos los mercados)
    try:
        r = requests.get(f"{BASE_URL}/api/v2/portafolio", headers=headers, timeout=10)
        if r.ok:
            activos = _extract_activos(r.json())
            if activos:
                return activos
    except Exception:
        pass

    # Fallback: consultar mercados por separado y deduplicar
    seen = set()
    activos = []
    for mercado in ("bCBA", "nYSE"):
        try:
            r = requests.get(
                f"{BASE_URL}/api/v2/portafolio/{mercado}", headers=headers, timeout=10
            )
            if not r.ok:
                continue
            for a in _extract_activos(r.json()):
                sym = (a.get("titulo") or {}).get("simbolo", "")
                if sym and sym not in seen:
                    seen.add(sym)
                    activos.append(a)
        except Exception:
            continue

    return activos


def get_account_balance() -> dict:
    """
    Intenta traer el saldo disponible de la cuenta (ARS y USD).
    Retorna {"ARS": float, "USD": float, "available": bool}.
    IOL puede devolver 500 en este endpoint — en ese caso retorna ceros con available=False.
    """
    token = _get_token()
    if not token:
        return {"ARS": 0.0, "USD": 0.0, "available": False}

    for path in ("/api/v2/cuenta/saldo", "/api/v2/cuenta/saldos"):
        try:
            r = requests.get(
                f"{BASE_URL}{path}",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10,
            )
            if not r.ok or not r.text.strip().startswith("{"):
                continue

            data = r.json()
            result = {"ARS": 0.0, "USD": 0.0, "available": True}
            cuentas = data if isinstance(data, list) else data.get("cuentas", [])
            for cuenta in cuentas:
                tipo = (cuenta.get("tipo") or "").lower()
                disponible = float(cuenta.get("disponible") or cuenta.get("saldo") or 0)
                if "dolar" in tipo or "usd" in tipo:
                    result["USD"] += disponible
                elif "peso" in tipo or "ars" in tipo:
                    result["ARS"] += disponible
            return result
        except Exception:
            continue

    return {"ARS": 0.0, "USD": 0.0, "available": False}


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
