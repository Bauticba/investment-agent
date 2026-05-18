import json
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()
client = Anthropic()


def analyze_fci_position(position: dict, fci_meta: dict, investor_profile: dict, macro: dict = None) -> dict:
    """
    Analiza una posición en un FCI (Fondo Común de Inversión).
    Usa la composición del fondo para estimar rendimiento efectivo
    y comparar contra alternativas de liquidez inmediata.
    """
    ticker     = position["ticker"]
    shares     = position.get("shares", 0)
    avg_price  = position.get("avg_buy_price", 0)
    cost_ars   = round(shares * avg_price, 2)
    current_value = position.get("current_value_ars") or cost_ars

    pnl_ars = round(current_value - cost_ars, 2)
    pnl_pct = round(pnl_ars / cost_ars * 100, 2) if cost_ars else 0.0

    composition = fci_meta.get("composition", {})

    # Estimar rendimiento efectivo ponderado con datos macro
    tna_pf    = (macro or {}).get("tna_pf", 20.0)          # TNA plazo fijo
    inflation = (macro or {}).get("inflation_monthly", 3.0) # inflación mensual
    caution_rate = tna_pf * 0.85                            # cauciones ≈ 85% de TNA_PF
    cer_annual   = inflation * 12                           # CER anualizado aproximado

    w_ramar = composition.get("corporativo_tasa_ramar", 0) / 100
    w_cer   = composition.get("soberano_tasa_cer", 0) / 100
    w_pf    = composition.get("plazo_fijo_tradicional", 0) / 100
    w_liq   = composition.get("liquidez", 0) / 100

    effective_yield_est = (
        w_ramar * caution_rate +
        w_cer   * cer_annual   +
        w_pf    * tna_pf       +
        w_liq   * 0.0
    )

    comp_lines = "\n".join(
        f"  - {k.replace('_', ' ').title()}: {v:.2f}%"
        for k, v in composition.items()
    )

    prompt = f"""
Sos un analista de inversiones especializado en el mercado argentino.
Analizás una posición en un FCI (Fondo Común de Inversión) money market para un inversor minorista que opera en IOL.

## Perfil del inversor
- Riesgo: {investor_profile.get("risk_profile", {}).get("level", "moderado")}
- Experiencia: {investor_profile.get("investor", {}).get("experience_level", "intermedio")}

## Posición actual — {ticker} ({fci_meta.get("name", ticker)})
- Administrador: {fci_meta.get("manager", "IOL")}
- Cuota-partes: {shares:,.3f}
- Precio promedio de suscripción: ${avg_price:.4f} ARS por cuota-parte
- Valor actual estimado: ${current_value:,.2f} ARS
- P&L: {pnl_pct:+.2f}% | ${pnl_ars:+,.2f} ARS

## Composición del fondo
{comp_lines}

## Contexto macro
- TNA plazo fijo bancario: {tna_pf:.1f}%
- Inflación mensual estimada: {inflation:.1f}% (≈ {cer_annual:.0f}% anualizado)
- Tasa caución bursátil estimada: {caution_rate:.1f}% TNA
- Rendimiento efectivo estimado del fondo: ~{effective_yield_est:.1f}% TNA (ponderado por composición)

## Tu tarea
Evaluá si tiene sentido mantener este FCI o si conviene rotar a otra alternativa de liquidez inmediata.
Considerá:
1. El rendimiento estimado del fondo vs inflación mensual actual
2. La concentración en cauciones bursátiles (corporativo tasa ramar) — ¿es adecuada?
3. La exposición CER (9.69%) en el contexto de desinflación — ¿ayuda o no?
4. Si el inversor moderado está bien servido por este FCI o debería considerar alternativas como:
   - LECAP cortas (tasa fija)
   - Plazo fijo UVA (CER puro, mínimo 90 días)
   - Otro FCI de la misma gestora con mejor composición

Devolvé SOLO JSON válido:
{{
  "action": "hold" | "switch" | "reduce",
  "urgency": "low" | "medium" | "high",
  "effective_yield_est_tna": {round(effective_yield_est, 1)},
  "vs_inflation": "positivo" | "neutro" | "negativo",
  "composition_assessment": "evaluación breve de la composición en 2 oraciones",
  "rationale": "recomendación concreta en 2-3 oraciones",
  "key_alert": "alerta principal o null",
  "vs_alternatives": "qué instrumento alternativo debería considerar y por qué"
}}
"""

    try:
        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        analysis = json.loads(text)
    except Exception as e:
        analysis = {
            "action":                  "hold",
            "urgency":                 "low",
            "effective_yield_est_tna": round(effective_yield_est, 1),
            "vs_inflation":            "neutro",
            "composition_assessment":  "Análisis automático no disponible.",
            "rationale":               f"Error de análisis ({e}). Mantener posición.",
            "key_alert":               None,
            "vs_alternatives":         "N/D",
        }

    return {
        "ticker":              ticker,
        "asset_type":          "fci_mm",
        "name":                fci_meta.get("name", ticker),
        "action":              analysis.get("action", "hold"),
        "urgency":             analysis.get("urgency", "low"),
        "shares":              shares,
        "avg_buy_price":       avg_price,
        "current_value_ars":   current_value,
        "cost_basis_ars":      cost_ars,
        "pnl_ars":             pnl_ars,
        "pnl_pct":             pnl_pct,
        "composition":         composition,
        "effective_yield_est_tna": analysis.get("effective_yield_est_tna", round(effective_yield_est, 1)),
        "vs_inflation":        analysis.get("vs_inflation", "neutro"),
        "composition_assessment": analysis.get("composition_assessment", ""),
        "rationale":           analysis.get("rationale", ""),
        "key_alert":           analysis.get("key_alert"),
        "vs_alternatives":     analysis.get("vs_alternatives", ""),
    }
