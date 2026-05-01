import json
import os
import sys
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv(override=True)
sys.path.append(".")

client = Anthropic()

from data.fetcher import get_stock_data
from agents.fundamental import analyze_fundamental
from agents.technical import analyze_technical
from agents.indicators import analyze_indicators
from agents.sentiment import analyze_sentiment


def run_analysis(ticker: str) -> dict:
    """
    Orquesta los 4 sub-agentes y genera la tesis final del CEO.
    """

    print(f"\n{'='*50}")
    print(f"  ANÁLISIS COMPLETO: {ticker}")
    print(f"{'='*50}\n")

    with open("instructions/investor_profile.json") as f:
        profile = json.load(f)

    # --- 1. Traer datos del mercado ---
    print("📡 Obteniendo datos del mercado...")
    stock_data = get_stock_data(ticker)
    if stock_data.get("status") == "error":
        return {"status": "error", "message": stock_data.get("message")}

    price = stock_data["price"]
    fundamental_info = stock_data["fundamental"]
    print(f"   {fundamental_info['company_name']} — ${price['current_price']} USD\n")

    # --- 2. Correr los 4 sub-agentes ---
    print("🔍 Agente Fundamental analizando...")
    fundamental_report = analyze_fundamental(ticker, stock_data, profile)
    print(f"   Veredicto: {fundamental_report.get('verdict')} | Score: {fundamental_report.get('score')}/10")

    print("📈 Agente Técnico analizando...")
    technical_report = analyze_technical(ticker, stock_data, profile)
    print(f"   Veredicto: {technical_report.get('verdict')} | Score: {technical_report.get('score')}/10")

    print("📊 Agente Indicadores analizando...")
    indicators_report = analyze_indicators(ticker, stock_data, profile)
    print(f"   Veredicto: {indicators_report.get('verdict')} | Score: {indicators_report.get('score')}/10")

    print("🧠 Agente Sentimiento analizando...")
    sentiment_report = analyze_sentiment(ticker, stock_data, profile)
    print(f"   Veredicto: {sentiment_report.get('verdict')} | Score: {sentiment_report.get('score')}/10\n")

    # --- 3. CEO sintetiza todo ---
    print("🎯 CEO generando tesis de inversión...")
    ceo_thesis = _run_ceo(ticker, stock_data, profile, {
        "fundamental": fundamental_report,
        "technical":   technical_report,
        "indicators":  indicators_report,
        "sentiment":   sentiment_report
    })

    return {
        "status":    "ok",
        "ticker":    ticker,
        "reports":   {
            "fundamental": fundamental_report,
            "technical":   technical_report,
            "indicators":  indicators_report,
            "sentiment":   sentiment_report
        },
        "ceo_thesis": ceo_thesis
    }


def _run_ceo(ticker, stock_data, profile, reports) -> dict:
    """
    El CEO recibe los 4 reportes y genera la tesis final.
    """

    price       = stock_data["price"]
    fundamental = stock_data["fundamental"]
    verdicts    = {k: v.get("verdict") for k, v in reports.items()}
    scores      = {k: v.get("score")   for k, v in reports.items()}
    avg_score   = round(sum(s for s in scores.values() if s) / len(scores), 1)

    prompt = f"""
Sos el Chief Executive Officer (CEO) de un family office. Recibís los reportes
de tus 4 analistas especializados y tomás la decisión final de inversión.
Tu responsabilidad es proteger el capital del inversor y generar retornos consistentes.

## Perfil del inversor
- Nombre: {profile["investor"]["name"]}
- Experiencia: {profile["investor"]["experience_level"]}
- Riesgo: {profile["risk_profile"]["level"]}
- Stop loss: {profile["risk_profile"]["stop_loss_pct"]}%
- Take profit: {profile["risk_profile"]["take_profit_pct"]}%
- Máximo por posición: {profile["risk_profile"]["max_portfolio_allocation_per_stock_pct"]}%

## Empresa: {ticker}
- Nombre: {fundamental.get("company_name")}
- Sector: {fundamental.get("sector")}
- Precio actual: ${price.get("current_price")}
- Market cap: ${price.get("market_cap"):,}

## Reportes de los sub-agentes
### Agente Fundamental (score: {scores["fundamental"]}/10)
{json.dumps(reports["fundamental"], ensure_ascii=False, indent=2)}

### Agente Técnico (score: {scores["technical"]}/10)
{json.dumps(reports["technical"], ensure_ascii=False, indent=2)}

### Agente Indicadores (score: {scores["indicators"]}/10)
{json.dumps(reports["indicators"], ensure_ascii=False, indent=2)}

### Agente Sentimiento (score: {scores["sentiment"]}/10)
{json.dumps(reports["sentiment"], ensure_ascii=False, indent=2)}

## Resumen de veredictos
- Fundamental: {verdicts["fundamental"]}
- Técnico: {verdicts["technical"]}
- Indicadores: {verdicts["indicators"]}
- Sentimiento: {verdicts["sentiment"]}
- Score promedio: {avg_score}/10

## Tu tarea
Analizá los 4 reportes, identificá coincidencias y conflictos entre analistas,
y tomá una decisión final. Si hay conflictos importantes, explicá por qué
priorizás unos sobre otros.

Respondé ÚNICAMENTE con JSON válido, sin texto adicional:

{{
  "final_verdict": "buy" | "sell" | "hold" | "avoid",
  "conviction": "high" | "medium" | "low",
  "ceo_score": <número del 1 al 10>,
  "price_target": <precio objetivo en USD o null>,
  "stop_loss":    <precio de stop loss en USD>,
  "take_profit":  <precio de take profit en USD>,
  "time_horizon": "corto plazo (1-4 semanas)" | "mediano plazo (1-3 meses)" | "largo plazo (6+ meses)",
  "analysts_agreement": "descripción de si los analistas coinciden o hay conflictos",
  "thesis": "tesis de inversión principal en 3-4 oraciones en español",
  "pros": ["argumento a favor 1", "argumento a favor 2", "argumento a favor 3"],
  "cons": ["argumento en contra 1", "argumento en contra 2"],
  "action_steps": [
    "Paso 1: descripción concreta",
    "Paso 2: descripción concreta",
    "Paso 3: descripción concreta"
  ],
  "risk_warning": "advertencia de riesgo personalizada para el inversor",
  "ceo_summary": "resumen ejecutivo en español de máximo 5 oraciones que el inversor puede leer en 30 segundos"
}}
"""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}]
    )

    text = response.content[0].text
    start, end = text.find("{"), text.rfind("}")
    raw = text[start:end + 1] if start != -1 and end != -1 else text.strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"verdict": "error", "raw_response": raw}


def print_thesis(result: dict):
    """
    Imprime la tesis del CEO de forma legible en la terminal.
    """
    if result.get("status") == "error":
        print(f"Error: {result.get('message')}")
        return

    thesis = result.get("ceo_thesis", {})
    ticker = result.get("ticker")

    print(f"\n{'='*50}")
    print(f"  TESIS CEO — {ticker}")
    print(f"{'='*50}")
    print(f"  Veredicto:   {thesis.get('final_verdict', '').upper()}")
    print(f"  Convicción:  {thesis.get('conviction', '').upper()}")
    print(f"  Score CEO:   {thesis.get('ceo_score')}/10")
    print(f"  Horizonte:   {thesis.get('time_horizon')}")
    print(f"  Stop Loss:   ${thesis.get('stop_loss')}")
    print(f"  Take Profit: ${thesis.get('take_profit')}")
    print(f"\n  TESIS:")
    print(f"  {thesis.get('thesis')}")
    print(f"\n  PROS:")
    for pro in thesis.get("pros", []):
        print(f"  ✓ {pro}")
    print(f"\n  CONTRAS:")
    for con in thesis.get("cons", []):
        print(f"  ✗ {con}")
    print(f"\n  PASOS A SEGUIR:")
    for step in thesis.get("action_steps", []):
        print(f"  → {step}")
    print(f"\n  ADVERTENCIA:")
    print(f"  {thesis.get('risk_warning')}")
    print(f"\n{'='*50}\n")


if __name__ == "__main__":
    ticker = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    result = run_analysis(ticker)
    print_thesis(result)

    output_file = f"storage/{ticker}_analysis.json"
    with open(output_file, "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"Análisis guardado en {output_file}")

    # Enviar email con la tesis
    from notifications.email_sender import send_investment_email
    send_investment_email(result)