"""
Agente que analiza acciones del panel MERVAL para un inversor argentino en IOL.
Evalúa en ARS: valuación en dólares implícitos, cobertura inflacionaria,
riesgo regulatorio/político, y comparación vs. alternativas (bonos CER, MEP).
"""
import json
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()
client = Anthropic()


def analyze_merval_stock(ticker: str, merval_data: dict, investor_profile: dict) -> dict:
    """
    Genera una recomendación de compra/venta para una acción del MERVAL.
    Devuelve JSON con action, score/10, rationale e instrucciones IOL.
    """
    ticker = ticker.upper()
    name   = merval_data.get("name", ticker)
    market_price = merval_data.get("market_price_ars")

    if not market_price:
        return {
            "ticker":     ticker,
            "name":       name,
            "asset_type": "merval",
            "action":     "sin_precio",
            "urgency":    "high",
            "score":      None,
            "rationale":  (
                "No se pudo obtener el precio de mercado vía IOL. "
                "Verificar que el ticker sea correcto o ingresar el precio manualmente."
            ),
            "key_alert":  "Precio no disponible — verificar en IOL",
        }

    variacion     = merval_data.get("variacion_pct")
    maximo        = merval_data.get("maximo")
    minimo        = merval_data.get("minimo")
    ccl_oficial   = merval_data.get("ccl_oficial")
    ccl_implicit  = merval_data.get("ccl_implicit")
    usd_adr       = merval_data.get("usd_adr")
    usd_adr_price = merval_data.get("usd_adr_price")
    sector        = merval_data.get("sector")
    macro         = merval_data.get("macro", {})
    infl_m        = macro.get("inflation_monthly")
    infl_ya       = macro.get("inflation_annual")

    # Precio en USD implícito para contexto
    price_usd_implicit = round(market_price / ccl_oficial, 2) if ccl_oficial else None

    prompt = f"""
Sos un analista especializado en acciones argentinas del panel MERVAL. Analizás para un inversor minorista que opera en IOL (Invertir Online) con pesos argentinos.

## Perfil del inversor
- Experiencia: {investor_profile["investor"]["experience_level"]}
- Riesgo: {investor_profile["risk_profile"]["level"]}
- Broker: Invertir Online (IOL)

## Acción: {ticker} — {name}
- Sector: {sector}
- Precio actual: ${market_price:,.2f} ARS
{f'- Precio equivalente en USD (CCL): ~${price_usd_implicit:.2f} USD' if price_usd_implicit else ''}
- Variación del día: {f'{variacion:+.2f}%' if variacion is not None else 'N/A'}
- Máximo / Mínimo del día: ${maximo:,.2f} / ${minimo:,.2f} ARS
{f'- ADR en USA ({usd_adr}): ${usd_adr_price:.2f} USD' if usd_adr_price else ''}
{f'- CCL implícito en la acción: ${ccl_implicit:,.0f} ARS/USD' if ccl_implicit else ''}
- CCL oficial (mercado unificado): ${ccl_oficial:,.0f} ARS/USD

## Contexto macro argentino
- Inflación mensual: {f'{infl_m:.1f}%' if infl_m else 'N/A'}
- Inflación interanual: {f'{infl_ya:.1f}%' if infl_ya else 'N/A'}
- Régimen cambiario: tipo de cambio unificado desde abril 2025 (acuerdo FMI)

## Alternativas de inversión en ARS para comparar
- **Bono CER (TX26/TX28)**: ajuste por inflación + cupón, riesgo soberano
- **Plazo fijo UVA**: CER puro, sin riesgo soberano, liquidez nula 30 días
- **Dólar MEP**: dolarización total, elimina riesgo inflación y soberano ARS
- **Caución bursátil**: tasa fija corto plazo, liquidez inmediata

## Tu tarea
Analizá esta acción del MERVAL considerando:
1. **Valuación en dólares**: con el CCL implícito vs. el CCL oficial, ¿la acción está barata o cara en términos de USD? Históricamente las acciones argentinas se valúan en USD para comparación entre períodos
2. **Cobertura inflacionaria**: ¿el negocio es un buen hedge vs. inflación? (energía, minería y exportadores son mejores que servicios regulados en pesos)
3. **Riesgo regulatorio/político**: tarifas, retenciones, intervención estatal. ¿Qué tan expuesto está {sector} a decisiones del gobierno?
4. **Comparación vs. alternativas**: con inflación mensual del {f'{infl_m:.1f}%' if infl_m else 'N/A'}, ¿esta acción ofrece mejor retorno ajustado por riesgo que un bono CER o MEP?
5. **Momento de entrada**: variación del día y rango máx/mín dan contexto del momentum intradía

Respondé ÚNICAMENTE con JSON válido, sin texto adicional:

{{
  "action": "buy" | "hold" | "sell" | "avoid",
  "score": <entero 1-10>,
  "urgency": "high" | "medium" | "low",
  "usd_valuation": "¿la acción está barata, en valor justo o cara en USD considerando el CCL implícito?",
  "inflation_hedge": "¿es buen hedge contra inflación este negocio? Breve justificación.",
  "regulatory_risk": "1 oración sobre el riesgo regulatorio/político de este sector en Argentina actualmente.",
  "vs_alternatives": "¿conviene esta acción vs. bono CER o MEP para un perfil {investor_profile['risk_profile']['level']}? 1-2 oraciones.",
  "rationale": "3-4 oraciones justificando la recomendación para esta acción específica.",
  "key_alert": "alerta importante si hay algo urgente, o null",
  "how_to_buy": "IOL > Operar > Acciones > buscar {ticker} > Comprar"
}}
"""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=800,
        messages=[{"role": "user", "content": prompt}]
    )

    text  = response.content[0].text
    start = text.find("{")
    end   = text.rfind("}")
    raw   = text[start:end + 1] if start != -1 else text.strip()

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        result = {"action": "error", "score": None, "urgency": "low", "rationale": raw}

    result.update({
        "ticker":           ticker,
        "name":             name,
        "asset_type":       "merval",
        "sector":           sector,
        "market_price_ars": market_price,
        "variacion_pct":    variacion,
        "ccl_implicit":     ccl_implicit,
        "ccl_oficial":      ccl_oficial,
        "usd_adr":          usd_adr,
        "usd_adr_price":    usd_adr_price,
        "price_usd_implicit": price_usd_implicit,
        "currency":         "ARS",
    })
    return result


def get_top_merval(investor_profile: dict, min_score: float = 6.0, max_count: int = 3) -> list[dict]:
    """
    Analiza todas las acciones del MERVAL registry y devuelve las mejores por score.
    Usado por invest_ars.py para dar picks concretos de acciones argentinas.
    """
    from data.merval import get_all_merval_data

    results = []
    for data in get_all_merval_data():
        analysis = analyze_merval_stock(data["ticker"], data, investor_profile)
        score = analysis.get("score")
        if score and score >= min_score:
            results.append(analysis)

    results.sort(key=lambda x: x.get("score", 0), reverse=True)
    return results[:max_count]
