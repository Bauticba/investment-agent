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


def main():
    args = _parse_args()

    print(f"\n{'='*58}")
    print(f"  RECOMENDACIÓN DE INVERSIÓN EN PESOS ARGENTINOS")
    print(f"  Capital: ${args.capital:,.0f} ARS  |  Riesgo: {args.riesgo.upper()}")
    print(f"{'='*58}\n")

    # --- 1. Contexto macro ---
    print("📊 Obteniendo contexto macro argentino...")
    macro = get_macro_data()
    _print_macro(macro)

    # --- 2. Universo de instrumentos ---
    print("\n📋 Construyendo universo de instrumentos disponibles...")
    instruments = get_instruments_universe(macro)
    relevant    = [i for i in instruments if args.riesgo in i.get("recommended_for", [])]
    print(f"   {len(instruments)} instrumentos totales | {len(relevant)} compatibles con riesgo {args.riesgo.upper()}")

    # --- 3. Recomendación ---
    with open("instructions/investor_profile.json") as f:
        profile = json.load(f)

    print(f"\n🤖 Generando recomendación personalizada...")
    rec = recommend_allocation(args.capital, args.riesgo, instruments, macro, profile)

    if "error" in rec:
        print(f"❌ Error al generar la recomendación: {rec.get('raw', '')[:200]}")
        return

    # --- 4. Mostrar ---
    _print_recommendation(rec, args.capital, args.riesgo)

    # --- 5. Guardar ---
    output_file = f"storage/inversion_ars_{date.today().isoformat()}.json"
    with open(output_file, "w") as f:
        json.dump({
            "date":       date.today().isoformat(),
            "capital_ars": args.capital,
            "riesgo":     args.riesgo,
            "macro":      macro,
            "recommendation": rec,
        }, f, indent=2, ensure_ascii=False)
    print(f"💾 Guardado en {output_file}\n")


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
        "bono_cer":       "📈",
        "plazo_fijo_uva": "🔒",
        "plazo_fijo":     "🔒",
        "dolar_mep":      "💵",
        "fci_mm":         "💧",
        "cedears":        "🌎",
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
