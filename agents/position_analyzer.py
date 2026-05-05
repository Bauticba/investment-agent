import json
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()
client = Anthropic()


def analyze_position(position: dict, stock_analysis: dict, investor_profile: dict) -> dict:
    ticker       = position["ticker"]
    shares       = position["shares"]
    avg_buy      = position["avg_buy_price"]
    currency     = position.get("currency", "USD")
    notes        = position.get("notes", "")

    price        = stock_analysis.get("price", {})
    current      = price.get("current_price", 0) or 0
    ceo          = stock_analysis.get("ceo_thesis", {})

    cost_basis   = shares * avg_buy
    current_val  = shares * current
    pnl_usd      = current_val - cost_basis
    pnl_pct      = ((current - avg_buy) / avg_buy * 100) if avg_buy else 0

    stop_price   = ceo.get("stop_loss")
    target_price = ceo.get("take_profit")
    dist_stop    = round((current - stop_price) / current * 100, 1) if stop_price and current else None
    dist_target  = round((target_price - current) / current * 100, 1) if target_price and current else None

    prompt = f"""
Sos un asesor de inversiones personal. Analizás una posición existente en el portafolio
de un inversor y recomendás qué hacer con ella en este momento.

## Perfil del inversor
- Nombre: {investor_profile["investor"]["name"]}
- Experiencia: {investor_profile["investor"]["experience_level"]}
- Riesgo: {investor_profile["risk_profile"]["level"]}
- Stop loss objetivo: {investor_profile["risk_profile"]["stop_loss_pct"]}%
- Take profit objetivo: {investor_profile["risk_profile"]["take_profit_pct"]}%

## Posición actual en {ticker}
- Cantidad de acciones/unidades: {shares}
- Precio promedio de compra: ${avg_buy:.2f} {currency}
- Precio actual de mercado: ${current:.2f} {currency}
- Valor actual de la posición: ${current_val:.2f}
- Costo base: ${cost_basis:.2f}
- Ganancia/Pérdida no realizada: ${pnl_usd:+.2f} ({pnl_pct:+.1f}%)
- Stop loss sugerido por análisis: ${stop_price}
- Take profit sugerido por análisis: ${target_price}
- Distancia al stop loss: {f'{dist_stop:+.1f}%' if dist_stop is not None else 'N/A'}
- Distancia al take profit: {f'{dist_target:+.1f}%' if dist_target is not None else 'N/A'}
{f'- Notas del inversor: {notes}' if notes else ''}

## Análisis actual del activo
- Veredicto CEO: {ceo.get("final_verdict", "N/A").upper()}
- Score CEO: {ceo.get("ceo_score", "N/A")}/10
- Convicción: {ceo.get("conviction", "N/A")}
- Horizonte sugerido: {ceo.get("time_horizon", "N/A")}
- Tesis: {ceo.get("thesis", "N/A")}
- Pros: {json.dumps(ceo.get("pros", []), ensure_ascii=False)}
- Contras: {json.dumps(ceo.get("cons", []), ensure_ascii=False)}
- Advertencia de riesgo: {ceo.get("risk_warning", "N/A")}

## Tu tarea
Analizá esta posición específica considerando:
1. El P&L actual y qué tan cerca está del stop loss o take profit
2. El veredicto actual del análisis del activo
3. Si tiene sentido mantener, agregar, reducir o salir dada la situación actual
4. Urgencia de la acción (¿hay que actuar hoy o puede esperar?)

Respondé ÚNICAMENTE con JSON válido, sin texto adicional:

{{
  "ticker": "{ticker}",
  "action": "hold" | "sell" | "add" | "reduce" | "stop_loss_triggered",
  "urgency": "high" | "medium" | "low",
  "shares_to_add": <entero o null>,
  "shares_to_sell": <entero o null>,
  "rationale": "2-3 oraciones en español explicando la recomendación para esta posición",
  "key_alert": "alerta importante si hay algo urgente (ej: stop loss a punto de tocarse, earnings próximos), o null"
}}
"""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=600,
        messages=[{"role": "user", "content": prompt}]
    )

    text = response.content[0].text
    start, end = text.find("{"), text.rfind("}")
    raw = text[start:end + 1] if start != -1 else text.strip()

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        result = {"ticker": ticker, "action": "error", "urgency": "low", "rationale": raw}

    result.update({
        "shares":          shares,
        "avg_buy_price":   avg_buy,
        "current_price":   current,
        "current_value_usd": round(current_val, 2),
        "cost_basis_usd":  round(cost_basis, 2),
        "pnl_usd":         round(pnl_usd, 2),
        "pnl_pct":         round(pnl_pct, 2),
        "stop_loss_price": stop_price,
        "take_profit_price": target_price,
        "currency":        currency,
    })
    return result
