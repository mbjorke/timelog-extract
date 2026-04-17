#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

STRICT_FLAG=()
if [[ "${STRICT_CLI_EXPERIMENTS:-0}" == "1" ]]; then
  STRICT_FLAG=(--strict)
fi

python3 scripts/ci/run_cli_experiments_ci.py "${STRICT_FLAG[@]}"
echo "CLI experiments completed."

