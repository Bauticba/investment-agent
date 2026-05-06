import json
import time
import argparse
from datetime import date
from agents.allocator import build_portfolio
from notifications.email_sender import send_portfolio_email
from core.cache import get_analysis_cached

DELAY_BETWEEN_TICKERS = 12
MIN_SCORE_TO_QUALIFY  = 6


def run_portfolio(capital: float, use_cache: bool = False):
    with open("instructions/investor_profile.json") as f:
        profile = json.load(f)

    universe = _flatten_universe(profile["universe"])
    print(f"\n{'='*55}")
    print(f"  PORTFOLIO BUILDER — Capital: ${capital:,.0f} USD")
    print(f"{'='*55}")
    print(f"  Universo: {len(universe)} candidatos\n")

    # --- 1. Analizar todos los candidatos ---
    all_results = []
    for i, ticker in enumerate(universe):
        if i > 0:
            print(f"\n⏳ Esperando {DELAY_BETWEEN_TICKERS}s...\n")
            time.sleep(DELAY_BETWEEN_TICKERS)

        result = get_analysis_cached(ticker, use_cache=use_cache)
        if result.get("status") == "ok":
            all_results.append(result)

    # --- 2. Filtrar candidatos aprobados ---
    approved = _filter_approved(all_results)

    print(f"\n{'='*55}")
    print(f"  RESULTADOS DEL SCREENING")
    print(f"{'='*55}")
    _print_screening_table(all_results)

    if not approved:
        print("\n⚠️  Ningún candidato calificó. Revisá los criterios de filtro.")
        return

    print(f"\n✅ {len(approved)} candidatos calificaron para el portafolio.\n")

    # --- 3. Agente allocator construye el portafolio ---
    print("💼 Allocator construyendo portafolio óptimo...")
    portfolio = build_portfolio(capital, approved, profile)

    if "error" in portfolio:
        print(f"❌ Error en allocator: {portfolio.get('raw')}")
        return

    # --- 4. Mostrar resultados ---
    _print_portfolio(portfolio, capital)

    # --- 5. Guardar y notificar ---
    output_file = f"storage/portfolio_{date.today().isoformat()}.json"
    with open(output_file, "w") as f:
        json.dump({
            "capital":   capital,
            "date":      date.today().isoformat(),
            "screening": _screening_summary(all_results),
            "portfolio": portfolio,
        }, f, indent=2, ensure_ascii=False)
    print(f"\n💾 Guardado en {output_file}")

    send_portfolio_email(portfolio, capital)


def main():
    args = _parse_args()
    run_portfolio(args.capital, use_cache=args.use_cache)


def _filter_approved(results: list) -> list:
    approved = []
    for r in results:
        ceo   = r.get("ceo_thesis", {})
        score = ceo.get("ceo_score", 0) or 0
        verdict = ceo.get("final_verdict", "")

        if verdict == "buy" and score >= MIN_SCORE_TO_QUALIFY:
            # Pegamos el precio y sector directamente en el resultado para el allocator
            r["price"] = r.get("price", {}).get("current_price")
            r["sector"] = r.get("reports", {}).get("sentiment", {}).get(
                "sector_outlook", r.get("reports", {}).get("fundamental", {}).get("sector", "unknown")
            )
            approved.append(r)

    return approved


def _print_screening_table(results: list):
    print(f"  {'Ticker':<8} {'Veredicto':<10} {'Score':<7} {'Convicción':<12} {'Estado'}")
    print(f"  {'-'*52}")
    for r in results:
        ceo     = r.get("ceo_thesis", {})
        ticker  = r.get("ticker", "?")
        verdict = ceo.get("final_verdict", "N/A").upper()
        score   = f"{ceo.get('ceo_score', 'N/A')}/10"
        conv    = ceo.get("conviction", "N/A").upper()
        qualifies = (
            ceo.get("final_verdict") == "buy"
            and (ceo.get("ceo_score") or 0) >= MIN_SCORE_TO_QUALIFY
        )
        estado = "✅ APROBADO" if qualifies else "❌ descartado"
        print(f"  {ticker:<8} {verdict:<10} {score:<7} {conv:<12} {estado}")


def _print_portfolio(portfolio: dict, capital: float):
    positions = portfolio.get("positions", [])
    print(f"\n{'='*60}")
    print(f"  PORTAFOLIO ÓPTIMO")
    print(f"{'='*60}")
    print(f"  Capital: ${capital:,.0f}  |  Invertido: ${portfolio.get('total_invested', 0):,.2f}  |  Cash: ${portfolio.get('cash_reserve', 0):,.2f}")
    print(f"\n  {'Ticker':<7} {'Acciones':>8} {'Precio':>9} {'Monto':>10} {'%':>6}  Ratio R/B")
    print(f"  {'-'*58}")

    for p in positions:
        ticker  = p["ticker"]
        shares  = p["shares"]
        price   = p["price"]
        amount  = p["amount_usd"]
        pct     = p["allocation_pct"]
        sl      = p.get("stop_loss", 0) or 0
        tp      = p.get("take_profit", 0) or 0
        rb      = f"SL ${sl}  TP ${tp}"
        print(f"  {ticker:<7} {shares:>8}  ${price:>8.2f}  ${amount:>9.2f}  {pct:>5.1f}%  {rb}")

    print(f"\n  TESIS DEL PORTAFOLIO:")
    print(f"  {portfolio.get('portfolio_thesis', '')}")
    print(f"\n  RIESGO PRINCIPAL:")
    print(f"  {portfolio.get('main_risk', '')}")
    print(f"{'='*60}\n")


def _screening_summary(results: list) -> list:
    return [
        {
            "ticker":  r["ticker"],
            "verdict": r.get("ceo_thesis", {}).get("final_verdict"),
            "score":   r.get("ceo_thesis", {}).get("ceo_score"),
        }
        for r in results
    ]


def _flatten_universe(universe: dict) -> list:
    tickers = []
    for sector_tickers in universe.values():
        tickers.extend(sector_tickers)
    return tickers


def _parse_args():
    parser = argparse.ArgumentParser(description="Portfolio Builder — Investment Agent")
    parser.add_argument(
        "--capital", type=float, required=True,
        help="Capital disponible en USD (ej: --capital 5000)"
    )
    parser.add_argument(
        "--use-cache", action="store_true",
        help="Usar análisis cacheados del día si existen"
    )
    return parser.parse_args()


if __name__ == "__main__":
    main()
