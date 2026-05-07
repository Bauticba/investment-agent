import streamlit as st
import pandas as pd
from glob import glob

st.set_page_config(page_title="Paper Trading", page_icon="📈", layout="wide")
st.title("📈 Paper Trading")
st.caption("Seguimiento de las señales históricas del CEO vs precios reales")

# ── Cargar datos ──────────────────────────────────────────────────────────────

@st.cache_data(ttl=300)
def load_data():
    from paper_trading import load_signals, fetch_current_prices, evaluate
    signals = load_signals()
    if not signals:
        return [], {}
    tickers = list(set(s["ticker"] for s in signals))
    prices  = fetch_current_prices(tickers)
    results = evaluate(signals, prices)
    return results, prices

with st.spinner("Cargando señales y precios actuales..."):
    results, prices = load_data()

if not results:
    st.info("No hay señales en `storage/history/`. Corré `python3 main.py actualizar` para generarlas.")
    st.stop()

# ── Métricas resumen ──────────────────────────────────────────────────────────

buys   = [r for r in results if r["verdict"] == "buy"   and r["pnl_pct"] is not None]
holds  = [r for r in results if r["verdict"] == "hold"  and r["pnl_pct"] is not None]
avoids = [r for r in results if r["verdict"] == "avoid" and r["pnl_pct"] is not None]
fechas = sorted(set(r["date"] for r in results))

targets_hit = sum(1 for r in buys if r["status"] == "target_hit")
stops_hit   = sum(1 for r in buys if r["status"] == "stop_hit")
win_rate    = targets_hit / len(buys) * 100 if buys else None
avg_pnl     = sum(r["pnl_pct"] for r in buys) / len(buys) if buys else None

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Señales totales", len(results), help=f"{len(fechas)} fechas distintas")
m2.metric("Señales BUY",   len(buys))
m3.metric("Señales HOLD",  len(holds))
m4.metric("Señales AVOID", len(avoids))
m5.metric("Win rate BUY",  f"{win_rate:.0f}%" if win_rate is not None else "—",
          help="Targets alcanzados / total señales BUY")

st.divider()

if buys:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("P&L promedio BUY", f"{avg_pnl:+.1f}%",
              delta_color="normal" if avg_pnl >= 0 else "inverse")
    c2.metric("Targets ✅",  targets_hit)
    c3.metric("Stops ❌",    stops_hit)
    c4.metric("Activas 🟡",  sum(1 for r in buys if r["status"] == "active"))
    st.divider()

# ── Filtros ───────────────────────────────────────────────────────────────────

st.subheader("Señales")
col_f1, col_f2, col_f3 = st.columns(3)
with col_f1:
    filtro_veredicto = st.multiselect(
        "Veredicto",
        ["buy", "hold", "avoid"],
        default=["buy", "hold", "avoid"],
    )
with col_f2:
    filtro_fecha = st.selectbox(
        "Fecha",
        ["Todas"] + fechas[::-1],
    )
with col_f3:
    filtro_status = st.multiselect(
        "Estado",
        ["active", "target_hit", "stop_hit", "correct", "sin_precio"],
        default=["active", "target_hit", "stop_hit", "correct"],
    )

# ── Tabla ─────────────────────────────────────────────────────────────────────

VERDICT_EMOJI = {"buy": "🟢 BUY", "hold": "🟡 HOLD", "avoid": "🔴 AVOID"}
STATUS_LABEL  = {
    "active":     "activo",
    "target_hit": "TARGET ✅",
    "stop_hit":   "STOP ❌",
    "correct":    "correcto ✅",
    "sin_precio": "sin precio",
}

filtered = [
    r for r in results
    if r["verdict"] in filtro_veredicto
    and (filtro_fecha == "Todas" or r["date"] == filtro_fecha)
    and r["status"] in filtro_status
]
filtered.sort(key=lambda r: (r["verdict"] != "buy", r["verdict"] != "hold", -(r["pnl_pct"] or 0)))

rows = []
for r in filtered:
    rows.append({
        "Ticker":     r["ticker"],
        "Fecha":      r["date"],
        "Veredicto":  VERDICT_EMOJI.get(r["verdict"], r["verdict"]),
        "Score":      f"{r['score']}/10",
        "Convicción": r.get("conviction", "?").upper(),
        "Entrada":    f"${r['entry']:,.2f}",
        "Stop":       f"${r['stop']:,.2f}",
        "Target":     f"${r['target']:,.2f}",
        "Actual":     f"${r['current']:,.2f}" if r["current"] else "N/A",
        "P&L %":      f"{r['pnl_pct']:+.1f}%" if r["pnl_pct"] is not None else "N/A",
        "Estado":     STATUS_LABEL.get(r["status"], r["status"]),
    })

if rows:
    st.dataframe(rows, use_container_width=True, hide_index=True)
    st.caption(f"{len(rows)} señales mostradas")
else:
    st.info("No hay señales con los filtros seleccionados.")

# ── Gráfico P&L por ticker ────────────────────────────────────────────────────

if buys:
    st.divider()
    st.subheader("P&L % por ticker (señales BUY)")

    buy_rows = [r for r in buys if filtro_fecha == "Todas" or r["date"] == filtro_fecha]
    if buy_rows:
        df = pd.DataFrame(buy_rows)[["ticker", "date", "pnl_pct", "status"]].copy()
        df = df.sort_values("pnl_pct", ascending=False)
        df.columns = ["Ticker", "Fecha", "P&L %", "Estado"]
        st.bar_chart(df.set_index("Ticker")["P&L %"])

# ── Historial de fechas ───────────────────────────────────────────────────────

st.divider()
st.subheader("Historial de ejecuciones")

archivos = sorted(glob("storage/history/*_analysis_*.json"), reverse=True)
fechas_unicas = sorted(set(
    f.split("_analysis_")[1].replace(".json", "")
    for f in archivos
), reverse=True)

resumen_fechas = []
for fecha in fechas_unicas:
    archivos_fecha = [f for f in archivos if f"_analysis_{fecha}.json" in f]
    buys_fecha  = sum(1 for r in results if r["date"] == fecha and r["verdict"] == "buy")
    holds_fecha = sum(1 for r in results if r["date"] == fecha and r["verdict"] == "hold")
    avoids_fecha= sum(1 for r in results if r["date"] == fecha and r["verdict"] == "avoid")
    resumen_fechas.append({
        "Fecha":         fecha,
        "Tickers":       len(archivos_fecha),
        "🟢 BUY":        buys_fecha,
        "🟡 HOLD":       holds_fecha,
        "🔴 AVOID":      avoids_fecha,
    })

if resumen_fechas:
    st.dataframe(resumen_fechas, use_container_width=True, hide_index=True)

st.caption("Los datos se actualizan automáticamente con el cron de las 5pm. Usá el botón de refrescar del navegador para ver los últimos datos.")
