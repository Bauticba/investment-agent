import json
import math
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv(override=True)
client = Anthropic()


def build_portfolio(capital: float, candidates: list[dict], profile: dict) -> dict:
    """
    Recibe los análisis aprobados y distribuye el capital.
    candidates: lista de resultados de run_analysis() con final_verdict == "buy"
    """
    risk      = profile["risk_profile"]
    max_pct   = risk["max_portfolio_allocation_per_stock_pct"]
    stop_pct  = risk["stop_loss_pct"]
    sectors   = {v["ticker"]: v.get("sector") for v in candidates}

    summaries = []
    for r in candidates:
        t   = r["ticker"]
        ceo = r["ceo_thesis"]
        rep = r["reports"]

        summaries.append({
            "ticker":          t,
            "sector":          r.get("sector", "unknown"),
            "price":           r.get("price"),
            "ceo_score":       ceo.get("ceo_score"),
            "conviction":      ceo.get("conviction"),
            "price_target":    ceo.get("price_target"),
            "stop_loss":       ceo.get("stop_loss"),
            "take_profit":     ceo.get("take_profit"),
            "time_horizon":    ceo.get("time_horizon"),
            "thesis":          ceo.get("thesis"),
            "scores": {
                "fundamental": rep["fundamental"].get("score"),
                "technical":   rep["technical"].get("score"),
                "indicators":  rep["indicators"].get("score"),
                "sentiment":   rep["sentiment"].get("score"),
            },
            "pros":  ceo.get("pros", []),
            "cons":  ceo.get("cons", []),
        })

    prompt = f"""
Sos un especialista en construcción de portafolios de inversión.
Tu trabajo es distribuir un capital disponible entre un conjunto de
acciones pre-aprobadas por el sistema de análisis, maximizando el
retorno ajustado por riesgo y cumpliendo las restricciones del inversor.

## Capital disponible: ${capital:,.0f} USD

## Perfil del inversor
- Experiencia: {profile["investor"]["experience_level"]}
- Riesgo: {profile["risk_profile"]["level"]}
- Máximo por posición: {max_pct}% del capital (= ${capital * max_pct / 100:,.0f})
- Stop loss por posición: {stop_pct}%
- Horizontes: {profile["investment_style"]["horizons"]}

## Candidatos aprobados (veredicto BUY del CEO)
{json.dumps(summaries, ensure_ascii=False, indent=2)}

## Reglas de construcción del portafolio
1. Solo podés incluir los candidatos de la lista — no agregar otros.
2. Máximo {max_pct}% del capital en una sola posición.
3. Máximo 3 posiciones del mismo sector para diversificar.
4. Priorizá conviction "high" sobre "medium".
5. Priorizá ceo_score más alto ante igualdad de conviction.
6. Reservá entre 5-10% del capital en cash (no invertir todo).
7. Las cantidades de acciones deben ser enteros (sin fracciones).
8. Si el capital disponible no alcanza para 1 acción de un candidato, excluilo.

## Tu tarea
Construí el portafolio óptimo para Bautista. Considerá la diversificación
sectorial, la relación riesgo/retorno de cada posición y el horizonte de inversión.
Si hay pocos candidatos con BUY, podés incluir alguno con conviction alta aunque
el veredicto sea HOLD, pero justificalo.

Respondé ÚNICAMENTE con JSON válido, sin texto adicional:

{{
  "positions": [
    {{
      "ticker":         "XXXX",
      "sector":         "technology",
      "price":          <precio actual>,
      "shares":         <cantidad entera de acciones>,
      "amount_usd":     <shares × price, redondeado a 2 decimales>,
      "allocation_pct": <porcentaje del capital total, redondeado a 1 decimal>,
      "conviction":     "high" | "medium" | "low",
      "ceo_score":      <score del CEO>,
      "stop_loss":      <precio de stop loss>,
      "take_profit":    <precio de take profit>,
      "rationale":      "1-2 oraciones en español explicando por qué esta posición y este tamaño"
    }}
  ],
  "cash_reserve":      <monto en USD que queda sin invertir>,
  "cash_reserve_pct":  <porcentaje del capital>,
  "total_invested":    <suma de todos los amount_usd>,
  "portfolio_thesis":  "párrafo en español describiendo la estrategia general del portafolio",
  "sector_breakdown":  {{"technology": X, "healthcare": Y, ...}},
  "expected_return":   "estimación cualitativa del retorno esperado en el horizonte definido",
  "main_risk":         "principal riesgo del portafolio construido"
}}
"""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=3000,
        messages=[{"role": "user", "content": prompt}]
    )

    text  = response.content[0].text
    start = text.find("{")
    end   = text.rfind("}")
    raw   = text[start:end + 1] if start != -1 and end != -1 else text.strip()

    try:
        portfolio = json.loads(raw)
        # Adjuntamos capital para que el email lo use
        portfolio["capital"] = capital
        return portfolio
    except json.JSONDecodeError:
        return {"error": "parse_error", "raw": raw}
