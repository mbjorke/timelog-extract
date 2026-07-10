#!/usr/bin/env python3
"""Seed a work-unit acceptance table from a clean v1 run (same build/config/flags).

Use this for a fair A/B: expected hours = v1 on tip, then score work_unit_v2 with
``run_work_unit_spike.py`` without mixing invoice-time freezes or other product
versions into the facit.

Never commit the written acceptance file (operator-local under ``~/.gittan/``).

Example::

    cp ~/.gittan/timelog_projects.json /tmp/projects.copy.json
    python scripts/calibration/prepare_work_unit_ab_acceptance.py \\
      --projects-config /tmp/projects.copy.json \\
      --date-from 2026-06-01 --date-to 2026-06-30 \\
      --out ~/.gittan/work-unit-acceptance.json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.config import load_profiles
from core.engine_api import run_report_payload
from core.work_unit_acceptance import UNCATEGORIZED, hours_by_project


def _customer_map(profiles: list) -> dict[str, str]:
    out: dict[str, str] = {}
    for profile in profiles:
        name = str(profile.get("name") or "").strip()
        if not name:
            continue
        out[name] = str(profile.get("customer") or name).strip() or name
    return out


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Seed work-unit acceptance JSON from a v1 report (clean A/B facit)."
    )
    parser.add_argument(
        "--projects-config",
        required=True,
        help="Path to a *copied* projects config (never the only live file).",
    )
    parser.add_argument("--date-from", required=True)
    parser.add_argument("--date-to", required=True)
    parser.add_argument(
        "--out",
        required=True,
        help="Operator-local acceptance JSON path (e.g. ~/.gittan/work-unit-acceptance.json).",
    )
    parser.add_argument(
        "--min-hours",
        type=float,
        default=0.25,
        help="Include lines with at least this many v1 hours (default 0.25).",
    )
    parser.add_argument(
        "--tolerance-hours",
        type=float,
        default=0.5,
        help="Scorecard tolerance when comparing v2 to this v1 facit.",
    )
    parser.add_argument(
        "--uncategorized-slack",
        type=float,
        default=0.0,
        help="Add this many hours to v1 Uncategorized for primary_uncategorized_max.",
    )
    parser.add_argument(
        "--screen-time",
        default="off",
        help="Passed through to the report options (default off).",
    )
    args = parser.parse_args()

    out_path = Path(args.out).expanduser()
    if out_path.exists():
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        backup = out_path.with_suffix(out_path.suffix + f".pre-ab-{stamp}")
        backup.write_text(out_path.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"backed up existing acceptance → {backup}")

    profiles, _cfg, _workspace = load_profiles(
        args.projects_config,
        SimpleNamespace(project="Uncategorized", keywords="", email=""),
    )
    profiles_list = list(profiles or [])
    customers = _customer_map(profiles_list)

    print(
        f"running v1 facit {args.date_from} → {args.date_to} "
        f"(screen-time={args.screen_time}) …",
        flush=True,
    )
    payload = run_report_payload(
        args.projects_config,
        args.date_from,
        args.date_to,
        {
            "include_uncategorized": True,
            "quiet": True,
            "attribution_classifier": "v1",
            "screen_time": args.screen_time,
        },
    )
    hours = hours_by_project(payload)
    unc = float(hours.get(UNCATEGORIZED, 0.0) or 0.0)
    generator = payload.get("generator") if isinstance(payload, dict) else {}

    lines: list[dict[str, object]] = []
    for name, value in sorted(hours.items(), key=lambda kv: -kv[1]):
        if name == UNCATEGORIZED:
            continue
        if value < args.min_hours:
            continue
        lines.append(
            {
                "customer": customers.get(name, name),
                "line": name,
                "expected_hours": round(float(value), 2),
            }
        )

    table = {
        "date_from": args.date_from,
        "date_to": args.date_to,
        "tolerance_hours": args.tolerance_hours,
        "primary_uncategorized_max": round(unc + args.uncategorized_slack, 2),
        "notes": (
            "CLEAN A/B facit: expected_hours = v1 on the same tip build/config/flags "
            f"(generator={generator}). Not an invoice freeze. Score with "
            "scripts/calibration/run_work_unit_spike.py against work_unit_v2."
        ),
        "lines": lines,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(table, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    total = sum(float(row["expected_hours"]) for row in lines)
    print(f"wrote {out_path}")
    print(f"lines={len(lines)} sum_expected={total:.2f}h uncategorized_max={table['primary_uncategorized_max']}")
    print("next:")
    print(
        "  .venv/bin/python scripts/calibration/run_work_unit_spike.py \\\n"
        f"    --projects-config {args.projects_config} \\\n"
        f"    --acceptance {out_path} \\\n"
        f"    --date-from {args.date_from} --date-to {args.date_to}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
