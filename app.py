import streamlit as st
import json
import os
from datetime import datetime

st.set_page_config(
    page_title="Investment Agent",
    page_icon="📈",
    layout="wide",
)

st.title("📈 Investment Agent")
st.caption("Sistema multi-agente de análisis bursátil — Bautista")

# ── Macro ─────────────────────────────────────────────────────────────────────
st.header("Contexto macro argentino")

@st.cache_data(ttl=1800)
def _macro():
    from data.argentina import get_macro_data
    return get_macro_data()

with st.spinner("Trayendo datos macro..."):
    macro = _macro()

c1, c2, c3, c4 = st.columns(4)
infl_m = macro.get("inflation_monthly")
infl_a = macro.get("inflation_annual")
usd    = macro.get("usd_oficial")
uva    = macro.get("uva")

c1.metric("Inflación mensual",  f"{infl_m:.1f}%" if infl_m else "N/A")
c2.metric("Inflación anual",    f"{infl_a:.1f}%" if infl_a else "N/A")
c3.metric("Dólar oficial",      f"${usd:,.0f}" if usd else "N/A")
c4.metric("UVA",                f"${uva:,.2f}" if uva else "N/A")

# ── Análisis cacheados ────────────────────────────────────────────────────────
st.divider()
st.header("Análisis guardados en storage/")

cache_files = sorted([
    f for f in os.listdir("storage")
    if f.endswith("_analysis.json") and not f.startswith("portfolio")
])

if not cache_files:
    st.info("No hay análisis guardados todavía. Usá la página **Watchlist** para generar uno.")
else:
    rows = []
    for fname in cache_files:
        with open(f"storage/{fname}") as f:
            data = json.load(f)
        ceo     = data.get("ceo_thesis", {})
        price   = data.get("price", {})
        rows.append({
            "Ticker":     data.get("ticker", fname.split("_")[0]),
            "Veredicto":  (ceo.get("final_verdict") or "N/A").upper(),
            "Score":      ceo.get("ceo_score"),
            "Convicción": (ceo.get("conviction") or "N/A").upper(),
            "Precio USD": price.get("current_price"),
            "Stop Loss":  ceo.get("stop_loss"),
            "Take Profit":ceo.get("take_profit"),
            "Fecha":      data.get("date", "?"),
        })

    st.dataframe(rows, use_container_width=True, hide_index=True)

st.caption(f"Actualizado: {datetime.now().strftime('%H:%M:%S')}")
