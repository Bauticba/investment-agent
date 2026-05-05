# Investment Agent — Contexto del proyecto

## Qué es esto
Sistema multi-agente de análisis bursátil construido en Python.
Cada agente usa la Claude API (claude-sonnet-4-6) como cerebro.
El objetivo es generar tesis de inversión personalizadas para Bautista
basadas en datos reales de múltiples fuentes.

## Cómo correr
```bash
source venv/bin/activate
python3 ceo/orchestrator.py AAPL              # analizar un ticker + email
python3 run_watchlist.py                      # watchlist (AAPL, MSFT, NVDA, GOOGL)
python3 run_watchlist.py AAPL MSFT            # tickers custom
python3 portfolio.py --capital 5000           # universo completo + construir portafolio
python3 portfolio.py --capital 5000 --use-cache  # ídem pero usando análisis ya guardados
```

## Arquitectura — flujo completo
```
                    ┌─────────────────────────┐
                    │      data/fetcher.py     │  ← orquesta las 3 fuentes
                    │  AV → Finnhub → yfinance │  (yfinance: 1 sola llamada cacheada)
                    └────────────┬────────────┘
                                 │ stock_data dict
           ┌─────────────────────┼─────────────────────┐
           ▼                     ▼                     ▼                     ▼
  agents/fundamental   agents/technical    agents/indicators    agents/sentiment
   (Alpha Vantage)      (Polygon.io)         (yfinance)        (Finnhub News)
           │                     │                     │                     │
           └──────────── corren en PARALELO ───────────────────────────────┘
                                 │ 4 reportes JSON con score/10
                                 ▼
                        ceo/orchestrator.py
                          tesis final CEO
                                 │
              ┌──────────────────┼──────────────────┐
              ▼                  ▼                  ▼
    storage/{TICKER}        email HTML         portfolio.py
    _analysis.json                           (si se usa)
                                                   │
                                        agents/allocator.py
                                        distribuye capital
                                                   │
                                    storage/portfolio_{fecha}.json
                                         + email portafolio
```

## Archivos — descripción detallada

### `data/fetcher.py`
Punto de entrada para obtener todos los datos de un ticker.
**Optimización clave:** llama a `yf.Ticker(ticker)` una sola vez al inicio y reutiliza
`yf_info` e `yf_history` en todas las funciones internas (antes se llamaba 2-3 veces).
Orquesta las fuentes con fallback automático:
- **Fundamental**: Alpha Vantage OVERVIEW → Finnhub metrics → yfinance (cache)
- **Técnico**: Polygon.io aggs + SMA/RSI → yfinance (cache)
- **Indicadores**: yfinance (cache, necesita serie completa para MACD/Bollinger)
- **Noticias**: Finnhub News API (últimos 7 días, hasta 10 artículos)

Devuelve un dict unificado con claves: `price`, `fundamental`, `technical`, `news`.

### `data/alpha_vantage.py`
Fuente primaria para datos fundamentales.
Endpoint: `OVERVIEW` de Alpha Vantage.
Trae: P/E, EPS, crecimiento ingresos/ganancias, márgenes, ROE, beta,
analyst target price, dividend yield, 52w high/low.
**Límite free tier:** 25 req/día, 5 req/min.
Retorna `{"status": "rate_limited"}` si se supera el límite (cae a Finnhub).

### `data/polygon.py`
Fuente primaria para datos técnicos.
Usa 5 endpoints de Polygon (límite del free tier: 5 req/min):
1. `/v2/aggs` — OHLCV diario últimos 210 días (precio actual, 52w high/low)
2. `/v1/indicators/sma` × 3 — MA20, MA50, MA200
3. `/v1/indicators/rsi` — RSI 14 períodos
Datos con delay de 15 min en el free tier.
**No incluye MACD** (requeriría un 6to request, superando el límite).
Si falla o rate-limita, cae a yfinance sin demora.

### `data/finnhub.py`
Dos funciones independientes:
- `get_fundamental(ticker)` — fallback si Alpha Vantage falla o rate limit.
  Usa `/stock/metric?metric=all`. Trae P/E, ROE, márgenes, beta, 52w high/low.
- `get_news(ticker, days=7)` — noticias reales para el agente de sentimiento.
  Devuelve lista de hasta 10 artículos con headline, summary, source, date.
**Límite free tier:** 60 req/min.

### `agents/fundamental.py`
Sub-agente que analiza la salud financiera de la empresa.
Recibe los datos fundamentales y los compara contra las reglas del perfil:
P/E máx 40, crecimiento mínimo 5%, deuda/equity máx 2.0, current ratio mín 1.0.
Devuelve JSON con: `verdict`, `score/10`, `strengths`, `weaknesses`, `flags`, `summary`.

### `agents/technical.py`
Sub-agente que evalúa el momento técnico de entrada.
Analiza tendencia (precio vs MA20/50/200), momentum, soportes y resistencias.
Reglas del perfil que verifica: solo operar sobre MA200, RSI entre 30-75,
confirmación de volumen.
Devuelve JSON con: `verdict`, `score/10`, `trend`, `entry_zone`,
`support_levels`, `resistance_levels`, `flags`.

### `agents/indicators.py`
Sub-agente cuantitativo de indicadores técnicos.
Calcula localmente (sin API extra): MACD (EMA12 - EMA26), Bollinger Bands (20 períodos, 2σ),
tendencia de volumen (últimos 10 vs 20 días).
Claude interpreta los valores calculados.
Devuelve JSON con: `verdict`, `score/10`, `momentum`, interpretaciones de
RSI/MACD/Bollinger/volumen.

### `agents/sentiment.py`
Sub-agente cualitativo. Analiza noticias reales de Finnhub + contexto macro.
Si hay noticias disponibles, evalúa tono mediático, catalizadores emergentes
y riesgos cualitativos. Si no hay noticias, razona por conocimiento general.
Devuelve JSON con: `verdict`, `score/10`, `market_sentiment`, `news_tone`,
`news_summary`, `competitive_position`, `sector_outlook`, `key_risks`, `key_catalysts`.

### `agents/allocator.py`
Agente de construcción de portafolio. Recibe los candidatos aprobados (BUY, score ≥ 6)
y el capital disponible, y genera una distribución óptima.
Reglas que aplica: máx 15% por posición, máx 3 del mismo sector, reserva 5-10% en cash,
prioriza conviction "high" y ceo_score más alto, solo acciones enteras.
Devuelve JSON con: `positions[]` (ticker, shares, amount_usd, allocation_pct, stop_loss,
take_profit, rationale), `cash_reserve`, `total_invested`, `portfolio_thesis`,
`sector_breakdown`, `expected_return`, `main_risk`.

### `ceo/orchestrator.py`
Función principal: `run_analysis(ticker)`.
1. Llama a `data/fetcher.py` para obtener todos los datos
2. Corre los 4 sub-agentes **en paralelo** con `ThreadPoolExecutor(max_workers=4)`
3. Envía los 4 reportes al CEO (Claude) que genera la tesis final
El CEO detecta conflictos entre analistas, aplica el perfil del inversor,
y produce: `final_verdict`, `conviction`, `ceo_score`, `price_target`,
`stop_loss`, `take_profit`, `thesis`, `pros`, `cons`, `action_steps`, `risk_warning`.

### `run_watchlist.py`
Script para analizar todos los tickers de la watchlist (AAPL, MSFT, NVDA, GOOGL).
Espera **12 segundos** entre tickers (respeta rate limit de Alpha Vantage 5 req/min).
Al final imprime tabla resumen con veredicto, score, stop loss y take profit.
Guarda cada análisis en `storage/` y envía email individual por ticker.

### `portfolio.py`
Script principal para analizar el **universo completo** (18 tickers de todos los sectores)
y construir un portafolio óptimo con el capital disponible.

Flags:
- `--capital XXXX` (requerido) — capital a invertir en USD
- `--use-cache` (opcional) — usa los análisis guardados en `storage/` sin re-analizar.
  Acepta cualquier archivo con `status=ok` independientemente de la fecha.
  Omite tickers sin cache en vez de analizarlos (útil cuando se agotan tokens de API).

Flujo:
1. Analiza todos los tickers del universo (o carga del cache con `--use-cache`)
2. Filtra candidatos con `final_verdict == "buy"` y `ceo_score >= 6`
3. Llama a `agents/allocator.py` para distribuir el capital
4. Guarda en `storage/portfolio_{fecha}.json` y envía email

### `notifications/email_sender.py`
Formatea la tesis del CEO en HTML y la envía vía Gmail SMTP (puerto 465, SSL).
El email incluye: veredicto con emoji, score CEO, stop loss/take profit,
pros y contras, pasos a seguir, tabla de scores por agente, advertencia de riesgo.
También envía el email del portafolio completo cuando se usa `portfolio.py`.
Credenciales en `.env`: `EMAIL_USER` y `EMAIL_PASSWORD` (app password de Gmail).

### `instructions/investor_profile.json`
Define las reglas y preferencias de Bautista:
- Riesgo: moderado | stop loss 8% | take profit 20% | máx 15% por posición
- Reglas fundamentales: P/E máx 40, crecimiento mínimo 5%, deuda/equity máx 2.0
- Reglas técnicas: solo sobre MA200, RSI entre 30-75, confirmar volumen
- Watchlist corta: AAPL, MSFT, NVDA, GOOGL
- Universo completo: 18 tickers en 5 sectores (technology, healthcare, finance, energy, consumer)
- Sectores prohibidos: gambling, tobacco, weapons

### `storage/`
JSONs de cada análisis completo (precio, reportes de los 4 agentes, tesis CEO).
Nombrados como `{TICKER}_analysis.json` y `portfolio_{fecha}.json`.
Actualmente hay análisis guardados de: AAPL, MSFT, NVDA, GOOGL, META, AMZN, TSLA,
JNJ, UNH, ABBV, JPM, V, MA, XOM, CVX, COST (16 tickers — faltan WMT y HD).

## Variables de entorno (`.env`)
```
ANTHROPIC_API_KEY   — Claude API
ALPHA_VANTAGE_KEY   — fundamentals (25 req/día free)
FINNHUB_KEY         — fundamentals fallback + noticias (60 req/min free)
POLYGON_KEY         — técnico (5 req/min free, delay 15min)
EMAIL_USER          — Gmail address
EMAIL_PASSWORD      — Gmail app password
```

## Performance
- **1 ticker**: ~55 segundos (datos + 4 agentes paralelos + CEO + email)
- **Watchlist (4 tickers)**: ~4-5 minutos
- **Universo completo (18 tickers)**: ~20 minutos (análisis frescos) / ~15 segundos (con `--use-cache`)
- Mejora clave implementada: agentes en paralelo + yfinance cacheado = ~40% más rápido que versión original

## Stack
Python 3.12 · anthropic · yfinance · requests · python-dotenv · smtplib · concurrent.futures

## Próximos pasos
1. Paper trading — registrar predicciones en DB y validar rentabilidad histórica
2. Automatización con cron — correr `portfolio.py` diariamente al cierre del mercado
3. Agente de macro — contexto de tasas, inflación, VIX para el CEO
4. Completar universo — agregar WMT y HD al storage (faltan análisis)
5. Ajustar umbral de aprobación — actualmente score ≥ 6 + BUY; con mercado en HOLD generalizado puede quedar poco candidatos
