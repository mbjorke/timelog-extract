#!/usr/bin/env python3
"""Measure timestamp parsing, so the standard rests on numbers anyone can re-run.

`docs/specs/timestamp-standard.md` §4 prefers `fromisoformat` over `strptime`.
That preference arrived as an assertion in an agent's journal (`.jules/bolt.md`)
with no script attached, which is not evidence — nobody could re-run it, on their
own interpreter or after a CPython release changed either function.

This script closes that gap. Every case below uses a format string and an input
shape taken from a real call site in this repo, verifies the alternatives return
the **identical** datetime before timing them, and reports the per-call cost next
to the ratio. Read both columns: a large ratio on a function called twice per
report is not a performance argument, and the per-call microseconds are what tell
you which is which.

    python3 scripts/bench_timestamp_parsing.py
    python3 scripts/bench_timestamp_parsing.py --iterations 500000

Exit code is 1 if any alternative disagrees with `strptime` on the parsed value.
"""

from __future__ import annotations

import argparse
import platform
import sys
import timeit
from datetime import date, datetime

# Each case: label, input, strptime format, the alternative, and where it is used.
# `alt` must return the same value as strptime for `sample` or the case fails.
CASES: list[dict] = [
    {
        "label": "date only (YYYY-MM-DD)",
        "sample": "2026-07-26",
        "fmt": "%Y-%m-%d",
        "alt_name": "fromisoformat",
        "alt": lambda s: datetime.fromisoformat(s),
        "site": "core/analytics.py::get_date_range — twice per report",
        "hot": False,
    },
    {
        "label": "worklog stamp (space, no seconds)",
        "sample": "2026-07-26 10:10",
        "fmt": "%Y-%m-%d %H:%M",
        "alt_name": "fromisoformat",
        "alt": lambda s: datetime.fromisoformat(s),
        "site": "collectors/timelog.py:26,36,78 — per worklog heading",
        "hot": False,
    },
    {
        "label": "IDE log line (space, microseconds)",
        "sample": "2026-07-26 10:10:00.123456",
        "fmt": "%Y-%m-%d %H:%M:%S.%f",
        "alt_name": "fromisoformat",
        "alt": lambda s: datetime.fromisoformat(s[:26]),
        "site": "collectors/cursor.py, vscode_fork.py — per log line, millions",
        "hot": True,
    },
    {
        "label": "compact folder name (basic format)",
        "sample": "20260709T162324",
        "fmt": "%Y%m%d",
        "alt_name": "int slicing",
        "alt": lambda s: date(int(s[:4]), int(s[4:6]), int(s[6:8])),
        "site": "collectors/cursor_log_scan.py — per launch folder, thousands",
        "hot": True,
        # strptime("%Y%m%d") only consumes the date half; compare on that.
        "strptime_input": "20260709",
        "strptime_result": lambda d: d.date(),
    },
]


def check(case: dict) -> str | None:
    """Return an error string if the alternative disagrees with strptime."""
    strp_in = case.get("strptime_input", case["sample"])
    expected = datetime.strptime(strp_in, case["fmt"])
    if "strptime_result" in case:
        expected = case["strptime_result"](expected)
    actual = case["alt"](case["sample"])
    if actual != expected:
        return f"{case['alt_name']} returned {actual!r}, strptime returned {expected!r}"
    return None


def time_case(case: dict, iterations: int) -> tuple[float, float]:
    strp_in = case.get("strptime_input", case["sample"])
    fmt = case["fmt"]
    baseline = timeit.timeit(lambda: datetime.strptime(strp_in, fmt), number=iterations)
    alt_fn = case["alt"]
    sample = case["sample"]
    alternative = timeit.timeit(lambda: alt_fn(sample), number=iterations)
    return baseline, alternative


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=int, default=200_000)
    args = parser.parse_args()
    if args.iterations <= 0:
        parser.error("--iterations must be a positive integer")

    print(f"Python {platform.python_version()} on {platform.platform()}")
    print(f"{args.iterations:,} iterations per case\n")

    failures = []
    for case in CASES:
        error = check(case)
        if error:
            failures.append(f"{case['label']}: {error}")
            print(f"MISMATCH  {case['label']}: {error}\n")
            continue

        baseline, alternative = time_case(case, args.iterations)
        per_call_base = baseline / args.iterations * 1e6
        per_call_alt = alternative / args.iterations * 1e6
        ratio = baseline / alternative if alternative else float("inf")

        print(f"{case['label']}  ({case['sample']!r})")
        print(f"  strptime          {baseline:6.3f}s   {per_call_base:6.3f} us/call")
        print(f"  {case['alt_name']:<17} {alternative:6.3f}s   {per_call_alt:6.3f} us/call")
        print(f"  ratio             {ratio:5.1f}x faster")
        print(f"  saved per call    {per_call_base - per_call_alt:6.3f} us")
        print(f"  call site         {case['site']}")
        print(f"  hot path          {'yes' if case['hot'] else 'NO — ratio is not the reason to switch'}\n")

    if failures:
        print(f"FAILED: {len(failures)} case(s) parse differently — a speedup that changes")
        print("the value is not a speedup. Fix the alternative before citing a number.")
        return 1
    print("All alternatives return values identical to strptime.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
