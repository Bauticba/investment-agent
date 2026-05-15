"""
Decorator de cache con TTL (time-to-live) independiente de Streamlit.
Funciona en CLI, Streamlit y scripts de cron.

Uso:
    from core.ttl_cache import ttl_cache

    @ttl_cache(seconds=1800)       # 30 min
    def get_macro_data(): ...

    @ttl_cache(seconds=3600)       # 1h
    def get_argentina_news(): ...

TTLs recomendados por tipo de dato:
    Inflación / UVA / oficial  → 1800s  (30 min) — dato diario, no cambia intraday
    PF tasas bancarias         → 86400s (24h)    — actualización diaria del BCRA
    Noticias RSS               → 3600s  (1h)     — RSS se actualiza cada ~1h
    MEP / CCL / FX             → 600s   (10 min) — ya manejado en data/fx.py
    Precios IOL intraday       → 300s   (5 min)  — cambia frecuentemente en mercado
"""
import time
import functools


def ttl_cache(seconds: int):
    """
    Decorator que cachea el resultado de una función por `seconds` segundos.
    El cache es per-proceso (in-memory). Si la función recibe argumentos,
    el cache key incluye los argumentos.
    """
    def decorator(func):
        _cache: dict = {}

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            key = (args, tuple(sorted(kwargs.items())))
            if key in _cache:
                result, ts = _cache[key]
                if time.time() - ts < seconds:
                    return result
            result = func(*args, **kwargs)
            _cache[key] = (result, time.time())
            return result

        def cache_clear():
            _cache.clear()

        def cache_info():
            return {
                "ttl_seconds": seconds,
                "entries":     len(_cache),
                "keys":        list(_cache.keys()),
            }

        wrapper.cache_clear = cache_clear
        wrapper.cache_info  = cache_info
        return wrapper

    return decorator
