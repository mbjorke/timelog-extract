#!/usr/bin/env python3
"""Backward-compatible entrypoint; prefer scripts/calibration/ path."""

from __future__ import annotations

import runpy
from pathlib import Path

if __name__ == "__main__":
    target = Path(__file__).resolve().parent / "calibration" / "run_march_calibration_report.py"
    runpy.run_path(str(target), run_name="__main__")

