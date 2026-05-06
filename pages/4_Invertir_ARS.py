import streamlit as st
import json
from datetime import date

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

# Fecha objetivo
from datetime import date, timedelta
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

# ── Ejecución ─────────────────────────────────────────────────────────────────
if st.button("Generar recomendación", type="primary", use_container_width=True):
    from data.argentina import get_macro_data
    from data.instruments_ar import get_instruments_universe
    from agents.ars_advisor import recommend_allocation
    from data.cedears import get_top_cedears
    from notifications.email_sender import send_ars_recommendation_email

    with open("instructions/investor_profile.json") as f:
        profile = json.load(f)

    # Macro
    with st.spinner("📊 Obteniendo contexto macro..."):
        macro = get_macro_data()

    infl_m = macro.get("inflation_monthly")
    infl_a = macro.get("inflation_annual")
    usd    = macro.get("usd_oficial")
    uva    = macro.get("uva")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Inflación mensual",  f"{infl_m:.1f}%" if infl_m else "N/A")
    m2.metric("Inflación anual",    f"{infl_a:.1f}%" if infl_a else "N/A")
    m3.metric("Dólar oficial",      f"${usd:,.0f}" if usd else "N/A")
    m4.metric("UVA",                f"${uva:,.2f}" if uva else "N/A")

    # Instrumentos
    with st.spinner("📋 Construyendo universo de instrumentos..."):
        instruments = get_instruments_universe(macro)

    relevant = [i for i in instruments if riesgo in i.get("recommended_for", [])]
    st.caption(f"{len(instruments)} instrumentos totales | {len(relevant)} compatibles con perfil {riesgo.upper()}")

    # Recomendación
    with st.spinner("🤖 Generando recomendación personalizada..."):
        rec = recommend_allocation(capital, riesgo, instruments, macro, profile, fecha_objetivo=fecha_objetivo)

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
            "Instrumento": f"{emoji} {pos.get('name', '?')}",
            "%":           f"{pos.get('allocation_pct', 0):.0f}%",
            "Monto ARS":   pos.get("amount_ars", 0),
            "Cómo comprar": pos.get("how_to_buy", ""),
            "Por qué":     pos.get("rationale", ""),
        })
    st.dataframe(rows, use_container_width=True, hide_index=True)

    total_pct = sum(p.get("allocation_pct", 0) for p in allocation)
    total_amt = sum(p.get("amount_ars", 0) for p in allocation)
    st.write(f"**Total: {total_pct:.0f}% — ${total_amt:,.0f} ARS**")

    # Métricas
    m1, m2, m3 = st.columns(3)
    m1.metric("Cobertura inflacionaria", f"{rec.get('inflation_coverage_pct', '?')}%")
    m2.metric("Exposición USD",          f"{rec.get('usd_exposure_pct', '?')}%")
    m3.metric("Horizonte",               rec.get("time_horizon", "?"))

    st.write("**Estrategia:**", rec.get("strategy_summary", ""))
    st.write("**Riesgo principal:**", rec.get("main_risk", ""))
    st.write("**Próxima revisión:**", rec.get("review_in", "?"))

    # ── CEDEARs específicos ───────────────────────────────────────────────────
    has_cedears = any(p.get("type") in ("cedear", "cedears") for p in allocation)
    cedear_picks = None
    if has_cedears:
        picks = get_top_cedears(max_count=3, min_score=6.0)
        if picks:
            st.divider()
            st.subheader("CEDEARs recomendados (basado en análisis cacheados)")
            cedear_picks = picks
            for p in picks:
                with st.expander(f"🌎 {p['ticker']} — {p['name']} | Score: {p['score']}/10"):
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Score CEO",    f"{p['score']}/10")
                    c2.metric("Convicción",   (p.get("conviction") or "N/A").upper())
                    c3.metric("Precio USD",   f"${p.get('us_price_usd', 'N/A')}")
                    if p.get("parity_price_ars"):
                        st.write(f"**Paridad estimada ARS:** ${p['parity_price_ars']:,.2f} (ratio 1:{p['ratio']})")
                    st.write(f"**Veredicto:** {p.get('verdict', '')}")
                    st.write(f"**Tesis:** {p.get('thesis', '')}")
                    st.write(f"**Cómo comprar:** {p.get('how_to_buy', '')}")
        else:
            st.info("No hay análisis cacheados de CEDEARs. Ejecutá la página **Watchlist** primero.")

    # ── Guardar y email ───────────────────────────────────────────────────────
    output_file = f"storage/inversion_ars_{date.today().isoformat()}.json"
    with open(output_file, "w") as f:
        json.dump({
            "date": date.today().isoformat(),
            "capital_ars": capital,
            "riesgo": riesgo,
            "macro": macro,
            "recommendation": rec,
        }, f, indent=2, ensure_ascii=False)
    st.caption(f"💾 Guardado en {output_file}")

    if send_email:
        send_ars_recommendation_email(rec, capital, riesgo, macro, cedear_picks)
        st.caption("📧 Email enviado.")
