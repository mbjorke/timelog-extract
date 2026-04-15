#!/usr/bin/env python3
"""Run two truth-payload reports with different --projects-config paths (same date range).

Use this to compare baseline vs candidate JSON without moving or renaming timelog_projects.json.
Writes JSON snapshots under --output-dir and prints a hours-per-project summary.

Example:
  python3 scripts/compare_project_configs.py \\
    --baseline timelog_projects.json \\
    --candidate private/compare/timelog_projects.candidate.json \\
    --last-week
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.cli import TimelogRunOptions
from core.compare_project_configs import format_comparison_text
from core.engine_api import run_report_payload


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Compare two project configs against the same report run (same machine, same date range)."
    )
    p.add_argument(
        "--baseline",
        default="timelog_projects.json",
        metavar="PATH",
        help="First projects config path (default: timelog_projects.json).",
    )
    p.add_argument(
        "--candidate",
        required=True,
        metavar="PATH",
        help="Second projects config path (e.g. a copy you edit for experiments).",
    )
    p.add_argument(
        "--output-dir",
        default="private/compare/out",
        metavar="DIR",
        help="Directory for baseline.json and candidate.json (created if missing).",
    )
    p.add_argument("--worklog", default=None, help="Optional TIMELOG path (same as gittan report --worklog).")
    p.add_argument(
        "--include-uncategorized",
        action="store_true",
        help="Pass include_uncategorized=True on both runs (same as gittan report).",
    )
    p.add_argument(
        "--source-strategy",
        default="auto",
        choices=("auto", "worklog-first", "balanced"),
        help="Source strategy for both runs.",
    )
    p.add_argument("--screen-time", default="auto", dest="screen_time", help="Screen Time collector mode.")

    p.add_argument("--today", action="store_true")
    p.add_argument("--yesterday", action="store_true")
    p.add_argument("--last-3-days", action="store_true", dest="last_3_days")
    p.add_argument("--last-week", action="store_true", dest="last_week")
    p.add_argument("--last-14-days", action="store_true", dest="last_14_days")
    p.add_argument("--last-month", action="store_true", dest="last_month")
    p.add_argument("--from", dest="date_from", metavar="YYYY-MM-DD", help="Start date (use with --to).")
    p.add_argument("--to", dest="date_to", metavar="YYYY-MM-DD", help="End date (use with --from).")

    return p.parse_args()


def _validate_date_flags(ns: argparse.Namespace) -> None:
    presets = (
        ns.today,
        ns.yesterday,
        ns.last_3_days,
        ns.last_week,
        ns.last_14_days,
        ns.last_month,
    )
    if sum(1 for x in presets if x) > 1:
        raise SystemExit("At most one of --today, --yesterday, --last-3-days, --last-week, --last-14-days, --last-month.")
    custom = bool(ns.date_from or ns.date_to)
    if custom:
        if not (ns.date_from and ns.date_to):
            raise SystemExit("Both --from and --to are required when using a custom range.")
        if any(presets):
            raise SystemExit("Do not combine --from/--to with preset range flags.")
    elif not any(presets):
        raise SystemExit(
            "Specify a date range: one of --today, --yesterday, --last-3-days, --last-week, "
            "--last-14-days, --last-month, or both --from and --to."
        )


def _options_for_compare(ns: argparse.Namespace) -> TimelogRunOptions:
    _validate_date_flags(ns)
    return TimelogRunOptions(
        date_from=ns.date_from,
        date_to=ns.date_to,
        today=ns.today,
        yesterday=ns.yesterday,
        last_3_days=ns.last_3_days,
        last_week=ns.last_week,
        last_14_days=ns.last_14_days,
        last_month=ns.last_month,
        worklog=ns.worklog,
        include_uncategorized=ns.include_uncategorized,
        source_strategy=ns.source_strategy,
        screen_time=ns.screen_time,
        output_format="json",
        quiet=True,
    )


def main() -> int:
    ns = _parse_args()
    opts = _options_for_compare(ns)
    out_dir = Path(ns.output_dir).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)

    baseline_path = str(Path(ns.baseline).expanduser())
    candidate_path = str(Path(ns.candidate).expanduser())

    print("Running baseline report...", file=sys.stderr)
    payload_a = run_report_payload(baseline_path, opts.date_from, opts.date_to, opts)
    print("Running candidate report...", file=sys.stderr)
    payload_b = run_report_payload(candidate_path, opts.date_from, opts.date_to, opts)

    a_file = out_dir / "baseline.json"
    b_file = out_dir / "candidate.json"
    a_file.write_text(json.dumps(payload_a, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    b_file.write_text(json.dumps(payload_b, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {a_file}", file=sys.stderr)
    print(f"Wrote {b_file}", file=sys.stderr)

    print(format_comparison_text(payload_a, payload_b, label_a="baseline", label_b="candidate"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
