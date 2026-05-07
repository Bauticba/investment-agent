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

cd "$PROJECT" && "$PYTHON" main.py actualizar >> "$LOG" 2>&1

echo "$(date '+%Y-%m-%d %H:%M:%S') — Finalizado" >> "$LOG"
