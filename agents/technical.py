import json
import os
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv(override=True)
client = Anthropic()


def analyze_technical(ticker: str, stock_data: dict, investor_profile: dict) -> dict:
    technical = stock_data.get("technical", {})
    price     = stock_data.get("price", {})
    rules     = investor_profile.get("technical_rules", {})

    prompt = f"""
Sos un analista técnico de mercados financieros. Analizás gráficos, 
medias móviles e indicadores para determinar el momento óptimo de entrada.

## Reglas del inversor
- Solo operar por encima de la MA200: {rules.get("only_above_200_day_ma")}
- RSI mínimo aceptable: {rules.get("min_rsi")}
- RSI máximo aceptable: {rules.get("max_rsi")}
- Requiere confirmación de volumen: {rules.get("require_volume_confirmation")}

## Datos técnicos de {ticker}
- Precio actual: ${price.get("current_price")}
- MA 20 días: {technical.get("ma_20")}
- MA 50 días: {technical.get("ma_50")}
- MA 200 días: {technical.get("ma_200")}
- RSI 14: {technical.get("rsi_14")}
- Máximo 52 semanas: {technical.get("52w_high")}
- Mínimo 52 semanas: {technical.get("52w_low")}
- Distancia al máximo 52s: {technical.get("price_vs_52w_high_pct")}%
- Últimos 30 cierres: {technical.get("price_history_6mo")}
- Últimos 30 volúmenes: {technical.get("volume_history_6mo")}

## Tu tarea
Analizá tendencia, momentum, soportes/resistencias y momento de entrada.
Respondé ÚNICAMENTE con JSON válido, sin texto adicional:

{{
  "agent": "technical",
  "ticker": "{ticker}",
  "verdict": "buy" | "sell" | "hold" | "avoid",
  "score": <número del 1 al 10>,
  "trend": "bullish" | "bearish" | "neutral",
  "entry_zone": "descripción del precio de entrada sugerido",
  "support_levels": [<precio1>, <precio2>],
  "resistance_levels": [<precio1>, <precio2>],
  "strengths": ["fortaleza técnica 1", "fortaleza técnica 2"],
  "weaknesses": ["debilidad técnica 1"],
  "flags": ["alerta si viola alguna regla del inversor"],
  "summary": "resumen en 2-3 oraciones en español"
}}
"""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}]
    )

    text = response.content[0].text
    start, end = text.find("{"), text.rfind("}")
    raw = text[start:end + 1] if start != -1 and end != -1 else text.strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {
            "agent": "technical",
            "ticker": ticker,
            "verdict": "error",
            "raw_response": raw
        }


if __name__ == "__main__":
    import sys
    sys.path.append(".")
    from data.fetcher import get_stock_data

    with open("instructions/investor_profile.json") as f:
        profile = json.load(f)

    ticker = "AAPL"
    print(f"Obteniendo datos de {ticker}...")
    stock_data = get_stock_data(ticker)

    print("Analizando con el agente técnico...")
    result = analyze_technical(ticker, stock_data, profile)
    print(json.dumps(result, indent=2, ensure_ascii=False))