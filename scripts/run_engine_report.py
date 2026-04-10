#!/usr/bin/env python3
"""Practical runner for the extension-facing engine API."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Dict

# Ensure repo root is importable when executed as a script.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.engine_api import run_report_with_optional_pdf


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Run timelog through core.engine_api and print a concise summary."
    )
    p.add_argument("--projects-config", default="timelog_projects.json")
    p.add_argument("--worklog", default="TIMELOG.md")
    p.add_argument("--from", dest="date_from", default=None, metavar="YYYY-MM-DD")
    p.add_argument("--to", dest="date_to", default=None, metavar="YYYY-MM-DD")
    p.add_argument("--today", action="store_true")
    p.add_argument("--include-uncategorized", action="store_true")
    p.add_argument("--pdf", action="store_true", help="Generate invoice PDF.")
    p.add_argument(
        "--json-file",
        default=None,
        metavar="PATH",
        help="Optional path to write full payload JSON.",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    options: Dict[str, Any] = {
        "today": args.today,
        "worklog": args.worklog,
        "include_uncategorized": args.include_uncategorized,
        "quiet": True,
        "screen_time": "off",
    }
    result = run_report_with_optional_pdf(
        args.projects_config,
        args.date_from,
        args.date_to,
        options,
        generate_pdf=args.pdf,
    )
    payload = result["payload"]
    totals = payload.get("totals", {})
    print("schema:", payload.get("schema"))
    print("version:", payload.get("version"))
    print(
        "totals:",
        f"hours={totals.get('hours_estimated', 0)}",
        f"days={totals.get('days_with_activity', 0)}",
        f"events={totals.get('event_count', 0)}",
    )
    if result.get("pdf_path"):
        print("pdf_path:", result["pdf_path"])
    if args.json_file:
        out = Path(args.json_file).expanduser()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("json_file:", str(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

