"""
Validador de carteras ARS generadas por ars_advisor.py.

Responsabilidad: auditar matemática y reglas financieras antes de
que la recomendación llegue al usuario. Claude redacta; este módulo valida.
"""

# Score de riesgo intrínseco por tipo de instrumento (0–100, contexto argentino).
# Refleja: volatilidad de precio, riesgo soberano, iliquidez y riesgo emisor.
_INSTRUMENT_RISK_SCORE: dict[str, int] = {
    "fci_mm":           5,   # liquidez pura, sin riesgo precio
    "caucion":          5,   # préstamo garantizado 1-7 días
    "plazo_fijo":      15,   # riesgo bancario + pierde vs inflación
    "dolar_mep":       20,   # riesgo regulatorio durante parking 24hs
    "plazo_fijo_uva":  20,   # riesgo bancario + iliquidez mínima 90 días
    "lecap":           30,   # soberano nominal corto plazo
    "lecer":           30,   # soberano CER corto plazo
    "fci_renta_fija":  35,   # mezcla CER + LECAP, algo de duración
    "fci_dolar_linked":40,   # dólar linked — riesgo devaluación inverso
    "bono_cer":        45,   # soberano CER — riesgo restructuración
    "on_usd":          50,   # corporativo USD — riesgo emisor
    "bono_hard_dollar":55,   # soberano hard dollar — riesgo precio y soberano
    "cedear":          65,   # equity dolarizado — alta volatilidad
    "cedears":         65,
    "accion_merval":   75,   # equity local — más volátil que CEDEAR
    "fci_acciones":    80,   # FCI equity — riesgo máximo
}

# Categorías de tipos de instrumento
_EQUITY       = {"cedear", "cedears", "accion_merval", "fci_acciones"}
_SOVEREIGN_HD = {"bono_hard_dollar"}
_CER_UVA      = {"bono_cer", "lecer", "plazo_fijo_uva"}
_LIQUIDITY    = {"fci_mm", "caucion"}
_MEP          = {"dolar_mep"}
_ON_USD       = {"on_usd"}


def compute_risk_score(allocation: list[dict], macro_sources: dict | None = None) -> dict:
    """
    Score cuantitativo de riesgo de la cartera (0–100).
    Promedio ponderado de _INSTRUMENT_RISK_SCORE por tipo de instrumento,
    con penalización opcional por datos macroeconómicos desactualizados.
    """
    if not allocation:
        return {"score": 0, "label": "Bajo", "breakdown": {}}

    weighted = sum(
        _INSTRUMENT_RISK_SCORE.get(p.get("type", ""), 50) * p.get("allocation_pct", 0)
        for p in allocation
    ) / 100

    stale_penalty = 0
    if macro_sources:
        stale_count = sum(1 for v in macro_sources.values() if isinstance(v, dict) and v.get("stale"))
        stale_penalty = stale_count * 3

    score = round(min(100, weighted + stale_penalty), 1)

    if score <= 25:
        label = "Bajo"
    elif score <= 55:
        label = "Moderado"
    else:
        label = "Alto"

    breakdown = {}
    for p in allocation:
        t = p.get("type", "desconocido")
        pct = p.get("allocation_pct", 0)
        risk = _INSTRUMENT_RISK_SCORE.get(t, 50)
        breakdown[t] = breakdown.get(t, {"pct": 0, "risk_score": risk})
        breakdown[t]["pct"] = round(breakdown[t]["pct"] + pct, 1)

    return {"score": score, "label": label, "stale_penalty": stale_penalty, "breakdown": breakdown}


def compute_exposures(allocation: list[dict]) -> dict:
    """
    Calcula exposiciones reales de la cartera a partir de los tipos de instrumento.
    No depende de lo que Claude declaró — solo de las posiciones concretas.
    """
    def pct(types):
        return sum(p.get("allocation_pct", 0) for p in allocation if p.get("type") in types)

    equity_pct       = pct(_EQUITY)
    sovereign_hd_pct = pct(_SOVEREIGN_HD)
    cer_uva_pct      = pct(_CER_UVA)
    liquidity_pct    = pct(_LIQUIDITY)
    mep_pct          = pct(_MEP)
    on_usd_pct       = pct(_ON_USD)

    return {
        "equity_pct":       equity_pct,
        "sovereign_hd_pct": sovereign_hd_pct,
        "cer_uva_pct":      cer_uva_pct,
        "liquidity_pct":    liquidity_pct,
        "mep_pct":          mep_pct,
        "on_usd_pct":       on_usd_pct,
        "usd_total_pct":    mep_pct + sovereign_hd_pct + on_usd_pct + equity_pct,
    }


def recalculate_fields(result: dict) -> dict:
    """
    Corrige en código los campos que Claude puede calcular mal.
    Llamar después de json.loads() y antes de validate_allocation().
    """
    allocation = result.get("allocation", [])
    exp = compute_exposures(allocation)

    # usd_exposure_pct desde el breakdown declarado (o calculado si falta)
    bd = result.get("usd_exposure_breakdown")
    if bd:
        result["usd_exposure_pct"] = (
            bd.get("dolar_liquido_pct", 0)
            + bd.get("renta_soberana_usd_pct", bd.get("renta_fija_usd_pct", 0))
            + bd.get("renta_corporativa_usd_pct", 0)
            + bd.get("equity_dolarizado_pct", 0)
        )
    else:
        result["usd_exposure_pct"] = exp["usd_total_pct"]

    # inflation_coverage_pct: solo CER/UVA/LECER — sin FCI MM
    result["inflation_coverage_pct"] = round(exp["cer_uva_pct"], 1)

    return result


def validate_allocation(
    result: dict,
    capital: float,
    riesgo: str,
    macro: dict,
    cedear_picks: list | None = None,
) -> list[str]:
    """
    Valida la asignación generada por Claude contra las reglas del sistema.
    Retorna lista de strings con los errores encontrados (vacía = ok).
    """
    errors = []
    allocation = result.get("allocation", [])

    if not allocation:
        return ["No hay instrumentos en la asignación"]

    # ── 1. Suma de porcentajes == 100 ─────────────────────────────────────────
    total_pct = sum(p.get("allocation_pct", 0) for p in allocation)
    if abs(total_pct - 100) > 0.5:
        errors.append(
            f"La suma de porcentajes es {total_pct:.1f}% — debe ser exactamente 100%"
        )

    # ── 2. Suma de montos == capital ──────────────────────────────────────────
    total_amt = sum(p.get("amount_ars", 0) for p in allocation)
    if abs(total_amt - capital) > capital * 0.01:
        errors.append(
            f"La suma de montos es ${total_amt:,.0f} ARS — debe ser ${capital:,.0f} ARS"
        )

    exp = compute_exposures(allocation)
    inflation_monthly = macro.get("inflation_monthly") or 0

    # ── 3–5. Reglas por perfil MODERADO ───────────────────────────────────────
    if riesgo == "moderado":
        if exp["equity_pct"] > 15:
            errors.append(
                f"Equity (CEDEARs/MERVAL) = {exp['equity_pct']:.0f}% — "
                f"máximo permitido para MODERADO es 15%"
            )
        if exp["sovereign_hd_pct"] > 15:
            errors.append(
                f"Bonos soberanos hard dollar = {exp['sovereign_hd_pct']:.0f}% — "
                f"máximo permitido para MODERADO es 15%"
            )
        if inflation_monthly > 3 and exp["cer_uva_pct"] < 35:
            errors.append(
                f"Cobertura CER/UVA = {exp['cer_uva_pct']:.0f}% — "
                f"mínimo 35% con inflación mensual de {inflation_monthly:.1f}%"
            )

    # ── 6. Liquidez mínima ────────────────────────────────────────────────────
    if exp["liquidity_pct"] < 5:
        errors.append(
            f"Reserva de liquidez (FCI MM / Caución) = {exp['liquidity_pct']:.0f}% — "
            f"mínimo requerido: 5%"
        )

    # ── 7. Sin MEP → FCI MM mínimo 15% ───────────────────────────────────────
    if exp["mep_pct"] == 0 and exp["liquidity_pct"] < 15:
        errors.append(
            f"Sin MEP en cartera: FCI MM / Caución debe ser ≥15% — "
            f"actualmente {exp['liquidity_pct']:.0f}%"
        )

    # ── 8. USD exposure declarado vs breakdown ────────────────────────────────
    bd = result.get("usd_exposure_breakdown")
    if bd:
        bd_sum = (
            bd.get("dolar_liquido_pct", 0)
            + bd.get("renta_soberana_usd_pct", bd.get("renta_fija_usd_pct", 0))
            + bd.get("renta_corporativa_usd_pct", 0)
            + bd.get("equity_dolarizado_pct", 0)
        )
        stated = result.get("usd_exposure_pct", 0)
        if abs(bd_sum - stated) > 1:
            errors.append(
                f"usd_exposure_pct declarado ({stated:.0f}%) no coincide con "
                f"la suma del breakdown ({bd_sum:.0f}%)"
            )

    # ── 9. FCI MM no cuenta como cobertura inflacionaria ─────────────────────
    stated_inf_cov = result.get("inflation_coverage_pct", 0)
    if stated_inf_cov and stated_inf_cov > exp["cer_uva_pct"] + 2:
        errors.append(
            f"inflation_coverage_pct declarado ({stated_inf_cov:.0f}%) supera "
            f"la cobertura CER/UVA real ({exp['cer_uva_pct']:.0f}%) — "
            f"FCI MM no cuenta como cobertura inflacionaria"
        )

    # ── 10. Triggers solo referencian instrumentos presentes ─────────────────
    alloc_text = " ".join(
        (p.get("instrument_id", "") + " " + p.get("name", "") + " " + p.get("type", "")).upper()
        for p in allocation
    )
    has_mep = exp["mep_pct"] > 0
    for trigger in result.get("rebalance_triggers", []):
        if "MEP" in trigger.upper() and not has_mep:
            errors.append(
                f"Trigger menciona MEP pero MEP no está en la cartera: "
                f"'{trigger[:100]}'"
            )

    # ── 11. Ejecutabilidad de CEDEARs (si hay picks con precios) ─────────────
    if cedear_picks:
        price_map = {
            p["ticker"].upper(): p.get("parity_price_ars") or 0
            for p in cedear_picks
        }
        for pos in allocation:
            if pos.get("type") not in ("cedear", "cedears"):
                continue
            ticker = pos.get("instrument_id", "").upper()
            amount = pos.get("amount_ars", 0)
            min_price = price_map.get(ticker, 0)
            if min_price and amount < min_price:
                errors.append(
                    f"{ticker}: monto asignado ${amount:,.0f} < precio de 1 unidad "
                    f"${min_price:,.0f} — no ejecutable"
                )

    return errors


def format_errors_for_prompt(errors: list[str]) -> str:
    """Formatea los errores para inyectarlos en el retry del prompt."""
    lines = [
        "\n\n⚠️ CORRECCIÓN OBLIGATORIA: Tu respuesta anterior tenía los siguientes errores.",
        "DEBÉS corregirlos todos antes de responder de nuevo:\n",
    ]
    for i, e in enumerate(errors, 1):
        lines.append(f"{i}. {e}")
    lines.append("\nRespondé con un JSON corregido que cumpla todas las reglas.")
    return "\n".join(lines)
