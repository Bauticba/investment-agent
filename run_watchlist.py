import json
import sys
import time
from ceo.orchestrator import run_analysis, print_thesis
from notifications.email_sender import send_investment_email

DELAY_BETWEEN_TICKERS = 12  # segundos — respeta rate limit Alpha Vantage (5 req/min = 12s entre calls)


def run_watchlist(tickers: list[str], send_email: bool = True):
    results = []

    for i, ticker in enumerate(tickers):
        if i > 0:
            print(f"\n⏳ Esperando {DELAY_BETWEEN_TICKERS}s (rate limit)...\n")
            time.sleep(DELAY_BETWEEN_TICKERS)

        result = run_analysis(ticker)
        print_thesis(result)

        if result.get("status") == "ok":
            results.append(result)
            if send_email:
                send_investment_email(result)

            output_file = f"storage/{ticker}_analysis.json"
            with open(output_file, "w") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            print(f"💾 Guardado en {output_file}")

    _print_summary(results)


def _print_summary(results: list):
    if not results:
        return

    print(f"\n{'='*60}")
    print(f"  RESUMEN WATCHLIST — {len(results)} tickers analizados")
    print(f"{'='*60}")
    print(f"  {'Ticker':<8} {'Veredicto':<10} {'Score':<8} {'Stop Loss':<12} {'Take Profit'}")
    print(f"  {'-'*55}")

    for r in results:
        t = r["ticker"]
        ceo = r.get("ceo_thesis", {})
        verdict    = ceo.get("final_verdict", "N/A").upper()
        score      = f"{ceo.get('ceo_score', 'N/A')}/10"
        stop_loss  = f"${ceo.get('stop_loss', 'N/A')}"
        take_profit= f"${ceo.get('take_profit', 'N/A')}"
        print(f"  {t:<8} {verdict:<10} {score:<8} {stop_loss:<12} {take_profit}")

    print(f"{'='*60}\n")


if __name__ == "__main__":
    with open("instructions/investor_profile.json") as f:
        profile = json.load(f)

    tickers = sys.argv[1:] if len(sys.argv) > 1 else profile.get("watchlist", [])

    print(f"📋 Watchlist: {tickers}\n")
    run_watchlist(tickers)
