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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-lines", type=int, default=500, help="Maximum lines allowed per file.")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    violations = []
    for path in tracked_python_files(repo_root):
        lines = count_lines(path)
        if lines > args.max_lines:
            violations.append((path.relative_to(repo_root), lines))

    if violations:
        print(f"Files over {args.max_lines} lines:")
        for rel_path, lines in sorted(violations, key=lambda item: item[1], reverse=True):
            print(f"- {rel_path}: {lines}")
        return 1

    print(f"OK: all tracked Python files are <= {args.max_lines} lines.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
