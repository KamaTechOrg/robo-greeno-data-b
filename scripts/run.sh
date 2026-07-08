#!/usr/bin/env bash
# Runs the vision container via docker compose in the foreground, capturing full STDIO
# to a timestamped log file for review (build/deploy visibility requirement).
set -euo pipefail

cd "$(dirname "$0")/.."

mkdir -p logs
LOG_FILE="logs/run_$(date -u +%Y%m%dT%H%M%SZ).log"

echo "[run] starting via docker compose, logging to ${LOG_FILE}"
docker compose up --build 2>&1 | tee "${LOG_FILE}"
