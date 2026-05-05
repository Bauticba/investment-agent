import json
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()
client = Anthropic()

RIESGO_DESC = {
    "bajo":     "preservar capital, mínima volatilidad, prioridad en cobertura de inflación y liquidez. Evitar acciones y exposición cambiaria directa.",
    "moderado": "balance entre cobertura inflacionaria, algo de exposición en dólares y equity moderado. Acepta algo de volatilidad a cambio de mejor rendimiento real.",
    "alto":     "maximizar retornos reales, acepta alta volatilidad. Fuerte exposición en dólares y equity (CEDEARs). Horizonte mínimo 6-12 meses.",
}


def recommend_allocation(
    capital: float,
    riesgo: str,
    instruments: list,
    macro: dict,
    profile: dict,
) -> dict:
    """
    Genera una recomendación de inversión en ARS para el capital y riesgo dados.
    """
    riesgo_desc       = RIESGO_DESC.get(riesgo, RIESGO_DESC["moderado"])
    inflation_monthly = macro.get("inflation_monthly") or 3.5
    inflation_annual  = macro.get("inflation_annual") or 42.0
    usd_oficial       = macro.get("usd_oficial") or 1400
    uva               = macro.get("uva")

    # Solo incluir instrumentos recomendados para el perfil de riesgo
    relevant = [i for i in instruments if riesgo in i.get("recommended_for", [])]

    prompt = f"""
Sos un asesor financiero personal especializado en el mercado argentino de capitales.
Tu trabajo es recomendar cómo distribuir un monto en pesos para maximizar el retorno
real (por encima de la inflación) cumpliendo el perfil de riesgo del inversor.

## Perfil del inversor
- Nombre: {profile["investor"]["name"]}
- Experiencia: {profile["investor"]["experience_level"]}
- Riesgo solicitado: {riesgo.upper()}
- Descripción del riesgo: {riesgo_desc}
- Broker: Bull Market Brokers (Argentina)

## Capital a invertir
- Monto: ${capital:,.0f} ARS

## Contexto macroeconómico actual
- Inflación mensual IPC: {inflation_monthly:.1f}% (marzo 2026, INDEC)
- Inflación anual: {inflation_annual:.1f}%
- Dólar oficial: ${usd_oficial:,.0f} ARS/USD
- UVA actual: {f'${uva:,.2f}' if uva else 'no disponible'}
- Régimen cambiario: tipo de cambio unificado desde abril 2025 (acuerdo FMI)
- Contexto: inflación desacelerando, crawling peg estable, riesgo soberano moderado

## Instrumentos disponibles (compatibles con el perfil de riesgo {riesgo.upper()})
{json.dumps(relevant, ensure_ascii=False, indent=2)}

## Reglas para construir la asignación
1. Usá SOLO instrumentos de la lista de arriba.
2. La suma de todos los `allocation_pct` debe ser exactamente 100.
3. Siempre incluir FCI Money Market como reserva de liquidez (5-10% mínimo).
4. Los montos en `amount_ars` deben ser enteros y sumar exactamente el capital.
5. Para riesgo BAJO: priorizar PF UVA + FCI. Sin CEDEARs. Máx 20% en bonos CER.
6. Para riesgo MODERADO: 30-50% cobertura CER/UVA + 20-30% dólar MEP + 10-20% CEDEARs + 10% FCI.
7. Para riesgo ALTO: 20-30% MEP + 30-40% CEDEARs + 20% bonos CER + 10% FCI.
8. Entre bonos CER, preferir el de vencimiento más corto si el riesgo es bajo/moderado.
9. El plazo fijo TRADICIONAL solo es recomendable si la TNA supera la inflación proyectada.
   Actualmente inflación mensual = {inflation_monthly:.1f}% → PF tradicional PIERDE en términos reales.
10. Sé muy específico: nombrar el bono exacto (TX26, TX28), no "bonos CER" genérico.

## Tu tarea
Diseñá la asignación óptima para {profile["investor"]["name"]} con ${capital:,.0f} ARS
y perfil de riesgo {riesgo.upper()}. Justificá brevemente cada posición.

Respondé ÚNICAMENTE con JSON válido, sin texto adicional:

{{
  "allocation": [
    {{
      "instrument_id": "id del instrumento (ej: tx26, dolar_mep, fci_money_market)",
      "name": "nombre legible del instrumento",
      "type": "tipo (bono_cer, plazo_fijo_uva, dolar_mep, fci_mm, cedears)",
      "allocation_pct": <número, porcentaje del capital>,
      "amount_ars": <monto en ARS, entero>,
      "rationale": "1-2 oraciones justificando esta posición específica en el contexto actual",
      "how_to_buy": "instrucciones exactas de cómo comprar en Bull Market"
    }}
  ],
  "inflation_coverage_pct": <% del portafolio con cobertura inflacionaria real (CER/UVA/USD)>,
  "usd_exposure_pct": <% del portafolio con exposición directa o indirecta en USD>,
  "strategy_summary": "3-4 oraciones en español explicando la lógica general de la estrategia",
  "main_risk": "principal riesgo de esta estrategia en el contexto argentino actual",
  "time_horizon": "horizonte de inversión recomendado (ej: 3-6 meses, 6-12 meses)",
  "review_in": "cuándo revisar la asignación (ej: próximo dato de inflación del INDEC, en 30 días)"
}}
"""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2500,
        messages=[{"role": "user", "content": prompt}]
    )

    text  = response.content[0].text
    start = text.find("{")
    end   = text.rfind("}")
    raw   = text[start:end + 1] if start != -1 else text.strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"error": "parse_error", "raw": raw}
