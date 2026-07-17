"""One-off diagnostic: time each ``git branch --show-current`` call the Cursor
agent-turns collector makes for a date range, to find which workspace root(s)
are slow.

Not part of the CLI; run directly from the repo root:

    .venv/bin/python scripts/diag_cursor_git_timing.py [--from YYYY-MM-DD] [--to YYYY-MM-DD]

Defaults to the same 30-day window ``get_date_range`` uses when no dates are
given. Prints one line per distinct workspace root actually probed, sorted
slowest first, plus a total.
"""

from __future__ import annotations

import argparse
import cProfile
import pstats
import time
from datetime import datetime
from pathlib import Path

import collectors.cursor_agent_turns as cat
from collectors.cursor_glass_meta import git_branch_leaf_at_path as real_git_branch_leaf_at_path
from core.analytics import get_date_range

_timings: list[tuple[str, float, str | None]] = []


def _timed_git_branch_leaf_at_path(repo_path: str):
    start = time.perf_counter()
    result = real_git_branch_leaf_at_path(repo_path)
    elapsed = time.perf_counter() - start
    _timings.append((repo_path, elapsed, result))
    return result


def _classify_project_stub(_text, _profiles=None):
    return "diagnostic"


def _make_event_stub(source, ts, detail, project, anchors=None):
    return {"source": source, "timestamp": ts, "detail": detail, "project": project, "anchors": anchors}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from", dest="date_from", default=None)
    parser.add_argument("--to", dest="date_to", default=None)
    args = parser.parse_args()

    home = Path.home()
    local_tz = datetime.now().astimezone().tzinfo
    dt_from, dt_to = get_date_range(args.date_from, args.date_to, local_tz)
    print(f"Window: {dt_from} .. {dt_to}")

    cat.git_branch_leaf_at_path = _timed_git_branch_leaf_at_path

    profiler = cProfile.Profile()
    wall_start = time.perf_counter()
    profiler.enable()
    events, _covered = cat.collect_cursor_agent_turns(
        profiles=[],
        dt_from=dt_from,
        dt_to=dt_to,
        home=home,
        local_tz=local_tz,
        classify_project=_classify_project_stub,
        make_event=_make_event_stub,
    )
    profiler.disable()
    wall_elapsed = time.perf_counter() - wall_start

    print(f"\ncollect_cursor_agent_turns: {len(events)} events, {wall_elapsed:.2f}s wall total")
    print(f"git branch --show-current calls: {len(_timings)}")
    print(f"{'seconds':>10}  {'branch':<20}  path")
    for path, elapsed, result in sorted(_timings, key=lambda row: row[1], reverse=True):
        print(f"{elapsed:>10.3f}  {str(result):<20}  {path}")

    if _timings:
        total_git = sum(elapsed for _p, elapsed, _r in _timings)
        print(f"\nTotal time inside git subprocess calls: {total_git:.2f}s")

    print("\n--- top 20 by self time (tottime) ---")
    pstats.Stats(profiler).sort_stats("tottime").print_stats(20)
    print("\n--- top 20 by cumulative time ---")
    pstats.Stats(profiler).sort_stats("cumulative").print_stats(20)


if __name__ == "__main__":
    main()
