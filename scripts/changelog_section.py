#!/usr/bin/env python3
"""Extract one version section from CHANGELOG.md for GitHub Release notes.

Usage:
  python3 scripts/changelog_section.py 0.4.0
  python3 scripts/changelog_section.py 0.4.0 --file CHANGELOG.md

Prints the body under ``## 0.4.0 - YYYY-MM-DD`` (heading excluded) until the
next ``## `` heading. Exits 1 when the version section is missing or empty.
Draft headings such as ``## 1.0.0 - Draft`` are rejected (no release date).
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Final-release headings only: "## X.Y.Z - YYYY-MM-DD" (not "## X.Y.Z - Draft …").
_HEADING_RE = re.compile(r"^##\s+(\d+\.\d+\.\d+)\s+-\s+\d{4}-\d{2}-\d{2}\s*$")


def extract_section(changelog_text: str, version: str) -> str:
    """Return the markdown body for ``version``, or raise ``ValueError``."""
    lines = changelog_text.splitlines()
    start: int | None = None
    for idx, line in enumerate(lines):
        match = _HEADING_RE.match(line.strip())
        if match and match.group(1) == version:
            start = idx + 1
            break
    if start is None:
        raise ValueError(
            f"No dated CHANGELOG section for version {version} "
            f"(expected '## {version} - YYYY-MM-DD')"
        )

    end = len(lines)
    for idx in range(start, len(lines)):
        if lines[idx].startswith("## "):
            end = idx
            break

    body = "\n".join(lines[start:end]).strip()
    if not body:
        raise ValueError(f"CHANGELOG section for {version} is empty")
    return body + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version", help="SemVer without leading v, e.g. 0.4.0")
    parser.add_argument(
        "--file",
        type=Path,
        default=Path("CHANGELOG.md"),
        help="Changelog path (default: CHANGELOG.md)",
    )
    args = parser.parse_args(argv)

    if not re.fullmatch(r"\d+\.\d+\.\d+", args.version):
        print(f"error: version must look like X.Y.Z, got {args.version!r}", file=sys.stderr)
        return 2

    text = args.file.read_text(encoding="utf-8")
    try:
        print(extract_section(text, args.version), end="")
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
