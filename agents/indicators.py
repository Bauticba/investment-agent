import json
import os
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv(override=True)
client = Anthropic()


def analyze_indicators(ticker: str, stock_data: dict, investor_profile: dict) -> dict:
    technical = stock_data.get("technical", {})
    price     = stock_data.get("price", {})
    rules     = investor_profile.get("technical_rules", {})

    closes  = technical.get("price_history_6mo", [])
    volumes = technical.get("volume_history_6mo", [])

    macd_signal = _calculate_macd(closes)
    bb          = _calculate_bollinger(closes)
    vol_trend   = _volume_trend(volumes)

    prompt = f"""
Sos un analista cuantitativo especializado en indicadores técnicos.
Tu trabajo es interpretar indicadores y determinar el momentum del activo.

## Reglas del inversor
- RSI mínimo: {rules.get("min_rsi")} / RSI máximo: {rules.get("max_rsi")}
- Confirmación de volumen requerida: {rules.get("require_volume_confirmation")}

## Indicadores calculados para {ticker}
- Precio actual: ${price.get("current_price")}
- RSI 14: {technical.get("rsi_14")}
- MA 20: {technical.get("ma_20")}
- MA 50: {technical.get("ma_50")}
- MA 200: {technical.get("ma_200")}
- MACD señal: {macd_signal}
- Bollinger Bands: {bb}
- Tendencia de volumen (últimos 10 días vs 20 días): {vol_trend}

## Tu tarea
Interpretá estos indicadores en conjunto y determiná el momentum actual.
Respondé ÚNICAMENTE con JSON válido, sin texto adicional:

{{
  "agent": "indicators",
  "ticker": "{ticker}",
  "verdict": "buy" | "sell" | "hold" | "avoid",
  "score": <número del 1 al 10>,
  "momentum": "strong_bullish" | "bullish" | "neutral" | "bearish" | "strong_bearish",
  "rsi_interpretation": "descripción breve del RSI actual",
  "macd_interpretation": "descripción breve del MACD",
  "bollinger_interpretation": "descripción breve respecto a las bandas",
  "volume_interpretation": "descripción breve del volumen",
  "strengths": ["señal positiva 1", "señal positiva 2"],
  "weaknesses": ["señal negativa 1"],
  "flags": ["alerta si algún indicador viola las reglas del inversor"],
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
            "agent": "indicators",
            "ticker": ticker,
            "verdict": "error",
            "raw_response": raw
        }


# --- Helpers de cálculo ---

def _calculate_macd(closes: list) -> dict:
    if len(closes) < 26:
        return {"signal": "insufficient_data"}
    ema12 = _ema(closes, 12)
    ema26 = _ema(closes, 26)
    if not ema12 or not ema26:
        return {"signal": "insufficient_data"}
    macd_line = ema12 - ema26
    return {
        "macd_line": round(macd_line, 3),
        "signal":    "bullish" if macd_line > 0 else "bearish"
    }


def _calculate_bollinger(closes: list, period: int = 20) -> dict:
    if len(closes) < period:
        return {"signal": "insufficient_data"}
    recent = closes[-period:]
    ma     = sum(recent) / period
    std    = (sum((x - ma) ** 2 for x in recent) / period) ** 0.5
    upper  = round(ma + 2 * std, 2)
    lower  = round(ma - 2 * std, 2)
    price  = closes[-1]
    if price > upper:
        position = "above_upper_band"
    elif price < lower:
        position = "below_lower_band"
    else:
        pct = round((price - lower) / (upper - lower) * 100, 1)
        position = f"inside_bands_{pct}pct_from_lower"
    return {"upper": upper, "lower": lower, "ma": round(ma, 2), "position": position}


def _ema(closes: list, period: int) -> float:
    if len(closes) < period:
        return None
    k   = 2 / (period + 1)
    ema = sum(closes[:period]) / period
    for price in closes[period:]:
        ema = price * k + ema * (1 - k)
    return ema


def _volume_trend(volumes: list) -> str:
    if len(volumes) < 20:
        return "insufficient_data"
    avg_recent = sum(volumes[-10:]) / 10
    avg_prior  = sum(volumes[-20:-10]) / 10
    if avg_prior == 0:
        return "insufficient_data"
    change = ((avg_recent - avg_prior) / avg_prior) * 100
    if change > 20:
        return f"increasing_strongly (+{round(change, 1)}%)"
    elif change > 5:
        return f"increasing (+{round(change, 1)}%)"
    elif change < -20:
        return f"decreasing_strongly ({round(change, 1)}%)"
    elif change < -5:
        return f"decreasing ({round(change, 1)}%)"
    else:
        return f"stable ({round(change, 1)}%)"


if __name__ == "__main__":
    import sys
    sys.path.append(".")
    from data.fetcher import get_stock_data

    with open("instructions/investor_profile.json") as f:
        profile = json.load(f)

    ticker = "AAPL"
    print(f"Obteniendo datos de {ticker}...")
    stock_data = get_stock_data(ticker)

    print("Analizando indicadores...")
    result = analyze_indicators(ticker, stock_data, profile)
    print(json.dumps(result, indent=2, ensure_ascii=False))