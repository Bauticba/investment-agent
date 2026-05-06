"""
Investment Agent — punto de entrada unificado.

Uso:
  python3 main.py watchlist                                  # analiza AAPL, MSFT, NVDA, GOOGL
  python3 main.py watchlist AAPL TSLA META                   # tickers custom
  python3 main.py portafolio --capital 5000                  # portafolio óptimo USD
  python3 main.py portafolio --capital 5000 --cache          # ídem con cache
  python3 main.py mi-portafolio                              # analiza lo que tenés comprado
  python3 main.py mi-portafolio --cache                      # ídem con cache
  python3 main.py invertir --capital 500000 --riesgo moderado
"""
import argparse
import json
import sys


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="Investment Agent — análisis bursátil multi-agente",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="command", metavar="COMANDO")

    # ── watchlist ─────────────────────────────────────────────────────────────
    wl = sub.add_parser(
        "watchlist",
        help="Analizar tickers y guardar en storage/ (envía email por ticker)",
    )
    wl.add_argument(
        "tickers", nargs="*",
        metavar="TICKER",
        help="Tickers a analizar (default: watchlist del perfil)",
    )

    # ── portafolio ────────────────────────────────────────────────────────────
    pf = sub.add_parser(
        "portafolio",
        help="Construir portafolio óptimo en USD a partir del universo completo",
    )
    pf.add_argument(
        "--capital", type=float, required=True,
        metavar="USD",
        help="Capital disponible en USD (ej: --capital 5000)",
    )
    pf.add_argument(
        "--cache", action="store_true",
        help="Usar análisis cacheados del storage en vez de re-analizar",
    )

    # ── mi-portafolio ─────────────────────────────────────────────────────────
    mp = sub.add_parser(
        "mi-portafolio",
        help="Analizar las posiciones existentes (acciones, bonos AR, CEDEARs)",
    )
    mp.add_argument(
        "--archivo", default="my_portfolio.json",
        metavar="ARCHIVO",
        help="JSON con tus posiciones (default: my_portfolio.json)",
    )
    mp.add_argument(
        "--cache", action="store_true",
        help="Usar análisis cacheados del storage en vez de re-analizar",
    )

    # ── invertir ──────────────────────────────────────────────────────────────
    inv = sub.add_parser(
        "invertir",
        help="Recomendación de inversión en pesos argentinos",
    )
    inv.add_argument(
        "--capital", type=float, required=True,
        metavar="ARS",
        help="Capital a invertir en ARS (ej: --capital 500000)",
    )
    inv.add_argument(
        "--riesgo", default="moderado",
        choices=["bajo", "moderado", "alto"],
        help="Perfil de riesgo (default: moderado)",
    )

    return parser


def main():
    parser = _build_parser()
    args   = parser.parse_args()

    if args.command == "watchlist":
        from run_watchlist import run_watchlist
        with open("instructions/investor_profile.json") as f:
            profile = json.load(f)
        tickers = args.tickers or profile.get("watchlist", [])
        print(f"📋 Watchlist: {tickers}\n")
        run_watchlist(tickers)

    elif args.command == "portafolio":
        from portfolio import run_portfolio
        run_portfolio(args.capital, use_cache=args.cache)

    elif args.command == "mi-portafolio":
        from analyze_portfolio import run_portfolio_analysis
        run_portfolio_analysis(args.archivo, use_cache=args.cache)

    elif args.command == "invertir":
        from invest_ars import run_ars
        run_ars(args.capital, args.riesgo)

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
