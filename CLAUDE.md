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
python3 portfolio.py --capital 5000 --use-cache  # ídem usando análisis ya guardados
python3 analyze_portfolio.py                  # analizar portafolio propio (my_portfolio.json)
python3 analyze_portfolio.py --use-cache      # ídem usando análisis cacheados
python3 invest_ars.py --capital 500000 --riesgo moderado  # recomendación en ARS
python3 invest_ars.py --capital 1000000 --riesgo bajo     # perfil conservador
python3 invest_ars.py --capital 200000 --riesgo alto      # perfil agresivo
```

## Arquitectura — flujo completo

### Flujo acciones americanas
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

### Flujo portafolio propio (bonos argentinos + acciones)
```
          my_portfolio.json
               │
               ▼
     analyze_portfolio.py
          │           │
          ▼           ▼
  acciones/ETFs    bonos argentinos
  (pipeline        (data/argentina.py
   existente)       + argentinadatos.com)
          │           │
          ▼           ▼
  agents/position_   agents/bond_
  analyzer.py        analyzer.py
          │           │
          └─────┬─────┘
                ▼
         CEO portfolio
         (síntesis final)
                │
                ▼
  storage/portfolio_analysis_{fecha}.json
```

### Flujo recomendación en ARS (Paso 3)
```
  invest_ars.py --capital X --riesgo [bajo|moderado|alto]
          │
          ├── data/argentina.py          ← macro en tiempo real
          │   (argentinadatos.com)         inflación, UVA, dólar oficial
          │
          ├── data/instruments_ar.py     ← universo de instrumentos
          │   (estático + macro)           bonos CER, PF UVA, MEP, FCI, CEDEARs
          │
          └── agents/ars_advisor.py      ← Claude genera la distribución
              (Claude API)                 adaptada al perfil de riesgo
                    │
                    ▼
          Tabla de asignación + instrucciones
          de ejecución en Bull Market
                    │
                    ▼
          storage/inversion_ars_{fecha}.json
```

## Archivos — descripción detallada

### `data/fetcher.py`
Punto de entrada para obtener todos los datos de un ticker de acciones.
**Optimización clave:** llama a `yf.Ticker(ticker)` una sola vez al inicio y reutiliza
`yf_info` e `yf_history` en todas las funciones internas (antes se llamaba 2-3 veces).
Orquesta las fuentes con fallback automático:
- **Fundamental**: Alpha Vantage OVERVIEW → Finnhub metrics → yfinance (cache)
- **Técnico**: Polygon.io aggs + SMA/RSI → yfinance (cache)
- **Indicadores**: yfinance (cache, necesita serie completa para MACD/Bollinger)
- **Noticias**: Finnhub News API (últimos 7 días, hasta 10 artículos)

Devuelve un dict unificado con claves: `price`, `fundamental`, `technical`, `news`.

### `data/argentina.py`
Fuente de datos para el mercado argentino. Sin API key requerida.
- `get_bond_data(ticker, price_override)` — metadata del bono (vencimiento, cupón, CER) + macro
- `get_macro_data()` — trae de **argentinadatos.com**:
  - Inflación mensual IPC (último dato: 3.4% en marzo 2026)
  - Inflación interanual (32.6%)
  - UVA diaria
  - Dólar oficial (compra/venta)
- `BOND_REGISTRY` — dict estático con metadata de bonos conocidos: TX26, TX28, TX30, DICP, CUAP
- **Precio del bono**: NO hay API pública gratuita para precios de bonos argentinos.
  yfinance no tiene TX26.BA, IOL/BYMA requieren auth, Rava no responde.
  → El usuario debe ingresar `current_price_override` en `my_portfolio.json`
  (el precio se ve en Bull Market > Cotizaciones).

### `data/alpha_vantage.py`
Fuente primaria para datos fundamentales de acciones americanas.
Endpoint: `OVERVIEW` de Alpha Vantage.
Trae: P/E, EPS, crecimiento ingresos/ganancias, márgenes, ROE, beta,
analyst target price, dividend yield, 52w high/low.
**Límite free tier:** 25 req/día, 5 req/min.
Retorna `{"status": "rate_limited"}` si se supera el límite (cae a Finnhub).

### `data/polygon.py`
Fuente primaria para datos técnicos de acciones americanas.
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

### `agents/position_analyzer.py`
Sub-agente que analiza una posición existente en acciones americanas.
Recibe: detalles de la posición (ticker, shares, avg_buy_price) + análisis del activo.
Calcula P&L, distancia al stop loss y take profit.
Recomienda: hold, sell, add, reduce, stop_loss_triggered.
Devuelve JSON con: `action`, `urgency`, `rationale`, `key_alert`, P&L calculado.

### `data/instruments_ar.py`
Universo de instrumentos de inversión en ARS disponibles en Bull Market Brokers.
Función principal: `get_instruments_universe(macro)` — devuelve lista de instrumentos con
características actualizadas al contexto macro del momento.
Instrumentos incluidos:
- **Bonos CER**: TX26, TX28, TX30, DICP, CUAP — con días a vencimiento calculados dinámicamente
- **Plazo fijo UVA**: cobertura CER, mínimo 90 días, garantizado SEDESA hasta $6M
- **Plazo fijo tradicional**: tasa fija TNA — marcado como ineficiente si inflación lo supera
- **Dólar MEP**: vía AL30/GD30, parking 24hs obligatorio, cobertura cambiaria total
- **FCI Money Market**: liquidez inmediata, ~TNA mercado, rescate 24hs
- **CEDEARs**: acciones extranjeras en ARS, referenciadas a USD implícito

Cada instrumento incluye: `return_estimate`, `liquidity`, `risk_level`, `recommended_for`,
`how_to_buy` (instrucciones exactas en Bull Market), `sovereign_risk`, `bank_risk`.
TNA plazo fijo: intenta traer de `argentinadatos.com/v1/finanzas/tasas/depositos`;
si falla, usa `TNA_PF_FALLBACK = 32.0%`.

### `agents/ars_advisor.py`
Agente Claude especializado en inversiones en pesos argentinos.
Recibe: capital, perfil de riesgo (bajo/moderado/alto), universo de instrumentos, macro.
Aplica reglas por perfil:
- **Bajo**: PF UVA + FCI. Sin CEDEARs. Máx 20% bonos CER.
- **Moderado**: 30-50% CER/UVA + 20-30% MEP + 10-20% CEDEARs + 10% FCI.
- **Alto**: 30-40% CEDEARs + 20-30% MEP + 20% CER + 10% FCI.
Descarta automáticamente PF tradicional si inflación mensual supera la TNA.
Devuelve JSON con: `allocation[]` (instrument_id, %, amount_ars, rationale, how_to_buy),
`inflation_coverage_pct`, `usd_exposure_pct`, `strategy_summary`, `main_risk`, `time_horizon`.

### `agents/bond_analyzer.py`
Sub-agente especializado en **renta fija argentina** (bonos CER/UVA).
Analiza posiciones en bonos soberanos como TX26, TX28, TX30, DICP.
Considera: precio sucio vs limpio, ajuste CER devengado, TIR real estimada,
paridad vs valor técnico, comparación vs plazo fijo UVA y dolarización MEP,
riesgo soberano argentino, tiempo a vencimiento.
Requiere que el precio se ingrese manualmente vía `current_price_override`.
Devuelve JSON con: `action`, `urgency`, `real_yield_estimate`, `paridad_assessment`,
`vs_alternatives`, `sovereign_risk_note`, `rationale`, `key_alert`.

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
Script para analizar el **universo completo** (18 tickers) y construir portafolio óptimo.
Flags: `--capital XXXX` (requerido), `--use-cache` (usa storage sin re-analizar).
Flujo: analiza → filtra BUY con score ≥ 6 → allocator distribuye capital → email.

### `analyze_portfolio.py`
Script para analizar el **portafolio propio** del usuario (lo que ya tiene comprado).
Lee `my_portfolio.json` y detecta automáticamente el tipo de activo:
- **Acciones americanas**: usa el pipeline existente (fetcher + 4 agentes)
- **Bonos argentinos**: detecta por `asset_type` o si el ticker está en `BOND_REGISTRY`

Flags: `--portfolio my_portfolio.json` (default), `--use-cache`.
Genera: análisis por posición + síntesis CEO del portafolio completo.
Guarda en `storage/portfolio_analysis_{fecha}.json`.

### `my_portfolio.json`
Archivo que el usuario completa con sus posiciones reales. Campos por posición:
- `ticker` — símbolo del activo (AAPL, TX26, etc.)
- `asset_type` — `"bono_argentino"` para bonos; omitir para acciones
- `shares` — cantidad de acciones/títulos
- `avg_buy_price` — precio promedio de compra
- `currency` — `"USD"` o `"ARS"`
- `current_price_override` — **obligatorio para bonos argentinos** (precio actual desde Bull Market)
- `notes` — notas opcionales

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

### `invest_ars.py`
Script principal para recomendación de inversión en pesos argentinos.
```bash
python3 invest_ars.py --capital 500000 --riesgo moderado
```
Flujo:
1. Trae macro en tiempo real (argentinadatos.com): inflación, UVA, dólar
2. Construye universo de instrumentos (data/instruments_ar.py)
3. Filtra los compatibles con el perfil de riesgo pedido
4. Llama a agents/ars_advisor.py para generar la distribución óptima
5. Imprime tabla de asignación + instrucciones paso a paso en Bull Market
6. Guarda en `storage/inversion_ars_{fecha}.json`

Argumentos: `--capital` (requerido, en ARS), `--riesgo` (bajo/moderado/alto, default: moderado).

### `storage/`
JSONs de cada análisis completo.
- `{TICKER}_analysis.json` — análisis de acciones (16 tickers; faltan WMT y HD)
- `portfolio_{fecha}.json` — portafolio óptimo generado por `portfolio.py`
- `portfolio_analysis_{fecha}.json` — análisis del portafolio propio (`analyze_portfolio.py`)
- `inversion_ars_{fecha}.json` — recomendación en ARS generada por `invest_ars.py`

## Variables de entorno (`.env`)
```
ANTHROPIC_API_KEY   — Claude API
ALPHA_VANTAGE_KEY   — fundamentals acciones (25 req/día free)
FINNHUB_KEY         — fundamentals fallback + noticias (60 req/min free)
POLYGON_KEY         — técnico acciones (5 req/min free, delay 15min)
EMAIL_USER          — Gmail address
EMAIL_PASSWORD      — Gmail app password
```
**Sin key requerida:** `data/argentina.py` usa argentinadatos.com (API pública).

## Performance
- **1 ticker acción**: ~55 segundos (datos + 4 agentes paralelos + CEO + email)
- **Watchlist (4 tickers)**: ~4-5 minutos
- **Universo completo (18 tickers)**: ~20 minutos frescos / ~15 segundos con `--use-cache`
- **Portafolio propio (bonos)**: ~15 segundos (sin re-análisis de mercado)
- **Recomendación ARS (`invest_ars.py`)**: ~20 segundos (macro + Claude advisor)
- Mejora clave: agentes en paralelo + yfinance cacheado = ~40% más rápido que versión original

## Stack
Python 3.12 · anthropic · yfinance · requests · python-dotenv · smtplib · concurrent.futures

## Roadmap — estado actual

| Paso | Feature | Estado |
|------|---------|--------|
| 1 | CEDEARs + tipo de cambio | ⏳ pendiente |
| 2 | Ingesta manual de portafolio | ✅ done (`my_portfolio.json` + `analyze_portfolio.py`) |
| 3 | Análisis de posiciones existentes | ✅ done (`agents/position_analyzer.py` + `agents/bond_analyzer.py`) |
| 3b | Recomendación "invertir $X ARS" | ✅ done (`invest_ars.py`) |
| 4 | Integración broker API (Bull Market / IOL) | ⏳ pendiente — bajo prioridad |
| 5 | Perfil de riesgo dinámico por usuario | ⏳ pendiente |

## Próximos pasos
1. **CEDEARs** — análisis de los subyacentes americanos aplicado a CEDEARs (precio en ARS, ratio de conversión, dólar implícito)
2. **Precio automático de bonos** — explorar IOL API (tiene auth) o BYMA con cuenta
3. **Automatización con cron** — correr `invest_ars.py` y `portfolio.py` diariamente
4. **Paper trading** — registrar predicciones en DB y validar rentabilidad histórica
