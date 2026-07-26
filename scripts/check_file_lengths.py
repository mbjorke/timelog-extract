#!/usr/bin/env python3
"""Report tracked Python files above the recommended line count.

File length is a **recommendation, not a gate**. Long files are worth a look —
they are often a sign that a module grew two responsibilities — but length alone
never says the code is wrong, and a size limit that fails the build makes
splitting a deadline problem instead of a design one.

By default this script reports and exits 0, which is how CI runs it. ``--strict``
opts into a hard failure (exit 1 when a file exceeds ``--max-lines``) for anyone
who wants the cap enforced locally.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def tracked_python_files(repo_root: Path) -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "*.py"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    )
    files = []
    for raw in result.stdout.splitlines():
        path = raw.strip()
        if not path:
            continue
        if path.startswith("build/"):
            continue
        files.append(repo_root / path)
    return files


def count_lines(path: Path) -> int:
    try:
        return sum(1 for _ in path.open("r", encoding="utf-8"))
    except UnicodeDecodeError:
        return sum(1 for _ in path.open("r", encoding="latin-1"))


def classify_lengths(counts, max_lines: int, warn_lines: int):
    """Split (rel_path, lines) pairs into over-limit files and approaching ones.

    Both lists are advisory. The split is kept so the report can distinguish
    "past the recommendation" from "getting close", which is useful signal even
    when nothing fails.
    """
    violations, warnings = [], []
    for rel_path, lines in counts:
        if lines > max_lines:
            violations.append((rel_path, lines))
        elif warn_lines <= lines <= max_lines:
            warnings.append((rel_path, lines))
    return violations, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--max-lines",
        type=int,
        default=500,
        help="Recommended maximum lines per file (advisory unless --strict).",
    )
    parser.add_argument(
        "--warn-lines",
        type=int,
        default=460,
        help="Also list files at or above this many lines — the approaching-the-recommendation band.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero when a file exceeds --max-lines (opt-in enforcement).",
    )
    args = parser.parse_args()
    warn_lines = min(args.warn_lines, args.max_lines)

    repo_root = Path(__file__).resolve().parent.parent
    counts = [
        (path.relative_to(repo_root), count_lines(path))
        for path in tracked_python_files(repo_root)
    ]
    violations, warnings = classify_lengths(counts, args.max_lines, warn_lines)

    if warnings:
        print(f"Approaching the {args.max_lines}-line recommendation:")
        for rel_path, lines in sorted(warnings, key=lambda item: item[1], reverse=True):
            print(f"- {rel_path}: {lines} ({args.max_lines - lines} to go)")

    if violations:
        label = "Files over" if args.strict else "Above the recommendation (advisory)"
        print(f"{label} {args.max_lines} lines:")
        for rel_path, lines in sorted(violations, key=lambda item: item[1], reverse=True):
            print(f"- {rel_path}: {lines}")
        if args.strict:
            return 1
        print("Not a failure — split when a file has two jobs, not when it hits a number.")
        return 0

    print(f"OK: all tracked Python files are <= {args.max_lines} lines.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
