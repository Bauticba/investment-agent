#!/bin/bash
# Corre todos los días a las 5pm para refrescar el storage con análisis nuevos.
# Los logs se guardan en logs/actualizar.log

PROJECT="/home/bautista/investment-agent"
PYTHON="$PROJECT/venv/bin/python3"
LOG="$PROJECT/logs/actualizar.log"

mkdir -p "$PROJECT/logs"

echo "" >> "$LOG"
echo "========================================" >> "$LOG"
echo "$(date '+%Y-%m-%d %H:%M:%S') — Iniciando actualización diaria" >> "$LOG"
echo "========================================" >> "$LOG"

# Actualiza solo los tickers del portafolio actual (económico, uso diario)
# Para actualizar el universo completo: python3 main.py actualizar
TICKERS=$("$PYTHON" -c "
import json
with open('my_portfolio.json') as f:
    p = json.load(f)
# Solo acciones (los bonos y CEDEARs traen precio de IOL, no necesitan análisis Claude)
tickers = [pos['ticker'] for pos in p.get('positions', [])
           if pos.get('asset_type') not in ('bono_argentino', 'bono_cer_argentino', 'cedear', 'bono')
           and pos['ticker'] not in ('TX26','TX28','TX30','DICP','CUAP')]
print(' '.join(tickers))
" 2>/dev/null)

if [ -z "$TICKERS" ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') — No hay acciones en el portafolio para actualizar." >> "$LOG"
else
    echo "$(date '+%Y-%m-%d %H:%M:%S') — Actualizando: $TICKERS" >> "$LOG"
    cd "$PROJECT" && "$PYTHON" main.py actualizar $TICKERS >> "$LOG" 2>&1
fi

echo "$(date '+%Y-%m-%d %H:%M:%S') — Finalizado" >> "$LOG"
