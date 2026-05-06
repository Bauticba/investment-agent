import argparse
import json
import sys
from datetime import date

from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, ".")

from data.argentina import get_macro_data
from data.instruments_ar import get_instruments_universe
from agents.ars_advisor import recommend_allocation
from data.cedears import get_top_cedears
from notifications.email_sender import send_ars_recommendation_email


def run_ars(capital: float, riesgo: str = "moderado"):
    print(f"\n{'='*58}")
    print(f"  RECOMENDACIÓN DE INVERSIÓN EN PESOS ARGENTINOS")
    print(f"  Capital: ${capital:,.0f} ARS  |  Riesgo: {riesgo.upper()}")
    print(f"{'='*58}\n")

    # --- 1. Contexto macro ---
    print("📊 Obteniendo contexto macro argentino...")
    macro = get_macro_data()
    _print_macro(macro)

    # --- 2. Universo de instrumentos ---
    print("\n📋 Construyendo universo de instrumentos disponibles...")
    instruments = get_instruments_universe(macro)
    relevant    = [i for i in instruments if riesgo in i.get("recommended_for", [])]
    print(f"   {len(instruments)} instrumentos totales | {len(relevant)} compatibles con riesgo {riesgo.upper()}")

    # --- 3. Recomendación ---
    with open("instructions/investor_profile.json") as f:
        profile = json.load(f)

    print(f"\n🤖 Generando recomendación personalizada...")
    rec = recommend_allocation(capital, riesgo, instruments, macro, profile)

    if "error" in rec:
        print(f"❌ Error al generar la recomendación: {rec.get('raw', '')[:200]}")
        return

    # --- 4. Mostrar ---
    _print_recommendation(rec, capital, riesgo)

    # --- 4b. Si hay CEDEARs en el portafolio recomendado, mostrar picks específicos ---
    has_cedears = any(p.get("type") in ("cedear", "cedears") for p in rec.get("allocation", []))
    cedear_picks = None
    if has_cedears:
        _print_cedear_picks()
        cedear_picks = get_top_cedears(max_count=3, min_score=6.0)

    # --- 4c. Enviar email ---
    print("📧 Enviando email...")
    send_ars_recommendation_email(rec, capital, riesgo, macro, cedear_picks)

    # --- 5. Guardar ---
    output_file = f"storage/inversion_ars_{date.today().isoformat()}.json"
    with open(output_file, "w") as f:
        json.dump({
            "date":           date.today().isoformat(),
            "capital_ars":    capital,
            "riesgo":         riesgo,
            "macro":          macro,
            "recommendation": rec,
        }, f, indent=2, ensure_ascii=False)
    print(f"💾 Guardado en {output_file}\n")


def main():
    args = _parse_args()
    run_ars(args.capital, args.riesgo)


# --- helpers de presentación ---

def _print_macro(macro: dict):
    infl_m = macro.get("inflation_monthly")
    infl_a = macro.get("inflation_annual")
    usd    = macro.get("usd_oficial")
    uva    = macro.get("uva")
    print(f"   Inflación mensual : {f'{infl_m:.1f}%' if infl_m else 'N/A'}")
    print(f"   Inflación anual   : {f'{infl_a:.1f}%' if infl_a else 'N/A'}")
    print(f"   Dólar oficial     : {f'${usd:,.0f} ARS/USD' if usd else 'N/A'}")
    print(f"   UVA               : {f'${uva:,.2f}' if uva else 'N/A'}")


def _print_recommendation(rec: dict, capital: float, riesgo: str):
    allocation = rec.get("allocation", [])

    # Tabla principal
    print(f"\n{'='*62}")
    print(f"  PORTAFOLIO RECOMENDADO — ${capital:,.0f} ARS — RIESGO {riesgo.upper()}")
    print(f"{'='*62}")
    print(f"\n  {'Instrumento':<32} {'%':>5}  {'Monto ARS':>14}")
    print(f"  {'-'*56}")

    type_emoji = {
        "bono_cer":          "📈",
        "lecer":             "📈",
        "lecap":             "📋",
        "caucion":           "🔐",
        "plazo_fijo_uva":    "🔒",
        "plazo_fijo":        "🔒",
        "dolar_mep":         "💵",
        "bono_hard_dollar":  "💲",
        "on_usd":            "🏢",
        "fci_mm":            "💧",
        "fci_renta_fija":    "💧",
        "fci_dolar_linked":  "💵",
        "fci_acciones":      "📊",
        "cedear":            "🌎",
        "cedears":           "🌎",
        "accion_merval":     "🇦🇷",
    }

    for pos in allocation:
        emoji = type_emoji.get(pos.get("type", ""), "  ")
        name  = f"{emoji} {pos.get('name', '?')}"[:32]
        pct   = pos.get("allocation_pct", 0)
        amt   = pos.get("amount_ars", 0)
        print(f"  {name:<32} {pct:>4.0f}%  ${amt:>13,.0f}")

    total_pct = sum(p.get("allocation_pct", 0) for p in allocation)
    total_amt = sum(p.get("amount_ars", 0) for p in allocation)
    print(f"  {'-'*56}")
    print(f"  {'TOTAL':<32} {total_pct:>4.0f}%  ${total_amt:>13,.0f}")

    # Métricas clave
    print(f"\n  Cobertura inflacionaria : {rec.get('inflation_coverage_pct', '?')}% del portafolio")
    print(f"  Exposición en USD       : {rec.get('usd_exposure_pct', '?')}% del portafolio")
    print(f"  Horizonte               : {rec.get('time_horizon', '?')}")

    # Estrategia
    print(f"\n  ESTRATEGIA:")
    print(f"  {rec.get('strategy_summary', '')}")

    # Instrucciones de ejecución
    print(f"\n  CÓMO EJECUTARLO EN BULL MARKET:")
    print(f"  {'-'*56}")
    for i, pos in enumerate(allocation, 1):
        emoji = type_emoji.get(pos.get("type", ""), "")
        print(f"\n  {i}. {emoji} {pos.get('name', '?')} — ${pos.get('amount_ars', 0):,.0f} ARS ({pos.get('allocation_pct', 0):.0f}%)")
        print(f"     Cómo: {pos.get('how_to_buy', '?')}")
        print(f"     Por qué: {pos.get('rationale', '')}")

    # Riesgos y revisión
    print(f"\n  RIESGO PRINCIPAL:")
    print(f"  {rec.get('main_risk', '')}")
    print(f"\n  PRÓXIMA REVISIÓN: {rec.get('review_in', '?')}")
    print(f"{'='*62}\n")


def _print_cedear_picks():
    print(f"\n{'='*62}")
    print(f"  CEDEARS RECOMENDADOS (basado en análisis cacheados)")
    print(f"{'='*62}")
    picks = get_top_cedears(max_count=3, min_score=6.0)
    if not picks:
        print("  No hay análisis cacheados de CEDEARs disponibles.")
        print("  Ejecutá: python3 run_watchlist.py   para generarlos.\n")
        return
    for i, p in enumerate(picks, 1):
        print(f"\n  {i}. {p['ticker']} — {p['name']}")
        print(f"     Score CEO: {p['score']}/10 | Convicción: {p.get('conviction', '?').upper()}")
        print(f"     Subyacente USA: ${p.get('us_price_usd', '?')} USD")
        if p.get("parity_price_ars"):
            print(f"     Paridad estimada ARS: ${p['parity_price_ars']:,.2f} (ratio 1:{p['ratio']})")
        print(f"     Veredicto: {p.get('verdict', '')}")
        print(f"     Tesis: {p.get('thesis', '')}")
        print(f"     Cómo comprar: {p.get('how_to_buy', '')}")
    print()


def _parse_args():
    parser = argparse.ArgumentParser(
        description="Recomendación de inversión en pesos argentinos",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python3 invest_ars.py --capital 500000 --riesgo moderado
  python3 invest_ars.py --capital 1000000 --riesgo bajo
  python3 invest_ars.py --capital 200000 --riesgo alto
        """
    )
    parser.add_argument(
        "--capital", type=float, required=True,
        help="Capital a invertir en ARS (ej: --capital 500000)"
    )
    parser.add_argument(
        "--riesgo", type=str, default="moderado",
        choices=["bajo", "moderado", "alto"],
        help="Perfil de riesgo: bajo, moderado o alto (default: moderado)"
    )
    return parser.parse_args()


if __name__ == "__main__":
    main()
