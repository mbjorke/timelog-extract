#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

python3 -m unittest \
  tests.test_cli_date_range \
  tests.test_cli_triage \
  tests.test_cli_triage_guided \
  tests.test_cli_status_integrity \
  tests.test_report_nudges
