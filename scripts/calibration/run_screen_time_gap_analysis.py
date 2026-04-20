#!/usr/bin/env python3
"""Analyze gaps between estimated hours and screen time."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.calibration.screen_time_gap import analyze_screen_time_gaps
from core.cli import TimelogRunOptions
from core.report_service import run_timelog_report


def _json_safe(value):
    if isinstance(value, float):
        if math.isinf(value) or math.isnan(value):
            return None
        return value
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    return value


def _build_markdown_summary(payload: dict, *, date_from: str, date_to: str) -> str:
    totals = payload.get("totals", {})
    days = payload.get("days", [])
    missing_reference_days = [row for row in days if bool(row.get("missing_reference_data", False))]
    worst_unexplained = sorted(
        days,
        key=lambda day: float(day.get("unexplained_screen_time_hours", 0.0)),
        reverse=True,
    )[:3]
    worst_over = sorted(
        [row for row in days if not bool(row.get("missing_reference_data", False))],
        key=lambda day: float(day.get("over_attributed_hours", 0.0)),
        reverse=True,
    )[:3]
    lines = [
        "# Screen Time Gap Analysis (Internal)",
        "",
        "Status: INTERNAL_ONLY (reconciliation artifact, not stage-demo surface).",
        "",
        f"Date range: {date_from} -> {date_to}",
        "",
        "## Totals",
        f"- Estimated hours: {float(totals.get('estimated_hours', 0.0)):.2f}",
        f"- Screen time hours: {float(totals.get('screen_time_hours', 0.0)):.2f}",
        f"- Coverage ratio: {float(totals.get('coverage_ratio', 0.0)):.4f}",
        f"- Unexplained screen time hours: {float(totals.get('unexplained_screen_time_hours', 0.0)):.2f}",
        f"- Over-attributed hours: {float(totals.get('over_attributed_hours', 0.0)):.2f}",
        f"- Missing reference-data days: {int(totals.get('missing_reference_day_count', 0))}",
        "",
        "## Top unexplained-screen-time days",
    ]
    if worst_unexplained:
        for row in worst_unexplained:
            lines.append(
                f"- {row.get('day')}: {float(row.get('unexplained_screen_time_hours', 0.0)):.2f}h unexplained"
            )
    else:
        lines.append("- None")
    lines.extend(["", "## Days with missing screen-time reference data"])
    if missing_reference_days:
        for row in sorted(
            missing_reference_days,
            key=lambda day: float(day.get("estimated_hours", 0.0)),
            reverse=True,
        )[:3]:
            lines.append(
                f"- {row.get('day')}: {float(row.get('estimated_hours', 0.0)):.2f}h estimated, "
                "screen-time reference missing"
            )
    else:
        lines.append("- None")
    lines.extend(["", "## Top over-attributed days"])
    if worst_over:
        for row in worst_over:
            lines.append(
                f"- {row.get('day')}: {float(row.get('over_attributed_hours', 0.0)):.2f}h over-attributed"
            )
    else:
        lines.append("- None")
    lines.extend(["", "See JSON payload for full details."])
    return "\n".join(lines) + "\n"


def main() -> int:
    """
    CLI entrypoint that runs a timelog screen-time gap analysis for a specified date range and writes a JSON payload plus a minimal Markdown pointer file.
    
    If either `--date-from` or `--date-to` is omitted, the missing boundary defaults to the first or last day of the previous calendar month, respectively. Writes the full analysis JSON to the path given by `--out-json` and a short Markdown pointer to `--out-md`.
    
    Returns:
        int: Exit code `0` on successful completion.
    """
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
    payload_safe = _json_safe(payload)
    out_json = Path(args.out_json)
    out_md = Path(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload_safe, indent=2), encoding="utf-8")
    out_md.write_text(
        _build_markdown_summary(payload_safe, date_from=date_from, date_to=date_to),
        encoding="utf-8",
    )
    print(f"Wrote: {out_json}")
    print(f"Wrote: {out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

