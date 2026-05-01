import yfinance as yf
import json
from datetime import datetime


def get_stock_data(ticker: str) -> dict:
    """
    Trae todos los datos de un ticker que necesitan los sub-agentes.
    Devuelve un diccionario estructurado con precio, fundamentals e historial.
    """
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        history = stock.history(period="6mo")

        # --- Datos de precio actual ---
        price_data = {
            "ticker": ticker,
            "current_price": info.get("currentPrice") or info.get("regularMarketPrice"),
            "currency": info.get("currency", "USD"),
            "market_cap": info.get("marketCap"),
            "avg_volume": info.get("averageVolume"),
            "fetched_at": datetime.now().isoformat()
        }

        # --- Datos fundamentales ---
        fundamental_data = {
            "pe_ratio": info.get("trailingPE"),
            "forward_pe": info.get("forwardPE"),
            "eps": info.get("trailingEps"),
            "revenue_growth": info.get("revenueGrowth"),
            "earnings_growth": info.get("earningsGrowth"),
            "debt_to_equity": info.get("debtToEquity"),
            "current_ratio": info.get("currentRatio"),
            "profit_margin": info.get("profitMargins"),
            "return_on_equity": info.get("returnOnEquity"),
            "free_cashflow": info.get("freeCashflow"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "company_name": info.get("longName"),
            "description": info.get("longBusinessSummary", "")[:500]
        }

        # --- Datos técnicos (últimos 6 meses) ---
        if not history.empty:
            closes = history["Close"].tolist()
            volumes = history["Volume"].tolist()

            ma_200 = _moving_average(closes, 200)
            ma_50  = _moving_average(closes, 50)
            ma_20  = _moving_average(closes, 20)
            rsi    = _calculate_rsi(closes)

            technical_data = {
                "price_history_6mo": closes[-30:],
                "volume_history_6mo": volumes[-30:],
                "ma_20":  round(ma_20,  2) if ma_20  else None,
                "ma_50":  round(ma_50,  2) if ma_50  else None,
                "ma_200": round(ma_200, 2) if ma_200 else None,
                "rsi_14": round(rsi, 2)    if rsi    else None,
                "52w_high": info.get("fiftyTwoWeekHigh"),
                "52w_low":  info.get("fiftyTwoWeekLow"),
                "price_vs_52w_high_pct": _pct_diff(
                    price_data["current_price"],
                    info.get("fiftyTwoWeekHigh")
                )
            }
        else:
            technical_data = {}

        return {
            "status": "ok",
            "price": price_data,
            "fundamental": fundamental_data,
            "technical": technical_data
        }

    except Exception as e:
        return {"status": "error", "message": str(e), "ticker": ticker}


# --- Helpers ---

def _moving_average(closes: list, period: int):
    if len(closes) < period:
        return None
    return sum(closes[-period:]) / period


def _calculate_rsi(closes: list, period: int = 14):
    if len(closes) < period + 1:
        return None
    deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
    gains  = [d for d in deltas[-period:] if d > 0]
    losses = [-d for d in deltas[-period:] if d < 0]
    avg_gain = sum(gains) / period if gains else 0
    avg_loss = sum(losses) / period if losses else 0
    if avg_loss == 0:
        return 100
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def _pct_diff(current, reference):
    if not current or not reference:
        return None
    return round(((current - reference) / reference) * 100, 2)


# --- Test rápido ---
if __name__ == "__main__":
    data = get_stock_data("AAPL")
    print(json.dumps(data, indent=2, default=str))