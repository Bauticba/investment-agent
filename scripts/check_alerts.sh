#!/bin/bash
# Corre cada hora en horario de mercado americano (14:30-21:00 Argentina).
# Chequea stop loss y take profit de todos los tickers del storage.

PROJECT="/home/bautista/investment-agent"
PYTHON="$PROJECT/venv/bin/python3"
LOG="$PROJECT/logs/alerts.log"

mkdir -p "$PROJECT/logs"

echo "" >> "$LOG"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Chequeando alertas..." >> "$LOG"

cd "$PROJECT" && "$PYTHON" alerts.py >> "$LOG" 2>&1

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Finalizado" >> "$LOG"
