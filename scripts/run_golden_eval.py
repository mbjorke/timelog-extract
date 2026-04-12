#!/usr/bin/env python3
"""Golden dataset eval (docs/ACCURACY_PLAN.md iteration 1).

Loads tests/fixtures/golden_dataset.json, runs run_timelog_report with fixture config,
compares per-(date, project) hours. Writes docs/evals/latest.md on success.

Usage:
  python3 scripts/run_golden_eval.py --check
  python3 scripts/run_golden_eval.py --print-expectations   # regenerate JSON hours from engine
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any


def _ensure_utc_tz() -> None:
    """Match CI/local day boundaries; must run before importing report_service."""
    os.environ["TZ"] = "UTC"
    if hasattr(time, "tzset"):
        time.tzset()


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def load_dataset(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def actual_hours_table(report: Any) -> dict[tuple[str, str], float]:
    out: dict[tuple[str, str], float] = {}
    for project_name, days in report.project_reports.items():
        for day, block in days.items():
            out[(day, project_name)] = float(block["hours"])
    return out


def compare_expectations(
    dataset: dict[str, Any], report: Any, tol: float
) -> tuple[list[str], dict[str, float]]:
    """Return (errors, kpis)."""
    actual = actual_hours_table(report)
    errors: list[str] = []
    exp = dataset["expectations"]
    expected_keys = {(row["date"], row["project"]) for row in exp}
    unexpected = sorted(set(actual.keys()) - expected_keys)
    if unexpected:
        errors.append(f"unexpected keys present: {unexpected}")
    for row in exp:
        key = (row["date"], row["project"])
        want = float(row["hours"])
        got = actual.get(key)
        if got is None:
            errors.append(f"missing {key!r} (have keys: {sorted(actual.keys())})")
            continue
        if abs(got - want) > tol:
            errors.append(f"{key!r} hours want {want} got {got} (tol {tol})")

    # Minimal KPIs from included events (attribution vs Uncategorized)
    unc = "Uncategorized"
    included = report.included_events
    total = len(included)
    uncat = sum(1 for e in included if e.get("project") == unc)
    uncat_rate = (uncat / total) if total else 0.0
    # Simple attribution: among expectations, did each row's project appear for that day?
    attrib_ok = 0
    attrib_total = len(exp)
    for row in exp:
        key = (row["date"], row["project"])
        if key in actual and abs(actual[key] - float(row["hours"])) <= tol:
            attrib_ok += 1
    attrib_acc = (attrib_ok / attrib_total) if attrib_total else 1.0

    kpis = {
        "attribution_match_rate": round(attrib_acc, 4),
        "uncategorized_rate": round(uncat_rate, 4),
        "included_event_count": float(total),
    }
    return errors, kpis


def write_latest_md(path: Path, dataset: dict[str, Any], kpis: dict[str, float], errors: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Golden eval — latest",
        "",
        f"**Dataset:** `{dataset.get('config_path', '')}`",
        f"**Range:** {dataset.get('date_from')} .. {dataset.get('date_to')}",
        "",
        "## KPIs (this run)",
        "",
        f"- Attribution match rate (rows): {kpis['attribution_match_rate']}",
        f"- Uncategorized rate (events): {kpis['uncategorized_rate']}",
        f"- Included event count: {int(kpis['included_event_count'])}",
        "",
        "## ACCURACY_PLAN targets (reference)",
        "",
        "- Attribution accuracy: >= 0.85",
        "- Uncategorized rate: <= 0.15",
        "",
    ]
    if errors:
        lines.extend(["## Status", "", "**FAILED**", ""])
        lines.extend(f"- {e}" for e in errors)
    else:
        lines.extend(["## Status", "", "**OK** — all golden rows matched within tolerance.", ""])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _ensure_repo_on_path() -> Path:
    root = repo_root()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    return root


def run_check(write_md: bool = True) -> int:
    _ensure_utc_tz()
    root = _ensure_repo_on_path()
    from core.report_service import run_timelog_report
    ds_path = root / "tests" / "fixtures" / "golden_dataset.json"
    dataset = load_dataset(ds_path)
    cfg = root / dataset["config_path"]
    if not cfg.is_file():
        print(f"missing config: {cfg}", file=sys.stderr)
        return 2

    opts = dict(dataset.get("run_options") or {})
    report = run_timelog_report(
        str(cfg),
        dataset["date_from"],
        dataset["date_to"],
        opts,
    )
    tol = 1e-4
    errors, kpis = compare_expectations(dataset, report, tol)

    out_md = root / "docs" / "evals" / "latest.md"
    if write_md:
        write_latest_md(out_md, dataset, kpis, errors)

    if errors:
        for e in errors:
            print(e, file=sys.stderr)
        return 1
    print("Golden eval: OK")
    print(f"KPIs: {kpis}")
    return 0


def print_expectations() -> int:
    _ensure_utc_tz()
    root = _ensure_repo_on_path()
    from core.report_service import run_timelog_report
    ds_path = root / "tests" / "fixtures" / "golden_dataset.json"
    dataset = load_dataset(ds_path)
    cfg = root / dataset["config_path"]
    if not cfg.is_file():
        print(f"missing config: {cfg}", file=sys.stderr)
        return 2
    opts = dict(dataset.get("run_options") or {})
    report = run_timelog_report(
        str(cfg),
        dataset["date_from"],
        dataset["date_to"],
        opts,
    )
    actual = actual_hours_table(report)
    print(json.dumps([{"date": k[0], "project": k[1], "hours": v} for k, v in sorted(actual.items())], indent=2))
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Golden dataset evaluation")
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true", help="Run comparison and write docs/evals/latest.md")
    group.add_argument(
        "--print-expectations",
        action="store_true",
        help="Print actual hours JSON from engine (use to refresh golden_dataset.json)",
    )
    args = p.parse_args()
    if args.print_expectations:
        return print_expectations()
    return run_check()


if __name__ == "__main__":
    raise SystemExit(main())
