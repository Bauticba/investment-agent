import streamlit as st
import json
import time
import os
from datetime import date

st.set_page_config(page_title="Portafolio USD", page_icon="💼", layout="wide")
st.title("💼 Portafolio óptimo en USD")
st.caption("Screening del universo completo + construcción de portafolio con el agente allocator.")

with open("instructions/investor_profile.json") as f:
    profile = json.load(f)

universe_flat = [t for tickers in profile.get("universe", {}).values() for t in tickers]

# ── Configuración ─────────────────────────────────────────────────────────────
st.subheader("Configuración")
col1, col2, col3 = st.columns(3)

with col1:
    capital = st.number_input("Capital disponible (USD)", min_value=100.0, value=5000.0, step=500.0)
with col2:
    use_cache = st.checkbox(
        "Usar análisis cacheados",
        value=False,
        help="Si está marcado, usa los JSONs de storage/ en vez de re-analizar (mucho más rápido)",
    )
with col3:
    send_email = st.checkbox("Enviar email con el portafolio", value=True)

cached_count = sum(1 for t in universe_flat if os.path.exists(f"storage/{t}_analysis.json"))
if use_cache:
    st.info(f"Cache disponible para {cached_count}/{len(universe_flat)} tickers.")
else:
    est = len(universe_flat) * 55 + (len(universe_flat) - 1) * 12
    st.info(f"Análisis en vivo: ~{est // 60} minutos para {len(universe_flat)} tickers.")

# ── Ejecución ─────────────────────────────────────────────────────────────────
if st.button("Construir portafolio", type="primary", use_container_width=True):
    from ceo.orchestrator import run_analysis
    from agents.allocator import build_portfolio
    from notifications.email_sender import send_portfolio_email
    from core.cache import get_analysis_cached

    DELAY = 12
    MIN_SCORE = 6

    all_results = []
    progress = st.progress(0, text="Iniciando screening...")

    for i, ticker in enumerate(universe_flat):
        if i > 0 and not use_cache:
            for remaining in range(DELAY, 0, -1):
                progress.progress(i / len(universe_flat), text=f"⏳ Rate limit: {remaining}s...")
                time.sleep(1)

        progress.progress(i / len(universe_flat), text=f"{'📂' if use_cache else '🔍'} {ticker}...")
        result = get_analysis_cached(ticker, use_cache)
        if result.get("status") == "ok":
            all_results.append(result)

    progress.progress(1.0, text="Screening completo.")

    # ── Tabla de screening ────────────────────────────────────────────────────
    st.divider()
    st.subheader("Resultados del screening")
    rows = []
    approved = []
    for r in all_results:
        ceo     = r.get("ceo_thesis", {})
        verdict = ceo.get("final_verdict", "N/A")
        score   = ceo.get("ceo_score") or 0
        qualifies = verdict == "buy" and score >= MIN_SCORE
        if qualifies:
            r["price"]  = r.get("price", {}).get("current_price")
            r["sector"] = (
                r.get("reports", {}).get("sentiment", {}).get("sector_outlook")
                or r.get("reports", {}).get("fundamental", {}).get("sector", "unknown")
            )
            approved.append(r)
        rows.append({
            "Ticker":     r.get("ticker", "?"),
            "Veredicto":  verdict.upper(),
            "Score":      score,
            "Convicción": (ceo.get("conviction") or "N/A").upper(),
            "Aprobado":   "✅" if qualifies else "❌",
        })
    st.dataframe(rows, use_container_width=True, hide_index=True)

    if not approved:
        st.warning("Ningún candidato calificó (BUY + score ≥ 6).")
        st.stop()

    st.success(f"{len(approved)} candidatos aprobados.")

    # ── Allocator ─────────────────────────────────────────────────────────────
    with st.spinner("💼 Allocator construyendo portafolio óptimo..."):
        portfolio = build_portfolio(capital, approved, profile)

    if "error" in portfolio:
        st.error(f"Error en allocator: {portfolio.get('raw', '')[:300]}")
        st.stop()

    # ── Resultado ─────────────────────────────────────────────────────────────
    st.divider()
    st.subheader("Portafolio óptimo")

    m1, m2, m3 = st.columns(3)
    m1.metric("Capital",   f"${capital:,.0f}")
    m2.metric("Invertido", f"${portfolio.get('total_invested', 0):,.2f}")
    m3.metric("Cash",      f"${portfolio.get('cash_reserve', 0):,.2f}")

    positions = portfolio.get("positions", [])
    pos_rows = []
    for p in positions:
        pos_rows.append({
            "Ticker":    p["ticker"],
            "Acciones":  p["shares"],
            "Precio":    f"${p['price']:,.2f}",
            "Monto USD": f"${p['amount_usd']:,.2f}",
            "%":         f"{p['allocation_pct']:.1f}%",
            "Stop Loss": f"${p.get('stop_loss', 'N/A')}",
            "Take Profit": f"${p.get('take_profit', 'N/A')}",
        })
    st.dataframe(pos_rows, use_container_width=True, hide_index=True)

    st.write("**Tesis del portafolio:**", portfolio.get("portfolio_thesis", ""))
    st.write("**Riesgo principal:**", portfolio.get("main_risk", ""))

    # ── Guardar y email ───────────────────────────────────────────────────────
    output_file = f"storage/portfolio_{date.today().isoformat()}.json"
    with open(output_file, "w") as f:
        json.dump({"capital": capital, "date": date.today().isoformat(), "portfolio": portfolio}, f, indent=2, ensure_ascii=False)
    st.caption(f"💾 Guardado en {output_file}")

    if send_email:
        send_portfolio_email(portfolio, capital)
        st.caption("📧 Email enviado.")
