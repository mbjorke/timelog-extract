#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

# Force a wide, deterministic terminal width. CLI smoke/status/triage tests assert
# on human-facing Rich output; in a narrow terminal Rich wraps/truncates those
# strings and the assertions fail locally though they pass in CI (wide/no-tty).
# Pinning COLUMNS makes local runs match CI regardless of the developer's window.
export COLUMNS=200

echo "Running Python unit tests..."
python3 scripts/check_file_lengths.py --max-lines 500
bash scripts/run_lint.sh
python3 -m unittest discover -s tests -p "test_*.py"

echo "Autotests completed successfully."
