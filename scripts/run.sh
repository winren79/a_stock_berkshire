#!/usr/bin/env bash
set -euo pipefail

ROOT="/Users/hechen/Documents/Codex/a_stock_berkshire"
PYTHON="$ROOT/venv/bin/python"
LOG="$ROOT/logs/cron.log"

cd "$ROOT"
mkdir -p "$ROOT/logs"

{
  echo "===== run started at $(date '+%Y-%m-%d %H:%M:%S') ====="
  "$PYTHON" "$ROOT/stock_engine.py"
  echo "===== run completed at $(date '+%Y-%m-%d %H:%M:%S') ====="
} >> "$LOG" 2>&1
