#!/usr/bin/env python3
"""Analyze gaps between estimated hours and screen time."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.calibration.screen_time_gap import analyze_screen_time_gaps
from core.cli import TimelogRunOptions
from core.report_service import run_timelog_report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--projects-config", default="timelog_projects.json")
    parser.add_argument("--date-from")
    parser.add_argument("--date-to")
    parser.add_argument("--out-json", default="out/reconciliation/screen_time_gap.json")
    parser.add_argument("--out-md", default="out/reconciliation/screen_time_gap.md")
    args = parser.parse_args()
    if not args.date_from or not args.date_to:
        parser.error("--date-from and --date-to are required (e.g. 2026-03-01 to 2026-03-31)")
    options = TimelogRunOptions(
        date_from=args.date_from,
        date_to=args.date_to,
        projects_config=args.projects_config,
        include_uncategorized=True,
        quiet=True,
        screen_time="on",
    )
    report = run_timelog_report(args.projects_config, args.date_from, args.date_to, options)
    payload = analyze_screen_time_gaps(report)
    out_json = Path(args.out_json)
    out_md = Path(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    out_md.write_text("See JSON payload for full details.\n", encoding="utf-8")
    print(f"Wrote: {out_json}")
    print(f"Wrote: {out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

