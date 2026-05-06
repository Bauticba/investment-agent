import streamlit as st
import json
import time
import os
from datetime import date

st.set_page_config(page_title="Mi Portafolio", page_icon="🗂️", layout="wide")
st.title("🗂️ Mi portafolio")
st.caption("Análisis de tus posiciones actuales: acciones, bonos argentinos y CEDEARs.")

# ── Configuración ─────────────────────────────────────────────────────────────
col1, col2, col3 = st.columns(3)
with col1:
    portfolio_file = st.text_input("Archivo de portafolio", value="my_portfolio.json")
with col2:
    use_cache = st.checkbox("Usar cache para acciones", value=False)
with col3:
    send_email = st.checkbox("Enviar email con análisis", value=True)

if not os.path.exists(portfolio_file):
    st.error(f"No se encontró `{portfolio_file}`. Crealo con tus posiciones.")
    st.stop()

with open(portfolio_file) as f:
    portfolio_input = json.load(f)

positions = portfolio_input.get("positions", [])
cash      = portfolio_input.get("cash", {"USD": 0, "ARS": 0})
broker    = portfolio_input.get("broker", "desconocido")

# ── Vista previa del portafolio ───────────────────────────────────────────────
st.subheader(f"Posiciones — {broker}")
if positions:
    st.dataframe(positions, use_container_width=True, hide_index=True)
else:
    st.warning("No hay posiciones en el archivo.")
    st.stop()

c1, c2 = st.columns(2)
c1.metric("Cash USD", f"${cash.get('USD', 0):,.0f}")
c2.metric("Cash ARS", f"${cash.get('ARS', 0):,.0f}")

# ── Análisis ──────────────────────────────────────────────────────────────────
if st.button("Analizar portafolio", type="primary", use_container_width=True):
    from agents.position_analyzer import analyze_position
    from agents.bond_analyzer import analyze_bond_position
    from agents.cedear_analyzer import analyze_cedear_position
    from data.argentina import get_bond_data, BOND_REGISTRY
    from data.cedears import get_cedear_data, CEDEAR_REGISTRY
    from notifications.email_sender import send_portfolio_analysis_email
    from core.cache import get_analysis_cached
    from analyze_portfolio import _run_portfolio_ceo, _print_summary, _is_arg_bond, _is_cedear

    with open("instructions/investor_profile.json") as f:
        profile = json.load(f)

    bond_positions   = [p for p in positions if _is_arg_bond(p)]
    cedear_positions = [p for p in positions if _is_cedear(p)]
    stock_positions  = [p for p in positions if not _is_arg_bond(p) and not _is_cedear(p)]

    DELAY = 12
    analyses = {}

    # Acciones
    stock_tickers = list({p["ticker"] for p in stock_positions})
    for i, ticker in enumerate(stock_tickers):
        if i > 0 and not use_cache:
            for r in range(DELAY, 0, -1):
                st.toast(f"⏳ Rate limit: {r}s...")
                time.sleep(1)
        with st.spinner(f"{'📂' if use_cache else '🔍'} {ticker}..."):
            result = get_analysis_cached(ticker, use_cache)
        if result.get("status") == "ok":
            analyses[ticker] = result

    # Bonos
    bond_data_map = {}
    for p in bond_positions:
        ticker   = p["ticker"]
        override = p.get("current_price_override")
        with st.spinner(f"🇦🇷 Obteniendo precio de {ticker}..."):
            bond_data_map[ticker] = get_bond_data(ticker, price_override=override)

    # CEDEARs
    cedear_data_map = {}
    for p in cedear_positions:
        ticker   = p["ticker"].upper()
        override = p.get("current_price_override")
        with st.spinner(f"🌎 Obteniendo precio de {ticker}..."):
            cedear_data_map[ticker] = get_cedear_data(ticker, price_ars_override=override)

    # ── Analizar posiciones ───────────────────────────────────────────────────
    position_reports = []

    for position in stock_positions:
        ticker = position["ticker"]
        if ticker not in analyses:
            continue
        with st.spinner(f"Analizando posición {ticker}..."):
            report = analyze_position(position, analyses[ticker], profile)
        position_reports.append(report)

    for position in bond_positions:
        ticker = position["ticker"]
        with st.spinner(f"Analizando bono {ticker}..."):
            report = analyze_bond_position(position, bond_data_map.get(ticker, {}), profile)
        position_reports.append(report)

    for position in cedear_positions:
        ticker = position["ticker"].upper()
        with st.spinner(f"Analizando CEDEAR {ticker}..."):
            report = analyze_cedear_position(position, cedear_data_map.get(ticker, {}), profile)
        position_reports.append(report)

    if not position_reports:
        st.warning("No se pudo analizar ninguna posición.")
        st.stop()

    # ── CEO síntesis ─────────────────────────────────────────────────────────
    with st.spinner("Sintetizando visión del portafolio..."):
        thesis = _run_portfolio_ceo(position_reports, cash, profile, broker)

    # ── Resultados ────────────────────────────────────────────────────────────
    st.divider()
    st.subheader("Resultado por posición")

    action_colors = {"hold": "🟡", "sell": "🔴", "add": "🟢", "reduce": "🟠", "stop_loss_triggered": "🚨"}
    rows = []
    for r in position_reports:
        pnl = r.get("pnl_pct")
        rows.append({
            "Ticker":   r.get("ticker", "?"),
            "Acción":   f"{action_colors.get(r.get('action',''), '❓')} {(r.get('action') or '?').upper()}",
            "P&L %":    f"{pnl:+.1f}%" if pnl is not None else "N/A",
            "Urgencia": (r.get("urgency") or "?").upper(),
            "Alerta":   r.get("key_alert", ""),
        })
    st.dataframe(rows, use_container_width=True, hide_index=True)

    # ── Síntesis CEO ──────────────────────────────────────────────────────────
    st.subheader("Síntesis CEO del portafolio")
    health = thesis.get("portfolio_health", "?")
    health_color = {"excellent": "🟢", "good": "🟢", "warning": "🟡", "critical": "🔴"}.get(health, "❓")

    m1, m2 = st.columns(2)
    m1.metric("Estado general", f"{health_color} {health.upper()}")
    m2.metric("Diversificación", f"{thesis.get('diversification_score', '?')}/10")

    st.write("**Resumen:**", thesis.get("portfolio_summary", ""))
    st.write("**Riesgo principal:**", thesis.get("main_risk", ""))
    st.write("**Recomendación de cash:**", thesis.get("cash_recommendation", ""))
    st.write("**Próxima revisión:**", thesis.get("next_review", ""))

    st.subheader("Acciones prioritarias")
    urgency_colors = {"high": "🔴", "medium": "🟡", "low": "🟢"}
    for a in thesis.get("priority_actions", []):
        ticker_str = f"**[{a['ticker']}]** " if a.get("ticker") else ""
        st.write(f"{urgency_colors.get(a.get('urgency',''), '')} {ticker_str}{a.get('action', '')}")

    # ── Guardar y email ───────────────────────────────────────────────────────
    output_file = f"storage/portfolio_analysis_{date.today().isoformat()}.json"
    with open(output_file, "w") as f:
        json.dump({
            "date": date.today().isoformat(),
            "broker": broker,
            "cash": cash,
            "positions": position_reports,
            "portfolio_thesis": thesis,
        }, f, indent=2, ensure_ascii=False)
    st.caption(f"💾 Guardado en {output_file}")

    if send_email:
        send_portfolio_analysis_email(position_reports, thesis, cash, broker)
        st.caption("📧 Email enviado.")
