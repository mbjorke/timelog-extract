#!/usr/bin/env python3
"""Run combined March calibration (invoice reconciliation + screen-time gap)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.calibration.report import build_march_calibration_payload
from core.cli import TimelogRunOptions
from core.report_service import run_timelog_report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--projects-config", default="timelog_projects.json")
    parser.add_argument("--ground-truth", required=True)
    parser.add_argument("--date-from", default="2026-03-01")
    parser.add_argument("--date-to", default="2026-03-31")
    parser.add_argument("--out-json", default="out/reconciliation/march_calibration.json")
    parser.add_argument("--out-md", default="out/reconciliation/march_calibration.md")
    args = parser.parse_args()

    truth = json.loads(Path(args.ground_truth).read_text(encoding="utf-8"))
    projects = truth.get("projects") or {}
    invoice_groups = truth.get("invoice_groups") or {}
    options = TimelogRunOptions(
        date_from=args.date_from,
        date_to=args.date_to,
        projects_config=args.projects_config,
        include_uncategorized=True,
        quiet=True,
        screen_time="on",
    )
    report = run_timelog_report(args.projects_config, args.date_from, args.date_to, options)
    payload = build_march_calibration_payload(
        report,
        {str(k): float(v) for k, v in projects.items()},
        invoice_groups={str(k): v for k, v in invoice_groups.items()} if invoice_groups else None,
    )
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

