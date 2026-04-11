#!/usr/bin/env python3
"""CLI entrypoint and backward-compatible exports for timelog extract."""

from __future__ import annotations
import sys
from pathlib import Path

# Ensure the project root is in sys.path so 'core', 'outputs', etc. are found
root = Path(__file__).parent.resolve()
if str(root) not in sys.path:
    sys.path.insert(0, str(root))

from core.cli import TimelogRunOptions, app, as_run_options, main
from core.config import normalize_profile
from core.report_service import (
    LOCAL_TZ,
    UNCATEGORIZED,
    estimate_hours_by_day,
    group_by_day,
)
from core.report_service import _classify_project as classify_project

if __name__ == "__main__":
    main()
