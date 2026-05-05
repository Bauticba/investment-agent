from datetime import datetime, date
from data.argentina import get_macro_data, BOND_REGISTRY

# TNA plazo fijo estimada: con inflación ~32% anual (mayo 2026), el BCRA fija tasa referencial
# levemente por debajo. Intentamos traerla; si falla, usamos esta estimación.
TNA_PF_FALLBACK = 32.0


def get_instruments_universe(macro: dict = None) -> list[dict]:
    """
    Devuelve el universo completo de instrumentos en ARS disponibles en Bull Market,
    con características y rendimientos actualizados al contexto macro.
    """
    if macro is None:
        macro = get_macro_data()

    inflation_monthly = macro.get("inflation_monthly") or 3.5
    usd_oficial       = macro.get("usd_oficial") or 1400
    uva               = macro.get("uva")
    tna_pf            = _fetch_tna_pf() or TNA_PF_FALLBACK
    tea_pf            = round(((1 + tna_pf / 100 / 365) ** 365 - 1) * 100, 1)
    today             = date.today()

    instruments = []

    # --- Bonos CER (ajustados por inflación) ---
    for ticker, meta in BOND_REGISTRY.items():
        mat_date  = datetime.strptime(meta["maturity"], "%Y-%m-%d").date()
        days_left = (mat_date - today).days
        if days_left < 0:
            continue

        risk = "bajo-medio" if days_left <= 365 else "medio"
        recommended = ["bajo", "moderado", "alto"] if days_left <= 365 else ["moderado", "alto"]

        instruments.append({
            "id":               ticker.lower(),
            "ticker":           ticker,
            "name":             meta["name"],
            "type":             "bono_cer",
            "currency":         "ARS",
            "adjusts_by":       "CER (inflación)",
            "return_estimate":  f"CER + {meta['coupon_annual']*100:.0f}% anual (rendimiento real positivo sobre inflación)",
            "maturity":         meta["maturity"],
            "days_to_maturity": days_left,
            "liquidity":        "alta (mercado secundario BYMA, T+1)",
            "min_investment_ars": 1000,
            "sovereign_risk":   True,
            "bank_risk":        False,
            "risk_level":       risk,
            "recommended_for":  recommended,
            "how_to_buy":       f"Bull Market > Cotizaciones > Bonos > {ticker} > Comprar",
            "notes":            "Precio debe ingresarse manualmente desde Bull Market. Capital ajustado diariamente por CER.",
        })

    # --- Plazo fijo UVA ---
    instruments.append({
        "id":               "plazo_fijo_uva",
        "ticker":           None,
        "name":             "Plazo Fijo UVA",
        "type":             "plazo_fijo_uva",
        "currency":         "ARS",
        "adjusts_by":       "UVA (equivalente a inflación CPI)",
        "return_estimate":  "CER + ~1% (cobertura total de inflación, sin riesgo precio de mercado)",
        "maturity":         "mínimo 90 días (sin rescate anticipado)",
        "days_to_maturity": 90,
        "liquidity":        "baja — inmovilizado 90 días",
        "min_investment_ars": 1000,
        "sovereign_risk":   False,
        "bank_risk":        True,
        "risk_level":       "bajo",
        "recommended_for":  ["bajo", "moderado"],
        "how_to_buy":       "Bull Market > Ahorro > Plazo Fijo > UVA > Simular y confirmar",
        "notes":            f"Garantizado por SEDESA hasta $6M ARS. UVA actual: ${uva:,.2f}. Sin riesgo precio (a diferencia de los bonos)." if uva else "Garantizado por SEDESA hasta $6M ARS. Sin riesgo precio.",
    })

    # --- Plazo fijo tradicional ---
    instruments.append({
        "id":               "plazo_fijo_tna",
        "ticker":           None,
        "name":             "Plazo Fijo Tradicional (tasa fija)",
        "type":             "plazo_fijo",
        "currency":         "ARS",
        "adjusts_by":       "tasa fija TNA",
        "return_estimate":  f"~{tna_pf:.0f}% TNA (~{tea_pf:.0f}% TEA) — RIESGO: inflación ({inflation_monthly:.1f}%/mes) puede superarla",
        "maturity":         "30 a 365 días",
        "days_to_maturity": 30,
        "liquidity":        "baja — inmovilizado al plazo pactado",
        "min_investment_ars": 1000,
        "sovereign_risk":   False,
        "bank_risk":        True,
        "risk_level":       "bajo-medio (riesgo inflacionario real)",
        "recommended_for":  ["bajo"],
        "how_to_buy":       "Bull Market > Ahorro > Plazo Fijo > Tradicional",
        "notes":            f"Solo conveniente si inflación baja de {tna_pf/12:.1f}%/mes. Actualmente inflación = {inflation_monthly:.1f}%/mes → el PF tradicional PIERDE en términos reales.",
    })

    # --- Dólar MEP ---
    instruments.append({
        "id":               "dolar_mep",
        "ticker":           "AL30 / GD30",
        "name":             "Dólar MEP (compra de USD vía bonos)",
        "type":             "dolar_mep",
        "currency":         "USD",
        "adjusts_by":       "tipo de cambio implícito (CCL/MEP)",
        "return_estimate":  f"Cobertura cambiaria completa. Precio implícito ~${usd_oficial:,.0f} ARS/USD",
        "maturity":         "sin vencimiento — activo permanente",
        "days_to_maturity": None,
        "liquidity":        "alta (T+1 con parking de 24hs)",
        "min_investment_ars": 10000,
        "sovereign_risk":   False,
        "bank_risk":        False,
        "risk_level":       "bajo en términos reales (cobertura total vs devaluación)",
        "recommended_for":  ["moderado", "alto"],
        "how_to_buy":       "Bull Market > Dólar MEP: comprar AL30 con pesos, esperar 24hs (parking), vender AL30D por dólares",
        "notes":            "No tributa bienes personales si se mantiene como USD. Requiere 1 día hábil de parking obligatorio (regulación CNV).",
    })

    # --- FCI Money Market ---
    instruments.append({
        "id":               "fci_money_market",
        "ticker":           None,
        "name":             "FCI Money Market (fondo de liquidez)",
        "type":             "fci_mm",
        "currency":         "ARS",
        "adjusts_by":       "tasa variable diaria (mercado de dinero)",
        "return_estimate":  f"~{tna_pf - 3:.0f}% TNA diaria acumulable — liquidez inmediata",
        "maturity":         "rescate en 24hs hábiles",
        "days_to_maturity": 1,
        "liquidity":        "muy alta — rescate en 24hs, sin penalidad",
        "min_investment_ars": 100,
        "sovereign_risk":   False,
        "bank_risk":        False,
        "risk_level":       "muy bajo",
        "recommended_for":  ["bajo", "moderado", "alto"],
        "how_to_buy":       "Bull Market > Fondos > Fondo Money Market > Suscribir",
        "notes":            "Ideal para la reserva de liquidez. Rinde más que caja de ahorro. Sin plazo mínimo.",
    })

    # --- CEDEARs ---
    instruments.append({
        "id":               "cedears",
        "ticker":           "AAPL / MSFT / NVDA / AMZN (CEDEAR)",
        "name":             "CEDEARs — acciones extranjeras en ARS",
        "type":             "cedear",
        "currency":         "ARS_linked_USD",
        "adjusts_by":       "precio acción USA × ratio × CCL implícito",
        "return_estimate":  "variable — sigue al subyacente en USD ajustado por tipo de cambio implícito",
        "maturity":         "sin vencimiento",
        "days_to_maturity": None,
        "liquidity":        "alta (mercado BYMA, T+2)",
        "min_investment_ars": 5000,
        "sovereign_risk":   False,
        "bank_risk":        False,
        "risk_level":       "medio-alto (volatilidad equity + tipo de cambio)",
        "recommended_for":  ["moderado", "alto"],
        "how_to_buy":       "Bull Market > Cotizaciones > CEDEARs > [TICKER] > Comprar",
        "notes":            "Exposición en USD sin salir del sistema en pesos. Este sistema ya analiza los subyacentes: AAPL, MSFT, NVDA, GOOGL, META, AMZN. Usar esos análisis para elegir cuál comprar.",
    })

    return instruments


def _fetch_tna_pf() -> float | None:
    """Intenta traer la TNA de plazo fijo desde argentinadatos.com."""
    import requests
    try:
        resp = requests.get(
            "https://api.argentinadatos.com/v1/finanzas/tasas/depositos",
            timeout=8,
        )
        if resp.ok:
            data = resp.json()
            if isinstance(data, list) and data:
                return data[-1].get("tna30") or data[-1].get("valor")
    except Exception:
        pass
    return None
