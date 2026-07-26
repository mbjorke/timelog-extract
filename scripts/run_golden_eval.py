#!/usr/bin/env python3
"""Golden dataset eval (docs/product/accuracy-plan.md iteration 1).

Runs all ``tests/fixtures/golden*dataset.json`` files. Each dataset drives
``run_timelog_report`` with fixture config and optional isolated HOME (for
Cursor ``state.vscdb`` regression guards).

Usage:
  python3 scripts/run_golden_eval.py --check
  python3 scripts/run_golden_eval.py --print-expectations
  python3 scripts/run_golden_eval.py --print-expectations --dataset tests/fixtures/golden_cursor_composer_dataset.json
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
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


def discover_dataset_paths(root: Path) -> list[Path]:
    fixtures = root / "tests" / "fixtures"
    return sorted(fixtures.glob("golden*dataset.json"))


def load_dataset(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def materialize_cursor_home(root: Path, dataset: dict[str, Any]) -> Path:
    rel = str(dataset.get("composer_headers_path") or "").strip()
    if not rel:
        raise ValueError("composer_headers_path required for cursor HOME materialization")
    headers_path = root / rel
    payload = json.loads(headers_path.read_text(encoding="utf-8"))
    tmp = Path(tempfile.mkdtemp(prefix="golden_cursor_home_"))
    db_dir = tmp / "Library" / "Application Support" / "Cursor" / "User" / "globalStorage"
    db_dir.mkdir(parents=True)
    conn = sqlite3.connect(db_dir / "state.vscdb")
    conn.execute("CREATE TABLE ItemTable (key TEXT PRIMARY KEY, value TEXT)")
    conn.execute(
        "INSERT INTO ItemTable VALUES (?, ?)",
        ("composer.composerHeaders", json.dumps(payload)),
    )
    conn.commit()
    conn.close()
    # collect_cursor() skips composer reads when the logs dir is missing.
    (tmp / "Library" / "Application Support" / "Cursor" / "logs").mkdir(
        parents=True, exist_ok=True
    )
    return tmp


def actual_hours_table(report: Any) -> dict[tuple[str, str], float]:
    out: dict[tuple[str, str], float] = {}
    for project_name, days in report.project_reports.items():
        for day, block in days.items():
            out[(day, project_name)] = float(block["hours"])
    return out


def compare_invariants(dataset: dict[str, Any], report: Any) -> list[str]:
    inv = dataset.get("invariants") or {}
    if not inv:
        return []
    from core.sanity_bounds import day_total_hours

    errors: list[str] = []
    day_totals = day_total_hours(report.project_reports)
    max_any_day = inv.get("max_hours_any_day")
    if max_any_day is not None:
        for day, hours in sorted(day_totals.items()):
            if hours > float(max_any_day) + 1e-6:
                errors.append(
                    f"day {day!r} total {hours}h exceeds max_hours_any_day {max_any_day}"
                )
    max_day_cap = inv.get("max_day_total_hours")
    if max_day_cap is not None:
        for day, hours in sorted(day_totals.items()):
            if hours > float(max_day_cap) + 1e-6:
                errors.append(
                    f"day {day!r} total {hours}h exceeds max_day_total_hours {max_day_cap}"
                )
    max_period = inv.get("max_period_total_hours")
    if max_period is not None:
        period_total = sum(day_totals.values())
        if period_total > float(max_period) + 1e-6:
            errors.append(
                f"period total {period_total}h exceeds max_period_total_hours {max_period}"
            )
    return errors


def compare_expectations(
    dataset: dict[str, Any], report: Any, tol: float
) -> tuple[list[str], dict[str, float]]:
    """Return (errors, kpis)."""
    actual = actual_hours_table(report)
    errors: list[str] = []
    exp = dataset.get("expectations") or []
    if exp:
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

    errors.extend(compare_invariants(dataset, report))

    unc = "Uncategorized"
    included = report.included_events
    total = len(included)
    uncat = sum(1 for e in included if e.get("project") == unc)
    uncat_rate = (uncat / total) if total else 0.0
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
        "period_total_hours": round(sum(actual.values()), 4),
    }
    return errors, kpis


def write_latest_md(
    path: Path,
    dataset_path: Path,
    dataset: dict[str, Any],
    kpis: dict[str, float],
    errors: list[str],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Golden eval — latest",
        "",
        f"**Dataset file:** `{dataset_path.relative_to(repo_root())}`",
        f"**Config:** `{dataset.get('config_path', '')}`",
        f"**Range:** {dataset.get('date_from')} .. {dataset.get('date_to')}",
        "",
        "## KPIs (this run)",
        "",
        f"- Attribution match rate (rows): {kpis['attribution_match_rate']}",
        f"- Uncategorized rate (events): {kpis['uncategorized_rate']}",
        f"- Included event count: {int(kpis['included_event_count'])}",
        f"- Period total hours: {kpis.get('period_total_hours', 0)}",
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
        lines.extend(["## Status", "", "**OK** — expectations and invariants passed.", ""])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _ensure_repo_on_path() -> Path:
    root = repo_root()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    return root


def run_single_dataset(
    dataset_path: Path,
    *,
    write_md: bool = False,
    md_path: Path | None = None,
) -> tuple[int, dict[str, float], list[str]]:
    _ensure_utc_tz()
    root = _ensure_repo_on_path()
    dataset = load_dataset(dataset_path)
    cfg = root / dataset["config_path"]
    if not cfg.is_file():
        return 2, {}, [f"missing config: {cfg}"]

    home_tmp: Path | None = None
    if dataset.get("composer_headers_path"):
        home_tmp = materialize_cursor_home(root, dataset)
        os.environ["HOME"] = str(home_tmp)

    from core.report_service import run_timelog_report

    opts = dict(dataset.get("run_options") or {})
    report = run_timelog_report(
        str(cfg),
        dataset["date_from"],
        dataset["date_to"],
        opts,
    )
    tol = 1e-4
    errors, kpis = compare_expectations(dataset, report, tol)

    if write_md and md_path is not None:
        write_latest_md(md_path, dataset_path, dataset, kpis, errors)

    if home_tmp is not None:
        import shutil

        shutil.rmtree(home_tmp, ignore_errors=True)

    if errors:
        return 1, kpis, errors
    return 0, kpis, []


def run_check(write_md: bool = True) -> int:
    root = repo_root()
    datasets = discover_dataset_paths(root)
    if not datasets:
        print("no golden datasets found", file=sys.stderr)
        return 2

    out_md = root / "docs" / "evals" / "latest.md"
    last_kpis: dict[str, float] = {}
    for ds_path in datasets:
        env = os.environ.copy()
        env["TZ"] = "UTC"
        env.pop("GOLDEN_EVAL_DATASET", None)
        proc = subprocess.run(
            [
                sys.executable,
                str(root / "scripts" / "run_golden_eval.py"),
                "--check-one",
                str(ds_path),
            ],
            cwd=str(root),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            print(proc.stderr, file=sys.stderr, end="")
            print(proc.stdout, file=sys.stderr, end="")
            return proc.returncode
        print(proc.stdout, end="")
        if write_md and ds_path == datasets[-1]:
            # Re-run last dataset in-process to refresh latest.md (subprocess already validated).
            code, last_kpis, errors = run_single_dataset(
                ds_path, write_md=True, md_path=out_md
            )
            if code != 0:
                for e in errors:
                    print(e, file=sys.stderr)
                return code
    print(f"Golden eval: OK ({len(datasets)} datasets)")
    if last_kpis:
        print(f"KPIs (last dataset): {last_kpis}")
    return 0


def print_expectations(dataset_path: Path | None) -> int:
    root = repo_root()
    ds_path = dataset_path or (root / "tests" / "fixtures" / "golden_dataset.json")
    _ensure_utc_tz()
    _ensure_repo_on_path()
    dataset = load_dataset(ds_path)
    cfg = root / dataset["config_path"]
    if not cfg.is_file():
        print(f"missing config: {cfg}", file=sys.stderr)
        return 2

    home_tmp: Path | None = None
    if dataset.get("composer_headers_path"):
        home_tmp = materialize_cursor_home(root, dataset)
        os.environ["HOME"] = str(home_tmp)

    from core.report_service import run_timelog_report

    opts = dict(dataset.get("run_options") or {})
    report = run_timelog_report(
        str(cfg),
        dataset["date_from"],
        dataset["date_to"],
        opts,
    )
    actual = actual_hours_table(report)
    print(
        json.dumps(
            [{"date": k[0], "project": k[1], "hours": v} for k, v in sorted(actual.items())],
            indent=2,
        )
    )
    if home_tmp is not None:
        import shutil

        shutil.rmtree(home_tmp, ignore_errors=True)
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Golden dataset evaluation")
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true", help="Run all golden datasets")
    group.add_argument(
        "--check-one",
        metavar="DATASET",
        help=argparse.SUPPRESS,
    )
    group.add_argument(
        "--print-expectations",
        action="store_true",
        help="Print actual hours JSON from engine (use to refresh expectations)",
    )
    p.add_argument(
        "--dataset",
        metavar="PATH",
        help="Dataset JSON for --print-expectations (default: golden_dataset.json)",
    )
    args = p.parse_args()
    if args.check_one:
        code, kpis, errors = run_single_dataset(Path(args.check_one))
        if errors:
            for e in errors:
                print(e, file=sys.stderr)
        if code == 0:
            print(f"Golden eval: OK — {args.check_one}")
            print(f"KPIs: {kpis}")
        return code
    if args.print_expectations:
        ds = Path(args.dataset) if args.dataset else None
        return print_expectations(ds)
    return run_check()


if __name__ == "__main__":
    raise SystemExit(main())
