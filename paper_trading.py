"""
Paper trading — seguimiento de señales del CEO.
Lee storage/history/ y compara las predicciones contra el precio actual.
"""
import json
import os
from datetime import date, datetime
from glob import glob

import yfinance as yf


# ── Carga de señales ─────────────────────────────────────────────────────────

def load_signals(history_dir: str = "storage/history") -> list[dict]:
    signals = []
    for path in sorted(glob(f"{history_dir}/*_analysis_*.json")):
        try:
            with open(path) as f:
                d = json.load(f)
            if d.get("status") != "ok":
                continue

            ceo   = d.get("ceo_thesis", {})
            price = d.get("price", {})

            entry = price.get("current_price")
            stop  = ceo.get("stop_loss")
            tp    = ceo.get("take_profit")
            if not all([entry, stop, tp]):
                continue

            signals.append({
                "ticker":    d["ticker"],
                "date":      d["date"],
                "verdict":   ceo.get("final_verdict", "?"),
                "score":     ceo.get("ceo_score", 0),
                "conviction":ceo.get("conviction", "?"),
                "entry":     float(entry),
                "stop":      float(stop),
                "target":    float(tp),
                "file":      os.path.basename(path),
            })
        except Exception:
            continue
    return signals


# ── Precios actuales ─────────────────────────────────────────────────────────

def fetch_current_prices(tickers: list[str]) -> dict[str, float]:
    prices = {}
    if not tickers:
        return prices
    try:
        data = yf.download(tickers, period="1d", progress=False, auto_adjust=True)
        close = data["Close"]
        if len(tickers) == 1:
            val = close.iloc[-1]
            prices[tickers[0]] = float(val)
        else:
            for t in tickers:
                if t in close.columns:
                    prices[t] = float(close[t].iloc[-1])
    except Exception:
        pass
    # fallback individual para los que fallaron
    for t in tickers:
        if t not in prices:
            try:
                prices[t] = float(yf.Ticker(t).fast_info["last_price"])
            except Exception:
                pass
    return prices


# ── Evaluación ───────────────────────────────────────────────────────────────

def _status(verdict: str, entry: float, stop: float, target: float, current: float) -> str:
    if verdict == "buy":
        if current <= stop:
            return "stop_hit"
        if current >= target:
            return "target_hit"
        return "active"
    if verdict == "avoid":
        # señal correcta si el precio bajó >5%
        return "correct" if current < entry * 0.95 else "active"
    return "active"  # hold


def evaluate(signals: list[dict], prices: dict[str, float]) -> list[dict]:
    results = []
    for s in signals:
        current = prices.get(s["ticker"])
        if current is None:
            pnl_pct = None
            status  = "sin_precio"
        else:
            pnl_pct = (current - s["entry"]) / s["entry"] * 100
            status  = _status(s["verdict"], s["entry"], s["stop"], s["target"], current)

        results.append({**s, "current": current, "pnl_pct": pnl_pct, "status": status})
    return results


# ── Presentación ─────────────────────────────────────────────────────────────

STATUS_LABEL = {
    "active":      "activo",
    "stop_hit":    "STOP ❌",
    "target_hit":  "TARGET ✅",
    "correct":     "correcto ✅",
    "sin_precio":  "sin precio",
}

VERDICT_EMOJI = {"buy": "🟢", "hold": "🟡", "avoid": "🔴"}


def print_report(results: list[dict]):
    if not results:
        print("No hay señales en storage/history/.")
        return

    print(f"\n{'='*90}")
    print(f"  PAPER TRADING — Seguimiento de señales CEO")
    print(f"  {len(results)} señales | actualizado {date.today()}")
    print(f"{'='*90}")
    print(f"  {'Ticker':<7} {'Fecha':<12} {'V':<2} {'Score':<6} {'Entrada':>9} {'Stop':>9} {'Target':>9} {'Actual':>9} {'P&L%':>7}  Estado")
    print(f"  {'-'*85}")

    # ordenar: buys primero, luego por P&L desc
    buy_results  = sorted([r for r in results if r["verdict"] == "buy"],  key=lambda r: r["pnl_pct"] or 0, reverse=True)
    hold_results = sorted([r for r in results if r["verdict"] == "hold"], key=lambda r: r["pnl_pct"] or 0, reverse=True)
    avoid_results= sorted([r for r in results if r["verdict"] == "avoid"],key=lambda r: r["pnl_pct"] or 0)

    for section, label in [(buy_results, "BUY"), (hold_results, "HOLD"), (avoid_results, "AVOID")]:
        if not section:
            continue
        print(f"\n  ── {label} ──")
        for r in section:
            emoji   = VERDICT_EMOJI.get(r["verdict"], " ")
            pnl_str = f"{r['pnl_pct']:+.1f}%" if r["pnl_pct"] is not None else "  N/A"
            cur_str = f"${r['current']:>8.2f}" if r["current"] else "      N/A"
            status  = STATUS_LABEL.get(r["status"], r["status"])
            print(
                f"  {r['ticker']:<7} {r['date']:<12} {emoji:<2} {r['score']}/10  "
                f"${r['entry']:>8.2f} ${r['stop']:>8.2f} ${r['target']:>8.2f} "
                f"{cur_str} {pnl_str:>7}  {status}"
            )

    _print_summary(results)


def _print_summary(results: list[dict]):
    buys = [r for r in results if r["verdict"] == "buy" and r["pnl_pct"] is not None]
    all_with_price = [r for r in results if r["pnl_pct"] is not None]

    print(f"\n{'='*90}")
    print(f"  RESUMEN")
    print(f"{'='*90}")

    if buys:
        wins      = [r for r in buys if r["status"] == "target_hit"]
        losses    = [r for r in buys if r["status"] == "stop_hit"]
        active    = [r for r in buys if r["status"] == "active"]
        avg_pnl   = sum(r["pnl_pct"] for r in buys) / len(buys)
        win_rate  = len(wins) / len(buys) * 100 if buys else 0
        best      = max(buys, key=lambda r: r["pnl_pct"])
        worst     = min(buys, key=lambda r: r["pnl_pct"])

        print(f"  Señales BUY     : {len(buys)} total | {len(active)} activas | {len(wins)} targets ✅ | {len(losses)} stops ❌")
        print(f"  P&L promedio    : {avg_pnl:+.1f}%")
        print(f"  Win rate        : {win_rate:.0f}%")
        print(f"  Mejor señal     : {best['ticker']} {best['pnl_pct']:+.1f}% ({best['date']})")
        print(f"  Peor señal      : {worst['ticker']} {worst['pnl_pct']:+.1f}% ({worst['date']})")

    holds = [r for r in results if r["verdict"] == "hold" and r["pnl_pct"] is not None]
    avoids = [r for r in results if r["verdict"] == "avoid" and r["pnl_pct"] is not None]

    if holds:
        avg_hold = sum(r["pnl_pct"] for r in holds) / len(holds)
        print(f"  Señales HOLD    : {len(holds)} | P&L promedio {avg_hold:+.1f}%")
    if avoids:
        correct = sum(1 for r in avoids if r["status"] == "correct")
        print(f"  Señales AVOID   : {len(avoids)} | correctas {correct}/{len(avoids)}")

    print(f"{'='*90}\n")


# ── Punto de entrada ──────────────────────────────────────────────────────────

def run_paper_trading(history_dir: str = "storage/history"):
    print(f"\n{'='*60}")
    print(f"  PAPER TRADING")
    print(f"{'='*60}\n")

    print("📂 Cargando señales históricas...")
    signals = load_signals(history_dir)
    if not signals:
        print("  No hay archivos en storage/history/. Corré primero: python3 main.py actualizar")
        return
    print(f"   {len(signals)} señales encontradas en {len(set(s['date'] for s in signals))} fechas\n")

    tickers = list(set(s["ticker"] for s in signals))
    print(f"💹 Obteniendo precios actuales ({len(tickers)} tickers)...")
    prices = fetch_current_prices(tickers)
    print(f"   {len(prices)}/{len(tickers)} precios obtenidos\n")

    results = evaluate(signals, prices)
    print_report(results)


if __name__ == "__main__":
    run_paper_trading()
