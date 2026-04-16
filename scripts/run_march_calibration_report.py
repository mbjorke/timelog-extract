#!/usr/bin/env python3
"""Run combined March calibration (invoice reconciliation + screen-time gap)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.cli import TimelogRunOptions
from core.march_calibration import build_march_calibration_payload
from core.report_service import run_timelog_report


def _markdown(payload: dict) -> str:
    recon = payload["reconciliation"]
    gap = payload["screen_time_gap"]
    lines: list[str] = ["## March Calibration Report", ""]
    lines.append(f"- Winner by invoice MAE: `{payload['winner_by_invoice_mae']}`")
    lines.append("")
    lines.append("### Reconciliation summary")
    for variant, summary in recon["summaries"].items():
        lines.append(
            f"- `{variant}`: mae={summary['mae']}, predicted_total={summary['total_predicted']}, "
            f"actual_total={summary['total_actual']}, delta={summary['total_delta']}"
        )
    lines.append("")
    totals = gap["totals"]
    lines.append("### Screen-time gap summary")
    lines.append(
        f"- estimated={totals['estimated_hours']}h, screen={totals['screen_time_hours']}h, "
        f"coverage={totals['coverage_ratio']}, unexplained={totals['unexplained_screen_time_hours']}h, "
        f"over-attributed={totals['over_attributed_hours']}h"
    )
    lines.append("")
    lines.append("### Largest project gap allocations")
    for name, value in list(gap["project_allocated_gap_hours"].items())[:10]:
        lines.append(f"- `{name}`: {value:+.4f}h")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--projects-config", default="timelog_projects.json")
    parser.add_argument("--ground-truth", required=True, help="JSON file: {'projects': {'Name': hours}}")
    parser.add_argument("--date-from", default="2026-03-01")
    parser.add_argument("--date-to", default="2026-03-31")
    parser.add_argument("--out-json", default="out/reconciliation/march_calibration.json")
    parser.add_argument("--out-md", default="out/reconciliation/march_calibration.md")
    args = parser.parse_args()

    truth = json.loads(Path(args.ground_truth).read_text(encoding="utf-8"))
    projects = truth.get("projects") or {}
    if not isinstance(projects, dict) or not projects:
        raise SystemExit("ground truth must include non-empty 'projects' object")

    options = TimelogRunOptions(
        date_from=args.date_from,
        date_to=args.date_to,
        projects_config=args.projects_config,
        include_uncategorized=True,
        quiet=True,
        screen_time="on",
    )
    report = run_timelog_report(args.projects_config, args.date_from, args.date_to, options)
    payload = build_march_calibration_payload(report, {str(k): float(v) for k, v in projects.items()})

    out_json = Path(args.out_json)
    out_md = Path(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    out_md.write_text(_markdown(payload), encoding="utf-8")
    print(f"Wrote: {out_json}")
    print(f"Wrote: {out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

