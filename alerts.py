"""
Alertas de precio — compara precios actuales vs stop loss y take profit del CEO.
Corre cada hora en horario de mercado americano vía cron.
"""
import json
import os
from datetime import date, datetime
from glob import glob

import yfinance as yf


STATE_FILE = "storage/alerts_state.json"

ALERT_NEAR_STOP   = "near_stop"    # precio a ≤3% del stop loss
ALERT_STOP_HIT    = "stop_hit"     # precio cruzó el stop loss
ALERT_TARGET_HIT  = "target_hit"   # precio alcanzó el take profit


# ── Estado (evita emails duplicados) ─────────────────────────────────────────

def _load_state() -> dict:
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {}


def _save_state(state: dict):
    os.makedirs("storage", exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def _already_sent_today(state: dict, ticker: str, alert_type: str) -> bool:
    last = state.get(ticker, {}).get(alert_type, {}).get("last_sent")
    return last == date.today().isoformat()


def _mark_sent(state: dict, ticker: str, alert_type: str, price: float):
    state.setdefault(ticker, {})[alert_type] = {
        "last_sent": date.today().isoformat(),
        "price":     round(price, 2),
    }


# ── Carga de señales del storage ──────────────────────────────────────────────

def load_watchlist_thresholds() -> list[dict]:
    """
    Lee todos los análisis del storage y extrae stop_loss / take_profit del CEO.
    Solo incluye tickers con análisis válido y ambos umbrales definidos.
    """
    signals = []
    for path in sorted(glob("storage/*_analysis.json")):
        try:
            with open(path) as f:
                d = json.load(f)
            if d.get("status") != "ok":
                continue
            ceo   = d.get("ceo_thesis", {})
            price = d.get("price", {})
            stop  = ceo.get("stop_loss")
            tp    = ceo.get("take_profit")
            entry = price.get("current_price")
            if not all([stop, tp, entry]):
                continue
            signals.append({
                "ticker":    d["ticker"],
                "verdict":   ceo.get("final_verdict", "?"),
                "score":     ceo.get("ceo_score", 0),
                "entry":     float(entry),
                "stop":      float(stop),
                "target":    float(tp),
                "analysis_date": d.get("date", "?"),
            })
        except Exception:
            continue
    return signals


# ── Precios actuales ──────────────────────────────────────────────────────────

def fetch_prices(tickers: list[str]) -> dict[str, float]:
    prices = {}
    if not tickers:
        return prices
    try:
        data = yf.download(tickers, period="1d", progress=False, auto_adjust=True)
        close = data["Close"]
        if len(tickers) == 1:
            prices[tickers[0]] = float(close.iloc[-1])
        else:
            for t in tickers:
                if t in close.columns:
                    val = close[t].iloc[-1]
                    if not str(val) == "nan":
                        prices[t] = float(val)
    except Exception:
        pass
    for t in tickers:
        if t not in prices:
            try:
                prices[t] = float(yf.Ticker(t).fast_info["last_price"])
            except Exception:
                pass
    return prices


# ── Evaluación de alertas ─────────────────────────────────────────────────────

def evaluate_alerts(signals: list[dict], prices: dict[str, float]) -> list[dict]:
    triggered = []
    for s in signals:
        current = prices.get(s["ticker"])
        if current is None:
            continue

        pnl_pct = (current - s["entry"]) / s["entry"] * 100

        if current <= s["stop"]:
            triggered.append({**s, "alert_type": ALERT_STOP_HIT,  "current": current, "pnl_pct": pnl_pct})
        elif current <= s["stop"] * 1.03:
            triggered.append({**s, "alert_type": ALERT_NEAR_STOP,  "current": current, "pnl_pct": pnl_pct})
        elif current >= s["target"]:
            triggered.append({**s, "alert_type": ALERT_TARGET_HIT, "current": current, "pnl_pct": pnl_pct})

    return triggered


# ── Email de alerta ───────────────────────────────────────────────────────────

def _send_alert_email(alerts: list[dict]):
    from notifications.email_sender import send_price_alert_email
    send_price_alert_email(alerts)


# ── Punto de entrada ──────────────────────────────────────────────────────────

def run_alerts():
    now = datetime.now()
    print(f"\n[{now.strftime('%Y-%m-%d %H:%M')}] Chequeando alertas de precio...")

    signals = load_watchlist_thresholds()
    if not signals:
        print("  Sin señales en storage/ — nada que chequear.")
        return

    tickers = [s["ticker"] for s in signals]
    print(f"  {len(tickers)} tickers con umbrales definidos")

    prices = fetch_prices(tickers)
    print(f"  {len(prices)}/{len(tickers)} precios obtenidos")

    triggered = evaluate_alerts(signals, prices)
    state     = _load_state()

    nuevas = []
    for alert in triggered:
        ticker     = alert["ticker"]
        alert_type = alert["alert_type"]
        if not _already_sent_today(state, ticker, alert_type):
            nuevas.append(alert)
            _mark_sent(state, ticker, alert_type, alert["current"])

    _save_state(state)

    if not nuevas:
        print("  Sin alertas nuevas.")
        return

    print(f"  ⚠️  {len(nuevas)} alerta(s) nueva(s) — enviando email...")
    _send_alert_email(nuevas)
    for a in nuevas:
        label = {"stop_hit": "STOP ❌", "near_stop": "CERCA DEL STOP ⚠️", "target_hit": "TARGET ✅"}.get(a["alert_type"], a["alert_type"])
        print(f"     {a['ticker']}: {label} — actual ${a['current']:.2f} (P&L {a['pnl_pct']:+.1f}%)")


if __name__ == "__main__":
    run_alerts()
