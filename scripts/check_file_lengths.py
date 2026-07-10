#!/usr/bin/env python3
"""Fail if tracked Python source files exceed configured line count."""

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
    """Split (rel_path, lines) pairs into hard violations and soft warnings.

    A file over ``max_lines`` is a violation (fails CI). A file at or above
    ``warn_lines`` but within the cap is a warning: it surfaces the "trimmed to
    just under the limit" pressure *before* the cliff, so the fix is to split by
    responsibility early rather than shave lines to stay green.
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
    parser.add_argument("--max-lines", type=int, default=500, help="Maximum lines allowed per file (hard cap).")
    parser.add_argument(
        "--warn-lines",
        type=int,
        default=460,
        help="Warn (without failing) for files at or above this many lines — the approaching-the-cap band.",
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
        print(f"Approaching the {args.max_lines}-line limit (split by responsibility — don't shave to fit):")
        for rel_path, lines in sorted(warnings, key=lambda item: item[1], reverse=True):
            print(f"- {rel_path}: {lines} ({args.max_lines - lines} to go)")

    if violations:
        print(f"Files over {args.max_lines} lines:")
        for rel_path, lines in sorted(violations, key=lambda item: item[1], reverse=True):
            print(f"- {rel_path}: {lines}")
        return 1

    print(f"OK: all tracked Python files are <= {args.max_lines} lines.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
