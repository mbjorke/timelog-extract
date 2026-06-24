#!/usr/bin/env python3
"""Read-only volume & footprint spike for the evidence shadow log (GH-151).

Runs the existing collectors via the stable engine API, builds in-memory
evidence records, and reports how much durable evidence the shadow log would
hold plus a storage-engine recommendation. Creates NO durable store and writes
only a measurement report under out/ (or --out).

Usage:
  python scripts/run_evidence_volume_spike.py --today
  python scripts/run_evidence_volume_spike.py --from 2026-06-01 --to 2026-06-18
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.engine_api import run_report_payload
from core.evidence_volume import PROVISIONAL_ENGINE_THRESHOLD_DAILY_MB, build_spike_report


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--projects-config", default="timelog_projects.json")
    p.add_argument("--worklog", default=None)
    p.add_argument("--from", dest="date_from", default=None, metavar="YYYY-MM-DD")
    p.add_argument("--to", dest="date_to", default=None, metavar="YYYY-MM-DD")
    p.add_argument("--today", action="store_true")
    p.add_argument("--last-week", action="store_true")
    p.add_argument(
        "--threshold-mb",
        type=float,
        default=PROVISIONAL_ENGINE_THRESHOLD_DAILY_MB,
        help="Provisional daily-MB engine gate (calibrate from real runs).",
    )
    p.add_argument("--out", default=None, metavar="PATH", help="Report JSON path.")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    options: Dict[str, Any] = {
        "today": args.today,
        "last_week": args.last_week,
        # Measure the full firehose the shadow log would capture, not just the
        # categorized subset.
        "include_uncategorized": True,
        "quiet": True,
        "screen_time": "off",
    }
    if args.worklog:
        options["worklog"] = args.worklog

    print("Running read-only evidence-volume spike (no durable store created)...", file=sys.stderr)
    payload = run_report_payload(args.projects_config, args.date_from, args.date_to, options)
    report = build_spike_report(payload, threshold_daily_mb=args.threshold_mb)

    out_path = (
        Path(args.out).expanduser()
        if args.out
        else REPO_ROOT / "out" / f"evidence-volume-spike-{datetime.now():%Y%m%dT%H%M%S}.json"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    totals = report["totals"]
    rec = report["engine_recommendation"]
    fp = report["footprint_projection"]
    print(
        f"records: {totals['evidence_records']} "
        f"(raw {totals['raw_collected']}, unique fp {totals['unique_fingerprints']}, "
        f"dedup_ratio {totals['dedup_ratio']})"
    )
    print(
        f"footprint: ~{fp['daily_jsonl_mb']} MB/day JSONL "
        f"(~{fp['yearly_jsonl_mb']} MB/yr), avg {fp['measured_avg_record_bytes']} B/record"
    )
    print(f"recommended engine: {rec['recommended']} (gate {rec['threshold_daily_mb']:g} MB/day)")
    print(f"report: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
