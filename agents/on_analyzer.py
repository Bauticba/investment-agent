import json
from anthropic import Anthropic
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
client = Anthropic()


def analyze_on_position(position: dict, on_data: dict, investor_profile: dict) -> dict:
    """
    Analiza una posición en una Obligación Negociable (ON) corporativa USD.
    Obtiene precio vía IOL (en ARS). Calcula P&L, time to maturity y recomienda hold/sell/add.
    """
    ticker  = position["ticker"]
    shares  = position.get("shares", 0)
    avg_buy = position.get("avg_buy_price", 0)

    market_price_ars = on_data.get("market_price_ars")

    if not market_price_ars:
        return {
            "ticker":            ticker,
            "asset_type":        "on_usd",
            "action":            "sin_precio",
            "urgency":           "medium",
            "rationale":         f"No se pudo obtener precio de IOL para {ticker}. Verificá que el ticker sea correcto.",
            "key_alert":         "Precio IOL no disponible",
            "shares":            shares,
            "avg_buy_price":     avg_buy,
            "current_price_ars": None,
            "pnl_pct":           None,
        }

    cost_basis    = shares * avg_buy
    current_value = shares * market_price_ars
    pnl_ars       = current_value - cost_basis
    pnl_pct       = ((market_price_ars - avg_buy) / avg_buy * 100) if avg_buy else 0

    maturity     = on_data.get("maturity", "desconocido")
    days_to_mat  = None
    if maturity and maturity != "desconocido":
        try:
            days_to_mat = (datetime.strptime(maturity, "%Y-%m-%d") - datetime.now()).days
        except ValueError:
            pass

    coupon     = on_data.get("coupon", 0)
    issuer     = on_data.get("issuer", ticker)
    ccl        = on_data.get("ccl", 1300)
    price_usd  = round(market_price_ars / ccl, 2) if ccl else None
    avg_usd    = round(avg_buy / ccl, 2) if ccl else None

    stop_pct   = investor_profile.get("risk_profile", {}).get("stop_loss_pct", 8) / 100
    target_pct = investor_profile.get("risk_profile", {}).get("take_profit_pct", 20) / 100

    prompt = f"""
Sos un analista especializado en obligaciones negociables (ONs) corporativas argentinas.
Analizás una posición para un inversor minorista que opera en IOL (Invertir Online).

## Perfil del inversor
- Riesgo: {investor_profile.get("risk_profile", {}).get("level", "moderado")}
- Stop loss: {stop_pct*100:.0f}% | Take profit: {target_pct*100:.0f}%

## Posición actual — {ticker}
- Emisor: {issuer}
- Cantidad: {shares:,.0f} unidades
- Precio promedio de compra: ${avg_buy:,.2f} ARS (≈ ${avg_usd} USD al CCL actual)
- Precio actual IOL: ${market_price_ars:,.2f} ARS (≈ ${price_usd} USD al CCL actual)
- P&L: {pnl_pct:+.2f}% | ${pnl_ars:+,.0f} ARS
- Costo total: ${cost_basis:,.0f} ARS | Valor actual: ${current_value:,.0f} ARS
- Vencimiento: {maturity} ({f'{days_to_mat} días' if days_to_mat else 'N/D'})
- Cupón anual: {coupon*100:.2f}% USD
- CCL utilizado: ${ccl:,.0f} ARS/USD

## Contexto
Las ONs corporativas argentinas son instrumentos de deuda emitidos en USD y que cotizan
en BYMA en ARS al tipo de cambio implícito. El riesgo es corporativo (no soberano).
El inversor cobra cupones en USD y recupera el capital al vencimiento.
La principal métrica es el precio vs par (100%) y la TIR implícita.

## Tu tarea
Analizá la posición considerando:
1. P&L actual y tendencia (cerca de stop loss o take profit?)
2. Tiempo a vencimiento: si hay poco tiempo (< 180 días), sostener es generalmente seguro
3. Precio vs par: ¿está a descuento, a la par o con prima?
4. Riesgo corporativo del emisor ({issuer})
5. Conveniencia de mantener vs alternar a otro instrumento

Devolvé SOLO JSON válido con este esquema:
{{
  "action": "hold" | "sell" | "add" | "reduce",
  "urgency": "low" | "medium" | "high",
  "price_vs_par": "descuento" | "par" | "prima",
  "estimated_tir_usd": "string con TIR estimada (ej: '9.2%')",
  "days_to_maturity": {days_to_mat or 0},
  "rationale": "explicación clara en 2-3 oraciones en español",
  "key_alert": "alerta principal en 1 oración",
  "vs_alternatives": "comparación breve vs bono soberano o CEDEAR"
}}
"""

    try:
        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=600,
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
            "action":           "hold",
            "urgency":          "low",
            "price_vs_par":     "desconocido",
            "estimated_tir_usd": "N/D",
            "days_to_maturity": days_to_mat or 0,
            "rationale":        f"Análisis automático no disponible ({e}). Mantener hasta nueva revisión.",
            "key_alert":        "Revisar manualmente",
            "vs_alternatives":  "N/D",
        }

    return {
        "ticker":            ticker,
        "asset_type":        "on_usd",
        "issuer":            issuer,
        "action":            analysis.get("action", "hold"),
        "urgency":           analysis.get("urgency", "low"),
        "shares":            shares,
        "avg_buy_price":     avg_buy,
        "current_price_ars": market_price_ars,
        "current_price_usd": price_usd,
        "pnl_pct":           round(pnl_pct, 2),
        "pnl_ars":           round(pnl_ars, 0),
        "cost_basis_ars":    round(cost_basis, 0),
        "current_value_ars": round(current_value, 0),
        "maturity":          maturity,
        "days_to_maturity":  days_to_mat,
        "coupon_pct":        round(coupon * 100, 2),
        "price_vs_par":      analysis.get("price_vs_par", "desconocido"),
        "estimated_tir_usd": analysis.get("estimated_tir_usd", "N/D"),
        "rationale":         analysis.get("rationale", ""),
        "key_alert":         analysis.get("key_alert", ""),
        "vs_alternatives":   analysis.get("vs_alternatives", ""),
    }
