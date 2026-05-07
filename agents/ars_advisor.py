import json
from datetime import date
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()
client = Anthropic()


def _horizonte_context(fecha_objetivo: str | None) -> tuple[str, int | None]:
    """
    Dado 'YYYY-MM' o 'YYYY-MM-DD', devuelve (descripción legible, meses_restantes).
    Si no se provee fecha, devuelve ("sin fecha límite definida", None).
    """
    if not fecha_objetivo:
        return "sin fecha límite definida", None

    try:
        parts = fecha_objetivo.strip().split("-")
        year, month = int(parts[0]), int(parts[1])
        target = date(year, month, 1)
        today  = date.today()
        meses  = (target.year - today.year) * 12 + (target.month - today.month)
        meses  = max(meses, 0)
        desc   = f"{fecha_objetivo} ({meses} meses desde hoy)"
        return desc, meses
    except Exception:
        return fecha_objetivo, None

RIESGO_DESC = {
    "bajo":     "preservar capital, mínima volatilidad. Prioridad en cobertura de inflación y liquidez. Evitar acciones, bonos hard dollar y exposición cambiaria directa. Horizonte hasta 6 meses.",
    "moderado": "balance entre cobertura inflacionaria, algo de exposición en dólares y equity moderado. Acepta volatilidad media. Puede incluir bonos hard dollar, ONs USD y CEDEARs en proporciones limitadas. Horizonte 6–12 meses.",
    "alto":     "maximizar retornos reales, acepta alta volatilidad. Fuerte exposición en dólares (MEP, hard dollar, ONs) y equity (CEDEARs, acciones MERVAL). Horizonte mínimo 12–24 meses.",
}


def _horizonte_rules(meses: int | None) -> str:
    if meses is None:
        return ""
    if meses <= 3:
        return "- RESTRICCIÓN CRÍTICA: el dinero se necesita en ≤3 meses. Priorizar EXCLUSIVAMENTE instrumentos de alta liquidez: Caución, FCI Money Market, LECER corta. Prohibido PF UVA (mínimo 90 días), bonos de largo plazo y CEDEARs."
    if meses <= 6:
        return "- RESTRICCIÓN: horizonte corto (≤6 meses). Preferir instrumentos con vencimiento antes de la fecha objetivo. Evitar PF UVA >90 días, CEDEARs y acciones. TX26 (vence nov 2026) puede ser válido si cae antes del objetivo."
    if meses <= 12:
        return "- Horizonte medio (6–12 meses). Podés incluir TX26, LECER, PF UVA, MEP y CEDEARs con moderación. Evitar bonos de largo plazo (TX28+, GD35+)."
    if meses <= 24:
        return "- Horizonte 1–2 años. Podés incluir el universo completo compatible con el perfil. Preferir vencimientos antes de la fecha objetivo para bonos CER."
    return "- Horizonte largo (>2 años). Sin restricciones de plazo. Podés asumir mayor iliquidez a cambio de mayor retorno."


def _filter_by_horizon(instruments: list, meses: int) -> list:
    """Descarta instrumentos cuyo plazo mínimo supera el horizonte disponible."""
    PLAZO_MINIMO = {
        "plazo_fijo_uva": 3,   # mínimo 90 días = 3 meses
        "plazo_fijo":     1,
        "fci_acciones":   12,  # no recomendable en menos de 12 meses
        "fci_dolar_linked": 6,
    }
    result = []
    for inst in instruments:
        tipo = inst.get("type", "")
        min_meses = PLAZO_MINIMO.get(tipo, 0)
        if min_meses <= meses:
            result.append(inst)
    return result


def _format_news_block(news: list | None) -> str:
    if not news:
        return "No se pudieron obtener noticias recientes."
    lines = []
    for a in news:
        lines.append(f"- [{a['date']} — {a['source']}] {a['title']}")
        if a.get("summary"):
            lines.append(f"  {a['summary']}")
    return "\n".join(lines)


def recommend_allocation(
    capital: float,
    riesgo: str,
    instruments: list,
    macro: dict,
    profile: dict,
    fecha_objetivo: str | None = None,
    news: list | None = None,
) -> dict:
    """
    Genera una recomendación de inversión en ARS para el capital y riesgo dados.
    fecha_objetivo: 'YYYY-MM' o 'YYYY-MM-DD' opcional — fecha en que el usuario necesita el dinero.
    """
    riesgo_desc       = RIESGO_DESC.get(riesgo, RIESGO_DESC["moderado"])
    inflation_monthly = macro.get("inflation_monthly") or 3.5
    inflation_annual  = macro.get("inflation_annual") or 42.0
    usd_oficial       = macro.get("usd_oficial") or 1400
    uva               = macro.get("uva")

    horizonte_desc, horizonte_meses = _horizonte_context(fecha_objetivo)

    relevant = [i for i in instruments if riesgo in i.get("recommended_for", [])]

    # Filtrar instrumentos cuyo vencimiento supera la fecha objetivo
    if horizonte_meses is not None:
        relevant = _filter_by_horizon(relevant, horizonte_meses)

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

## Horizonte de inversión
- Fecha objetivo: {horizonte_desc}
{f"- Meses disponibles: {horizonte_meses}" if horizonte_meses is not None else "- Sin restricción de plazo definida"}
{_horizonte_rules(horizonte_meses)}

## Contexto macroeconómico actual
- Inflación mensual IPC: {inflation_monthly:.1f}% (último dato INDEC)
- Inflación anual: {inflation_annual:.1f}%
- Dólar oficial: ${usd_oficial:,.0f} ARS/USD
- UVA actual: {f'${uva:,.2f}' if uva else 'no disponible'}
- Régimen cambiario: tipo de cambio unificado desde abril 2025 (acuerdo FMI)

## Noticias recientes (últimas horas — medios argentinos)
{_format_news_block(news)}

## Universo de instrumentos disponibles (compatibles con perfil {riesgo.upper()})
{json.dumps(relevant, ensure_ascii=False, indent=2)}

## Reglas para construir la asignación

### Generales
1. Usá SOLO instrumentos de la lista de arriba (respetando el campo `id` exacto).
2. La suma de `allocation_pct` debe ser exactamente 100.
3. Los `amount_ars` deben ser enteros y sumar exactamente ${capital:,.0f}.
4. Siempre incluir FCI Money Market o Caución como reserva de liquidez (5–10% mínimo).
5. PF tradicional SOLO si inflación < TNA/12. Actualmente inflación mensual = {inflation_monthly:.1f}% → descartarlo si la TNA no la supera.

### Por perfil de riesgo
**BAJO** (preservación de capital):
- 40–50% CER corto (LECER o TX26) + 20–30% PF UVA + 15–20% FCI Renta Fija + 10% FCI MM / Caución
- Sin hard dollar bonds, sin ONs USD, sin CEDEARs, sin acciones

**MODERADO** (balance):
- 25–35% CER/UVA (LECER, TX26, PF UVA) — cobertura inflacionaria
- 20–30% dolarización (MEP + bonos hard dollar GD30/AL30 o ONs USD) — protección cambiaria
- 10–20% CEDEARs (acciones USA en ARS) — retorno en dólares vía equity
- 10–15% FCI Renta Fija o LECAP — rendimiento mayor al MM
- 5–10% FCI MM / Caución — liquidez

**ALTO** (maximizar retorno real):
- 30–40% dolarización fuerte (MEP + hard dollar GD35/AL35 + ONs USD)
- 25–35% equity (CEDEARs + FCI Renta Variable o acciones MERVAL individuales)
- 15–20% CER (TX28/TX30 o LECER para algo de cobertura)
- 5–10% FCI MM / Caución — liquidez mínima

### Instrucciones adicionales
- Entre bonos CER: preferir vencimiento más corto para riesgo BAJO/MODERADO (TX26 sobre TX28/TX30).
- Entre bonos hard dollar: GD30 o AL30 para duraciones cortas (MODERADO); GD35/AL35/GD41 para ALTO.
- CEDEARs: nombrar sectores preferidos (tech, energía, finanzas) pero NO nombrar tickers específicos — el usuario consultará el análisis separado.
- ONs USD: preferir emisores con mejor rating y vencimiento más próximo para MODERADO.
- FCI Renta Variable solo para riesgo ALTO, horizonte mínimo 12 meses.
- Cauciones: excelentes para liquidez de muy corto plazo (1–7 días), rendimiento superior al FCI MM.

## Tu tarea
Diseñá la asignación óptima para {profile["investor"]["name"]} con ${capital:,.0f} ARS
y perfil de riesgo {riesgo.upper()}. Justificá brevemente cada posición en el contexto macro actual.

Respondé ÚNICAMENTE con JSON válido, sin texto adicional:

{{
  "allocation": [
    {{
      "instrument_id": "id exacto del instrumento (ej: tx26, dolar_mep, lecer, gd30, ymcho, fci_money_market)",
      "name": "nombre legible del instrumento",
      "type": "tipo (bono_cer, lecer, lecap, caucion, plazo_fijo_uva, dolar_mep, bono_hard_dollar, on_usd, fci_mm, fci_renta_fija, fci_dolar_linked, fci_acciones, cedear, accion_merval)",
      "allocation_pct": <número, porcentaje del capital>,
      "amount_ars": <monto en ARS, entero>,
      "rationale": "1–2 oraciones justificando esta posición en el contexto macro actual",
      "how_to_buy": "instrucciones exactas de cómo comprar en Bull Market"
    }}
  ],
  "inflation_coverage_pct": <% del portafolio con cobertura inflacionaria real (CER/UVA/LECER)>,
  "usd_exposure_pct": <% del portafolio con exposición directa o indirecta en USD>,
  "strategy_summary": "3–4 oraciones en español explicando la lógica general de la estrategia y por qué esta combinación de instrumentos es óptima para el contexto actual",
  "main_risk": "principal riesgo de esta estrategia en el contexto argentino actual",
  "time_horizon": "horizonte de inversión recomendado (ej: 3–6 meses, 6–12 meses)",
  "review_in": "cuándo revisar la asignación (ej: próximo dato de inflación INDEC, en 30 días, antes del vencimiento de X)"
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
    raw   = text[start:end + 1] if start != -1 else text.strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"error": "parse_error", "raw": raw}
