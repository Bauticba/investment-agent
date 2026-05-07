import json
import streamlit as st

PROFILE_PATH = "instructions/investor_profile.json"

st.set_page_config(page_title="Perfil de inversión", page_icon="⚙️", layout="wide")
st.title("⚙️ Perfil de inversión")
st.caption("Los cambios se aplican a todos los análisis futuros.")


def load_profile() -> dict:
    with open(PROFILE_PATH) as f:
        return json.load(f)


def save_profile(profile: dict):
    with open(PROFILE_PATH, "w") as f:
        json.dump(profile, f, indent=2, ensure_ascii=False)


profile = load_profile()
rp      = profile["risk_profile"]
fr      = profile["fundamental_rules"]
tr      = profile["technical_rules"]

# ── Perfil de riesgo ──────────────────────────────────────────────────────────
st.subheader("Perfil de riesgo")
c1, c2 = st.columns(2)

with c1:
    _nivel_map = {"low": "bajo", "moderate": "moderado", "high": "alto"}
    _nivel_actual = _nivel_map.get(rp.get("level", "moderado"), rp.get("level", "moderado"))
    nivel = st.selectbox(
        "Nivel de riesgo",
        ["bajo", "moderado", "alto"],
        index=["bajo", "moderado", "alto"].index(_nivel_actual) if _nivel_actual in ["bajo", "moderado", "alto"] else 1,
    )
    stop_loss = st.slider(
        "Stop loss %",
        min_value=3, max_value=20, value=int(rp.get("stop_loss_pct", 8)),
        help="El análisis CEO calcula el precio de stop loss en base a este porcentaje.",
    )

with c2:
    take_profit = st.slider(
        "Take profit %",
        min_value=10, max_value=60, value=int(rp.get("take_profit_pct", 20)),
    )
    max_per_pos = st.slider(
        "Máx % por posición",
        min_value=5, max_value=30, value=int(rp.get("max_portfolio_allocation_per_stock_pct", 15)),
        help="Límite de concentración por ticker en el portafolio.",
    )

# ── Reglas fundamentales ──────────────────────────────────────────────────────
st.divider()
st.subheader("Reglas fundamentales")
c3, c4 = st.columns(2)

with c3:
    max_pe = st.slider(
        "P/E máximo",
        min_value=10, max_value=120, value=int(fr.get("max_pe_ratio", 40)),
        help="Empresas con P/E mayor a este valor reciben flag negativo.",
    )
    min_growth = st.slider(
        "Crecimiento de ingresos mínimo %",
        min_value=0, max_value=30, value=int(fr.get("min_revenue_growth_pct", 5)),
    )

with c4:
    max_debt = st.slider(
        "Deuda/Equity máximo",
        min_value=0.5, max_value=5.0, step=0.1,
        value=float(fr.get("max_debt_to_equity", 2.0)),
    )
    min_current = st.slider(
        "Current ratio mínimo",
        min_value=0.5, max_value=3.0, step=0.1,
        value=float(fr.get("min_current_ratio", 1.0)),
    )

# ── Reglas técnicas ───────────────────────────────────────────────────────────
st.divider()
st.subheader("Reglas técnicas")
c5, c6 = st.columns(2)

with c5:
    only_above_ma200 = st.checkbox(
        "Solo operar por encima de la MA200",
        value=tr.get("only_above_200_day_ma", True),
    )
    require_volume = st.checkbox(
        "Requerir confirmación de volumen",
        value=tr.get("require_volume_confirmation", True),
    )

with c6:
    rsi_min, rsi_max = st.slider(
        "Rango de RSI aceptable",
        min_value=10, max_value=90,
        value=(int(tr.get("min_rsi", 30)), int(tr.get("max_rsi", 75))),
        help="Señales fuera de este rango son marcadas como desfavorables.",
    )

# ── Watchlist ─────────────────────────────────────────────────────────────────
st.divider()
st.subheader("Watchlist")

universe_flat = [t for sector in profile.get("universe", {}).values() for t in sector]
current_wl    = profile.get("watchlist", [])

watchlist = st.multiselect(
    "Tickers de la watchlist",
    options=sorted(universe_flat),
    default=current_wl,
    help="Estos tickers se usan con `python3 main.py watchlist` sin argumentos.",
)

# ── Guardar ───────────────────────────────────────────────────────────────────
st.divider()

col_btn, col_reset = st.columns([1, 5])
with col_btn:
    guardar = st.button("💾 Guardar cambios", type="primary", use_container_width=True)
with col_reset:
    resetear = st.button("↩️ Restaurar defaults", type="secondary")

if guardar:
    profile["risk_profile"]["level"]                              = nivel
    profile["risk_profile"]["stop_loss_pct"]                      = stop_loss
    profile["risk_profile"]["take_profit_pct"]                    = take_profit
    profile["risk_profile"]["max_portfolio_allocation_per_stock_pct"] = max_per_pos
    profile["fundamental_rules"]["max_pe_ratio"]                  = max_pe
    profile["fundamental_rules"]["min_revenue_growth_pct"]        = min_growth
    profile["fundamental_rules"]["max_debt_to_equity"]            = round(max_debt, 1)
    profile["fundamental_rules"]["min_current_ratio"]             = round(min_current, 1)
    profile["technical_rules"]["only_above_200_day_ma"]           = only_above_ma200
    profile["technical_rules"]["require_volume_confirmation"]     = require_volume
    profile["technical_rules"]["min_rsi"]                         = rsi_min
    profile["technical_rules"]["max_rsi"]                         = rsi_max
    profile["watchlist"]                                          = watchlist

    save_profile(profile)
    st.success("✅ Perfil guardado. Los próximos análisis usarán estas reglas.")
    st.rerun()

if resetear:
    DEFAULTS = {
        "risk_profile": {
            "level": "moderado", "stop_loss_pct": 8, "take_profit_pct": 20,
            "max_portfolio_allocation_per_stock_pct": 15, "max_loss_per_trade_pct": 5,
        },
        "fundamental_rules": {
            "max_pe_ratio": 40, "min_revenue_growth_pct": 5,
            "max_debt_to_equity": 2.0, "min_current_ratio": 1.0,
        },
        "technical_rules": {
            "only_above_200_day_ma": True, "min_rsi": 30,
            "max_rsi": 75, "require_volume_confirmation": True,
        },
        "watchlist": ["AAPL", "MSFT", "NVDA", "GOOGL", "META", "AMZN"],
    }
    for section, values in DEFAULTS.items():
        profile[section].update(values)
    save_profile(profile)
    st.success("↩️ Perfil restaurado a los valores originales.")
    st.rerun()

# ── Vista del JSON actual ─────────────────────────────────────────────────────
with st.expander("Ver JSON completo del perfil"):
    st.json(load_profile())
