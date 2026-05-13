import json
from datetime import date, timedelta

import streamlit as st

st.set_page_config(page_title="Invertir ARS", page_icon="💵", layout="wide")
st.title("💵 Recomendación de inversión en ARS")
st.caption("Asignación óptima para pesos argentinos según tu perfil de riesgo.")

# ── Configuración ─────────────────────────────────────────────────────────────
col1, col2, col3 = st.columns(3)

with col1:
    capital = st.number_input(
        "Capital a invertir (ARS)",
        min_value=1000.0,
        value=500_000.0,
        step=50_000.0,
        format="%.0f",
    )
with col2:
    riesgo = st.selectbox(
        "Perfil de riesgo",
        options=["bajo", "moderado", "alto"],
        index=1,
    )
with col3:
    send_email = st.checkbox("Enviar email con la recomendación", value=True)

col_fecha, col_info = st.columns([2, 3])
with col_fecha:
    usar_fecha = st.checkbox("Tengo una fecha objetivo para retirar el dinero")
    fecha_objetivo = None
    if usar_fecha:
        fecha_dt = st.date_input(
            "¿Cuándo necesitás el dinero?",
            value=date.today().replace(year=date.today().year + 1),
            min_value=date.today() + timedelta(days=1),
        )
        fecha_objetivo = fecha_dt.strftime("%Y-%m")
        meses = (fecha_dt.year - date.today().year) * 12 + (fecha_dt.month - date.today().month)
        st.caption(f"Horizonte: {meses} meses desde hoy")

with col_info:
    RIESGO_DESC = {
        "bajo":     "PF UVA + FCI. Sin CEDEARs. Máx 20% bonos CER. Prioridad: preservar capital.",
        "moderado": "30-50% CER/UVA + 20-30% MEP + 10-20% CEDEARs + 10% FCI.",
        "alto":     "30-40% CEDEARs + 20-30% MEP + 20% CER + 10% FCI. Mayor exposición USD.",
    }
    info = RIESGO_DESC[riesgo]
    if fecha_objetivo and usar_fecha:
        info += f" La recomendación priorizará instrumentos que venzan **antes de {fecha_objetivo}**."
    st.info(info)

if riesgo in ("moderado", "alto"):
    st.caption(
        "⚠️ Con perfil moderado/alto se analizan acciones MERVAL en tiempo real (~60 s adicionales)."
    )

# ── Ejecución ─────────────────────────────────────────────────────────────────
if st.button("Generar recomendación", type="primary", use_container_width=True):
    from data.argentina import get_macro_data
    from data.instruments_ar import get_instruments_universe
    from data.news_ar import get_argentina_news
    from data.cedears import get_top_cedears
    from agents.ars_advisor import recommend_allocation
    from agents.merval_analyzer import get_top_merval
    from notifications.email_sender import send_ars_recommendation_email

    with open("instructions/investor_profile.json") as f:
        profile = json.load(f)

    # ── Macro ─────────────────────────────────────────────────────────────────
    with st.spinner("📊 Obteniendo contexto macro..."):
        macro = get_macro_data()

    infl_m    = macro.get("inflation_monthly")
    infl_a    = macro.get("inflation_annual")
    infl_date = macro.get("inflation_date")
    usd       = macro.get("usd_oficial")
    uva       = macro.get("uva")

    # Etiqueta con el mes del último dato oficial de inflación
    _meses = ["ene","feb","mar","abr","may","jun","jul","ago","sep","oct","nov","dic"]
    if infl_date:
        try:
            _p = infl_date.split("-")
            infl_label = f"IPC {_meses[int(_p[1])-1]} {_p[0]} (INDEC)"
        except Exception:
            infl_label = "Inflación mensual (INDEC)"
    else:
        infl_label = "Inflación mensual (INDEC)"

    m1, m2, m3, m4 = st.columns(4)
    m1.metric(infl_label,      f"{infl_m:.1f}%" if infl_m else "N/A")
    m2.metric("Inflación anual",   f"{infl_a:.1f}%" if infl_a else "N/A")
    m3.metric("Dólar oficial",     f"${usd:,.0f}" if usd else "N/A")
    m4.metric("UVA",               f"${uva:,.2f}" if uva else "N/A")

    # ── Noticias ──────────────────────────────────────────────────────────────
    with st.spinner("📰 Obteniendo noticias recientes..."):
        news = get_argentina_news(max_articles=12)

    with st.expander(f"📰 Noticias del día ({len(news)} titulares)", expanded=False):
        for a in news:
            st.markdown(f"**[{a['date']} — {a['source']}]** {a['title']}")
            if a.get("summary"):
                st.caption(a["summary"])

    # ── Instrumentos ─────────────────────────────────────────────────────────
    with st.spinner("📋 Construyendo universo de instrumentos..."):
        instruments = get_instruments_universe(macro)

    relevant = [i for i in instruments if riesgo in i.get("recommended_for", [])]
    st.caption(
        f"{len(instruments)} instrumentos totales | {len(relevant)} compatibles con perfil {riesgo.upper()}"
    )

    # ── CEDEARs picks ─────────────────────────────────────────────────────────
    with st.spinner("📈 Cargando picks de CEDEARs..."):
        cedear_picks = get_top_cedears(max_count=5, min_score=5.0)
    st.caption(f"{len(cedear_picks)} CEDEARs con análisis cacheado disponibles")

    # ── MERVAL picks ──────────────────────────────────────────────────────────
    merval_picks = None
    if riesgo in ("moderado", "alto"):
        with st.spinner("🇦🇷 Analizando acciones MERVAL (puede tardar ~60 s)..."):
            merval_picks = get_top_merval(profile, min_score=6.0, max_count=3)
        st.caption(f"{len(merval_picks)} acciones MERVAL con score ≥ 6")

    # ── Recomendación ─────────────────────────────────────────────────────────
    with st.spinner("🤖 Generando recomendación personalizada..."):
        rec = recommend_allocation(
            capital, riesgo, instruments, macro, profile,
            fecha_objetivo=fecha_objetivo,
            news=news,
            cedear_picks=cedear_picks,
            merval_picks=merval_picks,
        )

    if "error" in rec:
        st.error(f"Error: {rec.get('raw', '')[:300]}")
        st.stop()

    # ── Tabla de asignación ───────────────────────────────────────────────────
    st.divider()
    st.subheader(f"Portafolio recomendado — ${capital:,.0f} ARS — Riesgo {riesgo.upper()}")

    type_emoji = {
        "bono_cer": "📈", "lecer": "📈", "lecap": "📋", "caucion": "🔐",
        "plazo_fijo_uva": "🔒", "plazo_fijo": "🔒", "dolar_mep": "💵",
        "bono_hard_dollar": "💲", "on_usd": "🏢", "fci_mm": "💧",
        "fci_renta_fija": "💧", "fci_dolar_linked": "💵", "fci_acciones": "📊",
        "cedear": "🌎", "cedears": "🌎", "accion_merval": "🇦🇷",
    }

    allocation = rec.get("allocation", [])
    rows = []
    for pos in allocation:
        emoji = type_emoji.get(pos.get("type", ""), "")
        rows.append({
            "Instrumento":  f"{emoji} {pos.get('name', '?')}",
            "%":            f"{pos.get('allocation_pct', 0):.0f}%",
            "Monto ARS":    pos.get("amount_ars", 0),
            "Cómo comprar": pos.get("how_to_buy", ""),
            "Por qué":      pos.get("rationale", ""),
        })
    st.dataframe(rows, use_container_width=True, hide_index=True)

    total_pct = sum(p.get("allocation_pct", 0) for p in allocation)
    total_amt = sum(p.get("amount_ars", 0) for p in allocation)
    st.write(f"**Total: {total_pct:.0f}% — ${total_amt:,.0f} ARS**")

    r1, r2, r3 = st.columns(3)
    r1.metric("Cobertura inflacionaria", f"{rec.get('inflation_coverage_pct', '?')}%")
    r2.metric("Exposición USD total",    f"{rec.get('usd_exposure_pct', '?')}%")
    r3.metric("Horizonte",               rec.get("time_horizon", "?"))

    usd_bd = rec.get("usd_exposure_breakdown")
    if usd_bd:
        bd1, bd2, bd3, bd4 = st.columns(4)
        bd1.metric("💵 MEP / dólar líquido",           f"{usd_bd.get('dolar_liquido_pct', 0):.0f}%")
        bd2.metric("🇦🇷 Soberano hard dollar",          f"{usd_bd.get('renta_soberana_usd_pct', usd_bd.get('renta_fija_usd_pct', 0)):.0f}%")
        bd3.metric("🏢 ONs corporativas USD",           f"{usd_bd.get('renta_corporativa_usd_pct', 0):.0f}%")
        bd4.metric("🌎 Equity dolarizado (CEDEARs)",    f"{usd_bd.get('equity_dolarizado_pct', 0):.0f}%")

    st.write("**Estrategia:**",        rec.get("strategy_summary", ""))
    st.write("**Riesgo principal:**",  rec.get("main_risk", ""))
    st.write("**Próxima revisión:**",  rec.get("review_in", "?"))

    # ── Tabla de riesgo por instrumento ──────────────────────────────────────
    risk_rows = [
        {
            "Instrumento": pos.get("name", "?"),
            "Riesgo principal": pos.get("main_risk", "—"),
            "Liquidez": pos.get("liquidity", "—"),
            "Rol": pos.get("role", "—"),
        }
        for pos in allocation
        if pos.get("main_risk") or pos.get("role")
    ]
    if risk_rows:
        st.divider()
        st.subheader("📋 Riesgo por instrumento")
        st.dataframe(risk_rows, use_container_width=True, hide_index=True)
        st.caption("⚠️ Los resultados no incluyen comisiones, spread de compra/venta ni diferencia entre precio teórico y ejecutado.")

    # ── Triggers de rebalanceo ─────────────────────────────────────────────────
    triggers = rec.get("rebalance_triggers", [])
    if triggers:
        st.subheader("🔁 Cuándo rebalancear")
        for t in triggers:
            st.markdown(f"- {t}")

    # ── CEDEARs picks detalle ─────────────────────────────────────────────────
    has_cedears = any(p.get("type") in ("cedear", "cedears") for p in allocation)
    if has_cedears and cedear_picks:
        # Separar picks incluidos en cartera de los que son solo alternativos
        alloc_text = " ".join(
            (pos.get("name", "") + " " + pos.get("instrument_id", "")).upper()
            for pos in allocation if pos.get("type") in ("cedear", "cedears")
        )
        en_cartera   = [p for p in cedear_picks if p["ticker"].upper() in alloc_text]
        alternativas = [p for p in cedear_picks if p["ticker"].upper() not in alloc_text]

        def _cedear_expander(p, badge="", in_cartera=True):
            label = f"🌎 {p['ticker']} — {p['name']} | Score: {p['score']}/10{badge}"
            with st.expander(label):
                c1, c2, c3 = st.columns(3)
                c1.metric("Score CEO",  f"{p['score']}/10")
                c2.metric("Convicción", (p.get("conviction") or "N/A").upper())
                c3.metric("Precio USD", f"${p.get('us_price_usd', 'N/A')}")
                if p.get("parity_price_ars"):
                    st.write(f"**Paridad ARS:** ${p['parity_price_ars']:,.0f} (ratio 1:{p['ratio']})")
                st.write(f"**Veredicto:** {p.get('verdict', '')}")
                st.write(f"**Tesis:** {p.get('thesis', '')}")
                if in_cartera:
                    how = p.get("how_to_buy") or f"IOL > Operar > CEDEARs > buscar {p['ticker']} > Comprar"
                    st.write(f"**Cómo comprar:** {how}")
                else:
                    st.caption(f"📌 Monitorear en IOL: Mercados > CEDEARs > {p['ticker']}. No ejecutar orden en esta cartera.")

        st.divider()
        st.subheader("CEDEARs incluidos en la cartera")
        if en_cartera:
            for p in en_cartera:
                _cedear_expander(p, " ✅")
        else:
            st.caption("El advisor no asignó CEDEARs específicos del análisis (puede haber usado un pick genérico).")

        if alternativas:
            st.subheader("CEDEARs analizados — no incluidos en esta cartera")
            st.caption("Buen score pero descartados por el advisor en este contexto. Consideralos como alternativas.")
            for p in alternativas:
                _cedear_expander(p, in_cartera=False)

    elif has_cedears and not cedear_picks:
        st.info("No hay análisis cacheados de CEDEARs. Ejecutá la página **Watchlist** primero.")

    # ── MERVAL picks detalle ──────────────────────────────────────────────────
    has_merval = any(p.get("type") == "accion_merval" for p in allocation)
    if has_merval and merval_picks:
        alloc_merval_text = " ".join(
            (pos.get("instrument_id", "") + " " + pos.get("name", "")).upper()
            for pos in allocation if pos.get("type") == "accion_merval"
        )
        en_cartera_m   = [p for p in merval_picks if p["ticker"].upper() in alloc_merval_text]
        alternativas_m = [p for p in merval_picks if p["ticker"].upper() not in alloc_merval_text]

        def _merval_expander(p):
            action = p.get("action", "hold")
            default_how = (
                f"IOL > Operar > Acciones > buscar {p['ticker']} > Comprar" if action == "buy"
                else f"Monitorear en IOL: Mercados > MERVAL > {p['ticker']}. No ejecutar orden aún."
            )
            with st.expander(
                f"🇦🇷 {p['ticker']} — {p.get('name', p['ticker'])} | Score: {p.get('score','?')}/10"
            ):
                mc1, mc2, mc3 = st.columns(3)
                mc1.metric("Score",      f"{p.get('score', '?')}/10")
                mc2.metric("Acción",     action.upper())
                if p.get("market_price_ars"):
                    mc3.metric("Precio ARS", f"${p['market_price_ars']:,.0f}")
                if p.get("ccl_implicit"):
                    st.caption(f"CCL implícito: ${p['ccl_implicit']:,.0f} ARS/USD")
                if p.get("rationale"):
                    st.write(f"**Análisis:** {p['rationale']}")
                if p.get("vs_alternatives"):
                    st.write(f"**Vs. alternativas:** {p['vs_alternatives']}")
                st.write(f"**IOL:** {p.get('how_to_buy') or default_how}")

        st.divider()
        if en_cartera_m:
            st.subheader("Acciones MERVAL incluidas en la cartera")
            for p in en_cartera_m:
                _merval_expander(p)

        if alternativas_m:
            st.subheader("Acciones MERVAL analizadas — no incluidas en cartera")
            st.caption("Score ≥ 6 pero el advisor no las seleccionó en este contexto. Seguirlas como alternativas.")
            for p in alternativas_m:
                _merval_expander(p)

    # ── Guardar y email ───────────────────────────────────────────────────────
    output_file = f"storage/inversion_ars_{date.today().isoformat()}.json"
    with open(output_file, "w") as f:
        json.dump({
            "date":           date.today().isoformat(),
            "capital_ars":    capital,
            "riesgo":         riesgo,
            "macro":          macro,
            "news":           news,
            "recommendation": rec,
        }, f, indent=2, ensure_ascii=False)
    st.caption(f"💾 Guardado en {output_file}")

    if send_email:
        send_ars_recommendation_email(rec, capital, riesgo, macro, cedear_picks, merval_picks)
        st.caption("📧 Email enviado.")
