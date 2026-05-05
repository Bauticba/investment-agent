import yfinance as yf
import json
from datetime import datetime
from dotenv import load_dotenv

from data.alpha_vantage import get_fundamental as av_fundamental
from data.finnhub import get_fundamental as fh_fundamental, get_news as fh_news
from data.polygon import get_technical as poly_technical

load_dotenv(override=True)


def get_stock_data(ticker: str) -> dict:
    try:
        # --- Fundamental: Alpha Vantage → Finnhub → yfinance ---
        fundamental_data, fundamental_source = _get_fundamental(ticker)

        # --- Technical: Polygon → yfinance ---
        technical_data, technical_source = _get_technical(ticker)

        # Si Polygon no trajo la serie de precios, la completamos con yfinance
        if not technical_data.get("price_history_6mo"):
            indicators_data = _get_yf_indicators(ticker)
            technical_data.update(indicators_data)

        # --- Noticias: Finnhub News API ---
        news = fh_news(ticker, days=7)

        # --- Precio: Polygon si disponible, si no yfinance ---
        price_data = _build_price(ticker, technical_data, fundamental_data)

        print(f"   Fuentes: fundamental={fundamental_source} | técnico={technical_source} | noticias={len(news)} artículos")

        return {
            "status":      "ok",
            "price":       price_data,
            "fundamental": fundamental_data,
            "technical":   technical_data,
            "news":        news,
        }

    except Exception as e:
        return {"status": "error", "message": str(e), "ticker": ticker}


# --- Fundamental ---

def _get_fundamental(ticker: str) -> tuple[dict, str]:
    result = av_fundamental(ticker)
    if result.get("status") == "ok":
        return result, "alpha_vantage"

    result = fh_fundamental(ticker)
    if result.get("status") == "ok":
        return result, "finnhub"

    return _yf_fundamental(ticker), "yfinance"


def _yf_fundamental(ticker: str) -> dict:
    info = yf.Ticker(ticker).info
    return {
        "status":          "ok",
        "company_name":    info.get("longName"),
        "sector":          info.get("sector"),
        "industry":        info.get("industry"),
        "description":     info.get("longBusinessSummary", "")[:500],
        "pe_ratio":        info.get("trailingPE"),
        "forward_pe":      info.get("forwardPE"),
        "eps":             info.get("trailingEps"),
        "revenue_growth":  info.get("revenueGrowth"),
        "earnings_growth": info.get("earningsGrowth"),
        "profit_margin":   info.get("profitMargins"),
        "return_on_equity":info.get("returnOnEquity"),
        "debt_to_equity":  info.get("debtToEquity"),
        "current_ratio":   info.get("currentRatio"),
        "free_cashflow":   info.get("freeCashflow"),
        "dividend_yield":  info.get("dividendYield"),
        "beta":            info.get("beta"),
        "analyst_target":  info.get("targetMeanPrice"),
        "52w_high":        info.get("fiftyTwoWeekHigh"),
        "52w_low":         info.get("fiftyTwoWeekLow"),
    }


# --- Technical ---

def _get_technical(ticker: str) -> tuple[dict, str]:
    result = poly_technical(ticker)
    if result.get("status") == "ok":
        return result, "polygon"

    return _yf_technical(ticker), "yfinance"


def _yf_technical(ticker: str) -> dict:
    stock   = yf.Ticker(ticker)
    info    = stock.info
    history = stock.history(period="6mo")

    if history.empty:
        return {}

    closes  = history["Close"].tolist()
    volumes = history["Volume"].tolist()

    return {
        "status":               "ok",
        "price_history_6mo":    closes[-30:],
        "volume_history_6mo":   volumes[-30:],
        "ma_20":                _ma(closes, 20),
        "ma_50":                _ma(closes, 50),
        "ma_200":               _ma(closes, 200),
        "rsi_14":               _rsi(closes),
        "macd":                 None,
        "52w_high":             info.get("fiftyTwoWeekHigh"),
        "52w_low":              info.get("fiftyTwoWeekLow"),
        "price_vs_52w_high_pct": _pct(
            info.get("currentPrice") or info.get("regularMarketPrice"),
            info.get("fiftyTwoWeekHigh"),
        ),
        "current_price":        info.get("currentPrice") or info.get("regularMarketPrice"),
    }


# --- Indicadores (siempre yfinance — necesitamos serie para MACD/Bollinger) ---

def _get_yf_indicators(ticker: str) -> dict:
    history = yf.Ticker(ticker).history(period="6mo")
    if history.empty:
        return {}
    closes  = history["Close"].tolist()
    volumes = history["Volume"].tolist()
    return {
        "price_history_6mo":  closes[-30:],
        "volume_history_6mo": volumes[-30:],
        "rsi_14":             _rsi(closes),
    }


# --- Precio unificado ---

def _build_price(ticker: str, technical: dict, fundamental: dict) -> dict:
    current_price = technical.get("current_price")

    if not current_price:
        info = yf.Ticker(ticker).info
        current_price = info.get("currentPrice") or info.get("regularMarketPrice")
        market_cap    = info.get("marketCap")
        avg_volume    = info.get("averageVolume")
    else:
        stock      = yf.Ticker(ticker).info
        market_cap = stock.get("marketCap")
        avg_volume = stock.get("averageVolume")

    return {
        "ticker":        ticker,
        "current_price": current_price,
        "currency":      "USD",
        "market_cap":    market_cap,
        "avg_volume":    avg_volume,
        "fetched_at":    datetime.now().isoformat(),
    }


# --- Helpers de cálculo ---

def _ma(closes: list, period: int) -> float | None:
    if len(closes) < period:
        return None
    return round(sum(closes[-period:]) / period, 2)


def _rsi(closes: list, period: int = 14) -> float | None:
    if len(closes) < period + 1:
        return None
    deltas    = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains     = [d for d in deltas[-period:] if d > 0]
    losses    = [-d for d in deltas[-period:] if d < 0]
    avg_gain  = sum(gains) / period if gains else 0
    avg_loss  = sum(losses) / period if losses else 0
    if avg_loss == 0:
        return 100.0
    return round(100 - (100 / (1 + avg_gain / avg_loss)), 2)


def _pct(current, reference) -> float | None:
    if not current or not reference:
        return None
    return round(((current - reference) / reference) * 100, 2)


# --- Test rápido ---
if __name__ == "__main__":
    import sys
    ticker = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    data = get_stock_data(ticker)
    print(json.dumps(data, indent=2, default=str))
