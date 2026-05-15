import json
import os

import streamlit as st

st.set_page_config(page_title="CEDEARs", page_icon="🌎", layout="wide")
st.title("🌎 CEDEARs — Acciones extranjeras en ARS")
st.caption("Paridad teórica, score CEO y calculadora de exposición USD.")

from data.cedears import CEDEAR_REGISTRY
from data.argentina import get_macro_data
from data.fx import ccl_price


@st.cache_data(ttl=1800)
def _macro():
    return get_macro_data()


macro = _macro()
ccl   = ccl_price(fallback=macro.get("usd_oficial") or 1400)
infl  = macro.get("inflation_monthly")

c1, c2, c3 = st.columns(3)
c1.metric("CCL (contado con liqui)", f"${ccl:,.0f} ARS/USD")
c2.metric("Inflación mensual",    f"{infl:.1f}%" if infl else "N/A")
c3.metric("CEDEARs en registro",  str(len(CEDEAR_REGISTRY)))


@st.cache_data(ttl=300)
def _load_rows() -> list[dict]:
    rows = []
    for ticker, meta in CEDEAR_REGISTRY.items():
        score, verdict, thesis = None, None, ""
        us_price, analysis_date = None, None
        pros: list = []
        cons: list = []

        path = f"storage/{ticker}_analysis.json"
        if os.path.exists(path):
            with open(path) as f:
                data = json.load(f)
            if data.get("status") == "ok":
                us_price      = (data.get("price") or {}).get("current_price")
                ceo           = data.get("ceo_thesis") or {}
                score         = ceo.get("ceo_score")
                verdict       = ceo.get("final_verdict", "")
                thesis        = (ceo.get("thesis") or "")[:300]
                pros          = (ceo.get("pros") or [])[:3]
                cons          = (ceo.get("cons") or [])[:2]
                analysis_date = data.get("date")

        ratio  = meta["ratio"]
        parity = round(us_price / ratio * ccl, 0) if us_price else None

        rows.append({
            "ticker":        ticker,
            "name":          meta["name"],
            "ratio":         ratio,
            "us_price_usd":  us_price,
            "parity_ars":    parity,
            "score":         score,
            "verdict":       verdict,
            "thesis":        thesis,
            "pros":          pros,
            "cons":          cons,
            "analysis_date": analysis_date,
        })

    return sorted(rows, key=lambda x: x["score"] or 0, reverse=True)


rows = _load_rows()

tab1, tab2 = st.tabs(["📊 Dashboard", "🔢 Calculadora USD"])

# ── Tab 1: Dashboard ──────────────────────────────────────────────────────────
with tab1:
    fc1, fc2 = st.columns(2)
    with fc1:
        filtro = st.multiselect(
            "Filtrar por veredicto",
            ["BUY", "HOLD", "AVOID"],
            placeholder="Todos",
        )
    with fc2:
        solo_analizados = st.checkbox("Solo con análisis CEO")

    table_rows = []
    for r in rows:
        if filtro and (r["verdict"] or "").upper() not in filtro:
            continue
        if solo_analizados and r["score"] is None:
            continue

        if r["score"] is None:
            sem = "⚪"
        elif r["score"] >= 7:
            sem = "🟢"
        elif r["score"] >= 5:
            sem = "🟡"
        else:
            sem = "🔴"

        table_rows.append({
            " ":           sem,
            "Ticker":      r["ticker"],
            "Nombre":      r["name"],
            "Ratio":       r["ratio"],
            "Precio USD":  f"${r['us_price_usd']:.2f}" if r["us_price_usd"] else "—",
            "Paridad ARS": f"${r['parity_ars']:,.0f}" if r["parity_ars"] else "—",
            "Score CEO":   f"{r['score']:.0f}/10" if r["score"] is not None else "Sin análisis",
            "Veredicto":   (r["verdict"] or "—").upper(),
            "Actualizado": r["analysis_date"] or "—",
        })

    st.dataframe(table_rows, use_container_width=True, hide_index=True)

    analyzed = sum(1 for r in rows if r["score"] is not None)
    st.caption(
        f"{analyzed}/{len(rows)} CEDEARs con análisis CEO. "
        "Para actualizar: `python3 main.py watchlist` o usá la página **Watchlist**."
    )

    # ── Detalle por ticker ────────────────────────────────────────────────────
    st.divider()
    st.subheader("Detalle por ticker")

    ticker_sel = st.selectbox(
        "Seleccioná un CEDEAR",
        [r["ticker"] for r in rows],
        format_func=lambda t: next(
            (f"{t} — {r['name']}" for r in rows if r["ticker"] == t), t
        ),
    )

    sel = next((r for r in rows if r["ticker"] == ticker_sel), None)
    if sel:
        ratio = CEDEAR_REGISTRY[ticker_sel]["ratio"]

        d1, d2, d3, d4 = st.columns(4)
        d1.metric("Score CEO",    f"{sel['score']:.0f}/10" if sel["score"] is not None else "N/A")
        d2.metric("Veredicto",    (sel["verdict"] or "N/A").upper())
        d3.metric("Precio USD",   f"${sel['us_price_usd']:.2f}" if sel["us_price_usd"] else "N/A")
        d4.metric("Paridad ARS",  f"${sel['parity_ars']:,.0f}" if sel["parity_ars"] else "N/A")

        st.info(
            f"**Ratio:** 1 acción {ticker_sel} = {ratio} CEDEARs  |  "
            f"**Cómo comprar:** IOL → Operar → CEDEARs → buscar {ticker_sel} → Comprar"
        )

        if sel["thesis"]:
            st.write("**Tesis CEO:**", sel["thesis"])

        if sel["pros"] or sel["cons"]:
            pc1, pc2 = st.columns(2)
            with pc1:
                if sel["pros"]:
                    st.write("**Pros:**")
                    for p in sel["pros"]:
                        st.write(f"✓ {p}")
            with pc2:
                if sel["cons"]:
                    st.write("**Contras:**")
                    for c_item in sel["cons"]:
                        st.write(f"✗ {c_item}")

        if sel["score"] is None:
            st.warning(
                f"Sin análisis para {ticker_sel}. "
                "Ejecutá la página **Watchlist** para generarlo."
            )

# ── Tab 2: Calculadora ────────────────────────────────────────────────────────
with tab2:
    st.subheader("Calculadora de exposición USD")
    st.caption(
        "¿Cuántos ARS necesitás para obtener X dólares de exposición vía CEDEAR?"
    )

    cc1, cc2 = st.columns(2)
    with cc1:
        calc_usd = st.number_input(
            "Exposición USD deseada ($)", min_value=100.0, value=1000.0, step=100.0
        )
    with cc2:
        opts = [r["ticker"] for r in rows if r["parity_ars"] is not None] or [r["ticker"] for r in rows]
        calc_ticker = st.selectbox(
            "CEDEAR",
            options=opts,
            format_func=lambda t: next(
                (f"{t} — {r['name']}" for r in rows if r["ticker"] == t), t
            ),
        )

    calc_row = next((r for r in rows if r["ticker"] == calc_ticker), None)
    if calc_row and calc_row["us_price_usd"] and calc_row["parity_ars"]:
        ars_needed     = calc_usd * ccl
        cedears_needed = round(calc_usd * calc_row["ratio"] / calc_row["us_price_usd"])

        rc1, rc2, rc3 = st.columns(3)
        rc1.metric("ARS necesarios",     f"${ars_needed:,.0f}")
        rc2.metric("CEDEARs a comprar",  f"~{cedears_needed}")
        rc3.metric("Paridad por CEDEAR", f"${calc_row['parity_ars']:,.0f} ARS")

        st.caption(
            f"CCL utilizado: ${ccl:,.0f} ARS/USD  |  "
            f"Precio subyacente: ${calc_row['us_price_usd']:.2f} USD  |  "
            f"Ratio 1:{calc_row['ratio']}"
        )
    elif calc_row and not calc_row["us_price_usd"]:
        st.warning(
            f"Sin precio USD en cache para {calc_ticker}. "
            "Ejecutá la página **Watchlist** para tener datos."
        )
