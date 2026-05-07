"""
Investment Agent — punto de entrada unificado.

── Actualizar datos ──────────────────────────────────────────────────────────
  python3 main.py actualizar                    # refresca los 50 tickers del universo
  python3 main.py actualizar AAPL MSFT NVDA     # refresca solo esos tickers

── Recomendaciones (usan storage, respuesta instantánea) ─────────────────────
  python3 main.py watchlist                     # analiza la watchlist con email
  python3 main.py portafolio --capital 5000     # portafolio óptimo USD
  python3 main.py mi-portafolio                 # qué hacer con lo que tenés
  python3 main.py invertir --capital 500000 --riesgo moderado
  python3 main.py invertir --capital 500000 --riesgo moderado --fecha 2027-01

── Gestión de portafolio ─────────────────────────────────────────────────────
  python3 main.py comprar AAPL 10 185.50        # compraste 10 acciones a $185.50
  python3 main.py vender AAPL 5                 # vendiste 5 acciones de AAPL
  python3 main.py posiciones                    # muestra tu portafolio actual
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

    # ── actualizar ────────────────────────────────────────────────────────────
    act = sub.add_parser(
        "actualizar",
        help="Refresca el storage con análisis nuevos (sin emails)",
    )
    act.add_argument(
        "tickers", nargs="*",
        metavar="TICKER",
        help="Tickers a actualizar (default: universo completo de 50)",
    )

    # ── watchlist ─────────────────────────────────────────────────────────────
    wl = sub.add_parser(
        "watchlist",
        help="Analiza la watchlist y envía email por ticker",
    )
    wl.add_argument(
        "tickers", nargs="*",
        metavar="TICKER",
        help="Tickers a analizar (default: watchlist del perfil)",
    )

    # ── portafolio ────────────────────────────────────────────────────────────
    pf = sub.add_parser(
        "portafolio",
        help="Construir portafolio óptimo en USD (usa storage por defecto)",
    )
    pf.add_argument(
        "--capital", type=float, required=True,
        metavar="USD",
        help="Capital disponible en USD (ej: --capital 5000)",
    )
    pf.add_argument(
        "--live", action="store_true",
        help="Re-analizar en vivo en vez de usar storage (lento)",
    )

    # ── mi-portafolio ─────────────────────────────────────────────────────────
    mp = sub.add_parser(
        "mi-portafolio",
        help="Qué hacer con tus posiciones actuales (usa storage)",
    )
    mp.add_argument(
        "--archivo", default="my_portfolio.json",
        metavar="ARCHIVO",
        help="JSON con tus posiciones (default: my_portfolio.json)",
    )
    mp.add_argument(
        "--live", action="store_true",
        help="Re-analizar acciones en vivo en vez de usar storage",
    )

    # ── invertir ──────────────────────────────────────────────────────────────
    inv = sub.add_parser(
        "invertir",
        help="Recomendación de inversión en pesos argentinos (usa storage)",
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
    inv.add_argument(
        "--fecha", default=None,
        metavar="YYYY-MM",
        help="Fecha en que necesitás el dinero (ej: --fecha 2027-01)",
    )

    # ── comprar ───────────────────────────────────────────────────────────────
    buy = sub.add_parser(
        "comprar",
        help="Registrar una compra en tu portafolio",
    )
    buy.add_argument("ticker",  metavar="TICKER",  help="Símbolo (ej: AAPL)")
    buy.add_argument("shares",  metavar="UNIDADES", type=float, help="Cantidad comprada")
    buy.add_argument("precio",  metavar="PRECIO",  type=float, help="Precio de compra")
    buy.add_argument("--moneda", default="USD", choices=["USD", "ARS"], help="Moneda (default: USD)")
    buy.add_argument("--tipo",   default=None,  help="Tipo de activo: cedear, bono_argentino, etc.")
    buy.add_argument("--nota",   default="",   help="Nota opcional")

    # ── vender ────────────────────────────────────────────────────────────────
    sell = sub.add_parser(
        "vender",
        help="Registrar una venta en tu portafolio",
    )
    sell.add_argument("ticker",  metavar="TICKER",  help="Símbolo (ej: AAPL)")
    sell.add_argument("shares",  metavar="UNIDADES", type=float, help="Cantidad vendida")

    # ── posiciones ────────────────────────────────────────────────────────────
    sub.add_parser(
        "posiciones",
        help="Mostrar el portafolio actual",
    )

    return parser


def main():
    parser = _build_parser()
    args   = parser.parse_args()

    with open("instructions/investor_profile.json") as f:
        profile = json.load(f)

    # ── actualizar ────────────────────────────────────────────────────────────
    if args.command == "actualizar":
        from run_watchlist import run_watchlist
        if args.tickers:
            tickers = [t.upper() for t in args.tickers]
        else:
            tickers = [t for s in profile["universe"].values() for t in s]
        total = len(tickers)
        import time
        eta = total * 55 + (total - 1) * 12
        print(f"\n🔄 Actualizando {total} tickers — ETA ~{eta // 60} min\n")
        run_watchlist(tickers, send_email=False)
        print(f"\n✅ Storage actualizado con {total} análisis frescos.")

    # ── watchlist ─────────────────────────────────────────────────────────────
    elif args.command == "watchlist":
        from run_watchlist import run_watchlist
        tickers = args.tickers or profile.get("watchlist", [])
        print(f"📋 Watchlist: {tickers}\n")
        run_watchlist(tickers, send_email=True)

    # ── portafolio ────────────────────────────────────────────────────────────
    elif args.command == "portafolio":
        from portfolio import run_portfolio
        use_cache = not args.live
        run_portfolio(args.capital, use_cache=use_cache)

    # ── mi-portafolio ─────────────────────────────────────────────────────────
    elif args.command == "mi-portafolio":
        from analyze_portfolio import run_portfolio_analysis
        use_cache = not args.live
        run_portfolio_analysis(args.archivo, use_cache=use_cache)

    # ── invertir ──────────────────────────────────────────────────────────────
    elif args.command == "invertir":
        from invest_ars import run_ars
        run_ars(args.capital, args.riesgo, fecha_objetivo=args.fecha)

    # ── comprar ───────────────────────────────────────────────────────────────
    elif args.command == "comprar":
        from core.portfolio_manager import add_position
        action = add_position(
            ticker     = args.ticker,
            shares     = args.shares,
            avg_price  = args.precio,
            currency   = args.moneda,
            asset_type = args.tipo,
            notes      = args.nota,
        )
        verb = "Agregado" if action == "added" else "Actualizado"
        print(f"✅ {verb}: {args.ticker.upper()} × {args.shares} @ ${args.precio} {args.moneda}")
        _print_positions()

    # ── vender ────────────────────────────────────────────────────────────────
    elif args.command == "vender":
        from core.portfolio_manager import sell_position
        ok, msg = sell_position(args.ticker, args.shares)
        print(f"{'✅' if ok else '❌'} {msg}")
        if ok:
            _print_positions()

    # ── posiciones ────────────────────────────────────────────────────────────
    elif args.command == "posiciones":
        _print_positions()

    else:
        parser.print_help()
        sys.exit(1)


def _print_positions():
    from core.portfolio_manager import get_portfolio
    p = get_portfolio()
    positions = p.get("positions", [])
    cash = p.get("cash", {})

    if not positions:
        print("\n  (portafolio vacío)")
        return

    print(f"\n  {'Ticker':<8} {'Unidades':>10} {'Precio prom':>13} {'Moneda':<6}  Tipo")
    print(f"  {'-'*55}")
    for pos in positions:
        tipo = pos.get("asset_type", "accion")
        print(f"  {pos['ticker']:<8} {pos['shares']:>10.2f} ${pos['avg_buy_price']:>12.2f} {pos.get('currency','USD'):<6}  {tipo}")
    print(f"\n  Cash: USD ${cash.get('USD', 0):,.0f}  |  ARS ${cash.get('ARS', 0):,.0f}")


if __name__ == "__main__":
    main()
