# Investment Agent — Contexto del proyecto

## Qué es esto
Sistema multi-agente de análisis bursátil construido en Python.
Cada agente usa la Claude API (claude-sonnet-4-6) como cerebro.
El objetivo es generar tesis de inversión personalizadas para el usuario
basadas en datos reales de múltiples fuentes.

## Cómo correr

### Interfaz web (recomendado)
```bash
source venv/bin/activate
streamlit run app.py                          # abre http://localhost:8501
```

### CLI unificado (main.py)
```bash
source venv/bin/activate
python3 main.py watchlist                               # AAPL, MSFT, NVDA, GOOGL
python3 main.py watchlist AAPL TSLA META               # tickers custom
python3 main.py portafolio --capital 5000              # universo completo + portafolio
python3 main.py portafolio --capital 5000 --cache      # ídem con análisis cacheados
python3 main.py mi-portafolio                          # analizar my_portfolio.json
python3 main.py mi-portafolio --cache                  # ídem con cache
python3 main.py invertir --capital 500000 --riesgo moderado
python3 main.py invertir --capital 200000 --riesgo alto
```

### Scripts individuales (backward compatible)
```bash
python3 run_watchlist.py                      # watchlist directa
python3 portfolio.py --capital 5000 --use-cache
python3 analyze_portfolio.py --use-cache
python3 invest_ars.py --capital 500000 --riesgo moderado
python3 ceo/orchestrator.py AAPL              # analizar un solo ticker
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

### Flujo portafolio propio (bonos + CEDEARs + ONs + FCIs + acciones)
```
          my_portfolio.json
               │
               ▼
     analyze_portfolio.py  ← detecta tipo via _is_arg_bond / _is_cedear /
          │    │   │   │      _is_on / _is_fci (orden de prioridad)
          ▼    ▼   ▼   ▼
  acciones bonos  ONs  CEDEARs  FCIs
  (USA)    AR     USD           (IOL*)
          │    │   │   │         │
          ▼    ▼   ▼   ▼         ▼
  position bond_ on_  cedear_  fci_
  _analyzer analyzer analyzer analyzer
          │    │   │   │         │
          └────┴───┴───┴─────────┘
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
          ├── data/news_ar.py            ← noticias en tiempo real
          │   (Google News RSS + Ámbito)   titulares económicos/financieros AR
          │
          ├── data/instruments_ar.py     ← universo de instrumentos
          │   (estático + macro)           bonos CER, PF UVA, MEP, FCI, CEDEARs
          │
          └── agents/ars_advisor.py      ← Claude genera la distribución
              (Claude API)                 adaptada al perfil de riesgo + noticias del día
                    │
                    ▼
          Tabla de asignación + instrucciones
          de ejecución en IOL (Invertir Online)
                    │
                    ▼
          storage/inversion_ars_{fecha}.json  ← incluye campo "news"
```

## Archivos — descripción detallada

### `main.py`
Punto de entrada unificado con subcomandos argparse. Importa y llama las funciones
exportadas de cada script (`run_watchlist`, `run_portfolio`, `run_portfolio_analysis`, `run_ars`).
No contiene lógica de negocio propia — solo routing de CLI.

### `app.py` + `pages/`
Interfaz web Streamlit. Arrancar con `streamlit run app.py`.
- **app.py** — home: macro en tiempo real (cache 30 min) + tabla de análisis guardados en `storage/`
- **pages/1_Watchlist.py** — selección de tickers, análisis con barra de progreso, tabla resumen
- **pages/2_Portafolio_USD.py** — capital + checkbox cache, screening completo + allocator
- **pages/3_Mi_Portafolio.py** — botón "Sincronizar desde IOL" (trae posiciones reales con tipo detectado automáticamente) + expander de saldo manual (IOL no expone /cuenta/saldo vía API) + análisis acciones/bonos/ONs/CEDEARs/FCIs + síntesis CEO
- **pages/4_Invertir_ARS.py** — capital ARS + perfil riesgo + checkbox "⚡ Modo rápido" (skip MERVAL en vivo) + portfolio risk score (0–100, Bajo/Moderado/Alto) + picks de CEDEARs y MERVAL
- **pages/5_Paper_Trading.py** — performance de señales históricas: win rate, P&L promedio, tabla filtrable por veredicto/fecha/estado, bar chart P&L por ticker, historial de ejecuciones por fecha
- **pages/6_Perfil.py** — edición del perfil de inversión desde la UI: nivel de riesgo, stop/take profit, reglas fundamentales y técnicas, watchlist. Botón de restaurar defaults incluido.

Todos los formularios tienen checkbox para enviar email y opción de usar cache.
Los análisis largos (>30s) muestran `st.spinner` y barra de progreso en tiempo real.

### `core/cache.py`
Helper compartido `get_analysis_cached(ticker, use_cache)`.
Lógica: si `use_cache=True` y existe `storage/{ticker}_analysis.json` con `status=ok`, lo devuelve.
Si `use_cache=True` pero no existe el archivo, devuelve `{"status": "skipped"}` (no re-analiza).
Si `use_cache=False`, llama a `run_analysis(ticker)` y guarda el resultado.

### `core/ttl_cache.py`
Decorador `@ttl_cache(seconds=N)` con TTLs diferenciados por tipo de dato:
- 300s — precios IOL (cambian en el mercado)
- 1800s — macro (inflación, UVA, CCL)
- 3600s — noticias
- 86400s — tasas PF
Incluye lógica stale: si el fetch falla, devuelve el último valor conocido marcado como `stale=True`.

### `core/portfolio_manager.py`
CRUD para `my_portfolio.json` + sincronización desde IOL.
- `get_portfolio()` — lee `my_portfolio.json`, retorna `_DEFAULTS` si no existe
- `save_portfolio(portfolio)` — persiste el dict completo
- `add_position(ticker, shares, avg_price, currency, asset_type, notes)` — agrega o promedia precio
- `sell_position(ticker, shares)` — reduce cantidad; elimina si shares ≥ total
- `remove_position(ticker)` — elimina posición completa
- `update_cash(usd, ars)` — actualiza saldo en efectivo
- `sync_from_iol()` — trae posiciones reales de IOL vía `get_portfolio_iol()`, detecta tipo de activo
  comparando ticker contra CEDEAR_REGISTRY, BOND_REGISTRY, HARD_DOLLAR_BOND_REGISTRY, ON_REGISTRY, MERVAL_STOCKS.
  Tickers que empiezan con `"IOL"` → `asset_type = "fci_mm"` (fondos IOL: IOLCAMA, etc.).
  Para FCIs, persiste `ultimoPrecio` y `valorizado` del endpoint de portafolio en la posición.
  Currency = ARS si `titulo.moneda == "peso_Argentino"` (incluyendo ONs que cotizan en ARS en BYMA).
  Cash preservado del archivo local (IOL no expone saldo vía API).
  Retorna dict con `synced_from_iol=True` y `sync_timestamp`.

### `data/iol.py`
Cliente OAuth2 para la API de Invertir Online (IOL).
- Autenticación: `POST /token` con `grant_type=password` usando `IOL_USERNAME` / `IOL_PASSWORD` del `.env`
- Token cacheado en memoria por 1200s (con 60s de margen de seguridad)
- `get_price(simbolo)` — `GET /api/v2/titulos/{simbolo}/cotizacion?mercado=bCBA`
  Funciona para: acciones MERVAL, CEDEARs, bonos soberanos (TX26, GD30, AL30...), ONs (YMCIO, etc.)
  Retorna: `simbolo`, `ultimo_precio`, `variacion_pct`, `apertura`, `maximo`, `minimo`, `fecha`
- `get_prices_bulk(simbolos)` — llama `get_price` en loop, omite los que fallan
- `get_portfolio_iol()` — `GET /api/v2/portafolio` (endpoint flat, trae todos los mercados).
  Fallback a `/api/v2/portafolio/{bCBA,nYSE}` con deduplicación por símbolo si el flat devuelve vacío.
  Cada activo tiene: `titulo.simbolo`, `titulo.tipo`, `titulo.moneda`, `cantidad`, `ppc` (precio promedio), `ultimoPrecio`, `valorizado`.
- `get_account_balance()` — intenta `/api/v2/cuenta/saldo` y `/api/v2/cuenta/saldos`. Devuelve `{"ARS": float, "USD": float, "available": bool}`. **Nota:** ambos endpoints devuelven 500 para esta cuenta — `available=False` es el resultado esperado. El saldo se ingresa manualmente en la UI.
- `get_profile()` — `GET /api/v2/perfil`. Retorna `username`, `nombre`, `numeroCuenta`, `tieneCuentaUSA`.
- `is_available()` — True si las credenciales IOL están configuradas y el token funciona
**Precios reales:** TX26≈$686 ARS, GD30≈$93000 ARS, AMZN≈$2715 ARS, YMCIO≈$157930 ARS

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

### `data/news_ar.py`
Fetcher de noticias financieras argentinas en tiempo real. Sin API key requerida.
- **Fuentes**: Google News RSS (3 búsquedas temáticas) + Ámbito RSS directo
  - `"dolar+bonos+merval+argentina"` — mercado local
  - `"inflacion+bcra+economia+argentina"` — macro
  - `"fed+reserva+federal+aranceles+trump+mercados"` — geopolítica global
- **Filtrado**: descarta artículos irrelevantes (supermercados, farmacias, deportes, etc.)
- **Deduplicación**: elimina títulos repetidos entre fuentes
- `get_argentina_news(max_articles=15)` — retorna lista de dicts con `source`, `title`, `summary`, `date`
- `format_news_for_prompt(articles)` — formatea para incluir en prompts de Claude
- **Nota**: Cronista, Infobae e iProfesional no tienen RSS público funcional (404/301). Solo Ámbito + Google News.

### `data/argentina.py`
Fuente de datos para el mercado argentino. Sin API key requerida.
- `get_bond_data(ticker, price_override)` — metadata del bono (vencimiento, cupón, CER) + macro.
  **Precio**: override manual > IOL API automático > unavailable.
  IOL provee precios reales de TX26, GD30, AL30, etc. sin necesidad de ingresarlos a mano.
- `get_macro_data()` — trae de **argentinadatos.com**:
  - Inflación mensual IPC
  - Inflación interanual
  - UVA diaria
  - Dólar oficial (compra/venta) — se usa como CCL (mercado unificado desde abr 2025)
- `BOND_REGISTRY` — dict estático con metadata de bonos conocidos: TX26, TX28, TX30, DICP, CUAP

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

### `agents/on_analyzer.py`
Sub-agente especializado en **Obligaciones Negociables (ONs) corporativas USD**.
Analiza posiciones en ONs que cotizan en ARS en BYMA pero se denominan en USD.
Recibe precio en ARS desde IOL, convierte a USD usando CCL para calcular precio vs par (100%) y TIR implícita.
Considera: P&L, tiempo a vencimiento, precio vs par, riesgo corporativo del emisor, comparación vs bonos soberanos y CEDEARs.
Devuelve JSON con: `action`, `urgency`, `price_vs_par`, `estimated_tir_usd`, `days_to_maturity`, `rationale`, `key_alert`, `vs_alternatives`, métricas P&L completas.

### `agents/fci_analyzer.py`
Sub-agente especializado en **FCIs (Fondos Comunes de Inversión)**.
Usa la composición del `FCI_REGISTRY` para estimar el rendimiento efectivo ponderado:
- Cauciones bursátiles (corporativo tasa ramar) → TNA_PF × 0.85
- Soberano CER → inflación mensual × 12 (anualizado)
- Plazo fijo tradicional → TNA_PF
- Liquidez → 0%
Compara el rendimiento estimado vs inflación actual y recomienda hold o switch hacia LECAP/PF UVA.
Si el FCI no está en `FCI_REGISTRY`, `_make_fci_report()` en `analyze_portfolio.py` actúa como fallback básico sin llamada a Claude.
Devuelve JSON con: `action`, `urgency`, `effective_yield_est_tna`, `vs_inflation`, `composition_assessment`, `rationale`, `key_alert`, `vs_alternatives`.

### `data/instruments_ar.py`
Universo de **37 instrumentos** de inversión en ARS/USD disponibles en IOL.
Función principal: `get_instruments_universe(macro)` — devuelve lista de instrumentos con
características actualizadas al contexto macro del momento.
Instrumentos incluidos (16 tipos):
- **Bonos CER**: TX26, TX28, TX30, DICP, CUAP — vencimientos calculados dinámicamente
- **Bonos hard dollar**: AL29, AL30, AL35, AL41, GD28, GD30, GD35, GD38, GD41, GD46
- **LECAPs**: letras de capitalización en ARS a tasa fija
- **LECERs**: letras ajustadas por CER, corto plazo
- **Plazo fijo UVA**: cobertura CER, mínimo 90 días, garantizado SEDESA hasta $6M
- **Plazo fijo tradicional**: tasa fija TNA — marcado como ineficiente si inflación lo supera
- **Dólar MEP**: vía AL30/GD30, parking 24hs obligatorio. Precio vía dolarapi.com
- **Cauciones bursátiles**: préstamos garantizados 1-7 días, TNA ≈ TNA_PF × 0.85
- **ONs USD (10 tickers verificados en IOL)**: YMCIO (YPF 2029), YM34O (YPF 2034), TSC3O (TGS 2031), MGC3O (Pampa 2029), MGCOO (Pampa 2034), IRCPD (IRSA 2035), PNDCO (PAE 2027), TLCMO (Telecom 2031), TTC9O (Tecpetrol 2029), VISTD (Vista Energy 2030). Sufijo `O` = liquidación USD hard. Todos con vencimiento > 2026-05-15.
- **FCI Money Market**: liquidez inmediata, ~TNA mercado, rescate 24hs
- **FCI Renta Fija**: bonos CER + LECAP, horizonte 3-6 meses
- **FCI Dólar Linked**: cobertura devaluación, horizonte 6+ meses
- **FCI Acciones**: MERVAL, riesgo alto, largo plazo
- **CEDEARs**: acciones extranjeras en ARS, referenciadas a USD implícito
- **Acciones MERVAL**: GGAL, YPFD, BMA, PAMP, TXAR, TECO2, BBAR, MIRG

Cada instrumento incluye: `return_estimate`, `liquidity`, `risk_level`, `recommended_for`,
`how_to_buy` (instrucciones exactas en IOL), `sovereign_risk`, `bank_risk`.
TNA plazo fijo: intenta traer de `argentinadatos.com/v1/finanzas/tasas/depositos`;
si falla, usa `TNA_PF_FALLBACK = 20.0%`.

**Registros estáticos en este archivo:**
- `ON_REGISTRY` — 10 ONs corporativas USD con metadata: issuer, maturity, coupon, rating.
  Función: `get_on_data(ticker, price_ars_override)` → precio IOL + metadata combinados.
- `HARD_DOLLAR_BOND_REGISTRY` — 10 bonos soberanos hard dollar (AL29…GD46) con metadata.
- `FCI_REGISTRY` — FCIs con composición declarada. Actualizar manualmente cuando IOL la cambia.
  IOLCAMA (actualizado 2026-05-18): 78.77% cauciones bursátiles, 9.69% CER soberano,
  7.92% plazo fijo tradicional, 3.63% liquidez.
- `MERVAL_STOCKS` — set de 10 tickers del panel líder BYMA para detección de tipo.

### `agents/ars_advisor.py`
Agente Claude especializado en inversiones en pesos argentinos.
Recibe: capital, perfil de riesgo (bajo/moderado/alto), universo de instrumentos, macro, **noticias del día**.
Parámetro `fast_mode=False`: si True, reduce max_attempts a 1 (sin retry) para mayor velocidad.
Aplica reglas por perfil:
- **Bajo**: PF UVA + FCI. Sin CEDEARs. Máx 20% bonos CER.
- **Moderado**: 30-50% CER/UVA + 20-30% MEP + 10-20% CEDEARs + 10% FCI.
- **Alto**: 30-40% CEDEARs + 20-30% MEP + 20% CER + 10% FCI.
Descarta automáticamente PF tradicional si inflación mensual supera la TNA.
**Noticias**: recibe lista de titulares de `data/news_ar.py`.
Después de generar la recomendación, llama `compute_risk_score()` y agrega `portfolio_risk_score` al resultado.
Devuelve JSON con: `allocation[]` (instrument_id, %, amount_ars, rationale, how_to_buy),
`inflation_coverage_pct`, `usd_exposure_pct`, `strategy_summary`, `main_risk`, `time_horizon`,
`portfolio_risk_score` (score 0–100, label Bajo/Moderado/Alto, breakdown por tipo).

### `agents/portfolio_validator.py`
Valida reglas financieras de la cartera ARS y calcula riesgo cuantitativo.
- `validate_allocation(allocation, macro, profile)` — 10 reglas hard: máx 15% CEDEAR individual (moderado), mín 35% CER si inflación >3% y moderado, máx 15% soberano hard dollar (moderado), mín 15% FCI MM si dolar_liquido=0, triggers solo referencian instrumentos presentes, etc. Retorna lista de errores.
- `recalculate_fields(allocation, macro)` — recalcula `usd_exposure_pct`, `inflation_coverage_pct` en Python para no depender del LLM.
- `compute_risk_score(allocation, macro_sources)` — score cuantitativo 0–100: promedio ponderado de `_INSTRUMENT_RISK_SCORE` × allocation_pct/100, + penalización 3pts por fuente de datos stale. Labels: Bajo (≤25), Moderado (≤55), Alto (>55).
- 21 tests en `tests/test_portfolio_validator.py`.

### `data/cedears.py`
Registro y datos de CEDEARs disponibles en BYMA.
- `CEDEAR_REGISTRY` — 16 CEDEARs con ratio de conversión verificado contra precios reales IOL + yfinance (mayo 2026):
  AAPL=20, MSFT=29, NVDA=23, GOOGL=57, AMZN=140, META=23, TSLA=15, JPM=15, V=18, MA=32, COST=47, XOM=10, CVX=16, JNJ=15, ABBV=10, UNH=32.
  **Fórmula de verificación:** `ratio = us_price_USD × CCL_MEP / market_price_ARS`. Verificar ante splits corporativos.
- `get_cedear_data(ticker, price_ars_override)` — obtiene precio subyacente vía yfinance, calcula paridad teórica en ARS (`us_price / ratio × CCL`), intenta precio de mercado vía **IOL primero** (luego yfinance `.BA` como fallback), y devuelve premium/discount vs paridad y CCL implícito.
- `get_top_cedears(max_count, min_score)` — carga análisis cacheados del storage y devuelve los mejores CEDEARs por score CEO para mostrarlos cuando `invest_ars.py` recomienda CEDEARs.
- Precio CCL = dólar oficial (mercado unificado desde abril 2025 — acuerdo FMI).
- **Precio BYMA en ARS**: IOL provee precios reales (AAPL=$21100, NVDA=$12150, etc.). yfinance `.BA` como fallback (frecuentemente falla).

### `agents/cedear_analyzer.py`
Sub-agente especializado en **CEDEARs** (certificados de acciones extranjeras que cotizan en ARS en BYMA).
Analiza posiciones en CEDEARs: P&L en ARS, paridad teórica vs precio de mercado, CCL implícito vs oficial.
Además carga el análisis cacheado del subyacente en USD para dar contexto sobre los fundamentales.
Considera: premium/discount vs paridad, CCL implícito (histórico tenía premio por dolarización, hoy con mercado unificado converge a 0), comparación vs dólar MEP, perspectiva del subyacente.
Devuelve JSON con: `action`, `urgency`, `parity_analysis`, `ccl_analysis`, `underlying_view`, `vs_dolar_mep`, `rationale`, `key_alert`.

### `agents/bond_analyzer.py`
Sub-agente especializado en **renta fija argentina** (bonos CER/UVA).
Analiza posiciones en bonos soberanos como TX26, TX28, TX30, DICP.
Considera: precio sucio vs limpio, ajuste CER devengado, TIR real estimada,
paridad vs valor técnico, comparación vs plazo fijo UVA y dolarización MEP,
riesgo soberano argentino, tiempo a vencimiento.
Precio obtenido automáticamente vía IOL (TX26, GD30, AL30...). `current_price_override` opcional para forzar precio manual.
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
**Bug fix**: `market_cap` puede ser `None` para ETFs (SPY, QQQ, GLD, XLE, XLF) — se muestra
`N/A` en el prompt en lugar de romper con `TypeError`.

### `run_watchlist.py`
Expone `run_watchlist(tickers)` — función callable usada por `main.py` y la página Streamlit.
Espera **12 segundos** entre tickers (respeta rate limit de Alpha Vantage 5 req/min).
Al final imprime tabla resumen con veredicto, score, stop loss y take profit.
Guarda cada análisis en dos lugares:
- `storage/{TICKER}_analysis.json` — sobreescribe (usado por el cache)
- `storage/history/{TICKER}_analysis_{fecha}.json` — archivo histórico, nunca se sobreescribe
Envía email individual por ticker.

### `portfolio.py`
Expone `run_portfolio(capital, use_cache)` — callable desde `main.py` y Streamlit.
Flujo: screening universo completo → filtra BUY con score ≥ 6 → allocator distribuye capital → email.
Usa `core.cache.get_analysis_cached` para leer/escribir cache.
Flags CLI: `--capital XXXX` (requerido), `--use-cache`.

### `analyze_portfolio.py`
Expone `run_portfolio_analysis(portfolio_file, use_cache)` — callable desde `main.py` y Streamlit.
Lee `my_portfolio.json` y detecta automáticamente el tipo de activo (orden de prioridad):
1. `_is_arg_bond()` → `bond_analyzer` — asset_type bono_* o ticker en BOND_REGISTRY. Precio IOL.
2. `_is_cedear()` → `cedear_analyzer` — asset_type cedear o ticker en CEDEAR_REGISTRY. Precio IOL.
3. `_is_on()` → `on_analyzer` — asset_type on_usd/bono_hard_dollar o ticker en ON_REGISTRY/HARD_DOLLAR_BOND_REGISTRY. Precio IOL.
4. `_is_fci()` → `fci_analyzer` (si en FCI_REGISTRY) o `_make_fci_report()` (fallback) — asset_type fci_mm o ticker startswith("IOL").
5. Resto → `position_analyzer` — pipeline USA (fetcher + CEO + storage cache).
Genera: análisis por posición + síntesis CEO del portafolio completo.
Guarda en `storage/portfolio_analysis_{fecha}.json`.

### `my_portfolio.json`
Archivo que el usuario completa con sus posiciones reales. Campos por posición:
- `ticker` — símbolo del activo (AAPL, TX26, NVDA, etc.)
- `asset_type` — `"bono_argentino"` para bonos CER, `"cedear"` para CEDEARs; omitir para acciones
- `shares` — cantidad de acciones/títulos/CEDEARs
- `avg_buy_price` — precio promedio de compra (en USD para acciones, en ARS para bonos/CEDEARs)
- `currency` — `"USD"` o `"ARS"`
- `current_price_override` — opcional: si se ingresa, tiene prioridad sobre IOL. Para bonos y CEDEARs, IOL provee el precio automáticamente; solo usar override si IOL falla o querés forzar un precio específico.
- `notes` — notas opcionales

### `notifications/email_sender.py`
Formatea la tesis del CEO en HTML y la envía vía Gmail SMTP (puerto 465, SSL).
El email incluye: veredicto con emoji, score CEO, stop loss/take profit,
pros y contras, pasos a seguir, tabla de scores por agente, advertencia de riesgo.
También envía el email del portafolio completo cuando se usa `portfolio.py`.
Credenciales en `.env`: `EMAIL_USER` y `EMAIL_PASSWORD` (app password de Gmail).

### `instructions/investor_profile.json`
Define las reglas y preferencias del inversor:
- Experiencia: **intermediate**
- Riesgo: moderado | stop loss 8% | take profit 20% | máx 15% por posición
- Reglas fundamentales: P/E máx 40, crecimiento mínimo 5%, deuda/equity máx 2.0
- Reglas técnicas: solo sobre MA200, RSI entre 30-75, confirmar volumen
- Watchlist: AAPL, MSFT, NVDA, GOOGL, META, AMZN (6 tickers)
- Universo completo: **76 tickers en 8 sectores**:
  - technology (19): AAPL, MSFT, NVDA, GOOGL, META, AMZN, TSLA, AMD, ORCL, CRM, ADBE, PLTR, BABA, BIDU, NIO, TSM, SONY, INFY, SE
  - healthcare (8): JNJ, UNH, ABBV, LLY, PFE, TMO, ISRG, AMGN
  - finance (9): JPM, V, MA, BAC, GS, AXP, BLK, NU, GGAL
  - energy (14): XOM, CVX, COP, EOG, OXY, VALE, PAM, SLB, HAL, PBR, TTE, PAAS, GOLD, HMY
  - consumer (10): COST, WMT, HD, MCD, SBUX, NKE, TGT, MO, JD, MELI
  - real_estate (3): O, PLD, AMT
  - communications (4): DIS, NFLX, CMCSA, T
  - etfs (9): SPY, QQQ, GLD, XLE, XLF, IWM, DIA, EEM, EWZ
- Sectores prohibidos: ninguno
- **ETFs**: el agente fundamental usa un prompt especializado (sin P/E/EPS — evalúa diversificación, costo, exposición sectorial)
- **transaction_costs**: `commission_pct=0.75`, `taxes={cedear:15, bono_argentino:0, bono_hard_dollar:0, on_usd:0, accion_merval:0}` — usado por `alerts.py` para calcular umbrales de stop/target netos

### `invest_ars.py`
Expone `run_ars(capital, riesgo, fecha_objetivo, fast=False)` — callable desde `main.py` y Streamlit.
Flujo:
1. Trae macro en tiempo real (argentinadatos.com): inflación, UVA, dólar
2. **Trae noticias** en tiempo real (data/news_ar.py): hasta 12 titulares (5 en fast mode)
3. Construye universo de 37 instrumentos (data/instruments_ar.py)
4. Filtra los compatibles con el perfil de riesgo pedido
5. Si `riesgo in (moderado, alto)` y no fast_mode: corre análisis MERVAL en vivo
6. Llama a agents/ars_advisor.py con macro + noticias + picks MERVAL/CEDEAR → `fast_mode` controla intentos
7. Imprime tabla de asignación + instrucciones paso a paso en IOL
8. **Si hay CEDEARs**: muestra top 3 por CEO score (de storage cacheado)
9. Envía email y guarda en `storage/inversion_ars_{fecha}.json`

Flags CLI: `--capital` (requerido, ARS), `--riesgo` (bajo/moderado/alto, default: moderado), `--fast` (skip MERVAL en vivo, 1 intento).

### `storage/`
JSONs de cada análisis completo.
- `{TICKER}_analysis.json` — análisis de acciones más reciente (76 tickers, se sobreescribe en cada `actualizar`)
- `portfolio_{fecha}.json` — portafolio óptimo generado por `portfolio.py`
- `portfolio_analysis_{fecha}.json` — análisis del portafolio propio (`analyze_portfolio.py`)
- `inversion_ars_{fecha}.json` — recomendación en ARS; incluye campos `macro`, `news` y `recommendation`

### `storage/history/`
Historial de análisis de acciones por fecha. Se crea automáticamente al correr `actualizar` o `watchlist`.
- `{TICKER}_analysis_{fecha}.json` — snapshot del análisis de ese ticker en esa fecha
- Nunca se sobreescribe — cada día de ejecución genera un archivo nuevo
- Es la fuente de datos para `paper_trading.py`

### `alerts.py`
Sistema de alertas de precio en tiempo real. Dos fuentes de señales:

**Fuente 1 — Watchlist USA** (`load_watchlist_thresholds()`):
Lee `storage/*_analysis.json`, extrae stop_loss / take_profit del CEO en USD.
Precios vía yfinance (bulk download).

**Fuente 2 — Portafolio IOL** (`load_portfolio_thresholds()`):
Lee `my_portfolio.json`, obtiene precios actuales de cada posición vía `data/iol.get_price()`.
Stop/target calculados con ajuste a **ganancia/pérdida neta real**:
- `stop = ppc × (1 - (stop_pct - commission))` — pérdida neta = stop_pct exacto
- `target = ppc × (1 + (target_pct + commission) / (1 - tax_rate))` — ganancia neta = target_pct exacto
- Comisión y tax leídos de `instructions/investor_profile.json → transaction_costs`
- Tax por tipo: cedear=15%, bono_argentino/bono_hard_dollar/on_usd/accion_merval=0%

`run_alerts()` combina ambas fuentes. `state_key = f"{ticker}_{source}"` distingue watchlist vs portafolio para evitar colisiones en `alerts_state.json`.

**Cron:** cada hora de 11:30 a 21:30 Argentina (14:30–00:30 UTC), Lun–Vie — cubre BYMA (abre 11:00 AR) y NYSE (abre 14:30 AR).
(`30 14,15,16,17,18,19,20,21,22,23,0 * * 1-5 scripts/check_alerts.sh`)
**Logs:** `logs/alerts.log`
**Estado:** `storage/alerts_state.json` — registra última alerta enviada por state_key y tipo

### `paper_trading.py`
Seguimiento de performance de las señales del CEO contra precios reales.
Expone `run_paper_trading(history_dir)` — callable desde `main.py`.
Flujo:
1. Lee todos los `storage/history/*_analysis_*.json`
2. Extrae por cada señal: ticker, fecha, veredicto, score, entrada, stop loss, take profit
3. Obtiene precios actuales vía yfinance (bulk download, rápido)
4. Calcula P&L% y status: `active`, `stop_hit`, `target_hit`, `correct` (para AVOID)
5. Imprime tabla ordenada por veredicto (BUY → HOLD → AVOID) y dentro de cada grupo por P&L desc
6. Resumen con win rate, P&L promedio, mejor/peor señal

**Cómo correr:** `python3 main.py paper-trading`
**Nota:** Solo tiene datos desde que se empezó a guardar `storage/history/` (2026-05-07). El historial crece automáticamente con el cron diario de las 5pm.

## Variables de entorno (`.env`)
```
ANTHROPIC_API_KEY   — Claude API
ALPHA_VANTAGE_KEY   — fundamentals acciones (25 req/día free)
FINNHUB_KEY         — fundamentals fallback + noticias (60 req/min free)
POLYGON_KEY         — técnico acciones (5 req/min free, delay 15min)
EMAIL_USER          — Gmail address
EMAIL_PASSWORD      — Gmail app password (no la contraseña normal, una app password de Google)
IOL_USERNAME        — usuario de Invertir Online (email completo, ej: usuario@gmail.com)
IOL_PASSWORD        — contraseña normal de IOL (no es una app password)
```
**Sin key requerida:** `data/argentina.py` usa argentinadatos.com y dolarapi.com (APIs públicas).

## Crons activos
| Schedule | Script | Qué hace |
|----------|--------|----------|
| `0 20 * * 1-5` (5pm AR) | `scripts/actualizar_diario.sh` | Re-analiza las acciones del portafolio |
| `30 14-23,0 * * 1-5` (cada hora, BYMA + NYSE) | `scripts/check_alerts.sh` | Alertas watchlist USA (yfinance) + portafolio IOL (ARS neto) |

## Performance
- **1 ticker acción**: ~55 segundos (datos + 4 agentes paralelos + CEO + email)
- **Watchlist (4 tickers)**: ~4-5 minutos
- **Universo completo (76 tickers)**: ~90 minutos frescos / ~15 segundos con `--cache`
- **Portafolio propio (bonos/CEDEARs)**: ~15 segundos (IOL provee precios automáticamente)
- **Recomendación ARS**: ~20 segundos (macro + Claude advisor)
- **Interfaz Streamlit**: muestra progreso en tiempo real con `st.spinner` y barra de progreso

## Stack
Python 3.12 · anthropic · streamlit · yfinance · feedparser · requests · python-dotenv · smtplib · concurrent.futures

## Roadmap — estado actual

| Paso | Feature | Estado |
|------|---------|--------|
| 1 | CEDEARs + tipo de cambio | ✅ done (`data/cedears.py`, `agents/cedear_analyzer.py`) |
| 2 | Ingesta manual de portafolio | ✅ done (`my_portfolio.json` + `analyze_portfolio.py`) |
| 3 | Análisis de posiciones existentes | ✅ done (`agents/position_analyzer.py` + `agents/bond_analyzer.py` + `agents/cedear_analyzer.py`) |
| 3b | Recomendación "invertir $X ARS" | ✅ done (`invest_ars.py`, 32 instrumentos, picks de CEDEARs) |
| 4 | Integración broker API (IOL) | ✅ done (`data/iol.py` — precios reales de bonos y CEDEARs) |
| 5 | Universo de instrumentos ARS ampliado | ✅ done (32 instrumentos, 16 tipos en `data/instruments_ar.py`) |
| 6 | CLI unificado | ✅ done (`main.py` con subcomandos, `core/cache.py` compartido) |
| 7 | Interfaz web Streamlit | ✅ done (`app.py` + 4 páginas en `pages/`) |
| 8 | Noticias en tiempo real para ARS advisor | ✅ done (`data/news_ar.py` — Google News RSS + Ámbito, inyectadas en el prompt) |
| 9 | Automatización diaria (cron/scheduler) | ✅ done (cron 5pm Argentina, `scripts/actualizar_diario.sh`, logs en `logs/actualizar.log`) |
| 9b | Historial de análisis por fecha | ✅ done (`storage/history/{TICKER}_analysis_{fecha}.json`) |
| 10 | Paper trading — validar rentabilidad histórica | ✅ done (`paper_trading.py` — señales históricas vs precio actual, win rate, P&L) |
| 11 | Alertas de precio | ✅ done (`alerts.py` — stop/target/near_stop, cron BYMA+NYSE, email HTML, umbrales netos) |
| 12 | Perfil de riesgo dinámico por usuario | ✅ done (`pages/6_Perfil.py` — sliders, checkboxes, watchlist, restaurar defaults) |
| 13 | Sincronización portafolio desde IOL | ✅ done (`core/portfolio_manager.sync_from_iol()` — detecta tipo automáticamente, preserva cash) |
| 14 | ONs corporativas en universo ARS | ✅ done (10 tickers verificados en IOL: YMCIO, YM34O, TSC3O, MGC3O, MGCOO, IRCPD, PNDCO, TLCMO, TTC9O, VISTD) |
| 15 | Alertas con ajuste neto (comisión + impuesto) | ✅ done (`transaction_costs` en perfil — CEDEAR 15%, bonos exentos, comisión 0.75%) |
| 16 | FCI analyzer con composición real | ✅ done (`agents/fci_analyzer.py` + `FCI_REGISTRY` — IOLCAMA deja de mostrar -100% loss) |

## Próximos pasos
El roadmap original está completo. Posibles extensiones:
1. **Notificaciones push / Telegram** — alertas además de email
2. **Backtesting** — evaluar las reglas del perfil contra datos históricos
3. **Multi-usuario** — perfiles separados por usuario en la UI

---

## Plan: Migración a sistema Argentina-focused

**Motivación:** El sistema actual tiene dos mundos separados (análisis USA en USD y recomendaciones ARS) que no se integran bien. El usuario opera en IOL (Invertir Online) en ARS — nunca compra acciones directamente en NYSE. El objetivo es hacer del pipeline de análisis USA el *motor interno* que informa qué CEDEARs comprar, y unificar toda la salida en ARS con instrucciones de IOL.

**Lo que NO cambia:** el pipeline de análisis USA (fetcher + 4 agentes + CEO orchestrator) se mantiene como motor de inteligencia para determinar qué CEDEARs son buenos. Solo cambia que su output alimenta recomendaciones en ARS en lugar de un portafolio USD.

### Fase 1 — MERVAL como asset class real
*Archivos nuevos, sin romper nada existente.*

**`data/merval.py`** (crear)
- Lista de acciones MERVAL con tickers IOL: GGAL, YPFD, BMA, PAMP, TXAR, TECO2, BBAR, MIRG, ALUA, LOMA
- `get_merval_data(ticker)` → precio ARS vía IOL + indicadores básicos (52w high/low, volumen, variación)
- Reutilizar `get_macro_data()` de `data/argentina.py` para contexto macro

**`agents/merval_analyzer.py`** (crear)
- Analiza acción argentina: valuación en ARS, relación con dólar implícito, contexto macro local
- Reglas distintas a acciones USA: no aplica MA200 en USD, evalúa en términos de dólar CCL y cobertura inflacionaria
- Devuelve: `action`, `score/10`, `rationale`, `how_to_buy` (instrucciones IOL exactas)

### Fase 2 — Integración profunda CEDEAR ↔ análisis USA
*Modifica archivos existentes sin cambiar la interfaz externa.*

**`agents/ars_advisor.py`** (modificar)
- Hoy recibe solo el `ceo_score` (número). Pasar la **tesis completa**: pros, contras, stop_loss, take_profit, thesis
- El advisor genera recomendaciones de CEDEARs con fundamento real en ARS
- Agregar MERVAL como categoría de instrumento con picks concretos

**`data/instruments_ar.py`** (modificar)
- Agregar sección MERVAL con los 10 tickers y sus características (liquidez, riesgo, cómo comprar en IOL)
- Si hay CEDEARs con score ≥ 7, incluirlos como picks específicos con nombre, ratio, precio paridad y precio IOL

**`data/cedears.py`** (modificar)
- Expandir `CEDEAR_REGISTRY` de 16 a ~25 tickers (agregar AMD, TSLA, COP, COST, WMT, etc.)
- Verificar ratios con fórmula: `ratio = us_price_USD × CCL / market_price_ARS`

### Fase 3 — Comando unificado en ARS
*El cambio más visible para el usuario.*

**`invest_ars.py`** (modificar)
- Antes de llamar al advisor: correr `get_top_cedears()` Y nuevo `get_top_merval()`
- El advisor recibe: macro + noticias + instrumentos + **análisis completo de mejores CEDEARs** + **análisis MERVAL**
- Output: una sola tabla en ARS con todo mezclado (CEDEARs, MERVAL, bonos, cash) + instrucciones IOL

**`main.py`** (modificar)
- Deprecar/ocultar comando `portafolio` (USD) o convertirlo en herramienta interna
- Hacer `invertir` el comando principal: `python3 main.py invertir --capital 500000`

### Fase 4 — Streamlit actualizado
*Últimos cambios, cuando el backend esté listo.*

**`pages/2_Portafolio_USD.py`** → reemplazar por **`pages/2_CEDEARs.py`**
- Tabla de todos los CEDEARs del registry: precio IOL, paridad, premium/discount, score CEO
- Semáforo: verde (score ≥ 7), amarillo (5-6), rojo (<5)
- Calculadora: "¿cuánto equivale X USD en ARS vía este CEDEAR?"

**`pages/4_Invertir_ARS.py`** (enriquecer)
- Sección MERVAL en los resultados
- Tesis completa de cada CEDEAR recomendado (no solo el nombre)
- Slider de horizonte temporal (corto/mediano/largo plazo)

**`pages/6_Perfil.py`** (modificar)
- Agregar sección "Acciones argentinas (MERVAL)" con lista toggleable
- Reemplazar referencias a "universo USD" por "universo CEDEAR + MERVAL"

### Orden de implementación

| # | Tarea | Archivos | Estado |
|---|-------|----------|--------|
| 1 | Crear `data/merval.py` + `agents/merval_analyzer.py` | 2 nuevos | ✅ done |
| 2 | Expandir `CEDEAR_REGISTRY` en `data/cedears.py` | existente | ✅ done (16 tickers verificados) |
| 3 | Pasar tesis completa al advisor en `agents/ars_advisor.py` | existente | ✅ done |
| 4 | Integrar MERVAL en `data/instruments_ar.py` + `invest_ars.py` | existentes | ✅ done |
| 5 | Reemplazar `pages/2_Portafolio_USD.py` por dashboard CEDEARs | existente | ✅ done (`pages/2_CEDEARs.py`) |
| 6 | Enriquecer `pages/4_Invertir_ARS.py` con MERVAL + tesis | existente | ✅ done |
| 7 | Deprecar comando `portafolio` USD en `main.py` | existente | Baja — pendiente |
