#!/usr/bin/env python3
"""Run March reconciliation: baseline and A/B/C vs invoiced ground truth."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.cli import TimelogRunOptions
from core.march_reconciliation import evaluate_reconciliation
from core.report_service import run_timelog_report


def _markdown(payload: dict) -> str:
    lines = ["## March Reconciliation", ""]
    lines.append(f"- Winner by MAE: `{payload['winner']}`")
    lines.append(
        f"- Primary metric mode: `{payload.get('primary_metric_mode', 'project')}` "
        f"(winner: `{payload.get('primary_winner', payload['winner'])}`)"
    )
    lines.append("")
    lines.append("### Summary")
    for variant, summary in payload["summaries"].items():
        lines.append(
            f"- `{variant}`: mae={summary['mae']}, "
            f"predicted_total={summary['total_predicted']}, "
            f"actual_total={summary['total_actual']}, "
            f"delta={summary['total_delta']}"
        )
    lines.append("")
    if payload.get("group_summaries"):
        lines.append(f"### Grouped summary (winner: `{payload.get('winner_grouped', payload['winner'])}`)")
        for variant, summary in payload["group_summaries"].items():
            lines.append(
                f"- `{variant}`: mae={summary['mae']}, "
                f"predicted_total={summary['total_predicted']}, "
                f"actual_total={summary['total_actual']}, "
                f"delta={summary['total_delta']}"
            )
        lines.append("")
    lines.append("### Per-project (winner)")
    for row in payload["rows"][payload["winner"]]:
        lines.append(
            f"- `{row['project']}`: actual={row['actual_hours']}, "
            f"predicted={row['predicted_hours']}, abs_err={row['absolute_error']}"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--projects-config", default="timelog_projects.json")
    parser.add_argument("--ground-truth", required=True, help="JSON file: {'projects': {'Name': hours}}")
    parser.add_argument("--date-from", default="2026-03-01")
    parser.add_argument("--date-to", default="2026-03-31")
    parser.add_argument("--out-json", default="out/reconciliation/march_scorecard.json")
    parser.add_argument("--out-md", default="out/reconciliation/march_scorecard.md")
    args = parser.parse_args()

    truth_path = Path(args.ground_truth)
    truth = json.loads(truth_path.read_text(encoding="utf-8"))
    projects = truth.get("projects") or {}
    invoice_groups = truth.get("invoice_groups") or {}
    if not isinstance(projects, dict) or not projects:
        raise SystemExit("ground truth must include non-empty 'projects' object")
    if invoice_groups and not isinstance(invoice_groups, dict):
        raise SystemExit("'invoice_groups' must be an object when provided")

    options = TimelogRunOptions(
        date_from=args.date_from,
        date_to=args.date_to,
        projects_config=args.projects_config,
        include_uncategorized=True,
        quiet=True,
    )
    report = run_timelog_report(args.projects_config, args.date_from, args.date_to, options)
    payload = evaluate_reconciliation(
        report,
        {str(k): float(v) for k, v in projects.items()},
        invoice_groups={str(k): v for k, v in invoice_groups.items()} if invoice_groups else None,
    )

    out_json = Path(args.out_json)
    out_md = Path(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    out_md.write_text(_markdown(payload), encoding="utf-8")
    print(f"Wrote: {out_json}")
    print(f"Wrote: {out_md}")
    print(f"Winner by MAE: {payload['winner']}")
    if payload.get("group_summaries"):
        print(f"Winner by grouped MAE: {payload.get('winner_grouped', payload['winner'])}")
    print(
        "Primary metric mode: "
        f"{payload.get('primary_metric_mode', 'project')} "
        f"(winner: {payload.get('primary_winner', payload['winner'])})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

