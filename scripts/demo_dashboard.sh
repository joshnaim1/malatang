#!/usr/bin/env bash
# Launch the Malatang pipeline dashboard for live iteration demos.
#
# Usage:
#   bash scripts/demo_dashboard.sh
#   bash scripts/demo_dashboard.sh 8765 0.0.0.0
#
# Then open http://127.0.0.1:8765/ (or the notebook public URL) while the
# runner is active:
#   python -m harness.runner --creator live --start-iteration 3

set -euo pipefail

PORT="${1:-8765}"
HOST="${2:-127.0.0.1}"

echo "[dashboard] Starting on http://${HOST}:${PORT}/"
python -m scripts.dashboard_server --host "$HOST" --port "$PORT"
