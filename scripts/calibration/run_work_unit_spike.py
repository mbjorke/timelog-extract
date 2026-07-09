#!/usr/bin/env python3
"""Work-unit v2 spike: compare v1 vs work_unit_v2 attribution on a copied config.

Runs the stable engine API twice (default v1 classifier vs injected work-unit
classifier), scores the v2 run against an operator-local acceptance file, and
writes JSON + Markdown scorecards.

Operator acceptance stays outside the repo (e.g. ``~/.gittan/work-unit-acceptance.md``).
Use the committed placeholder under ``tests/fixtures/work_unit_acceptance.example.json``
for shape only — never commit real customers/hours.

Example::

    cp ~/.gittan/timelog_projects.json /tmp/projects.copy.json
    python scripts/calibration/run_work_unit_spike.py \\
      --projects-config /tmp/projects.copy.json \\
      --acceptance ~/.gittan/work-unit-acceptance.json \\
      --date-from 2026-06-01 --date-to 2026-06-30
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.config import load_profiles
from core.engine_api import run_report_payload
from core.work_unit_acceptance import (
    evaluate_spike,
    hours_by_project,
    load_acceptance_file,
    scorecard_markdown,
)
from core.work_unit_classifier import ATTRIBUTION_CLASSIFIER_WORK_UNIT_V2


def _load_profiles(projects_config: str) -> list:
    profiles, _cfg, _workspace = load_profiles(
        projects_config,
        SimpleNamespace(project="Uncategorized", keywords="", email=""),
    )
    return list(profiles or [])


def _run_payload(
    projects_config: str,
    date_from: str,
    date_to: str,
    *,
    attribution_classifier: str,
) -> dict:
    return run_report_payload(
        projects_config,
        date_from,
        date_to,
        {
            "include_uncategorized": True,
            "quiet": True,
            "attribution_classifier": attribution_classifier,
        },
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Work-unit v2 spike scorecard (v1 vs work_unit_v2 on copied config)."
    )
    parser.add_argument(
        "--projects-config",
        required=True,
        help="Path to a *copied* projects config (never the only live file).",
    )
    parser.add_argument(
        "--acceptance",
        required=True,
        help="Operator-local acceptance JSON or markdown (outside repo).",
    )
    parser.add_argument("--date-from", default=None)
    parser.add_argument("--date-to", default=None)
    parser.add_argument(
        "--out-json",
        default="out/work-unit-spike/scorecard.json",
    )
    parser.add_argument(
        "--out-md",
        default="out/work-unit-spike/scorecard.md",
    )
    parser.add_argument(
        "--skip-baseline",
        action="store_true",
        help="Only run work_unit_v2 (faster; no before Uncategorized).",
    )
    args = parser.parse_args()

    acceptance = load_acceptance_file(args.acceptance)
    date_from = args.date_from or acceptance.date_from or None
    date_to = args.date_to or acceptance.date_to or None
    if not date_from or not date_to:
        print("error: date_from/date_to required (flags or acceptance file)", file=sys.stderr)
        return 2

    profiles = _load_profiles(args.projects_config)

    baseline_unc: float | None = None
    if not args.skip_baseline:
        baseline = _run_payload(
            args.projects_config,
            date_from,
            date_to,
            attribution_classifier="v1",
        )
        baseline_unc = float(hours_by_project(baseline).get("Uncategorized", 0.0) or 0.0)

    spike_payload = _run_payload(
        args.projects_config,
        date_from,
        date_to,
        attribution_classifier=ATTRIBUTION_CLASSIFIER_WORK_UNIT_V2,
    )
    verdict = evaluate_spike(
        spike_payload,
        acceptance,
        profiles=profiles,
        baseline_uncategorized=baseline_unc,
    )

    payload = {
        "date_from": date_from,
        "date_to": date_to,
        "projects_config": args.projects_config,
        "acceptance": acceptance.as_dict(),
        "baseline_uncategorized_hours": baseline_unc,
        "verdict": verdict.as_dict(),
        "after_hours_by_line": hours_by_project(spike_payload),
    }

    out_json = Path(args.out_json)
    out_md = Path(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    out_md.write_text(
        scorecard_markdown(verdict, baseline_uncategorized=baseline_unc),
        encoding="utf-8",
    )
    print(f"Decision: {verdict.decision}")
    print(f"Wrote: {out_json}")
    print(f"Wrote: {out_md}")
    return 0 if verdict.decision == "GO" else 1


if __name__ == "__main__":
    raise SystemExit(main())
