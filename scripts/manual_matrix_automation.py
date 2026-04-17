#!/usr/bin/env python3
"""Automate checks from docs/runbooks/manual-test-matrix-0-2-x.md.

  * Deterministic block (seeded worklog, fixed dates) — CI-safe, no real Chrome/Mail needed.
  * Optional --last-month: previous calendar month, real data (your machine / repo).

Examples:

  python3 scripts/manual_matrix_automation.py --deterministic
  python3 scripts/manual_matrix_automation.py --last-month --repo-root .
  QA_MATRIX_MIN_EVENTS=10 python3 scripts/manual_matrix_automation.py --last-month
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parent.parent
ENTRY = REPO_ROOT / "timelog_extract.py"

WORKLOG_NAME = "manual_qa_worklog.md"
WORKLOG_BODY = """## 2024-01-01 09:00
- Client review https://example.com/foo Test Project

## 2024-01-01 10:15
- Follow-up https://example.com/foo docs

## 2024-01-01 11:00
- Test Project standup notes

## 2024-01-01 14:00
- Deep work Test Project

## 2024-01-02 09:30
- https://example.com/foo regression check

## 2024-01-02 15:00
- Wrap-up Test Project
"""


def previous_calendar_month_bounds() -> tuple[str, str]:
    """First and last calendar day of the month before today (local date)."""
    today = date.today()
    first_this = date(today.year, today.month, 1)
    last_prev = first_this - timedelta(days=1)
    first_prev = date(last_prev.year, last_prev.month, 1)
    return first_prev.isoformat(), last_prev.isoformat()


def _run_cli(cwd: Path, args: list[str], env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    cmd = [sys.executable, str(ENTRY), *args]
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        env={**os.environ, **(env or {})},
        check=False,
    )


def _parse_json_stdout(stdout: str) -> dict[str, Any]:
    text = stdout.strip()
    if not text:
        raise ValueError("empty stdout (expected JSON)")
    return json.loads(text)


def _walk_event_details(payload: dict[str, Any]) -> list[str]:
    """Truth payload uses days[iso_date] = { sessions: [...] }."""
    out: list[str] = []
    days = payload.get("days")
    if not isinstance(days, dict):
        return out
    for _day_key, day in days.items():
        if not isinstance(day, dict):
            continue
        for sess in day.get("sessions") or []:
            if not isinstance(sess, dict):
                continue
            for ev in sess.get("events") or []:
                if not isinstance(ev, dict):
                    continue
                d = ev.get("detail")
                if d:
                    out.append(str(d))
    return out


def _details_match_seed(payload: dict[str, Any]) -> bool:
    needles = ("example.com/foo", "Test Project")
    blob = " ".join(_walk_event_details(payload))
    return any(n in blob for n in needles)


def run_deterministic() -> None:
    """Matrix D1 + D2/D4-style checks using a temp directory (no timelog_projects.json)."""
    if not ENTRY.is_file():
        raise FileNotFoundError(f"missing entrypoint: {ENTRY}")

    with tempfile.TemporaryDirectory() as tmp:
        tdir = Path(tmp)
        wl = tdir / WORKLOG_NAME
        wl.write_text(WORKLOG_BODY, encoding="utf-8")

        # D1 — doctor
        r_doc = _run_cli(tdir, ["doctor"])
        if r_doc.returncode != 0:
            sys.stderr.write(r_doc.stdout + r_doc.stderr)
            raise SystemExit(f"doctor failed (exit {r_doc.returncode})")

        # D2 / D4 — report + JSON
        r_args = [
            "report",
            "--date-from",
            "2024-01-01",
            "--date-to",
            "2024-01-02",
            "--worklog",
            str(wl),
            "--worklog-format",
            "md",
            "--keywords",
            "test,example,foo",
            "--output-format",
            "json",
        ]
        r_rep = _run_cli(tdir, r_args)
        if r_rep.returncode != 0:
            sys.stderr.write(r_rep.stdout + r_rep.stderr)
            raise SystemExit(f"report failed (exit {r_rep.returncode})")

        payload = _parse_json_stdout(r_rep.stdout)
        if payload.get("schema") != "timelog_extract.truth_payload":
            raise SystemExit(f"unexpected schema: {payload.get('schema')!r}")
        if "version" not in payload:
            raise SystemExit("payload missing version")
        totals = payload.get("totals") or {}
        ec = int(totals.get("event_count", 0))
        if ec < 5:
            raise SystemExit(f"totals.event_count expected >= 5, got {ec}")
        if not _details_match_seed(payload):
            raise SystemExit("no event detail contained example.com/foo or Test Project")

    print("Deterministic matrix checks: OK (doctor + worklog JSON thresholds).")


def run_last_month(repo_root: Path, min_events: int) -> None:
    """Smoke: full stack for previous calendar month (uses your real sources / config)."""
    if not ENTRY.is_file():
        raise FileNotFoundError(f"missing entrypoint: {ENTRY}")
    if not repo_root.is_dir():
        raise NotADirectoryError(repo_root)

    df, dt = previous_calendar_month_bounds()
    r = _run_cli(
        repo_root,
        [
            "report",
            "--date-from",
            df,
            "--date-to",
            dt,
            "--output-format",
            "json",
        ],
    )
    if r.returncode != 0:
        sys.stderr.write(r.stdout + r.stderr)
        raise SystemExit(f"report --last-month range failed (exit {r.returncode})")

    payload = _parse_json_stdout(r.stdout)
    if payload.get("schema") != "timelog_extract.truth_payload":
        raise SystemExit(f"unexpected schema: {payload.get('schema')!r}")
    if "version" not in payload:
        raise SystemExit("payload missing version")
    ec = int((payload.get("totals") or {}).get("event_count", 0))
    if ec < min_events:
        raise SystemExit(
            f"totals.event_count {ec} < QA_MATRIX_MIN_EVENTS ({min_events}). "
            "Adjust keywords/config, widen range, or lower QA_MATRIX_MIN_EVENTS."
        )

    print(f"Last-month smoke ({df} .. {dt}): OK (event_count={ec} >= {min_events}).")


def main(argv: Iterable[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Partial automation for MANUAL_TEST_MATRIX_0_2_x.md")
    p.add_argument(
        "--deterministic",
        action="store_true",
        help="Run seeded worklog checks (fixed 2024-01-01..02 dates).",
    )
    p.add_argument(
        "--last-month",
        action="store_true",
        help="Smoke-test previous calendar month using cwd config and real sources.",
    )
    p.add_argument(
        "--repo-root",
        type=Path,
        default=Path.cwd(),
        help="Working directory for --last-month (default: current directory).",
    )
    args = p.parse_args(list(argv) if argv is not None else None)

    if not args.deterministic and not args.last_month:
        p.error("specify at least one of --deterministic or --last-month")

    if args.deterministic:
        run_deterministic()

    if args.last_month:
        min_ev = int(os.environ.get("QA_MATRIX_MIN_EVENTS", "1"))
        run_last_month(args.repo_root.resolve(), min_ev)


if __name__ == "__main__":
    main()
