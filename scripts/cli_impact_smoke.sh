#!/usr/bin/env bash
# Minimal CLI smoke loop for agent-driven work (see docs/decisions/agent-inline-cli-ux-validation.md).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PY="${PYTHON:-python3}"
ENTRY="${TIMOLOG_ENTRY:-timelog_extract.py}"
echo "==> $PY $ENTRY -V"
"$PY" "$ENTRY" -V
echo "==> report --today --source-summary --quiet"
"$PY" "$ENTRY" report --today --source-summary --quiet
echo "==> ux-heroes"
"$PY" "$ENTRY" ux-heroes
echo "==> handoff: run CI fixtures with scripts/run_cli_experiments_ci.sh (report-only by default)"
echo "CLI impact smoke: OK"
