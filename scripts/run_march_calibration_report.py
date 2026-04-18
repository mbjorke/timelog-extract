#!/usr/bin/env python3
"""Backward-compatible entrypoint; prefer scripts/calibration/ path."""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

if __name__ == "__main__":
    target = Path(__file__).resolve().parent / "calibration" / "run_march_calibration_report.py"
    if not target.exists():
        print(f"Error: Target script not found at {target}", file=sys.stderr)
        print("The script has moved to scripts/calibration/run_march_calibration_report.py", file=sys.stderr)
        sys.exit(1)
    runpy.run_path(str(target), run_name="__main__")

