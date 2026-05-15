"""
Tests automáticos para agents/portfolio_validator.py.
Cubren las 10 reglas financieras core que el validador debe detectar.

Correr: python3 -m pytest tests/test_portfolio_validator.py -v
"""
import pytest
from agents.portfolio_validator import validate_allocation, compute_exposures, recalculate_fields

CAPITAL = 300_000
MACRO_INF_3_4 = {"inflation_monthly": 3.4}
MACRO_INF_2_5 = {"inflation_monthly": 2.5}


def _make_rec(allocation, triggers=None, usd_exposure_pct=None, usd_breakdown=None, inf_cov=None):
    bd = usd_breakdown or {
        "dolar_liquido_pct": 0,
        "renta_soberana_usd_pct": 0,
        "renta_corporativa_usd_pct": 0,
        "equity_dolarizado_pct": 0,
    }
    return {
        "allocation": allocation,
        "inflation_coverage_pct": inf_cov or 0,
        "usd_exposure_pct": usd_exposure_pct or 0,
        "usd_exposure_breakdown": bd,
        "rebalance_triggers": triggers or [],
    }


def _ok(allocation, triggers=None, **kw):
    """Cartera válida base para moderado con inf 3.4%."""
    rec = _make_rec(allocation, triggers, **kw)
    errors = validate_allocation(rec, CAPITAL, "moderado", MACRO_INF_3_4)
    return errors


# ─── 1. Suma de porcentajes == 100 ───────────────────────────────────────────
def test_allocation_sums_100_pass():
    alloc = [
        {"instrument_id": "tx26",            "type": "bono_cer",  "allocation_pct": 45, "amount_ars": 135000},
        {"instrument_id": "pamp3",           "type": "on_usd",    "allocation_pct": 15, "amount_ars": 45000},
        {"instrument_id": "nvda_cedear",     "type": "cedear",    "allocation_pct": 15, "amount_ars": 45000},
        {"instrument_id": "fci_money_market","type": "fci_mm",    "allocation_pct": 25, "amount_ars": 75000},
    ]
    errors = _ok(alloc, usd_breakdown={"dolar_liquido_pct":0,"renta_soberana_usd_pct":0,"renta_corporativa_usd_pct":15,"equity_dolarizado_pct":15})
    assert not any("suma de porcentajes" in e for e in errors)


def test_allocation_sums_100_fail():
    alloc = [
        {"instrument_id": "tx26",            "type": "bono_cer",  "allocation_pct": 45, "amount_ars": 135000},
        {"instrument_id": "fci_money_market","type": "fci_mm",    "allocation_pct": 50, "amount_ars": 150000},
    ]
    rec = _make_rec(alloc)
    errors = validate_allocation(rec, CAPITAL, "moderado", MACRO_INF_3_4)
    assert any("suma de porcentajes" in e for e in errors)


# ─── 2. Suma de montos == capital ─────────────────────────────────────────────
def test_amounts_sum_capital_fail():
    alloc = [
        {"instrument_id": "tx26",            "type": "bono_cer",  "allocation_pct": 50, "amount_ars": 100000},
        {"instrument_id": "fci_money_market","type": "fci_mm",    "allocation_pct": 50, "amount_ars": 100000},
    ]
    rec = _make_rec(alloc)
    errors = validate_allocation(rec, CAPITAL, "moderado", MACRO_INF_3_4)
    assert any("suma de montos" in e for e in errors)


# ─── 3. Moderado: equity máx 15% ─────────────────────────────────────────────
def test_moderado_max_equity_15_fail():
    alloc = [
        {"instrument_id": "tx26",            "type": "bono_cer",  "allocation_pct": 35, "amount_ars": 105000},
        {"instrument_id": "nvda_cedear",     "type": "cedear",    "allocation_pct": 20, "amount_ars": 60000},
        {"instrument_id": "fci_money_market","type": "fci_mm",    "allocation_pct": 45, "amount_ars": 135000},
    ]
    rec = _make_rec(alloc)
    errors = validate_allocation(rec, CAPITAL, "moderado", MACRO_INF_3_4)
    assert any("Equity" in e and "15%" in e for e in errors)


def test_moderado_max_equity_15_pass():
    alloc = [
        {"instrument_id": "tx26",            "type": "bono_cer",  "allocation_pct": 45, "amount_ars": 135000},
        {"instrument_id": "nvda_cedear",     "type": "cedear",    "allocation_pct": 15, "amount_ars": 45000},
        {"instrument_id": "fci_money_market","type": "fci_mm",    "allocation_pct": 40, "amount_ars": 120000},
    ]
    rec = _make_rec(alloc, usd_breakdown={"dolar_liquido_pct":0,"renta_soberana_usd_pct":0,"renta_corporativa_usd_pct":0,"equity_dolarizado_pct":15})
    errors = validate_allocation(rec, CAPITAL, "moderado", MACRO_INF_3_4)
    assert not any("Equity" in e for e in errors)


# ─── 4. Moderado: soberanos hard dollar máx 15% ───────────────────────────────
def test_moderado_max_hard_dollar_15_fail():
    alloc = [
        {"instrument_id": "tx26", "type": "bono_cer",        "allocation_pct": 35, "amount_ars": 105000},
        {"instrument_id": "gd28", "type": "bono_hard_dollar", "allocation_pct": 20, "amount_ars": 60000},
        {"instrument_id": "fci_money_market","type": "fci_mm","allocation_pct": 45, "amount_ars": 135000},
    ]
    rec = _make_rec(alloc)
    errors = validate_allocation(rec, CAPITAL, "moderado", MACRO_INF_3_4)
    assert any("hard dollar" in e and "15%" in e for e in errors)


def test_moderado_max_hard_dollar_15_pass():
    alloc = [
        {"instrument_id": "tx26", "type": "bono_cer",        "allocation_pct": 45, "amount_ars": 135000},
        {"instrument_id": "gd28", "type": "bono_hard_dollar", "allocation_pct": 15, "amount_ars": 45000},
        {"instrument_id": "fci_money_market","type": "fci_mm","allocation_pct": 40, "amount_ars": 120000},
    ]
    rec = _make_rec(alloc, usd_breakdown={"dolar_liquido_pct":0,"renta_soberana_usd_pct":15,"renta_corporativa_usd_pct":0,"equity_dolarizado_pct":0})
    errors = validate_allocation(rec, CAPITAL, "moderado", MACRO_INF_3_4)
    assert not any("hard dollar" in e for e in errors)


# ─── 5. Cobertura CER/UVA mínima 35% cuando inflación > 3% ──────────────────
def test_inflation_coverage_min_35_when_ipc_gt_3_fail():
    alloc = [
        {"instrument_id": "tx26", "type": "bono_cer",        "allocation_pct": 30, "amount_ars": 90000},
        {"instrument_id": "gd28", "type": "bono_hard_dollar", "allocation_pct": 15, "amount_ars": 45000},
        {"instrument_id": "fci_money_market","type": "fci_mm","allocation_pct": 55, "amount_ars": 165000},
    ]
    rec = _make_rec(alloc)
    errors = validate_allocation(rec, CAPITAL, "moderado", MACRO_INF_3_4)
    assert any("CER/UVA" in e and "35%" in e for e in errors)


def test_inflation_coverage_min_35_not_active_below_3():
    alloc = [
        {"instrument_id": "tx26", "type": "bono_cer",        "allocation_pct": 30, "amount_ars": 90000},
        {"instrument_id": "fci_money_market","type": "fci_mm","allocation_pct": 70, "amount_ars": 210000},
    ]
    rec = _make_rec(alloc)
    errors = validate_allocation(rec, CAPITAL, "moderado", MACRO_INF_2_5)
    assert not any("CER/UVA" in e and "35%" in e for e in errors)


# ─── 6. Sin MEP en cartera: FCI MM mínimo 15% ────────────────────────────────
def test_no_mep_trigger_fci_min_15_fail():
    alloc = [
        {"instrument_id": "tx26", "type": "bono_cer", "allocation_pct": 90, "amount_ars": 270000},
        {"instrument_id": "fci_money_market","type": "fci_mm","allocation_pct": 10, "amount_ars": 30000},
    ]
    rec = _make_rec(alloc)
    errors = validate_allocation(rec, CAPITAL, "moderado", MACRO_INF_3_4)
    # Sin MEP y FCI MM al 10% → debe detectar que falta liquidez (regla: ≥15% sin MEP)
    assert any("Sin MEP" in e for e in errors)


def test_no_mep_fci_15_pass():
    alloc = [
        {"instrument_id": "tx26", "type": "bono_cer",        "allocation_pct": 40, "amount_ars": 120000},
        {"instrument_id": "gd28", "type": "bono_hard_dollar", "allocation_pct": 15, "amount_ars": 45000},
        {"instrument_id": "fci_money_market","type": "fci_mm","allocation_pct": 45, "amount_ars": 135000},
    ]
    rec = _make_rec(alloc, usd_breakdown={"dolar_liquido_pct":0,"renta_soberana_usd_pct":15,"renta_corporativa_usd_pct":0,"equity_dolarizado_pct":0})
    errors = validate_allocation(rec, CAPITAL, "moderado", MACRO_INF_3_4)
    assert not any("Sin MEP" in e for e in errors)


# ─── 7. USD exposure matches breakdown ────────────────────────────────────────
def test_usd_exposure_matches_breakdown_fail():
    alloc = [
        {"instrument_id": "tx26",             "type": "bono_cer",       "allocation_pct": 45, "amount_ars": 135000},
        {"instrument_id": "pamp3",            "type": "on_usd",          "allocation_pct": 15, "amount_ars": 45000},
        {"instrument_id": "fci_money_market", "type": "fci_mm",          "allocation_pct": 40, "amount_ars": 120000},
    ]
    rec = _make_rec(alloc, usd_exposure_pct=40,
                    usd_breakdown={"dolar_liquido_pct":0,"renta_soberana_usd_pct":0,"renta_corporativa_usd_pct":10,"equity_dolarizado_pct":0})
    errors = validate_allocation(rec, CAPITAL, "moderado", MACRO_INF_3_4)
    assert any("breakdown" in e for e in errors)


# ─── 8. FCI MM no cuenta como cobertura inflacionaria ────────────────────────
def test_money_market_not_counted_as_inflation_coverage():
    alloc = [
        {"instrument_id": "tx26",             "type": "bono_cer",  "allocation_pct": 35, "amount_ars": 105000},
        {"instrument_id": "fci_money_market", "type": "fci_mm",    "allocation_pct": 65, "amount_ars": 195000},
    ]
    rec = _make_rec(alloc, inf_cov=100)  # Claude declara 100% de cobertura inflacionaria (incorrecto)
    errors = validate_allocation(rec, CAPITAL, "moderado", MACRO_INF_3_4)
    assert any("inflation_coverage_pct" in e or "FCI MM" in e for e in errors)


# ─── 9. Triggers solo referencian instrumentos presentes ─────────────────────
def test_no_mep_trigger_when_mep_is_zero():
    alloc = [
        {"instrument_id": "tx26",             "type": "bono_cer",  "allocation_pct": 50, "amount_ars": 150000},
        {"instrument_id": "fci_money_market", "type": "fci_mm",    "allocation_pct": 50, "amount_ars": 150000},
    ]
    rec = _make_rec(alloc, triggers=["Reducir MEP si el tipo de cambio oficial sube 10%"])
    errors = validate_allocation(rec, CAPITAL, "moderado", MACRO_INF_3_4)
    assert any("MEP" in e and "no está en la cartera" in e for e in errors)


def test_trigger_mep_ok_when_mep_present():
    alloc = [
        {"instrument_id": "tx26",             "type": "bono_cer",    "allocation_pct": 35, "amount_ars": 105000},
        {"instrument_id": "dolar_mep",        "type": "dolar_mep",   "allocation_pct": 30, "amount_ars": 90000},
        {"instrument_id": "fci_money_market", "type": "fci_mm",      "allocation_pct": 35, "amount_ars": 105000},
    ]
    rec = _make_rec(alloc, triggers=["Reducir MEP si tipo de cambio sube 10%"],
                    usd_breakdown={"dolar_liquido_pct":30,"renta_soberana_usd_pct":0,"renta_corporativa_usd_pct":0,"equity_dolarizado_pct":0})
    errors = validate_allocation(rec, CAPITAL, "moderado", MACRO_INF_3_4)
    assert not any("MEP" in e and "no está en la cartera" in e for e in errors)


# ─── 10. recalculate_fields corrige inflation_coverage_pct ───────────────────
def test_recalculate_fields_fixes_inflation_coverage():
    alloc = [
        {"instrument_id": "tx26",             "type": "bono_cer",  "allocation_pct": 40, "amount_ars": 120000},
        {"instrument_id": "fci_money_market", "type": "fci_mm",    "allocation_pct": 60, "amount_ars": 180000},
    ]
    rec = {
        "allocation": alloc,
        "inflation_coverage_pct": 100,  # declarado mal por Claude
        "usd_exposure_pct": 0,
        "usd_exposure_breakdown": {"dolar_liquido_pct":0,"renta_soberana_usd_pct":0,"renta_corporativa_usd_pct":0,"equity_dolarizado_pct":0},
        "rebalance_triggers": [],
    }
    fixed = recalculate_fields(rec)
    assert fixed["inflation_coverage_pct"] == 40.0
