import json
import os
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv(override=True)
client = Anthropic()


def analyze_sentiment(ticker: str, stock_data: dict, investor_profile: dict) -> dict:
    fundamental = stock_data.get("fundamental", {})
    price       = stock_data.get("price", {})
    technical   = stock_data.get("technical", {})
    news        = stock_data.get("news", [])

    news_block = _format_news(news) if news else "No hay noticias recientes disponibles."

    is_etf = ticker.upper() in ("SPY", "QQQ", "GLD", "XLE", "XLF", "VTI", "IWM", "VOO") or \
             fundamental.get("quote_type", "").upper() in ("ETF", "MUTUALFUND")
    asset_label = "ETF/Fondo indexado" if is_etf else "Empresa"
    etf_note = "\nNOTA: Este es un ETF — evaluá el sentimiento del mercado/sector que representa, no de una empresa individual." if is_etf else ""

    market_cap = price.get("market_cap")
    market_cap_str = f"${market_cap:,}" if market_cap else "N/A"

    prompt = f"""
Sos un analista de sentimiento de mercado. Tu trabajo es evaluar el contexto
general del mercado, la narrativa alrededor del activo y señales cualitativas
que los otros agentes no capturan con números.{etf_note}

## {asset_label} analizado
- Ticker: {ticker}
- Nombre: {fundamental.get("company_name")}
- Sector: {fundamental.get("sector")} / {fundamental.get("industry")}
- Precio actual: ${price.get("current_price")}
- Market cap: {market_cap_str}
- Descripción: {fundamental.get("description")}

## Contexto cuantitativo
- RSI actual: {technical.get("rsi_14")}
- Distancia al máximo 52 semanas: {technical.get("price_vs_52w_high_pct")}%
- Crecimiento de ingresos: {fundamental.get("revenue_growth")}
- Margen de ganancia: {fundamental.get("profit_margin")}
- ROE: {fundamental.get("return_on_equity")}
- Beta: {fundamental.get("beta")}
- Precio objetivo analistas: {fundamental.get("analyst_target")}

## Noticias recientes (Finnhub — últimos 7 días)
{news_block}

## Perfil del inversor
- Nivel: {investor_profile.get("investor", {}).get("experience_level")}
- Horizonte: {investor_profile.get("investment_style", {}).get("horizons")}
- Sectores permitidos: {investor_profile.get("sectors", {}).get("allowed")}

## Tu tarea
Analizá las noticias recientes junto con el contexto del sector y la empresa.
Evaluá el tono general de la cobertura mediática, posibles catalizadores o riesgos
emergentes, y si el sentimiento actual es consistente con los fundamentos.

Respondé ÚNICAMENTE con JSON válido, sin texto adicional:

{{
  "agent": "sentiment",
  "ticker": "{ticker}",
  "verdict": "buy" | "sell" | "hold" | "avoid",
  "score": <número del 1 al 10>,
  "market_sentiment": "very_bullish" | "bullish" | "neutral" | "bearish" | "very_bearish",
  "news_tone": "very_positive" | "positive" | "neutral" | "negative" | "very_negative",
  "news_summary": "resumen de 1-2 oraciones sobre el tono de las noticias recientes",
  "competitive_position": "descripción de la posición competitiva de la empresa",
  "sector_outlook": "perspectiva del sector en el corto/mediano plazo",
  "key_risks": ["riesgo 1", "riesgo 2", "riesgo 3"],
  "key_catalysts": ["catalizador positivo 1", "catalizador positivo 2"],
  "investor_fit": "descripción de si esta inversión es apropiada para el perfil del inversor",
  "strengths": ["fortaleza cualitativa 1", "fortaleza cualitativa 2"],
  "weaknesses": ["debilidad cualitativa 1"],
  "flags": ["alerta importante si existe"],
  "summary": "resumen en 2-3 oraciones en español"
}}
"""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}]
    )

    text  = response.content[0].text
    start = text.find("{")
    end   = text.rfind("}")
    raw   = text[start:end + 1] if start != -1 and end != -1 else text.strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"agent": "sentiment", "ticker": ticker, "verdict": "error", "raw_response": raw}


def _format_news(articles: list) -> str:
    lines = []
    for i, a in enumerate(articles, 1):
        lines.append(f"{i}. [{a['date']}] {a['source']}: {a['headline']}")
        if a.get("summary"):
            lines.append(f"   {a['summary']}")
    return "\n".join(lines)


if __name__ == "__main__":
    import sys
    sys.path.append(".")
    from data.fetcher import get_stock_data

    with open("instructions/investor_profile.json") as f:
        profile = json.load(f)

    ticker = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    print(f"Obteniendo datos de {ticker}...")
    stock_data = get_stock_data(ticker)

    print("Analizando sentimiento...")
    result = analyze_sentiment(ticker, stock_data, profile)
    print(json.dumps(result, indent=2, ensure_ascii=False))
