"""
Validador de carteras ARS generadas por ars_advisor.py.

Responsabilidad: auditar matemática y reglas financieras antes de
que la recomendación llegue al usuario. Claude redacta; este módulo valida.
"""

# Categorías de tipos de instrumento
_EQUITY       = {"cedear", "cedears", "accion_merval", "fci_acciones"}
_SOVEREIGN_HD = {"bono_hard_dollar"}
_CER_UVA      = {"bono_cer", "lecer", "plazo_fijo_uva"}
_LIQUIDITY    = {"fci_mm", "caucion"}
_MEP          = {"dolar_mep"}
_ON_USD       = {"on_usd"}


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
