#!/usr/bin/env bash
# Optional local lint/format gate (Ruff). Not in CI yet — see CONTRIBUTING.md.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ -x "$ROOT_DIR/.venv/bin/ruff" ]]; then
  RUFF="$ROOT_DIR/.venv/bin/ruff"
elif command -v ruff >/dev/null 2>&1; then
  RUFF=ruff
else
  echo "ruff not found; install dev deps: python -m pip install -e '.[dev]'" >&2
  exit 1
fi

MODE="${1:-check}"

case "$MODE" in
  check)
    echo "Running ruff check..."
    "$RUFF" check .
    echo "Lint check passed."
    ;;
  format)
    echo "Running ruff check..."
    "$RUFF" check .
    echo "Running ruff format --check..."
    "$RUFF" format --check .
    echo "Lint and format check passed."
    ;;
  fix)
    echo "Running ruff check --fix..."
    "$RUFF" check --fix .
    echo "Running ruff format..."
    "$RUFF" format .
    echo "Auto-fix and format completed."
    ;;
  *)
    echo "Usage: $0 [check|format|fix]" >&2
    echo "  check   — ruff check only (default)" >&2
    echo "  format  — ruff check + format --check" >&2
    echo "  fix     — ruff check --fix + format" >&2
    exit 2
    ;;
esac
