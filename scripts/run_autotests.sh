#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "Running Python unit tests..."
python3 -m unittest discover -s tests -p "test_*.py"

echo "Autotests completed successfully."
