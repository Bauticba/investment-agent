import json
import os
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()
client = Anthropic()


def analyze_fundamental(ticker: str, stock_data: dict, investor_profile: dict) -> dict:
    """
    Sub-agente de análisis fundamental.
    Recibe los datos del mercado y el perfil del inversor,
    devuelve un análisis estructurado en JSON.
    """

    fundamental = stock_data.get("fundamental", {})
    price       = stock_data.get("price", {})
    rules       = investor_profile.get("fundamental_rules", {})
    risk        = investor_profile.get("risk_profile", {})

    market_cap = price.get("market_cap")
    market_cap_str = f"${market_cap:,}" if market_cap else "N/A"

    is_etf = fundamental.get("quote_type", "").upper() in ("ETF", "MUTUALFUND") or \
             fundamental.get("sector") in ("etf", "ETF") or \
             ticker.upper() in ("SPY", "QQQ", "GLD", "XLE", "XLF", "VTI", "IWM", "VOO")

    if is_etf:
        prompt = f"""
Sos un analista de inversiones senior especializado en ETFs y fondos indexados.
Los ETFs no tienen P/E ni EPS individuales — evaluás su estructura, diversificación,
costos, activos subyacentes y comportamiento de mercado.

## Perfil del inversor
- Experiencia: {investor_profile.get("investor", {}).get("experience_level")}
- Riesgo: {risk.get("level")}

## Datos del ETF {ticker}
- Nombre: {fundamental.get("company_name")}
- Sector/categoría: {fundamental.get("sector")} / {fundamental.get("industry")}
- Precio actual: ${price.get("current_price")}
- AUM / Market cap proxy: {market_cap_str}
- Beta: {fundamental.get("beta")}
- Dividend yield: {fundamental.get("dividend_yield")}
- Descripción: {fundamental.get("description")}

## Tu tarea
Analizá este ETF como vehículo de inversión — diversificación, liquidez, costo, exposición sectorial
y si es adecuado para el perfil del inversor. Respondé ÚNICAMENTE con JSON válido:

{{
  "agent": "fundamental",
  "ticker": "{ticker}",
  "asset_type": "etf",
  "verdict": "buy" | "sell" | "hold" | "avoid",
  "score": <número del 1 al 10>,
  "strengths": ["fortaleza 1", "fortaleza 2"],
  "weaknesses": ["debilidad 1", "debilidad 2"],
  "flags": ["alerta si hay algo que no encaje con el perfil del inversor"],
  "summary": "resumen en 2-3 oraciones en español explicando el veredicto"
}}
"""
    else:
        prompt = f"""
Sos un analista fundamental de inversiones senior. Tu trabajo es analizar
los datos financieros de una empresa y emitir un veredicto claro.

## Perfil del inversor
- Nivel de experiencia: {investor_profile.get("investor", {}).get("experience_level")}
- Riesgo: {risk.get("level")}
- P/E máximo aceptable: {rules.get("max_pe_ratio")}
- Crecimiento mínimo de ingresos: {rules.get("min_revenue_growth_pct")}%
- Deuda/equity máxima: {rules.get("max_debt_to_equity")}
- Current ratio mínimo: {rules.get("min_current_ratio")}

## Datos fundamentales de {ticker}
- Empresa: {fundamental.get("company_name")}
- Sector: {fundamental.get("sector")} / {fundamental.get("industry")}
- Precio actual: ${price.get("current_price")}
- Market cap: {market_cap_str}
- P/E ratio: {fundamental.get("pe_ratio")}
- P/E forward: {fundamental.get("forward_pe")}
- EPS: {fundamental.get("eps")}
- Crecimiento ingresos: {fundamental.get("revenue_growth")}
- Crecimiento ganancias: {fundamental.get("earnings_growth")}
- Deuda/equity: {fundamental.get("debt_to_equity")}
- Current ratio: {fundamental.get("current_ratio")}
- Margen de ganancia: {fundamental.get("profit_margin")}
- ROE: {fundamental.get("return_on_equity")}
- Free cash flow: {fundamental.get("free_cashflow")}
- Beta: {fundamental.get("beta")}
- Dividend yield: {fundamental.get("dividend_yield")}
- Precio objetivo analistas: {fundamental.get("analyst_target")}
- Descripción: {fundamental.get("description")}

## Tu tarea
Analizá estos datos contra el perfil del inversor y respondé ÚNICAMENTE
con un JSON válido con esta estructura exacta, sin texto adicional:

{{
  "agent": "fundamental",
  "ticker": "{ticker}",
  "verdict": "buy" | "sell" | "hold" | "avoid",
  "score": <número del 1 al 10>,
  "strengths": ["fortaleza 1", "fortaleza 2"],
  "weaknesses": ["debilidad 1", "debilidad 2"],
  "flags": ["alerta 1 si hay algo que viole las reglas del inversor"],
  "summary": "resumen en 2-3 oraciones en español explicando el veredicto"
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
            "agent": "fundamental",
            "ticker": ticker,
            "verdict": "error",
            "raw_response": raw
        }


# --- Test rápido ---
if __name__ == "__main__":
    import sys
    sys.path.append(".")
    from data.fetcher import get_stock_data

    with open("instructions/investor_profile.json") as f:
        profile = json.load(f)

    ticker = "AAPL"
    print(f"Obteniendo datos de {ticker}...")
    stock_data = get_stock_data(ticker)

    print("Analizando con el agente fundamental...")
    result = analyze_fundamental(ticker, stock_data, profile)

    print(json.dumps(result, indent=2, ensure_ascii=False))