"""
Fuente centralizada de tipos de cambio desde dolarapi.com.

Uso por módulo:
  CEDEARs / paridad BYMA → get_ccl()  (contado con liqui — referencia BYMA)
  Operaciones MEP en IOL  → get_mep()  (dólar bolsa)
  Referencia macro        → get_oficial()

No usar usd_oficial como aproximación de CCL — desde may 2026 hay spread real
entre oficial (~$1.390), MEP (~$1.425) y CCL (~$1.477).
"""
import requests
from datetime import datetime, timezone, timedelta

_BASE = "https://dolarapi.com/v1/dolares"
_ART  = timezone(timedelta(hours=-3))
_TTL  = 10 * 60  # 10 minutos

_cache: dict[str, dict] = {}


def _fetch(endpoint: str) -> dict:
    """Trae y cachea un endpoint de dolarapi.com."""
    import time
    cached = _cache.get(endpoint)
    if cached and time.time() - cached["_ts"] < _TTL:
        return cached

    try:
        resp = requests.get(f"{_BASE}/{endpoint}", timeout=8)
        if resp.ok:
            d = resp.json()
            price = (d.get("venta") or d.get("compra")) or None
            fecha_utc = d.get("fechaActualizacion", "")
            fecha_art = ""
            data_dt   = None
            if fecha_utc:
                try:
                    data_dt   = datetime.fromisoformat(fecha_utc.replace("Z", "+00:00"))
                    fecha_art = data_dt.astimezone(_ART).strftime("%d/%m %H:%M ART")
                except Exception:
                    fecha_art = fecha_utc[:16]
            # Stale solo si no pudimos obtener precio (falla real de API).
            # Datos de "ayer" son normales fuera del horario de mercado.
            stale = price is None
            result = {
                "price":  price,
                "compra": d.get("compra"),
                "venta":  d.get("venta"),
                "fecha":  fecha_art,
                "source": "dolarapi.com",
                "stale":  stale,
                "_ts":    time.time(),
            }
            _cache[endpoint] = result
            return result
    except Exception:
        pass
    return {"price": None, "compra": None, "venta": None, "fecha": "", "source": "dolarapi.com", "stale": True, "_ts": 0}


def get_ccl() -> dict:
    """Contado con liquidación — referencia para paridad BYMA (CEDEARs, MERVAL vs ADR)."""
    return _fetch("contadoconliqui")


def get_mep() -> dict:
    """Dólar bolsa / MEP — precio de operaciones MEP en IOL."""
    return _fetch("bolsa")


def get_oficial() -> dict:
    """Dólar oficial — referencia macro / crawling peg."""
    return _fetch("oficial")


def ccl_price(fallback: float = 1400.0) -> float:
    """Retorna el precio de venta del CCL, con fallback si la API no responde."""
    return get_ccl().get("price") or fallback


def mep_price(fallback: float = 1400.0) -> float:
    """Retorna el precio de venta del MEP, con fallback si la API no responde."""
    return get_mep().get("price") or fallback


def oficial_price(fallback: float = 1400.0) -> float:
    """Retorna el precio de venta del dólar oficial, con fallback."""
    return get_oficial().get("price") or fallback
