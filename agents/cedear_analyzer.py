import json
import os
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()
client = Anthropic()


def analyze_cedear_position(position: dict, cedear_data: dict, investor_profile: dict) -> dict:
    """
    Analiza una posición en un CEDEAR: P&L en ARS, paridad vs precio de mercado,
    CCL implícito, y recomendación teniendo en cuenta el análisis cacheado del subyacente.
    """
    ticker   = position["ticker"].upper()
    shares   = position.get("shares", 0)
    avg_buy  = position.get("avg_buy_price", 0)
    notes    = position.get("notes", "")

    market_price_ars = cedear_data.get("market_price_ars")

    if not market_price_ars:
        return {
            "ticker":            ticker,
            "asset_type":        "cedear",
            "action":            "sin_precio",
            "urgency":           "high",
            "rationale":         (
                "No se pudo obtener el precio de mercado del CEDEAR automáticamente. "
                "Agregá el precio actual en ARS en my_portfolio.json con el campo "
                "\"current_price_override\" (lo encontrás en la app de Bull Market)."
            ),
            "key_alert":         "Precio no disponible — completar manualmente",
            "shares":            shares,
            "avg_buy_price":     avg_buy,
            "current_price_ars": None,
            "pnl_pct":           None,
        }

    cost_basis    = shares * avg_buy
    current_value = shares * market_price_ars
    pnl_ars       = current_value - cost_basis
    pnl_pct       = ((market_price_ars - avg_buy) / avg_buy * 100) if avg_buy else 0

    # Cargar análisis cacheado del subyacente
    cached_analysis = _load_cached_analysis(ticker)
    ceo_score   = None
    ceo_verdict = None
    ceo_thesis  = None
    if cached_analysis:
        ceo = cached_analysis.get("ceo_thesis", {})
        ceo_score   = ceo.get("ceo_score")
        ceo_verdict = ceo.get("final_verdict")
        ceo_thesis  = ceo.get("thesis", "")[:300]

    parity      = cedear_data.get("parity_price_ars")
    premium_pct = cedear_data.get("premium_discount_pct")
    ccl         = cedear_data.get("ccl_oficial")
    ccl_impl    = cedear_data.get("ccl_implicit")
    us_price    = cedear_data.get("us_price_usd")
    ratio       = cedear_data.get("ratio")
    price_src   = cedear_data.get("price_source", "?")
    macro       = cedear_data.get("macro", {})
    infl_m      = macro.get("inflation_monthly")

    prompt = f"""
Sos un analista especializado en CEDEARs argentinos. Los CEDEARs son certificados que
replican acciones extranjeras que cotizan en pesos en BYMA. El inversor tiene en Bull
Market Brokers una posición en {ticker} (CEDEAR).

## Perfil del inversor
- Nombre: {investor_profile["investor"]["name"]}
- Experiencia: {investor_profile["investor"]["experience_level"]}
- Riesgo: {investor_profile["risk_profile"]["level"]}
- Broker: Bull Market Brokers (Argentina)

## Posición: CEDEAR {ticker} — {cedear_data.get("name", ticker)}
- Ratio de conversión: {ratio} CEDEARs = 1 acción en USA
- Precio subyacente USA: ${us_price} USD
- Precio de paridad teórica: ${parity:,.2f} ARS (us_price / ratio × CCL oficial)
- Precio actual de mercado ARS: ${market_price_ars:,.2f} ARS (fuente: {price_src})
- Premium/Discount vs paridad: {f'{premium_pct:+.1f}%' if premium_pct is not None else 'N/A'}
- CCL oficial (tipo de cambio unificado): ${ccl:,.0f} ARS/USD
- CCL implícito en el CEDEAR: ${ccl_impl:,.0f} ARS/USD

- Cantidad de CEDEARs: {shares:,}
- Precio promedio de compra: ${avg_buy:,.2f} ARS
- Precio actual: ${market_price_ars:,.2f} ARS
- Valor actual de la posición: ${current_value:,.2f} ARS
- Costo base total: ${cost_basis:,.2f} ARS
- Ganancia/Pérdida nominal ARS: ${pnl_ars:+,.2f} ({pnl_pct:+.1f}%)
{f'- Notas del inversor: {notes}' if notes else ''}

## Análisis del subyacente en USD (generado por el sistema)
{f'- Score CEO: {ceo_score}/10' if ceo_score else '- Score CEO: no disponible'}
{f'- Veredicto: {ceo_verdict}' if ceo_verdict else ''}
{f'- Tesis: {ceo_thesis}' if ceo_thesis else '- Tesis: ejecutá python3 run_watchlist.py {ticker} para generar análisis'}

## Contexto macro argentino
- Inflación mensual: {f'{infl_m:.1f}%' if infl_m else 'N/A'}
- Régimen cambiario: tipo de cambio unificado desde abril 2025 (acuerdo FMI)
- CCL y MEP convergen al oficial, eliminando la brecha cambiaria histórica

## Tu tarea
Analizá la posición considerando:
1. **P&L en ARS**: el inversor ganó o perdió en pesos; el CEDEAR protege vs devaluación porque replica el subyacente en USD
2. **Premium/Discount vs paridad**: si cotiza muy por encima de la paridad teórica, el CEDEAR puede estar caro en términos relativos
3. **CCL implícito**: compará el CCL implícito en el CEDEAR vs el CCL oficial; históricamente el CEDEAR tenía premium por ser una forma de dolarizarse, hoy con el mercado unificado la brecha tiende a 0
4. **Fundamentales del subyacente**: si el score CEO del subyacente en USD es alto, eso apoya mantener/agregar; si es bajo, reconsiderar
5. **Perfil del inversor**: moderado, principiante. La recomendación debe ser clara y accionable en Bull Market

Respondé ÚNICAMENTE con JSON válido, sin texto adicional:

{{
  "action": "hold" | "sell" | "add" | "reduce",
  "urgency": "high" | "medium" | "low",
  "parity_analysis": "¿el CEDEAR cotiza cerca de la paridad? ¿hay premium o descuento significativo?",
  "ccl_analysis": "comparación entre CCL implícito y CCL oficial, y qué significa para el inversor",
  "underlying_view": "1 oración sobre la perspectiva del subyacente {ticker} en USD",
  "vs_dolar_mep": "¿conviene tener este CEDEAR vs comprar directamente dólares MEP? 1-2 oraciones",
  "rationale": "3-4 oraciones en español justificando la recomendación para esta posición específica",
  "key_alert": "alerta importante si hay algo urgente, o null"
}}
"""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}]
    )

    text  = response.content[0].text
    start = text.find("{")
    end   = text.rfind("}")
    raw   = text[start:end + 1] if start != -1 else text.strip()

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        result = {"action": "error", "urgency": "low", "rationale": raw}

    result.update({
        "ticker":            ticker,
        "asset_type":        "cedear",
        "shares":            shares,
        "avg_buy_price":     avg_buy,
        "current_price_ars": market_price_ars,
        "current_value_ars": round(current_value, 2),
        "cost_basis_ars":    round(cost_basis, 2),
        "pnl_ars":           round(pnl_ars, 2),
        "pnl_pct":           round(pnl_pct, 2),
        "parity_price_ars":  parity,
        "premium_discount_pct": premium_pct,
        "ccl_implicit":      ccl_impl,
        "us_price_usd":      us_price,
        "ratio":             ratio,
        "ceo_score":         ceo_score,
        "currency":          "ARS",
    })
    return result


def _load_cached_analysis(ticker: str) -> dict | None:
    cache_file = f"storage/{ticker}_analysis.json"
    if not os.path.exists(cache_file):
        return None
    try:
        with open(cache_file) as f:
            data = json.load(f)
        return data if data.get("status") == "ok" else None
    except Exception:
        return None
