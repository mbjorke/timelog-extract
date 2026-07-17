#!/usr/bin/env python3
"""Benchmark the classification + session-math hot path across git revisions.

Feeds the same synthetic dataset (from scripts/bench_synth_data.py) through
each revision's ``classify_project`` / ``group_by_day`` / ``estimate_hours_by_day``
and reports timings side by side, to locate where a performance regression
landed. Uses ``git archive`` extractions in a temp dir — never touches the
working tree or GitButler state.

Usage:
    # single run against the current working tree
    python scripts/bench_hotpath.py --run --dataset private/bench/synth_events.json

    # compare across revisions (worktree = current uncommitted tree)
    python scripts/bench_hotpath.py --compare v0.2.8 v0.2.15 v0.3.1 worktree \
        --dataset private/bench/synth_events.json --repeat 3
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
UNCATEGORIZED = "Uncategorized"


def run_benchmark(dataset_path: str, gap: int, min_session: int, min_passive: int) -> dict:
    """Time this checkout's hot path on the dataset. Imports resolve via PYTHONPATH."""
    import functools
    import inspect

    from core.analytics import estimate_hours_by_day, group_by_day
    from core.domain import classify_project, compute_sessions, session_duration_hours

    # Newer versions take an explicit ai_sources argument; older ones don't.
    if "ai_sources" in inspect.signature(session_duration_hours).parameters:
        from core.sources import AI_SOURCES

        session_duration_hours = functools.partial(session_duration_hours, ai_sources=AI_SOURCES)

    data = json.loads(Path(dataset_path).read_text())
    profiles = data["profiles"]
    local_tz = datetime.now().astimezone().tzinfo
    events = [
        {**e, "timestamp": datetime.fromisoformat(e["timestamp"])}
        for e in data["events"]
    ]

    t0 = time.perf_counter()
    for e in events:
        e["project"] = classify_project(e["detail"], profiles, UNCATEGORIZED)
    t_classify = time.perf_counter() - t0

    t0 = time.perf_counter()
    days = group_by_day(events, local_tz)
    t_group = time.perf_counter() - t0

    t0 = time.perf_counter()
    per_day = estimate_hours_by_day(
        days,
        gap,
        min_session,
        min_passive,
        compute_sessions_fn=compute_sessions,
        session_duration_hours_fn=session_duration_hours,
    )
    t_estimate = time.perf_counter() - t0

    total_hours = round(sum(d["hours"] for d in per_day.values()), 2)
    uncategorized = sum(1 for e in events if e["project"] == UNCATEGORIZED)
    return {
        "events": len(events),
        "classify_s": round(t_classify, 4),
        "group_s": round(t_group, 4),
        "estimate_s": round(t_estimate, 4),
        "total_s": round(t_classify + t_group + t_estimate, 4),
        "total_hours": total_hours,
        "uncategorized": uncategorized,
    }


def extract_revision(rev: str, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    archive = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "archive", rev],
        check=True, capture_output=True,
    )
    subprocess.run(["tar", "-x", "-C", str(dest)], input=archive.stdout, check=True)


def run_for_revision(rev: str, code_root: Path, args: argparse.Namespace) -> dict:
    env = {**os.environ, "PYTHONPATH": str(code_root)}
    cmd = [
        sys.executable, str(Path(__file__).resolve()), "--run",
        "--dataset", str(Path(args.dataset).resolve()),
        "--gap", str(args.gap),
        "--min-session", str(args.min_session),
        "--min-session-passive", str(args.min_session_passive),
        "--json",
    ]
    best: dict | None = None
    for _ in range(max(1, args.repeat)):
        proc = subprocess.run(cmd, env=env, capture_output=True, text=True)
        if proc.returncode != 0:
            return {"error": (proc.stderr or "").strip().splitlines()[-1][:120] if proc.stderr else "failed"}
        result = json.loads(proc.stdout)
        if best is None or result["total_s"] < best["total_s"]:
            best = result
    return best or {"error": "no runs"}


def compare(revs: list[str], args: argparse.Namespace) -> None:
    rows = []
    with tempfile.TemporaryDirectory(prefix="gittan-bench-") as tmp:
        for rev in revs:
            if rev == "worktree":
                code_root = REPO_ROOT
            else:
                code_root = Path(tmp) / rev.replace("/", "_")
                try:
                    extract_revision(rev, code_root)
                except subprocess.CalledProcessError as exc:
                    rows.append((rev, {"error": exc.stderr.decode(errors="replace").strip()[:120]}))
                    continue
            print(f"benchmarking {rev} …", file=sys.stderr)
            rows.append((rev, run_for_revision(rev, code_root, args)))

    header = f"{'revision':<28} {'classify':>10} {'group':>8} {'estimate':>9} {'total':>9} {'hours':>7} {'uncat':>6}"
    print(header)
    print("-" * len(header))
    for rev, r in rows:
        if "error" in r:
            print(f"{rev:<28} ERROR: {r['error']}")
            continue
        print(
            f"{rev:<28} {r['classify_s']:>9.3f}s {r['group_s']:>7.3f}s {r['estimate_s']:>8.3f}s"
            f" {r['total_s']:>8.3f}s {r['total_hours']:>7.2f} {r['uncategorized']:>6}"
        )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run", action="store_true", help="benchmark the checkout on PYTHONPATH/cwd")
    ap.add_argument("--compare", nargs="+", metavar="REV", help="revisions to compare ('worktree' = current tree)")
    ap.add_argument("--dataset", default="private/bench/synth_events.json")
    ap.add_argument("--gap", type=int, default=15)
    ap.add_argument("--min-session", type=int, default=10)
    ap.add_argument("--min-session-passive", type=int, default=5)
    ap.add_argument("--repeat", type=int, default=3, help="runs per revision; best total kept")
    ap.add_argument("--json", action="store_true", help="with --run: emit JSON")
    ns = ap.parse_args()

    if ns.run:
        # Fallback so direct `--run` finds the repo's core/; PYTHONPATH (set by
        # --compare per revision) still takes precedence since this is appended.
        sys.path.append(str(REPO_ROOT))
        result = run_benchmark(ns.dataset, ns.gap, ns.min_session, ns.min_session_passive)
        print(json.dumps(result) if ns.json else json.dumps(result, indent=2))
    elif ns.compare:
        compare(ns.compare, ns)
    else:
        ap.error("pass --run or --compare")


if __name__ == "__main__":
    main()
