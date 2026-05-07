# 📈 Investment Agent

Sistema multi-agente de análisis bursátil construido en Python, usando la **Claude API** como cerebro de cada agente. Genera tesis de inversión personalizadas para acciones americanas, bonos argentinos y CEDEARs, con una interfaz web en Streamlit y automatización completa vía cron.

---

## ¿Qué hace?

- **Analiza acciones americanas** (50 tickers) con 4 agentes especializados corriendo en paralelo: fundamental, técnico, indicadores y sentimiento — sintetizados por un agente CEO que genera la tesis final
- **Analiza el mercado argentino** — bonos CER (TX26, TX28, TX30), CEDEARs y 32 instrumentos en ARS con contexto macro en tiempo real e incorpora noticias del día (Google News + Ámbito)
- **Monitorea tu portafolio** — acciones, bonos y CEDEARs con precios reales vía API de Invertir Online
- **Paper trading** — rastrea si las señales del CEO aciertan comparando predicciones contra precios reales
- **Alertas de precio** — notifica por email cuando un ticker toca el stop loss o take profit
- **Automatización diaria** — cron que actualiza análisis a las 5pm y chequea alertas cada hora en horario de mercado

---

## Arquitectura

```
                    ┌─────────────────────────┐
                    │      data/fetcher.py     │  ← orquesta las fuentes
                    │  Alpha Vantage · Finnhub │
                    │  Polygon · yfinance      │
                    └────────────┬────────────┘
                                 │
           ┌─────────────────────┼──────────────────────┐
           ▼                     ▼                      ▼                    ▼
  agents/fundamental   agents/technical    agents/indicators   agents/sentiment
   (P/E, ROE, deuda)  (MA, RSI, soportes) (MACD, Bollinger)  (noticias Finnhub)
           │                     │                      │                    │
           └──────────────── PARALELO ──────────────────────────────────────┘
                                 │ 4 reportes JSON con score/10
                                 ▼
                        ceo/orchestrator.py
                    tesis final · stop loss · take profit
                                 │
              ┌──────────────────┼──────────────────┐
              ▼                  ▼                  ▼
    storage/{TICKER}        email HTML       storage/history/
    _analysis.json                        (historial por fecha)
```

---

## Interfaz web — Streamlit

```bash
source venv/bin/activate
streamlit run app.py  # http://localhost:8501
```

| Página | Descripción |
|--------|-------------|
| 🏠 Home | Macro argentina en tiempo real + tabla de todos los análisis guardados |
| 📋 Watchlist | Analizar tickers a elección con barra de progreso |
| 💼 Portafolio USD | Screening de 50 tickers + distribución óptima de capital |
| 🗂️ Mi Portafolio | Análisis de posiciones reales (acciones, bonos, CEDEARs) |
| 🇦🇷 Invertir ARS | Recomendación en pesos con noticias del día incorporadas |
| 📈 Paper Trading | Win rate, P&L% y seguimiento de señales históricas |
| ⚙️ Perfil | Editar stop loss, take profit, RSI, P/E y watchlist desde la UI |

---

## CLI

```bash
source venv/bin/activate

# Actualizar storage
python3 main.py actualizar                          # 50 tickers del universo
python3 main.py actualizar AAPL MSFT NVDA           # tickers específicos

# Análisis
python3 main.py watchlist                           # watchlist con email
python3 main.py portafolio --capital 5000           # portafolio óptimo USD
python3 main.py mi-portafolio                       # analizar my_portfolio.json
python3 main.py invertir --capital 500000 --riesgo moderado
python3 main.py invertir --capital 500000 --riesgo moderado --fecha 2027-01

# Portafolio
python3 main.py comprar AAPL 10 185.50
python3 main.py vender AAPL 5
python3 main.py posiciones

# Paper trading
python3 main.py paper-trading
```

---

## Stack de datos

| Fuente | Qué provee | Límite free |
|--------|-----------|-------------|
| [Alpha Vantage](https://www.alphavantage.co/) | Fundamentals (P/E, EPS, ROE, márgenes) | 25 req/día |
| [Finnhub](https://finnhub.io/) | Fundamentals fallback + noticias | 60 req/min |
| [Polygon.io](https://polygon.io/) | Datos técnicos (OHLCV, SMA, RSI) | 5 req/min |
| [yfinance](https://github.com/ranaroussi/yfinance) | Indicadores (MACD, Bollinger, volumen) | Sin límite |
| [IOL API](https://api.invertironline.com/) | Precios reales de bonos y CEDEARs en BYMA | Requiere cuenta |
| [argentinadatos.com](https://argentinadatos.com/) | Macro argentina (inflación, UVA, dólar) | Pública |
| Google News RSS | Noticias económicas argentinas en tiempo real | Pública |

---

## Instalación

```bash
git clone https://github.com/Bauticba/investment-agent.git
cd investment-agent
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Crear `.env` con las variables necesarias:

```env
ANTHROPIC_API_KEY=...
ALPHA_VANTAGE_KEY=...
FINNHUB_KEY=...
POLYGON_KEY=...
EMAIL_USER=tu@gmail.com
EMAIL_PASSWORD=...        # App password de Gmail, no la contraseña normal
IOL_USERNAME=...          # Email de tu cuenta Invertir Online
IOL_PASSWORD=...
```

> **Mínimo requerido:** solo `ANTHROPIC_API_KEY` para correr. yfinance funciona sin key. Las demás mejoran la calidad de los datos con fallback automático.

Crear `my_portfolio.json` con tus posiciones (el archivo no se incluye en el repo):

```json
{
  "broker": "Tu broker",
  "positions": [
    {
      "ticker": "AAPL",
      "shares": 10,
      "avg_buy_price": 185.50,
      "currency": "USD"
    },
    {
      "ticker": "TX26",
      "asset_type": "bono_argentino",
      "shares": 1000,
      "avg_buy_price": 1450.00,
      "currency": "ARS"
    }
  ],
  "cash": { "USD": 0, "ARS": 0 }
}
```

> `asset_type` puede ser `"bono_argentino"` o `"cedear"`. Para acciones americanas omitirlo. El campo `current_price_override` es opcional — si no se completa, el precio se obtiene automáticamente vía IOL o yfinance.

---

## Automatización

Dos crons preconfigurados (ajustar con `crontab -e`):

```cron
# Actualiza análisis del portafolio a las 5pm Argentina (Lun-Vie)
0 20 * * 1-5 /ruta/al/proyecto/scripts/actualizar_diario.sh

# Chequea stop loss y take profit cada hora en horario de mercado
30 17,18,19,20,21,22,23,0 * * 1-5 /ruta/al/proyecto/scripts/check_alerts.sh
```

Logs en `logs/actualizar.log` y `logs/alerts.log`.

---

## Agentes especializados

| Agente | Analiza | Veredicto |
|--------|---------|-----------|
| `fundamental.py` | P/E, EPS, ROE, deuda, márgenes | buy / hold / avoid |
| `technical.py` | Tendencia, MA20/50/200, RSI, soportes | buy / hold / avoid |
| `indicators.py` | MACD, Bollinger Bands, volumen | buy / hold / avoid |
| `sentiment.py` | Noticias Finnhub, posición competitiva | buy / hold / avoid |
| `ceo/orchestrator.py` | Síntesis final de los 4 agentes | tesis + stop/target |
| `allocator.py` | Distribución óptima de capital | posiciones + pesos |
| `ars_advisor.py` | Inversión en ARS con macro + noticias | asignación en pesos |
| `bond_analyzer.py` | Bonos CER argentinos (TX26, TX28...) | hold / sell / add |
| `cedear_analyzer.py` | CEDEARs: paridad, CCL implícito | hold / sell / add |
| `position_analyzer.py` | Posiciones existentes en acciones | hold / sell / add |

---

## Perfil del inversor

El sistema usa `instructions/investor_profile.json` (editable desde la UI en Perfil):

- **Riesgo:** moderado — stop loss 8%, take profit 20%, máx 15% por posición
- **Reglas fundamentales:** P/E ≤ 40, crecimiento ≥ 5%, deuda/equity ≤ 2.0
- **Reglas técnicas:** solo sobre MA200, RSI entre 30–75, confirmar volumen
- **Universo:** 50 tickers en 8 sectores (tech, healthcare, finance, energy, consumer, real estate, communications, ETFs)

---

## Estructura del proyecto

```
investment-agent/
├── main.py                    # CLI unificado
├── app.py                     # Streamlit home
├── pages/                     # 6 páginas Streamlit
├── agents/                    # 10 agentes especializados
├── ceo/orchestrator.py        # Síntesis CEO
├── data/                      # 9 módulos de datos
├── core/                      # Cache y gestión de portafolio
├── notifications/             # Email HTML
├── scripts/                   # Scripts de cron
├── storage/                   # JSONs de análisis
│   └── history/               # Historial por fecha (paper trading)
├── alerts.py                  # Sistema de alertas de precio
├── paper_trading.py           # Seguimiento de señales históricas
├── instructions/              # Perfil del inversor
└── my_portfolio.json          # Posiciones reales
```

---

## Stack tecnológico

Python 3.12 · [Anthropic Claude](https://www.anthropic.com/) · Streamlit · yfinance · feedparser · requests · python-dotenv · smtplib · concurrent.futures

---

> **Disclaimer:** Este sistema es una herramienta educativa y de análisis personal. No constituye asesoramiento financiero. Siempre consultá con un profesional antes de tomar decisiones de inversión.
