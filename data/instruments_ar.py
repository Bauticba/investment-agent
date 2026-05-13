import requests
from datetime import datetime, date
from data.argentina import get_macro_data, BOND_REGISTRY

TNA_PF_FALLBACK = 20.0

# Obligaciones Negociables corporativas en USD con buena liquidez en BYMA
ON_REGISTRY = {
    "YMCHO": {"name": "YPF ON 2026 (USD)",          "issuer": "YPF S.A.",            "currency": "USD", "maturity": "2026-07-09", "coupon": 0.085, "rating": "B+"},
    "PAE26":  {"name": "Pan American Energy ON 2026","issuer": "Pan American Energy", "currency": "USD", "maturity": "2026-07-15", "coupon": 0.075, "rating": "BB-"},
    "TGS26":  {"name": "TGS ON 2026 (USD)",          "issuer": "TGS",                 "currency": "USD", "maturity": "2026-05-07", "coupon": 0.066, "rating": "B+"},
    "IRCP":   {"name": "IRSA Propiedades ON (USD)",  "issuer": "IRSA",                "currency": "USD", "maturity": "2028-03-20", "coupon": 0.085, "rating": "B"},
    "PAMP3":  {"name": "Pampa Energía ON 2027 (USD)","issuer": "Pampa Energía",       "currency": "USD", "maturity": "2027-01-15", "coupon": 0.072, "rating": "B+"},
}

# Bonos soberanos hard dollar Argentina
HARD_DOLLAR_BOND_REGISTRY = {
    "AL29": {"name": "Bonar 2029",  "maturity": "2029-07-09", "coupon": 0.01,    "amortization": "cuotas"},
    "AL30": {"name": "Bonar 2030",  "maturity": "2030-07-09", "coupon": 0.005,   "amortization": "cuotas"},
    "AL35": {"name": "Bonar 2035",  "maturity": "2035-07-09", "coupon": 0.03625, "amortization": "cuotas"},
    "AL41": {"name": "Bonar 2041",  "maturity": "2041-07-09", "coupon": 0.0425,  "amortization": "cuotas"},
    "GD28": {"name": "Global 2028", "maturity": "2028-01-09", "coupon": 0.03625, "amortization": "cuotas"},
    "GD30": {"name": "Global 2030", "maturity": "2030-07-09", "coupon": 0.0075,  "amortization": "cuotas"},
    "GD35": {"name": "Global 2035", "maturity": "2035-07-09", "coupon": 0.03625, "amortization": "cuotas"},
    "GD38": {"name": "Global 2038", "maturity": "2038-01-09", "coupon": 0.0125,  "amortization": "cuotas"},
    "GD41": {"name": "Global 2041", "maturity": "2041-07-09", "coupon": 0.0425,  "amortization": "cuotas"},
    "GD46": {"name": "Global 2046", "maturity": "2046-07-09", "coupon": 0.04625, "amortization": "cuotas"},
}

# Acciones del panel líder MERVAL disponibles como CEDEARs o directamente en BYMA
MERVAL_STOCKS = {
    "GGAL": {"name": "Grupo Financiero Galicia",  "sector": "Finanzas",   "description": "Mayor banco privado argentino por depósitos. Exposición a crédito y actividad económica local."},
    "YPFD": {"name": "YPF S.A.",                  "sector": "Energía",    "description": "Empresa nacional de petróleo y gas. Alta exposición a precio del petróleo y política energética."},
    "BMA":  {"name": "Banco Macro",               "sector": "Finanzas",   "description": "Banco regional con fuerte presencia en el interior. Sólido en períodos de crecimiento económico."},
    "PAMP": {"name": "Pampa Energía",             "sector": "Energía",    "description": "Generación eléctrica y petróleo. Beneficiaria del crecimiento de Vaca Muerta."},
    "TXAR": {"name": "Ternium Argentina",         "sector": "Materiales", "description": "Siderúrgica. Correlaciona con obra pública y construcción local."},
    "TECO2":{"name": "Telecom Argentina",         "sector": "Telecomunicaciones", "description": "Principal operador de telecomunicaciones. Negocio defensivo con flujo estable."},
    "BBAR": {"name": "BBVA Argentina",            "sector": "Finanzas",   "description": "Subsidiaria de BBVA. Exposición a crédito y recuperación del consumo."},
    "MIRG": {"name": "Mirgor",                    "sector": "Industrial", "description": "Producción de electrónica y autopartes. Alta exposición al ciclo económico local."},
}


def get_instruments_universe(macro: dict = None) -> list[dict]:
    """
    Devuelve el universo completo de instrumentos en ARS/USD disponibles en IOL (Invertir Online),
    con características actualizadas al contexto macro del momento.
    """
    if macro is None:
        macro = get_macro_data()

    inflation_monthly = macro.get("inflation_monthly") or 3.5
    inflation_annual  = macro.get("inflation_annual") or 42.0
    usd_oficial       = macro.get("usd_oficial") or 1400
    uva               = macro.get("uva")
    tna_pf            = _fetch_tna_pf() or TNA_PF_FALLBACK
    tea_pf            = round(((1 + tna_pf / 100 / 365) ** 365 - 1) * 100, 1)
    today             = date.today()

    instruments = []

    # ─── BONOS CER (ajustados por inflación) ──────────────────────────────────
    for ticker, meta in BOND_REGISTRY.items():
        mat_date  = datetime.strptime(meta["maturity"], "%Y-%m-%d").date()
        days_left = (mat_date - today).days
        if days_left < 0:
            continue
        risk        = "bajo-medio" if days_left <= 365 else "medio"
        recommended = ["bajo", "moderado", "alto"] if days_left <= 365 else ["moderado", "alto"]
        instruments.append({
            "id":                 ticker.lower(),
            "ticker":             ticker,
            "name":               meta["name"],
            "type":               "bono_cer",
            "currency":           "ARS",
            "adjusts_by":         "CER (inflación)",
            "return_estimate":    f"CER + {meta['coupon_annual']*100:.0f}% anual (retorno real sobre inflación)",
            "maturity":           meta["maturity"],
            "days_to_maturity":   days_left,
            "liquidity":          "alta (mercado secundario BYMA, T+1)",
            "min_investment_ars": 1000,
            "sovereign_risk":     True,
            "bank_risk":          False,
            "risk_level":         risk,
            "recommended_for":    recommended,
            "how_to_buy":         f"IOL > Operar > Renta Fija > Bonos > buscar {ticker} > Comprar",
            "notes":              "Capital ajustado diariamente por CER. Precio visible en IOL.",
        })

    # ─── LECAP (Letras del Tesoro a tasa fija) ────────────────────────────────
    instruments.append({
        "id":                 "lecap",
        "ticker":             "S31E6 / S28F7 (LECAP)",
        "name":               "LECAP — Letra del Tesoro a Tasa Fija",
        "type":               "lecap",
        "currency":           "ARS",
        "adjusts_by":         "Tasa fija (capitaliza mensualmente)",
        "return_estimate":    f"~{tna_pf + 8:.0f}–{tna_pf + 12:.0f}% TNA (tasa de licitación primaria; sin ajuste CER)",
        "maturity":           "3 a 12 meses según serie",
        "days_to_maturity":   None,
        "liquidity":          "alta (mercado secundario BYMA, T+1)",
        "min_investment_ars": 1000,
        "sovereign_risk":     True,
        "bank_risk":          False,
        "risk_level":         "bajo-medio (riesgo si inflación supera la tasa fija)",
        "recommended_for":    ["bajo", "moderado"],
        "how_to_buy":         "IOL > Operar > Renta Fija > Letras > buscar LECAP > Comprar (elegir serie con mayor volumen operado)",
        "notes":              f"No ajusta por CER. Si inflación mensual supera {(tna_pf+10)/12:.1f}%/mes, pierde en términos reales. Ideal cuando se espera desinflación.",
    })

    # ─── LECER (Letras del Tesoro ajustadas por CER) ─────────────────────────
    instruments.append({
        "id":                 "lecer",
        "ticker":             "LECER",
        "name":               "LECER — Letra del Tesoro ajustada por CER",
        "type":               "lecer",
        "currency":           "ARS",
        "adjusts_by":         "CER (inflación)",
        "return_estimate":    "CER + 0–3% anual (bono CER de corto plazo, liquidez alta)",
        "maturity":           "3 a 9 meses según serie",
        "days_to_maturity":   None,
        "liquidity":          "alta (mercado secundario BYMA, T+1)",
        "min_investment_ars": 1000,
        "sovereign_risk":     True,
        "bank_risk":          False,
        "risk_level":         "bajo-medio",
        "recommended_for":    ["bajo", "moderado"],
        "how_to_buy":         "IOL > Operar > Renta Fija > Letras > buscar LECER > Comprar",
        "notes":              "Equivalente a un bono CER de muy corto plazo. Menos volatilidad de precio que TX26/TX28 por su duration menor.",
    })

    # ─── CAUCIÓN BURSÁTIL ────────────────────────────────────────────────────
    tna_caucion = _fetch_tna_caucion() or (tna_pf - 2)
    instruments.append({
        "id":                 "caucion_bursatil",
        "ticker":             "CAUCION",
        "name":               "Caución Bursátil (repo intradía/semanal)",
        "type":               "caucion",
        "currency":           "ARS",
        "adjusts_by":         "tasa variable diaria BYMA",
        "return_estimate":    f"~{tna_caucion:.0f}% TNA (plazo 1–7 días, con renovación automática)",
        "maturity":           "1 a 7 días hábiles (renovable)",
        "days_to_maturity":   1,
        "liquidity":          "máxima — vence en días, sin mercado secundario necesario",
        "min_investment_ars": 10000,
        "sovereign_risk":     False,
        "bank_risk":          False,
        "risk_level":         "muy bajo (garantía: cartera de valores del prestatario)",
        "recommended_for":    ["bajo", "moderado", "alto"],
        "how_to_buy":         "IOL > Operar > Cauciones > Colocar > elegir plazo 1 o 7 días > confirmar monto",
        "notes":              "Equivalente a un préstamo garantizado con títulos bursátiles. Sin riesgo crediticio directo. Ideal para liquidez de cortísimo plazo con rendimiento superior al FCI MM.",
    })

    # ─── PLAZO FIJO UVA ──────────────────────────────────────────────────────
    instruments.append({
        "id":                 "plazo_fijo_uva",
        "ticker":             None,
        "name":               "Plazo Fijo UVA",
        "type":               "plazo_fijo_uva",
        "currency":           "ARS",
        "adjusts_by":         "UVA (equivalente a inflación CPI)",
        "return_estimate":    "CER + ~1% (cobertura total de inflación, sin riesgo precio de mercado)",
        "maturity":           "mínimo 90 días (sin rescate anticipado)",
        "days_to_maturity":   90,
        "liquidity":          "baja — inmovilizado 90 días",
        "min_investment_ars": 1000,
        "sovereign_risk":     False,
        "bank_risk":          True,
        "risk_level":         "bajo",
        "recommended_for":    ["bajo", "moderado"],
        "how_to_buy":         "IOL > Operar > Plazo Fijo > UVA > Simular y confirmar",
        "notes":              f"Garantizado por SEDESA hasta $6M ARS. UVA actual: ${uva:,.2f}. Sin riesgo precio." if uva else "Garantizado por SEDESA hasta $6M ARS.",
    })

    # ─── PLAZO FIJO TRADICIONAL ──────────────────────────────────────────────
    instruments.append({
        "id":                 "plazo_fijo_tna",
        "ticker":             None,
        "name":               "Plazo Fijo Tradicional (tasa fija)",
        "type":               "plazo_fijo",
        "currency":           "ARS",
        "adjusts_by":         "tasa fija TNA",
        "return_estimate":    f"~{tna_pf:.0f}% TNA (~{tea_pf:.0f}% TEA) — RIESGO: inflación ({inflation_monthly:.1f}%/mes) puede superarla",
        "maturity":           "30 a 365 días",
        "days_to_maturity":   30,
        "liquidity":          "baja — inmovilizado al plazo pactado",
        "min_investment_ars": 1000,
        "sovereign_risk":     False,
        "bank_risk":          True,
        "risk_level":         "bajo-medio (riesgo inflacionario real)",
        "recommended_for":    ["bajo"],
        "how_to_buy":         "IOL > Operar > Plazo Fijo > Tradicional",
        "notes":              f"Solo conveniente si inflación baja de {tna_pf/12:.1f}%/mes. Actualmente inflación = {inflation_monthly:.1f}%/mes → el PF tradicional PIERDE en términos reales.",
    })

    # ─── DÓLAR MEP ───────────────────────────────────────────────────────────
    _mep = _fetch_mep_data()
    mep_price = _mep["price"] or usd_oficial
    mep_fecha = _mep["fecha"]
    _mep_price_str = f"~${mep_price:,.0f} ARS/USD"
    _mep_source = f" (dolarapi.com, {mep_fecha})" if mep_fecha else " (dolarapi.com)"
    instruments.append({
        "id":                 "dolar_mep",
        "ticker":             "AL30 / GD30",
        "name":               "Dólar MEP (compra de USD vía bonos)",
        "type":               "dolar_mep",
        "currency":           "USD",
        "adjusts_by":         "tipo de cambio implícito MEP",
        "return_estimate":    f"Cobertura cambiaria completa. Precio MEP actual {_mep_price_str}{_mep_source}",
        "maturity":           "sin vencimiento — activo permanente",
        "days_to_maturity":   None,
        "liquidity":          "alta (T+1 con parking de 24hs hábiles)",
        "min_investment_ars": 10000,
        "sovereign_risk":     False,
        "bank_risk":          False,
        "risk_level":         "muy bajo en términos reales (cobertura total vs devaluación)",
        "recommended_for":    ["moderado", "alto"],
        "how_to_buy":         "IOL > Operar > Dólar MEP > comprar AL30 con pesos, esperar 24hs hábiles (parking CNV), vender AL30D por dólares",
        "notes":              "No tributa bienes personales si se mantiene como USD. Requiere 1 día hábil de parking obligatorio.",
        "mep_fetch_timestamp": mep_fecha,
    })

    # ─── BONOS SOBERANOS HARD DOLLAR ────────────────────────────────────────
    for ticker, meta in HARD_DOLLAR_BOND_REGISTRY.items():
        mat_date  = datetime.strptime(meta["maturity"], "%Y-%m-%d").date()
        days_left = (mat_date - today).days
        if days_left < 0:
            continue
        risk_level  = "medio" if days_left <= 3 * 365 else "medio-alto"
        recommended = ["moderado"] if days_left <= 3 * 365 else ["moderado", "alto"]
        instruments.append({
            "id":                 ticker.lower(),
            "ticker":             ticker,
            "name":               f"{meta['name']} (hard dollar)",
            "type":               "bono_hard_dollar",
            "currency":           "USD",
            "adjusts_by":         "precio USD en mercado secundario",
            "return_estimate":    f"~{meta['coupon']*100:.2f}% cupón USD anual + ganancia/pérdida de precio (TIR ~8–15% en USD según precio de mercado)",
            "maturity":           meta["maturity"],
            "days_to_maturity":   days_left,
            "liquidity":          "media-alta (BYMA T+2, spread bid-ask variable)",
            "min_investment_ars": int(100 * usd_oficial),
            "sovereign_risk":     True,
            "bank_risk":          False,
            "risk_level":         risk_level,
            "recommended_for":    recommended,
            "how_to_buy":         f"IOL > Operar > Renta Fija > Bonos > buscar {ticker} > Comprar (precio en USD, liquidación en ARS al tipo de cambio MEP implícito)",
            "notes":              "Riesgo soberano argentino. Precio en USD. Permite dolarización dentro del sistema financiero local. Históricamente alta volatilidad ante eventos políticos.",
        })

    # ─── OBLIGACIONES NEGOCIABLES (ONs USD) ──────────────────────────────────
    for ticker, meta in ON_REGISTRY.items():
        mat_date  = datetime.strptime(meta["maturity"], "%Y-%m-%d").date()
        days_left = (mat_date - today).days
        if days_left < 0:
            continue
        instruments.append({
            "id":                 ticker.lower(),
            "ticker":             ticker,
            "name":               meta["name"],
            "type":               "on_usd",
            "currency":           "USD",
            "adjusts_by":         "precio USD en mercado secundario",
            "return_estimate":    f"~{meta['coupon']*100:.1f}% cupón anual en USD (TIR estimada similar al cupón a precios actuales de mercado)",
            "maturity":           meta["maturity"],
            "days_to_maturity":   days_left,
            "liquidity":          "media (BYMA T+2, volumen moderado)",
            "min_investment_ars": int(100 * usd_oficial),
            "sovereign_risk":     False,
            "bank_risk":          False,
            "risk_level":         "medio (riesgo corporativo argentino, sin riesgo soberano directo)",
            "recommended_for":    ["moderado", "alto"],
            "how_to_buy":         f"IOL > Operar > Renta Fija > ONs > buscar {ticker} > Comprar",
            "notes":              f"Emisor: {meta['issuer']}. Rating: {meta['rating']}. USD hard. Menor riesgo que soberanos pero menor liquidez. Cupones pagados en USD o ARS al tipo de cambio.",
        })

    # ─── FCI MONEY MARKET ────────────────────────────────────────────────────
    instruments.append({
        "id":                 "fci_money_market",
        "ticker":             None,
        "name":               "FCI Money Market (fondo de liquidez)",
        "type":               "fci_mm",
        "currency":           "ARS",
        "adjusts_by":         "tasa variable diaria (mercado de dinero)",
        "return_estimate":    f"~{tna_pf - 3:.0f}% TNA diaria acumulable — liquidez inmediata",
        "maturity":           "rescate en 24hs hábiles",
        "days_to_maturity":   1,
        "liquidity":          "muy alta — rescate en 24hs, sin penalidad",
        "min_investment_ars": 100,
        "sovereign_risk":     False,
        "bank_risk":          False,
        "risk_level":         "muy bajo",
        "recommended_for":    ["bajo", "moderado", "alto"],
        "how_to_buy":         "IOL > Operar > Fondos > Money Market > Suscribir (ej: IOL Money Market, Balanz Ahorro)",
        "notes":              "Ideal para la reserva de liquidez. Rinde más que caja de ahorro. Sin plazo mínimo.",
    })

    # ─── FCI RENTA FIJA ARS ──────────────────────────────────────────────────
    instruments.append({
        "id":                 "fci_renta_fija",
        "ticker":             None,
        "name":               "FCI Renta Fija ARS (bono corto + LECAP)",
        "type":               "fci_renta_fija",
        "currency":           "ARS",
        "adjusts_by":         "cartera de bonos CER + LECAP + caucion",
        "return_estimate":    f"~{tna_pf + 5:.0f}–{tna_pf + 10:.0f}% TNA estimada (supera MM, con algo de volatilidad NAV)",
        "maturity":           "rescate en 48–72hs hábiles",
        "days_to_maturity":   2,
        "liquidity":          "alta — rescate en 2–3 días hábiles",
        "min_investment_ars": 1000,
        "sovereign_risk":     True,
        "bank_risk":          False,
        "risk_level":         "bajo-medio",
        "recommended_for":    ["bajo", "moderado"],
        "how_to_buy":         "IOL > Operar > Fondos > Renta Fija > Suscribir (ej: Balanz Renta Fija, SBS Renta Pesos)",
        "notes":              "Invierte en bonos CER cortos, LECAPs y cauciones. Más rendimiento que MM a cambio de algo de volatilidad en el NAV. Buena opción para liquidez de mediano plazo.",
    })

    # ─── FCI DÓLAR LINKED ────────────────────────────────────────────────────
    instruments.append({
        "id":                 "fci_dolar_linked",
        "ticker":             None,
        "name":               "FCI Dólar Linked (cobertura tipo de cambio)",
        "type":               "fci_dolar_linked",
        "currency":           "ARS",
        "adjusts_by":         "variación del tipo de cambio oficial ARS/USD",
        "return_estimate":    f"Variación del TC oficial + ~2–4% anual. Cubre devaluación del peso vs USD oficial.",
        "maturity":           "rescate en 48–72hs hábiles",
        "days_to_maturity":   2,
        "liquidity":          "alta",
        "min_investment_ars": 1000,
        "sovereign_risk":     False,
        "bank_risk":          False,
        "risk_level":         "medio (cubre devaluación pero no garantiza retorno real)",
        "recommended_for":    ["moderado", "alto"],
        "how_to_buy":         "IOL > Operar > Fondos > Dólar Linked > Suscribir (ej: Balanz Dólar Linked, SBS Dólar)",
        "notes":              "Sigue al tipo de cambio oficial, no al MEP. Conveniente si se espera devaluación del oficial. En contexto de crawling peg estable, puede perder vs CER.",
    })

    # ─── FCI RENTA VARIABLE (MERVAL) ─────────────────────────────────────────
    instruments.append({
        "id":                 "fci_renta_variable",
        "ticker":             None,
        "name":               "FCI Renta Variable (acciones argentinas MERVAL)",
        "type":               "fci_acciones",
        "currency":           "ARS",
        "adjusts_by":         "precio de acciones del panel líder MERVAL",
        "return_estimate":    "variable — alta volatilidad, potencial de retorno muy superior a inflación en ciclos alcistas",
        "maturity":           "rescate en 72–96hs hábiles",
        "days_to_maturity":   3,
        "liquidity":          "media — rescate en 3–4 días hábiles",
        "min_investment_ars": 1000,
        "sovereign_risk":     False,
        "bank_risk":          False,
        "risk_level":         "alto",
        "recommended_for":    ["alto"],
        "how_to_buy":         "IOL > Operar > Fondos > Renta Variable > Suscribir (ej: Balanz Capital, Santander Acciones)",
        "notes":              "Exposición diversificada al MERVAL (GGAL, YPFD, BMA, PAMP, TXAR, etc.). Horizonte mínimo 12–24 meses. No recomendado para capital que pueda necesitarse en el corto plazo.",
    })

    # ─── ACCIONES MERVAL (individuales) ──────────────────────────────────────
    instruments.append({
        "id":                 "acciones_merval",
        "ticker":             "GGAL / YPFD / BMA / PAMP / TXAR",
        "name":               "Acciones argentinas MERVAL (panel líder)",
        "type":               "accion_merval",
        "currency":           "ARS",
        "adjusts_by":         "precio de mercado en BYMA",
        "return_estimate":    "variable — correlaciona con actividad económica, política y precios energéticos locales",
        "maturity":           "sin vencimiento",
        "days_to_maturity":   None,
        "liquidity":          "alta (BYMA T+2, mercado continuo)",
        "min_investment_ars": 5000,
        "sovereign_risk":     False,
        "bank_risk":          False,
        "risk_level":         "alto",
        "recommended_for":    ["alto"],
        "how_to_buy":         "IOL > Operar > Acciones > buscar [TICKER] > Comprar. Principales: GGAL (bancos), YPFD (energía), BMA (banco), PAMP (energía), TXAR (industria).",
        "notes":              "Empresas argentinas listadas en BYMA. Muy alta volatilidad vs acciones USA. Se ven afectadas por riesgo político, fiscal y cambiario local. Recomendado solo para perfil ALTO con horizonte 12–24 meses. Stocks destacados: GGAL, YPFD, BMA, PAMP, TXAR, TECO2.",
    })

    # ─── CEDEARs ─────────────────────────────────────────────────────────────
    instruments.append({
        "id":                 "cedears",
        "ticker":             "AAPL / MSFT / NVDA / AMZN (CEDEAR)",
        "name":               "CEDEARs — acciones extranjeras en ARS",
        "type":               "cedear",
        "currency":           "ARS_linked_USD",
        "adjusts_by":         "precio acción USA × ratio × CCL implícito",
        "return_estimate":    "variable — sigue al subyacente en USD ajustado por tipo de cambio implícito",
        "maturity":           "sin vencimiento",
        "days_to_maturity":   None,
        "liquidity":          "alta (BYMA T+2)",
        "min_investment_ars": 5000,
        "sovereign_risk":     False,
        "bank_risk":          False,
        "risk_level":         "medio-alto (volatilidad equity + tipo de cambio)",
        "recommended_for":    ["moderado", "alto"],
        "how_to_buy":         "IOL > Operar > CEDEARs > buscar [TICKER] > Comprar",
        "notes":              "Exposición en USD sin salir del sistema en pesos. Este sistema analiza: AAPL, MSFT, NVDA, GOOGL, META, AMZN, JPM, TSLA, V, MA, COST, XOM, CVX, JNJ, ABBV, UNH. Usar los análisis cacheados para elegir cuál comprar.",
    })

    return instruments


# ─── helpers ──────────────────────────────────────────────────────────────────

_PF_URL = "https://api.argentinadatos.com/v1/finanzas/tasas/plazoFijo"


def _fetch_pf_bancos() -> list[dict]:
    """Devuelve lista de bancos con tnaClientes en % anual, ordenada desc."""
    try:
        resp = requests.get(_PF_URL, timeout=8)
        if resp.ok:
            data = resp.json()
            if isinstance(data, list):
                result = []
                for b in data:
                    tna_raw = b.get("tnaClientes") or 0
                    # La API devuelve valores como 0.175 (= 17.5% TNA anual)
                    tna_pct = round(tna_raw * 100, 2) if tna_raw < 5 else round(tna_raw, 2)
                    if tna_pct > 0:
                        result.append({
                            "entidad": b.get("entidad", ""),
                            "tna_pct": tna_pct,
                        })
                return sorted(result, key=lambda x: x["tna_pct"], reverse=True)
    except Exception:
        pass
    return []


def _fetch_tna_pf() -> float | None:
    bancos = _fetch_pf_bancos()
    if bancos:
        tasas = [b["tna_pct"] for b in bancos]
        return round(sum(tasas) / len(tasas), 1)
    return None


def _fetch_tna_caucion() -> float | None:
    tna = _fetch_tna_pf()
    if tna:
        return round(tna * 0.85, 1)
    return None


def get_rates_validation(macro: dict) -> dict:
    """
    Devuelve validación de tasas en tiempo real para mostrar en la UI.
    - PF tradicional: tasas por banco vs inflación mensual
    - Bonos CER: precio IOL en tiempo real
    """
    from data.iol import get_prices_bulk, is_available

    inflation_monthly = macro.get("inflation_monthly") or 0
    inflation_annual  = round(inflation_monthly * 12, 1)

    # PF por banco
    bancos = _fetch_pf_bancos()
    pf_rows = []
    for b in bancos[:10]:
        tna = b["tna_pct"]
        mensual = round(tna / 12, 2)
        supera  = mensual > inflation_monthly
        pf_rows.append({
            "entidad":   b["entidad"],
            "tna_pct":   tna,
            "mensual":   mensual,
            "supera_inf": supera,
        })

    # Bonos CER desde IOL
    cer_precios = {}
    if is_available():
        precios = get_prices_bulk(["TX26", "TX28", "TX30", "DICP"])
        for ticker, p in precios.items():
            cer_precios[ticker] = {
                "precio": p["ultimo_precio"],
                "variacion_pct": p.get("variacion_pct"),
                "fecha": p.get("fecha", ""),
            }

    return {
        "inflation_monthly": inflation_monthly,
        "inflation_annual":  inflation_annual,
        "pf_bancos":         pf_rows,
        "cer_precios_iol":   cer_precios,
    }


def _fetch_mep_data() -> dict:
    """Trae precio y timestamp del dólar MEP desde dolarapi.com."""
    try:
        resp = requests.get("https://dolarapi.com/v1/dolares/bolsa", timeout=8)
        if resp.ok:
            data = resp.json()
            price = data.get("venta") or data.get("compra")
            fecha_utc = data.get("fechaActualizacion", "")
            # Convertir a hora Argentina (UTC-3)
            fecha_art = ""
            if fecha_utc:
                try:
                    from datetime import datetime, timezone, timedelta
                    dt = datetime.fromisoformat(fecha_utc.replace("Z", "+00:00"))
                    art = dt.astimezone(timezone(timedelta(hours=-3)))
                    fecha_art = art.strftime("%d/%m %H:%M ART")
                except Exception:
                    fecha_art = fecha_utc[:16]
            return {"price": price, "fecha": fecha_art}
    except Exception:
        pass
    return {"price": None, "fecha": ""}
