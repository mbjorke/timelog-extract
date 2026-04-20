#!/usr/bin/env python3
"""Compatibility entrypoint for day-level gap triage."""

from __future__ import annotations

import runpy
from pathlib import Path

if __name__ == "__main__":
    target = Path(__file__).resolve().parent / "calibration" / "gap_day_triage.py"
    runpy.run_path(str(target), run_name="__main__")
