#!/usr/bin/env python3
"""Run a repeatable month-end invoice check with optional end-date sanity diff."""

from __future__ import annotations

import argparse
import json
from datetime import date, timedelta
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.cli import TimelogRunOptions
from core.report_service import run_timelog_report


def _project_hours(report) -> dict[str, float]:
    return {
        str(name): round(sum(float(day.get("hours", 0.0)) for day in days.values()), 6)
        for name, days in report.project_reports.items()
    }


def _top_deltas(current: dict[str, float], previous: dict[str, float], limit: int = 8) -> list[dict[str, float | str]]:
    names = sorted(set(current) | set(previous), key=str.lower)
    out: list[dict[str, float | str]] = []
    for name in names:
        delta = float(current.get(name, 0.0) - previous.get(name, 0.0))
        if abs(delta) < 1e-9:
            continue
        out.append(
            {
                "project": name,
                "current_hours": round(float(current.get(name, 0.0)), 6),
                "previous_hours": round(float(previous.get(name, 0.0)), 6),
                "delta_hours": round(delta, 6),
            }
        )
    out.sort(key=lambda row: abs(float(row["delta_hours"])), reverse=True)
    return out[:limit]


def _markdown(payload: dict) -> str:
    lines = [
        "# Month-end invoice check",
        "",
        f"- Period: `{payload['range']['from']}` -> `{payload['range']['to']}`",
        f"- Invoice mode: `{payload['invoice_mode']}`",
        f"- Ground truth: `{payload['ground_truth_path']}`",
        f"- Report total (raw timeline): `{payload['report_total_hours']:.3f}h`",
        f"- Ground truth projects total: `{payload['ground_truth_total_hours']:.3f}h`",
        "",
    ]
    prev = payload.get("previous_day_comparison")
    if isinstance(prev, dict):
        lines.extend(
            [
                "## End-date sanity check",
                "",
                f"- Previous day range total: `{prev['previous_total_hours']:.3f}h`",
                f"- Current minus previous: `{prev['delta_hours']:+.3f}h`",
                "",
            ]
        )
        top = prev.get("top_project_deltas") or []
        if top:
            lines.append("Top project deltas:")
            for row in top:
                lines.append(
                    f"- `{row['project']}`: `{float(row['delta_hours']):+.3f}h` "
                    f"({float(row['previous_hours']):.3f} -> {float(row['current_hours']):.3f})"
                )
            lines.append("")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--projects-config", default="timelog_projects.json")
    parser.add_argument("--ground-truth", required=True)
    parser.add_argument("--date-from", required=True)
    parser.add_argument("--date-to", required=True)
    parser.add_argument("--invoice-mode", default="calibrated-a", choices=["baseline", "calibrated-a"])
    parser.add_argument("--skip-prev-day-check", action="store_true")
    parser.add_argument("--out-json", default="out/reconciliation/month_end_invoice_check.json")
    parser.add_argument("--out-md", default="out/reconciliation/month_end_invoice_check.md")
    args = parser.parse_args()

    truth_path = Path(args.ground_truth).expanduser()
    truth = json.loads(truth_path.read_text(encoding="utf-8"))
    truth_projects = {str(k): float(v) for k, v in (truth.get("projects") or {}).items()}

    options = TimelogRunOptions(
        projects_config=args.projects_config,
        date_from=args.date_from,
        date_to=args.date_to,
        include_uncategorized=False,
        quiet=True,
        invoice_mode=args.invoice_mode,
        invoice_ground_truth=str(truth_path),
    )
    report = run_timelog_report(options.projects_config, options.date_from, options.date_to, options)
    current_project_hours = _project_hours(report)
    report_total = round(sum(float(day.get("hours", 0.0)) for day in report.overall_days.values()), 6)

    payload: dict[str, object] = {
        "range": {"from": args.date_from, "to": args.date_to},
        "invoice_mode": args.invoice_mode,
        "ground_truth_path": str(truth_path),
        "report_total_hours": report_total,
        "ground_truth_total_hours": round(sum(truth_projects.values()), 6),
        "projects": current_project_hours,
        "ground_truth_projects": truth_projects,
    }

    if not args.skip_prev_day_check:
        to_date = date.fromisoformat(args.date_to)
        prev_to = (to_date - timedelta(days=1)).isoformat()
        prev_options = TimelogRunOptions(
            projects_config=args.projects_config,
            date_from=args.date_from,
            date_to=prev_to,
            include_uncategorized=False,
            quiet=True,
            invoice_mode=args.invoice_mode,
            invoice_ground_truth=str(truth_path),
        )
        prev_report = run_timelog_report(
            prev_options.projects_config,
            prev_options.date_from,
            prev_options.date_to,
            prev_options,
        )
        prev_project_hours = _project_hours(prev_report)
        prev_total = round(sum(float(day.get("hours", 0.0)) for day in prev_report.overall_days.values()), 6)
        payload["previous_day_comparison"] = {
            "range_to": prev_to,
            "previous_total_hours": prev_total,
            "delta_hours": round(report_total - prev_total, 6),
            "top_project_deltas": _top_deltas(current_project_hours, prev_project_hours),
        }

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

