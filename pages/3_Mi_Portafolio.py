import streamlit as st
import json
import time
import os
from datetime import date

st.set_page_config(page_title="Mi Portafolio", page_icon="🗂️", layout="wide")
st.title("🗂️ Mi portafolio")

# ── Sincronización IOL ────────────────────────────────────────────────────────
from data.iol import is_available as _iol_available
from core.portfolio_manager import sync_from_iol, save_portfolio as _save_portfolio

if _iol_available():
    _col_sync, _col_status = st.columns([2, 3])
    with _col_sync:
        if st.button("🔄 Sincronizar desde IOL", type="primary", use_container_width=True):
            with st.spinner("Conectando con IOL y trayendo posiciones..."):
                _synced = sync_from_iol()
            if _synced and _synced.get("positions") is not None:
                _save_portfolio(_synced)
                n = len(_synced["positions"])
                st.success(f"✅ {n} posición{'es' if n != 1 else ''} sincronizada{'s' if n != 1 else ''} desde IOL")
                st.rerun()
            else:
                st.error("No se pudo obtener el portafolio desde IOL. Verificá las credenciales.")
    with _col_status:
        from core.portfolio_manager import get_portfolio as _gp_check
        _pf_check = _gp_check()
        if _pf_check.get("synced_from_iol"):
            st.caption(f"🟢 Última sincronización: {_pf_check.get('sync_timestamp', '—')}")
        else:
            st.caption("🟡 Portafolio cargado manualmente (no sincronizado desde IOL)")
else:
    st.info("💡 Configurá `IOL_USERNAME` e `IOL_PASSWORD` en `.env` para sincronizar automáticamente desde IOL.")

st.divider()

# ── Gestión de posiciones ─────────────────────────────────────────────────────
with st.expander("➕ Registrar compra / venta manualmente", expanded=False):
    tab_comprar, tab_vender, tab_eliminar = st.tabs(["Comprar", "Vender", "Eliminar posición"])

    with tab_comprar:
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            buy_ticker = st.text_input("Ticker", placeholder="AAPL", key="buy_ticker").upper()
        with c2:
            buy_shares = st.number_input("Cantidad", min_value=0.001, value=1.0, step=1.0, key="buy_shares")
        with c3:
            buy_price = st.number_input("Precio de compra", min_value=0.01, value=100.0, key="buy_price")
        with c4:
            buy_currency = st.selectbox("Moneda", ["USD", "ARS"], key="buy_currency")

        c5, c6 = st.columns(2)
        with c5:
            buy_type = st.selectbox(
                "Tipo de activo",
                ["(automático)", "cedear", "bono_argentino", "accion_merval"],
                key="buy_type",
            )
        with c6:
            buy_note = st.text_input("Nota (opcional)", key="buy_note")

        if st.button("Registrar compra", type="primary", key="btn_comprar"):
            if not buy_ticker:
                st.error("Ingresá el ticker.")
            else:
                from core.portfolio_manager import add_position
                asset_type = None if buy_type == "(automático)" else buy_type
                action = add_position(buy_ticker, buy_shares, buy_price, buy_currency, asset_type, buy_note)
                verb = "Agregado" if action == "added" else "Precio promediado"
                st.success(f"✅ {verb}: {buy_ticker} × {buy_shares} @ ${buy_price} {buy_currency}")
                st.rerun()

    with tab_vender:
        from core.portfolio_manager import get_portfolio
        _pf = get_portfolio()
        _tickers = [p["ticker"] for p in _pf.get("positions", [])]

        if not _tickers:
            st.info("No tenés posiciones registradas.")
        else:
            sv1, sv2 = st.columns(2)
            with sv1:
                sell_ticker = st.selectbox("Ticker a vender", _tickers, key="sell_ticker")
            with sv2:
                sell_shares = st.number_input("Cantidad a vender", min_value=0.001, value=1.0, step=1.0, key="sell_shares")

            if st.button("Registrar venta", type="primary", key="btn_vender"):
                from core.portfolio_manager import sell_position
                ok, msg = sell_position(sell_ticker, sell_shares)
                if ok:
                    st.success(f"✅ {msg}")
                    st.rerun()
                else:
                    st.error(msg)

    with tab_eliminar:
        if not _tickers:
            st.info("No tenés posiciones registradas.")
        else:
            del_ticker = st.selectbox("Ticker a eliminar", _tickers, key="del_ticker")
            if st.button("Eliminar posición completa", type="secondary", key="btn_eliminar"):
                from core.portfolio_manager import remove_position
                if remove_position(del_ticker):
                    st.success(f"✅ {del_ticker} eliminado del portafolio.")
                    st.rerun()

st.divider()

# ── Vista del portafolio actual ───────────────────────────────────────────────
from core.portfolio_manager import get_portfolio as _get_portfolio
portfolio_input = _get_portfolio()

positions = portfolio_input.get("positions", [])
cash      = portfolio_input.get("cash", {"USD": 0, "ARS": 0})
broker    = portfolio_input.get("broker", "desconocido")

st.subheader(f"Posiciones actuales — {broker}")

if not positions:
    st.info("No tenés posiciones. Usá el panel de arriba para registrar una compra.")
    st.stop()

st.dataframe(positions, use_container_width=True, hide_index=True)

# ── Saldo en efectivo ─────────────────────────────────────────────────────────
with st.expander("💵 Actualizar saldo en efectivo", expanded=cash.get("USD", 0) == 0 and cash.get("ARS", 0) == 0):
    st.caption("IOL no expone el saldo vía API — ingresalo manualmente y se conserva entre sincronizaciones.")
    _cs1, _cs2, _cs3 = st.columns([2, 2, 1])
    with _cs1:
        _new_usd = st.number_input("Cash USD", min_value=0.0, value=float(cash.get("USD", 0)), step=100.0, format="%.2f", key="cash_usd_input")
    with _cs2:
        _new_ars = st.number_input("Cash ARS", min_value=0.0, value=float(cash.get("ARS", 0)), step=1000.0, format="%.0f", key="cash_ars_input")
    with _cs3:
        st.write("")
        st.write("")
        if st.button("Guardar saldo", key="btn_cash"):
            from core.portfolio_manager import update_cash
            update_cash(usd=_new_usd, ars=_new_ars)
            st.success("✅ Saldo actualizado.")
            st.rerun()

c1, c2 = st.columns(2)
c1.metric("Cash USD", f"${cash.get('USD', 0):,.2f}")
c2.metric("Cash ARS", f"${cash.get('ARS', 0):,.0f}")

st.divider()

# ── Análisis de posiciones ────────────────────────────────────────────────────
st.subheader("Análisis y recomendaciones")

col_opts1, col_opts2 = st.columns(2)
with col_opts1:
    live_mode = st.checkbox(
        "Modo en vivo (re-analiza desde cero, más lento)",
        value=False,
        help="Desactivado = usa los análisis del storage (instantáneo). Activalo si querés datos frescos.",
    )
with col_opts2:
    send_email = st.checkbox("Enviar email con el análisis", value=True)

use_cache = not live_mode

if not live_mode:
    from analyze_portfolio import _is_arg_bond, _is_cedear, _is_on
    stock_positions = [p for p in positions if not _is_arg_bond(p) and not _is_cedear(p) and not _is_on(p)]
    cached = sum(1 for p in stock_positions if os.path.exists(f"storage/{p['ticker']}_analysis.json"))
    total_stocks = len(stock_positions)
    if total_stocks > 0:
        st.caption(f"Storage disponible para {cached}/{total_stocks} acciones. Bonos, ONs y CEDEARs traen precio desde IOL en tiempo real.")

if st.button("Analizar portafolio", type="primary", use_container_width=True):
    from agents.position_analyzer import analyze_position
    from agents.bond_analyzer import analyze_bond_position
    from agents.cedear_analyzer import analyze_cedear_position
    from agents.on_analyzer import analyze_on_position
    from data.argentina import get_bond_data, BOND_REGISTRY
    from data.cedears import get_cedear_data, CEDEAR_REGISTRY
    from data.instruments_ar import get_on_data
    from notifications.email_sender import send_portfolio_analysis_email
    from core.cache import get_analysis_cached
    from analyze_portfolio import _run_portfolio_ceo, _is_arg_bond, _is_cedear, _is_on

    with open("instructions/investor_profile.json") as f:
        profile = json.load(f)

    bond_positions   = [p for p in positions if _is_arg_bond(p)]
    cedear_positions = [p for p in positions if _is_cedear(p)]
    on_positions     = [p for p in positions if _is_on(p) and not _is_arg_bond(p)]
    stock_positions  = [p for p in positions if not _is_arg_bond(p) and not _is_cedear(p) and not _is_on(p)]

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
        elif result.get("status") == "skipped":
            st.warning(f"⚠️ {ticker}: sin análisis en storage. Corré `main.py actualizar {ticker}` primero.")

    # Bonos argentinos
    bond_data_map = {}
    for p in bond_positions:
        ticker = p["ticker"]
        with st.spinner(f"🇦🇷 Precio de {ticker} (IOL)..."):
            bond_data_map[ticker] = get_bond_data(ticker, price_override=p.get("current_price_override"))

    # ONs corporativas
    on_data_map = {}
    for p in on_positions:
        ticker = p["ticker"].upper()
        with st.spinner(f"🏦 Precio de {ticker} (IOL)..."):
            on_data_map[ticker] = get_on_data(ticker, price_ars_override=p.get("current_price_override"))

    # CEDEARs
    cedear_data_map = {}
    for p in cedear_positions:
        ticker = p["ticker"].upper()
        with st.spinner(f"🌎 Precio de {ticker} (IOL)..."):
            cedear_data_map[ticker] = get_cedear_data(ticker, price_ars_override=p.get("current_price_override"))

    # Analizar posiciones
    position_reports = []
    for position in stock_positions:
        ticker = position["ticker"]
        if ticker not in analyses:
            continue
        with st.spinner(f"Analizando {ticker}..."):
            report = analyze_position(position, analyses[ticker], profile)
        position_reports.append(report)

    for position in bond_positions:
        ticker = position["ticker"]
        with st.spinner(f"Analizando bono {ticker}..."):
            report = analyze_bond_position(position, bond_data_map.get(ticker, {}), profile)
        position_reports.append(report)

    for position in on_positions:
        ticker = position["ticker"].upper()
        with st.spinner(f"Analizando ON {ticker}..."):
            report = analyze_on_position(position, on_data_map.get(ticker, {}), profile)
        position_reports.append(report)

    for position in cedear_positions:
        ticker = position["ticker"].upper()
        with st.spinner(f"Analizando CEDEAR {ticker}..."):
            report = analyze_cedear_position(position, cedear_data_map.get(ticker, {}), profile)
        position_reports.append(report)

    if not position_reports:
        st.warning("No se pudo analizar ninguna posición. Corré `main.py actualizar` primero.")
        st.stop()

    # CEO síntesis
    with st.spinner("Sintetizando visión general del portafolio..."):
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

    # CEO síntesis
    st.subheader("Síntesis CEO")
    health = thesis.get("portfolio_health", "?")
    health_color = {"excellent": "🟢", "good": "🟢", "warning": "🟡", "critical": "🔴"}.get(health, "❓")

    m1, m2 = st.columns(2)
    m1.metric("Estado general",  f"{health_color} {health.upper()}")
    m2.metric("Diversificación", f"{thesis.get('diversification_score', '?')}/10")

    st.write("**Resumen:**",              thesis.get("portfolio_summary", ""))
    st.write("**Riesgo principal:**",     thesis.get("main_risk", ""))
    st.write("**Recomendación cash:**",   thesis.get("cash_recommendation", ""))
    st.write("**Próxima revisión:**",     thesis.get("next_review", ""))

    st.subheader("Acciones prioritarias")
    urgency_colors = {"high": "🔴", "medium": "🟡", "low": "🟢"}
    for a in thesis.get("priority_actions", []):
        ticker_str = f"**[{a['ticker']}]** " if a.get("ticker") else ""
        st.write(f"{urgency_colors.get(a.get('urgency',''), '')} {ticker_str}{a.get('action', '')}")

    # Guardar y email
    output_file = f"storage/portfolio_analysis_{date.today().isoformat()}.json"
    os.makedirs("storage", exist_ok=True)
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
