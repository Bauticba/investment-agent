import streamlit as st
import json
import time
import os

st.set_page_config(page_title="Watchlist", page_icon="🔍", layout="wide")
st.title("🔍 Watchlist — analizar tickers")

with open("instructions/investor_profile.json") as f:
    profile = json.load(f)

default_watchlist = profile.get("watchlist", ["AAPL", "MSFT", "NVDA", "GOOGL"])
universe_flat = [t for tickers in profile.get("universe", {}).values() for t in tickers]

# ── Configuración ─────────────────────────────────────────────────────────────
st.subheader("Configuración")
col1, col2 = st.columns([3, 1])

with col1:
    tickers_input = st.multiselect(
        "Tickers a analizar",
        options=sorted(set(universe_flat + default_watchlist)),
        default=default_watchlist,
        help="Seleccioná los tickers o escribí uno nuevo",
    )

with col2:
    st.write("")
    st.write("")
    send_email = st.checkbox("Enviar email por ticker", value=True)

DELAY = 12

if not tickers_input:
    st.warning("Seleccioná al menos un ticker.")
    st.stop()

st.info(f"Tiempo estimado: ~{len(tickers_input) * 55 + (len(tickers_input)-1) * DELAY}s")

# ── Análisis ──────────────────────────────────────────────────────────────────
if st.button("Analizar", type="primary", use_container_width=True):
    from ceo.orchestrator import run_analysis, print_thesis
    from notifications.email_sender import send_investment_email

    results = []
    progress = st.progress(0, text="Iniciando...")

    for i, ticker in enumerate(tickers_input):
        if i > 0:
            for remaining in range(DELAY, 0, -1):
                progress.progress(i / len(tickers_input), text=f"⏳ Esperando {remaining}s (rate limit)...")
                time.sleep(1)

        progress.progress(i / len(tickers_input), text=f"🔍 Analizando {ticker}...")

        with st.spinner(f"Analizando {ticker}..."):
            result = run_analysis(ticker)

        if result.get("status") == "ok":
            results.append(result)
            ceo = result.get("ceo_thesis", {})

            with open(f"storage/{ticker}_analysis.json", "w") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)

            verdict = (ceo.get("final_verdict") or "").upper()
            score   = ceo.get("ceo_score", "?")
            verdict_color = {"BUY": "🟢", "HOLD": "🟡", "SELL": "🔴"}.get(verdict, "❓")

            with st.expander(f"{verdict_color} {ticker} — {verdict} | Score: {score}/10", expanded=True):
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Score CEO",    f"{score}/10")
                c2.metric("Convicción",   (ceo.get("conviction") or "N/A").upper())
                c3.metric("Stop Loss",    f"${ceo.get('stop_loss', 'N/A')}")
                c4.metric("Take Profit",  f"${ceo.get('take_profit', 'N/A')}")

                st.write("**Tesis:**", ceo.get("thesis", "N/A"))

                pros = ceo.get("pros", [])
                cons = ceo.get("cons", [])
                if pros or cons:
                    pc1, pc2 = st.columns(2)
                    with pc1:
                        st.write("**Pros**")
                        for p in pros:
                            st.write(f"✅ {p}")
                    with pc2:
                        st.write("**Contras**")
                        for c in cons:
                            st.write(f"❌ {c}")

            if send_email:
                send_investment_email(result)
                st.caption(f"📧 Email enviado para {ticker}")

        else:
            st.error(f"❌ {ticker}: {result.get('message', 'error desconocido')}")

    progress.progress(1.0, text="Listo.")

    # ── Tabla resumen ──────────────────────────────────────────────────────────
    if results:
        st.divider()
        st.subheader("Resumen")
        rows = []
        for r in results:
            ceo = r.get("ceo_thesis", {})
            rows.append({
                "Ticker":     r["ticker"],
                "Veredicto":  (ceo.get("final_verdict") or "N/A").upper(),
                "Score":      ceo.get("ceo_score"),
                "Convicción": (ceo.get("conviction") or "N/A").upper(),
                "Stop Loss":  ceo.get("stop_loss"),
                "Take Profit":ceo.get("take_profit"),
            })
        st.dataframe(rows, use_container_width=True, hide_index=True)
