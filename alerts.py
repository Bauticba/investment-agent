"""
Alertas de precio — dos fuentes:
  1. Watchlist USA: storage/*_analysis.json con stop/target del CEO en USD (yfinance)
  2. Portafolio IOL: my_portfolio.json con stop/target calculados desde perfil en ARS (IOL)
Corre cada hora en horario de mercado (americano y BYMA) vía cron.
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


# ── Señales desde portafolio IOL ─────────────────────────────────────────────

def load_portfolio_thresholds() -> list[dict]:
    """
    Lee my_portfolio.json y construye señales usando stop/target del perfil del inversor.
    Obtiene precios actuales desde IOL. Solo incluye posiciones con precio disponible.
    """
    from core.portfolio_manager import get_portfolio
    from data.iol import get_price as iol_price, is_available as iol_available

    if not iol_available():
        return []

    try:
        with open("instructions/investor_profile.json") as f:
            profile = json.load(f)
        stop_pct   = profile["risk_profile"]["stop_loss_pct"] / 100
        target_pct = profile["risk_profile"]["take_profit_pct"] / 100
        costs      = profile.get("transaction_costs", {})
        commission = costs.get("commission_pct", 0.75) / 100
        tax_map    = {k: v / 100 for k, v in costs.get("taxes", {}).items()}
    except Exception:
        stop_pct, target_pct, commission = 0.08, 0.20, 0.0075
        tax_map = {}

    portfolio  = get_portfolio()
    positions  = portfolio.get("positions", [])
    signals    = []

    for pos in positions:
        ticker     = pos.get("ticker", "")
        avg_price  = float(pos.get("avg_buy_price") or 0)
        asset_type = pos.get("asset_type", "")
        if not ticker or avg_price <= 0:
            continue

        price_data = iol_price(ticker)
        if not price_data:
            continue
        current = float(price_data["ultimo_precio"])

        tax_rate = tax_map.get(asset_type, 0.0)

        # Stop: precio al que la pérdida NETA (incluyendo comisión de venta) = stop_pct
        gross_stop   = stop_pct - commission
        # Target: precio al que la ganancia NETA (después de comisión + impuesto) = target_pct
        gross_target = (target_pct + commission) / (1 - tax_rate) if tax_rate < 1 else target_pct + commission

        signals.append({
            "ticker":        ticker,
            "verdict":       "portfolio",
            "score":         None,
            "entry":         avg_price,
            "stop":          round(avg_price * (1 - gross_stop), 4),
            "target":        round(avg_price * (1 + gross_target), 4),
            "analysis_date": pos.get("notes", "sincronizado IOL"),
            "currency":      pos.get("currency", "ARS"),
            "asset_type":    asset_type,
            "source":        "portfolio_iol",
            "tax_rate":      tax_rate,
            "commission":    commission,
            "_current":      current,
        })

    return signals


# ── Evaluación de alertas ─────────────────────────────────────────────────────

def evaluate_alerts(signals: list[dict], prices: dict[str, float]) -> list[dict]:
    triggered = []
    for s in signals:
        # Señales del portafolio IOL ya traen el precio en _current
        current = s.pop("_current", None) or prices.get(s["ticker"])
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

    # Fuente 1: watchlist USA (storage/ → CEO stop/target en USD)
    watchlist_signals = load_watchlist_thresholds()
    usa_tickers = [s["ticker"] for s in watchlist_signals]
    usa_prices  = fetch_prices(usa_tickers) if usa_tickers else {}
    print(f"  Watchlist USA: {len(watchlist_signals)} señales, {len(usa_prices)} precios")

    # Fuente 2: portafolio IOL (my_portfolio.json → stop/target por perfil en ARS)
    portfolio_signals = load_portfolio_thresholds()
    print(f"  Portafolio IOL: {len(portfolio_signals)} posiciones con precio IOL")

    all_signals = watchlist_signals + portfolio_signals
    if not all_signals:
        print("  Sin señales — nada que chequear.")
        return

    triggered = evaluate_alerts(all_signals, usa_prices)
    state     = _load_state()

    nuevas = []
    for alert in triggered:
        ticker     = alert["ticker"]
        alert_type = alert["alert_type"]
        # Distinguir watchlist vs portafolio para evitar colisiones de estado
        state_key  = f"{ticker}_{alert.get('source', 'watchlist')}"
        if not _already_sent_today(state, state_key, alert_type):
            nuevas.append(alert)
            _mark_sent(state, state_key, alert_type, alert["current"])

    _save_state(state)

    if not nuevas:
        print("  Sin alertas nuevas.")
        return

    print(f"  ⚠️  {len(nuevas)} alerta(s) nueva(s) — enviando email...")
    _send_alert_email(nuevas)
    for a in nuevas:
        label = {"stop_hit": "STOP ❌", "near_stop": "CERCA DEL STOP ⚠️", "target_hit": "TARGET ✅"}.get(a["alert_type"], a["alert_type"])
        src   = " [IOL]" if a.get("source") == "portfolio_iol" else ""
        print(f"     {a['ticker']}{src}: {label} — actual {a['current']:.2f} {a.get('currency','USD')} (P&L {a['pnl_pct']:+.1f}%)")


if __name__ == "__main__":
    run_alerts()
