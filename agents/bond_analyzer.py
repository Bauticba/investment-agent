import json
from anthropic import Anthropic
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
client = Anthropic()


def analyze_bond_position(position: dict, bond_data: dict, investor_profile: dict) -> dict:
    """
    Analiza una posición en un bono argentino y recomienda qué hacer.
    Especializado en bonos CER (ajustados por inflación).
    """
    ticker   = position["ticker"]
    shares   = position.get("shares", 0)
    avg_buy  = position.get("avg_buy_price", 0)
    notes    = position.get("notes", "")

    market_price = bond_data.get("market_price")

    if not market_price:
        return {
            "ticker":          ticker,
            "asset_type":      "bono_argentino",
            "action":          "sin_precio",
            "urgency":         "high",
            "rationale":       (
                "No se pudo obtener el precio de mercado automáticamente. "
                "Agregá el precio actual en my_portfolio.json con el campo "
                "\"current_price_override\" (el precio lo encontrás en la app de IOL)."
            ),
            "key_alert":       "Precio no disponible — completar manualmente",
            "shares":          shares,
            "avg_buy_price":   avg_buy,
            "current_price_ars": None,
            "pnl_pct":         None,
        }

    cost_basis    = shares * avg_buy
    current_value = shares * market_price
    pnl_ars       = current_value - cost_basis
    pnl_pct       = ((market_price - avg_buy) / avg_buy * 100) if avg_buy else 0

    maturity     = bond_data.get("maturity")
    days_to_mat  = None
    if maturity:
        days_to_mat = (datetime.strptime(maturity, "%Y-%m-%d") - datetime.now()).days

    cer             = bond_data.get("cer")
    usd_oficial     = bond_data.get("usd_oficial")
    infl_monthly    = bond_data.get("inflation_monthly")
    coupon_annual   = bond_data.get("coupon_annual", 0)
    adjusts_by      = bond_data.get("adjusts_by", "CER")

    prompt = f"""
Sos un analista especializado en renta fija argentina. Analizás bonos soberanos
ajustados por inflación (CER/UVA) para inversores minoristas argentinos.

## Perfil del inversor
- Nombre: {investor_profile["investor"]["name"]}
- Experiencia: {investor_profile["investor"]["experience_level"]}
- Riesgo: {investor_profile["risk_profile"]["level"]}
- Contexto: inversor argentino en pesos, usa Invertir Online (IOL)

## Posición: {ticker} — {bond_data.get("name", ticker)}
- Tipo: Bono soberano argentino ajustado por {adjusts_by}
- Vencimiento: {maturity} ({days_to_mat} días corridos desde hoy)
- Cupón: {coupon_annual * 100:.1f}% anual sobre capital ajustado {adjusts_by}
- Amortización: {bond_data.get("amortization", "bullet")}

- Cantidad de títulos (VN $1): {shares:,}
- Precio promedio de compra: ${avg_buy:,.2f} ARS
- Precio actual de mercado: ${market_price:,.2f} ARS
- Valor actual de la posición: ${current_value:,.2f} ARS
- Costo base total: ${cost_basis:,.2f} ARS
- Ganancia/Pérdida nominal: ${pnl_ars:+,.2f} ARS ({pnl_pct:+.1f}%)
{f'- Notas del inversor: {notes}' if notes else ''}

## Contexto macro argentino (datos BCRA)
- Índice CER actual: {cer if cer else 'no disponible'}
- Tipo de cambio oficial: ${usd_oficial} ARS/USD {('(aprox)' if usd_oficial else '(no disponible)')}
- Inflación mensual último dato: {f'{infl_monthly:.1f}%' if infl_monthly else 'no disponible'}

## Alternativas de inversión en ARS para comparar
- **Plazo fijo UVA**: rinde CER puro, sin riesgo soberano, pero con riesgo bancario y liquidez nula 30 días
- **LECAP (Letra del Tesoro)**: tasa fija en pesos, sin ajuste CER, riesgo que la inflación la licúe
- **Dólar MEP (GD30/AL30)**: dolarización total, elimina riesgo CER y soberano pesos, pero pierde el cupón
- **FCI Money Market**: liquidez inmediata, tasa variable, sin ajuste inflación
- **Otros bonos CER**: TX28, TX30 para más duration; DICP con mayor cupón

## Tu tarea
Analizá esta posición de renta fija argentina considerando:
1. **P&L nominal vs real**: el pnl nominal puede ser positivo pero si la inflación superó ese retorno, perdiste poder adquisitivo
2. **Tiempo a vencimiento**: ¿conviene esperar al vencimiento (bullet) o salir antes en mercado secundario?
3. **Cobertura CER**: ¿sigue siendo relevante mantener cobertura de inflación con este bono?
4. **Riesgo soberano**: posibilidad de reestructuración, extensión de plazos (como pasó con los Bonos Dolar Link en 2020), o cambio en la fórmula CER
5. **Comparación vs alternativas**: ¿el precio actual del bono implica un rendimiento razonable vs un plazo fijo UVA o dolarizar?
6. **Perfil del inversor**: principiante con riesgo moderado; la recomendación debe ser clara y accionable

Respondé ÚNICAMENTE con JSON válido, sin texto adicional:

{{
  "action": "hold" | "sell" | "add" | "reduce",
  "urgency": "high" | "medium" | "low",
  "real_yield_estimate": "estimación de la TIR real aproximada (ej: 'CER + 5%' o 'negativa en términos reales')",
  "paridad_assessment": "análisis de si el precio de mercado parece caro, justo o barato vs el valor teórico CER",
  "vs_alternatives": "comparación concreta en 2 oraciones: ¿este bono vs plazo fijo UVA y vs dolarizar?",
  "sovereign_risk_note": "1 oración sobre el riesgo soberano actual y si afecta la recomendación",
  "rationale": "3-4 oraciones en español explicando la recomendación para esta posición específica",
  "key_alert": "alerta importante si hay algo urgente o relevante, o null"
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
        "asset_type":        "bono_argentino",
        "shares":            shares,
        "avg_buy_price":     avg_buy,
        "current_price_ars": market_price,
        "current_value_ars": round(current_value, 2),
        "cost_basis_ars":    round(cost_basis, 2),
        "pnl_ars":           round(pnl_ars, 2),
        "pnl_pct":           round(pnl_pct, 2),
        "maturity":          maturity,
        "days_to_maturity":  days_to_mat,
        "currency":          "ARS",
    })
    return result
