#!/usr/bin/env python3
"""Run March reconciliation: baseline and A/B/C vs invoiced ground truth."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.calibration.reconciliation import evaluate_reconciliation
from core.cli import TimelogRunOptions
from core.report_service import run_timelog_report


def _markdown(payload: dict) -> str:
    lines = ["## March Reconciliation", ""]
    lines.append(f"- Winner by MAE: `{payload['winner']}`")
    lines.append(f"- Primary metric mode: `{payload.get('primary_metric_mode', 'project')}`")
    lines.append("")
    for variant, summary in payload["summaries"].items():
        lines.append(f"- `{variant}`: mae={summary['mae']}, delta={summary['total_delta']}")
    return "\n".join(lines) + "\n"


def main() -> int:
    """
    CLI entrypoint that runs the March reconciliation flow and emits JSON and Markdown scorecards.
    
    Parses command-line arguments for project configuration, ground-truth file, date range, and output paths; loads the ground-truth JSON; generates a timelog report and evaluates reconciliation against the ground truth; writes a formatted JSON payload and a Markdown summary to the specified output files and prints the output paths.
    
    Returns:
        int: 0 on successful completion.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--projects-config", default="timelog_projects.json")
    parser.add_argument("--ground-truth", required=True)
    parser.add_argument("--date-from", default="2026-03-01")
    parser.add_argument("--date-to", default="2026-03-31")
    parser.add_argument("--out-json", default="out/reconciliation/march_scorecard.json")
    parser.add_argument("--out-md", default="out/reconciliation/march_scorecard.md")
    args = parser.parse_args()

    truth = json.loads(Path(args.ground_truth).read_text(encoding="utf-8"))
    projects = truth.get("projects") or {}
    invoice_groups = truth.get("invoice_groups") or {}
    options = TimelogRunOptions(
        projects_config=args.projects_config,
        date_from=args.date_from,
        date_to=args.date_to,
        include_uncategorized=True,
        quiet=True,
    )
    report = run_timelog_report(options.projects_config, options.date_from, options.date_to, options)
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

