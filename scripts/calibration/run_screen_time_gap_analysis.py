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
    parser = argparse.ArgumentParser(description="Analyze gaps between estimated hours and screen time.")
    parser.add_argument("--projects-config", default="timelog_projects.json")
    parser.add_argument("--date-from", help="Start date (YYYY-MM-DD, defaults to first day of last month)")
    parser.add_argument("--date-to", help="End date (YYYY-MM-DD, defaults to last day of last month)")
    parser.add_argument("--out-json", default="out/reconciliation/screen_time_gap.json")
    parser.add_argument("--out-md", default="out/reconciliation/screen_time_gap.md")
    args = parser.parse_args()
    
    from datetime import date, timedelta
    if not args.date_from or not args.date_to:
        today = date.today()
        first_of_this_month = today.replace(day=1)
        last_of_last_month = first_of_this_month - timedelta(days=1)
        first_of_last_month = last_of_last_month.replace(day=1)
        date_from = args.date_from or first_of_last_month.isoformat()
        date_to = args.date_to or last_of_last_month.isoformat()
    else:
        date_from = args.date_from
        date_to = args.date_to
    
    options = TimelogRunOptions(
        projects_config=args.projects_config,
        date_from=date_from,
        date_to=date_to,
        include_uncategorized=True,
        quiet=True,
        screen_time="on",
    )
    report = run_timelog_report(options.projects_config, options.date_from, options.date_to, options)
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

