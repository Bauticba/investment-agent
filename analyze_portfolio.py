import json
import time
import argparse
from datetime import date
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

from agents.position_analyzer import analyze_position
from agents.bond_analyzer import analyze_bond_position
from agents.cedear_analyzer import analyze_cedear_position
from agents.on_analyzer import analyze_on_position
from agents.fci_analyzer import analyze_fci_position
from data.argentina import get_bond_data, BOND_REGISTRY
from data.cedears import get_cedear_data, CEDEAR_REGISTRY
from data.instruments_ar import get_on_data, ON_REGISTRY, HARD_DOLLAR_BOND_REGISTRY, FCI_REGISTRY
from notifications.email_sender import send_portfolio_analysis_email
from core.cache import get_analysis_cached

client = Anthropic()
DELAY_BETWEEN_TICKERS = 12


def run_portfolio_analysis(portfolio_file: str = "my_portfolio.json", use_cache: bool = False):
    with open("instructions/investor_profile.json") as f:
        profile = json.load(f)

    with open(portfolio_file) as f:
        portfolio_input = json.load(f)

    positions = portfolio_input.get("positions", [])
    cash      = portfolio_input.get("cash", {"USD": 0, "ARS": 0})
    broker    = portfolio_input.get("broker", "desconocido")

    print(f"\n{'='*55}")
    print(f"  ANÁLISIS DE PORTAFOLIO — {broker}")
    print(f"{'='*55}")
    print(f"  Posiciones: {len(positions)} activos")
    print(f"  Cash: USD ${cash.get('USD', 0):,.0f} | ARS ${cash.get('ARS', 0):,.0f}\n")

    # --- Clasificar posiciones ---
    bond_positions   = [p for p in positions if _is_arg_bond(p)]
    cedear_positions = [p for p in positions if _is_cedear(p)]
    on_positions     = [p for p in positions if _is_on(p) and not _is_arg_bond(p)]
    fci_positions    = [p for p in positions if _is_fci(p)]
    stock_positions  = [p for p in positions if
                        not _is_arg_bond(p) and not _is_cedear(p)
                        and not _is_on(p) and not _is_fci(p)]

    # --- 1a. Análisis de acciones (pipeline existente) ---
    analyses = {}
    stock_tickers = list({p["ticker"] for p in stock_positions})
    for i, ticker in enumerate(stock_tickers):
        if i > 0:
            print(f"⏳ Esperando {DELAY_BETWEEN_TICKERS}s (rate limit)...")
            time.sleep(DELAY_BETWEEN_TICKERS)
        result = get_analysis_cached(ticker, use_cache)
        if result.get("status") == "ok":
            analyses[ticker] = result
        else:
            print(f"⚠️  {ticker}: no se pudo analizar — {result.get('message', 'error')}")

    # --- 1b. Datos de bonos argentinos ---
    bond_data_map = {}
    for p in bond_positions:
        ticker   = p["ticker"]
        override = p.get("current_price_override")
        print(f"🇦🇷 Obteniendo datos de {ticker} (bono argentino)...")
        bond_data_map[ticker] = get_bond_data(ticker, price_override=override)
        src = bond_data_map[ticker].get("price_source", "?")
        price = bond_data_map[ticker].get("market_price")
        print(f"   Precio: ${price:,.2f} ARS (fuente: {src})" if price else f"   ⚠️  Precio no disponible")

    # --- 1c. Datos de ONs (obligaciones negociables) ---
    on_data_map = {}
    for p in on_positions:
        ticker   = p["ticker"].upper()
        override = p.get("current_price_override")
        print(f"🏦 Obteniendo datos de {ticker} (ON corporativa USD)...")
        on_data_map[ticker] = get_on_data(ticker, price_ars_override=override)
        od = on_data_map[ticker]
        price = od.get("market_price_ars")
        src   = od.get("price_source", "?")
        print(f"   ARS: ${price:,.2f} (fuente: {src})" if price else f"   ⚠️  Precio no disponible")

    # --- 1d. Datos de CEDEARs ---
    cedear_data_map = {}
    for p in cedear_positions:
        ticker   = p["ticker"].upper()
        override = p.get("current_price_override")
        print(f"🌎 Obteniendo datos de {ticker} (CEDEAR)...")
        cedear_data_map[ticker] = get_cedear_data(ticker, price_ars_override=override)
        cd = cedear_data_map[ticker]
        if cd.get("status") == "ok":
            src   = cd.get("price_source", "?")
            price = cd.get("market_price_ars")
            par   = cd.get("parity_price_ars")
            print(f"   ARS: ${price:,.2f} | Paridad: ${par:,.2f} (fuente: {src})")
        else:
            print(f"   ⚠️  {cd.get('message', 'error')}")

    # --- 2. Analizar cada posición ---
    print(f"\n{'='*55}")
    print(f"  ANÁLISIS POR POSICIÓN")
    print(f"{'='*55}")

    position_reports = []

    for position in stock_positions:
        ticker = position["ticker"]
        if ticker not in analyses:
            print(f"⚠️  {ticker}: sin análisis, se omite")
            continue
        report = analyze_position(position, analyses[ticker], profile)
        position_reports.append(report)
        emoji = {"hold": "⏸", "sell": "🔴", "add": "🟢", "reduce": "🟡",
                 "stop_loss_triggered": "🚨"}.get(report.get("action"), "❓")
        print(f"  {emoji} {ticker}: {report.get('action','?').upper()} | "
              f"P&L: {report.get('pnl_pct', 0):+.1f}% | Urgencia: {report.get('urgency','?').upper()}")
        if report.get("key_alert"):
            print(f"     ⚠️  {report['key_alert']}")

    for position in bond_positions:
        ticker = position["ticker"]
        bd = bond_data_map.get(ticker, {})
        print(f"  🇦🇷 Analizando bono {ticker}...")
        report = analyze_bond_position(position, bd, profile)
        position_reports.append(report)
        emoji = {"hold": "⏸", "sell": "🔴", "add": "🟢", "reduce": "🟡",
                 "sin_precio": "❓"}.get(report.get("action"), "❓")
        pnl_str = f"{report.get('pnl_pct', 0):+.1f}%" if report.get("pnl_pct") is not None else "N/A"
        print(f"  {emoji} {ticker}: {report.get('action','?').upper()} | "
              f"P&L: {pnl_str} | Urgencia: {report.get('urgency','?').upper()}")
        if report.get("key_alert"):
            print(f"     ⚠️  {report['key_alert']}")

    for position in on_positions:
        ticker = position["ticker"].upper()
        od = on_data_map.get(ticker, {})
        print(f"  🏦 Analizando ON {ticker}...")
        report = analyze_on_position(position, od, profile)
        position_reports.append(report)
        emoji = {"hold": "⏸", "sell": "🔴", "add": "🟢", "reduce": "🟡",
                 "sin_precio": "❓"}.get(report.get("action"), "❓")
        pnl_str = f"{report.get('pnl_pct', 0):+.1f}%" if report.get("pnl_pct") is not None else "N/A"
        print(f"  {emoji} {ticker}: {report.get('action','?').upper()} | "
              f"P&L: {pnl_str} | TIR: {report.get('estimated_tir_usd','N/D')}")
        if report.get("key_alert"):
            print(f"     ⚠️  {report['key_alert']}")

    for position in cedear_positions:
        ticker = position["ticker"].upper()
        cd = cedear_data_map.get(ticker, {})
        print(f"  🌎 Analizando CEDEAR {ticker}...")
        report = analyze_cedear_position(position, cd, profile)
        position_reports.append(report)
        emoji = {"hold": "⏸", "sell": "🔴", "add": "🟢", "reduce": "🟡",
                 "sin_precio": "❓"}.get(report.get("action"), "❓")
        pnl_str = f"{report.get('pnl_pct', 0):+.1f}%" if report.get("pnl_pct") is not None else "N/A"
        premium = report.get("premium_discount_pct")
        premium_str = f" | Paridad: {premium:+.1f}%" if premium is not None else ""
        print(f"  {emoji} {ticker}: {report.get('action','?').upper()} | "
              f"P&L: {pnl_str}{premium_str} | Urgencia: {report.get('urgency','?').upper()}")
        if report.get("key_alert"):
            print(f"     ⚠️  {report['key_alert']}")

    # --- 1e. Macro para FCI (necesario para estimar rendimiento efectivo) ---
    fci_macro = None
    if fci_positions:
        try:
            from data.argentina import get_macro_data
            fci_macro = get_macro_data()
        except Exception:
            pass

    for position in fci_positions:
        ticker   = position["ticker"]
        fci_meta = FCI_REGISTRY.get(ticker, {})
        if fci_meta:
            print(f"  💵 Analizando FCI {ticker} ({fci_meta.get('name', ticker)})...")
            report = analyze_fci_position(position, fci_meta, profile, macro=fci_macro)
            print(f"     Rendimiento estimado: ~{report.get('effective_yield_est_tna','?')}% TNA | "
                  f"Acción: {report.get('action','?').upper()}")
        else:
            print(f"  💵 {ticker}: FCI sin composición registrada — reporte básico")
            report = _make_fci_report(position)
        position_reports.append(report)

    if not position_reports:
        print("No hay posiciones para analizar.")
        return

    # --- 3. CEO sintetiza el portafolio completo ---
    print(f"\n  Sintetizando visión general del portafolio...")
    thesis = _run_portfolio_ceo(position_reports, cash, profile, broker)

    # --- 4. Mostrar resumen ---
    _print_summary(position_reports, thesis, cash)

    # --- 5. Enviar email ---
    print("📧 Enviando email...")
    send_portfolio_analysis_email(position_reports, thesis, cash, broker)

    # --- 6. Guardar ---
    output_file = f"storage/portfolio_analysis_{date.today().isoformat()}.json"
    with open(output_file, "w") as f:
        json.dump({
            "date":             date.today().isoformat(),
            "broker":           broker,
            "cash":             cash,
            "positions":        position_reports,
            "portfolio_thesis": thesis,
        }, f, indent=2, ensure_ascii=False)
    print(f"💾 Guardado en {output_file}\n")


def main():
    args = _parse_args()
    run_portfolio_analysis(args.portfolio, use_cache=args.use_cache)


# --- Helpers ---

def _run_portfolio_ceo(position_reports, cash, profile, broker) -> dict:
    total_cost  = sum(r.get("cost_basis_usd", 0) for r in position_reports)
    total_value = sum(r.get("current_value_usd", 0) for r in position_reports)
    total_pnl   = total_value - total_cost
    pnl_pct     = (total_pnl / total_cost * 100) if total_cost else 0

    prompt = f"""
Sos el CEO de un family office analizando el portafolio completo de un inversor.
Tu trabajo es dar una visión holística y las acciones concretas y prioritarias.

## Perfil del inversor
- Nombre: {profile["investor"]["name"]}
- Experiencia: {profile["investor"]["experience_level"]}
- Riesgo: {profile["risk_profile"]["level"]}
- Broker: {broker}

## Estado del portafolio
- Costo base total: ${total_cost:,.2f} USD
- Valor actual: ${total_value:,.2f} USD
- P&L no realizado: ${total_pnl:+,.2f} USD ({pnl_pct:+.1f}%)
- Cash disponible: USD ${cash.get('USD', 0):,.0f} | ARS ${cash.get('ARS', 0):,.0f}

## Análisis por posición
{json.dumps(position_reports, ensure_ascii=False, indent=2)}

## Tu tarea
Respondé ÚNICAMENTE con JSON válido:

{{
  "portfolio_health": "excellent" | "good" | "warning" | "critical",
  "diversification_score": <1 al 10>,
  "overall_assessment": "descripción del estado general del portafolio en 2 oraciones",
  "priority_actions": [
    {{"ticker": "XXXX o null", "action": "descripción concreta de qué hacer", "urgency": "high|medium|low"}}
  ],
  "cash_recommendation": "qué hacer con el cash disponible, en 1-2 oraciones",
  "portfolio_summary": "resumen ejecutivo de 3-4 oraciones para el inversor",
  "main_risk": "principal riesgo del portafolio actual",
  "next_review": "cuándo revisar el portafolio (ej: en 2 semanas, antes del próximo earnings)"
}}
"""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}]
    )

    text = response.content[0].text
    start, end = text.find("{"), text.rfind("}")
    raw = text[start:end + 1] if start != -1 else text.strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"error": "parse_error", "raw": raw}


def _print_summary(position_reports, thesis, cash):
    total_cost_usd  = sum(r.get("cost_basis_usd", 0) for r in position_reports)
    total_value_usd = sum(r.get("current_value_usd", 0) for r in position_reports)
    total_cost_ars  = sum(r.get("cost_basis_ars", 0) for r in position_reports)
    total_value_ars = sum(r.get("current_value_ars", 0) for r in position_reports)
    total_pnl_usd   = total_value_usd - total_cost_usd
    total_pnl_ars   = total_value_ars - total_cost_ars
    pnl_pct_usd     = (total_pnl_usd / total_cost_usd * 100) if total_cost_usd else 0
    pnl_pct_ars     = (total_pnl_ars / total_cost_ars * 100) if total_cost_ars else 0

    # alias para el CEO prompt (que usa usd keys)
    total_cost  = total_cost_usd
    total_value = total_value_usd
    total_pnl   = total_pnl_usd
    pnl_pct     = pnl_pct_usd

    action_labels = {
        "hold":                "⏸  MANTENER",
        "sell":                "🔴 VENDER",
        "add":                 "🟢 COMPRAR MÁS",
        "reduce":              "🟡 REDUCIR",
        "stop_loss_triggered": "🚨 STOP LOSS",
    }
    urgency_order = {"high": 0, "medium": 1, "low": 2}

    print(f"\n{'='*60}")
    print(f"  RESUMEN PORTAFOLIO")
    print(f"{'='*60}")
    if total_cost_usd:
        print(f"  Acciones USD  — Invertido: ${total_cost_usd:>10,.2f}  |  Valor: ${total_value_usd:>10,.2f}  |  P&L: ${total_pnl_usd:>+10,.2f} ({pnl_pct_usd:+.1f}%)")
    if total_cost_ars:
        print(f"  Bonos ARS     — Invertido: ${total_cost_ars:>10,.0f}  |  Valor: ${total_value_ars:>10,.0f}  |  P&L: ${total_pnl_ars:>+10,.0f} ({pnl_pct_ars:+.1f}%)")
    print(f"  Cash USD:     ${cash.get('USD', 0):>12,.0f}")
    print(f"  Cash ARS:     ${cash.get('ARS', 0):>12,.0f}")

    print(f"\n  {'Ticker':<8} {'Acción':<22} {'P&L %':>8}  {'Urgencia'}")
    print(f"  {'-'*55}")
    for r in sorted(position_reports, key=lambda x: urgency_order.get(x.get("urgency", "low"), 2)):
        label   = action_labels.get(r.get("action", ""), r.get("action", "?"))
        pnl_str = f"{r.get('pnl_pct', 0):+.1f}%"
        urgency = r.get("urgency", "?").upper()
        print(f"  {r.get('ticker','?'):<8} {label:<22} {pnl_str:>8}  {urgency}")
        if r.get("key_alert"):
            print(f"           ⚠️  {r['key_alert']}")

    health_emoji = {"excellent": "✅", "good": "🟢", "warning": "🟡", "critical": "🔴"}.get(
        thesis.get("portfolio_health", ""), "❓"
    )
    print(f"\n  ESTADO GENERAL: {health_emoji} {thesis.get('portfolio_health', '?').upper()}")
    print(f"  Diversificación: {thesis.get('diversification_score', '?')}/10")

    print(f"\n  RESUMEN:")
    print(f"  {thesis.get('portfolio_summary', '')}")

    print(f"\n  ACCIONES PRIORITARIAS:")
    emoji_u = {"high": "🔴", "medium": "🟡", "low": "🟢"}
    for a in thesis.get("priority_actions", []):
        ticker_str = f"[{a['ticker']}] " if a.get("ticker") else ""
        print(f"  {emoji_u.get(a.get('urgency',''), '')} {ticker_str}{a.get('action', '')}")

    print(f"\n  CASH:")
    print(f"  {thesis.get('cash_recommendation', '')}")

    print(f"\n  RIESGO PRINCIPAL:")
    print(f"  {thesis.get('main_risk', '')}")

    print(f"\n  PRÓXIMA REVISIÓN: {thesis.get('next_review', '')}")
    print(f"{'='*60}\n")


def _is_arg_bond(position: dict) -> bool:
    if position.get("asset_type") in ("bono_cer_argentino", "bono_argentino", "bono"):
        return True
    return position["ticker"].upper() in BOND_REGISTRY


def _is_cedear(position: dict) -> bool:
    if position.get("asset_type") == "cedear":
        return True
    return position["ticker"].upper() in CEDEAR_REGISTRY


def _is_on(position: dict) -> bool:
    if position.get("asset_type") in ("on_usd", "bono_hard_dollar"):
        return True
    ticker = position["ticker"].upper()
    return ticker in ON_REGISTRY or ticker in HARD_DOLLAR_BOND_REGISTRY


def _is_fci(position: dict) -> bool:
    if position.get("asset_type") in ("fci_mm", "fci", "fondo_comun"):
        return True
    return position["ticker"].upper().startswith("IOL")


def _make_fci_report(position: dict) -> dict:
    """
    Genera un reporte informativo para FCIs (fondos comunes de inversión).
    No llama APIs externas — usa el valor guardado por el sync de IOL si está disponible.
    """
    ticker    = position["ticker"]
    shares    = position.get("shares", 0)
    avg_price = position.get("avg_buy_price", 0)
    cost_ars  = round(shares * avg_price, 2)

    # IOL sync stores valorizado in current_value_ars when available
    current_value = position.get("current_value_ars") or cost_ars
    current_price = position.get("current_price_ars") or avg_price
    pnl_ars = round(current_value - cost_ars, 2)
    pnl_pct = round(pnl_ars / cost_ars * 100, 2) if cost_ars else 0.0

    return {
        "ticker":            ticker,
        "asset_type":        "fci_mm",
        "action":            "hold",
        "urgency":           "low",
        "shares":            shares,
        "avg_buy_price":     avg_price,
        "current_price_ars": current_price,
        "current_value_ars": current_value,
        "cost_basis_ars":    cost_ars,
        "pnl_ars":           pnl_ars,
        "pnl_pct":           pnl_pct,
        "rationale":         (
            "FCI money market — instrumento de liquidez diaria equivalente a efectivo. "
            "El capital rinde a tasa de mercado. No aplica stop loss ni take profit. "
            "Consultá el valor actualizado de las cuota-partes en la app de IOL."
        ),
        "key_alert":         None,
    }


def _parse_args():
    parser = argparse.ArgumentParser(description="Análisis de portafolio existente")
    parser.add_argument(
        "--portfolio", default="my_portfolio.json",
        help="JSON con tus posiciones (default: my_portfolio.json)"
    )
    parser.add_argument(
        "--use-cache", action="store_true",
        help="Usar análisis cacheados del storage en vez de re-analizar"
    )
    return parser.parse_args()


if __name__ == "__main__":
    main()
