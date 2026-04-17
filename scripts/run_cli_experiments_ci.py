#!/usr/bin/env python3
"""Backward-compatible entrypoint; prefer `scripts/ci/run_cli_experiments_ci.py`."""

from __future__ import annotations

import runpy
from pathlib import Path

if __name__ == "__main__":
    target = Path(__file__).resolve().parent / "ci" / "run_cli_experiments_ci.py"
    runpy.run_path(str(target), run_name="__main__")

