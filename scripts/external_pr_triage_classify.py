#!/usr/bin/env python3
"""Classify an external (fork) pull request for triage.

Decides between **auto-close** (a high-confidence link-rot spam signature) and
**needs-review** (label + notify the maintainer). Pure metadata: it reads the PR
author association, changed file names, title/body, and the diff *patches* — it
NEVER checks out or runs the PR's code. Used by
`.github/workflows/external-pr-triage.yml`, which runs under `pull_request_target`
and must therefore stay metadata-only.

Auto-close is deliberately narrow so a real first-time contributor is never
slammed. It fires only when ALL hold:
  1. docs-only  — every changed file is documentation/text
  2. link-fix claim — the title/body claims a broken/dead-link or archive fix
  3. archive.org downgrade — a diff line adds a web.archive.org URL (a live link
     swapped for a stale snapshot — the observed probe signature, PR #433/#443)

CLI: file list JSON on `--files` (from `gh api repos/OWNER/REPO/pulls/N/files`);
title/body/association from env PR_TITLE / PR_BODY / PR_AUTHOR_ASSOCIATION.
Prints the action to stdout and the reason to stderr.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

_DOC_SUFFIXES = (".md", ".markdown", ".mdx", ".rst", ".txt")
_DOC_BASENAME_PREFIXES = ("readme", "contributing", "changelog", "license", "authors")
_LINK_FIX_CLAIM = re.compile(
    r"\b(?:broken|dead)\b[^\n]{0,40}\blink"
    r"|\bfix\b[^\n]{0,20}\blink"
    r"|\brestore\b[^\n]{0,20}\blink"
    r"|wayback|web\.archive\.org|archive\.org",
    re.IGNORECASE,
)
_TRUSTED_ASSOCIATIONS = frozenset({"OWNER", "MEMBER", "COLLABORATOR"})


def is_external_author(author_association: str) -> bool:
    """External = not an owner/member/collaborator (fork PRs are the primary gate)."""
    return (author_association or "").strip().upper() not in _TRUSTED_ASSOCIATIONS


def is_docs_only(changed_files: list[str]) -> bool:
    files = [str(f).strip() for f in changed_files if str(f).strip()]
    if not files:
        return False
    for path in files:
        low = path.lower()
        if low.endswith(_DOC_SUFFIXES) or low.startswith("docs/"):
            continue
        base = low.rsplit("/", 1)[-1]
        if any(base.startswith(p) for p in _DOC_BASENAME_PREFIXES):
            continue
        return False
    return True


def has_archive_downgrade(patches: list[str]) -> bool:
    """True if any *added* diff line introduces a web.archive.org URL."""
    for patch in patches:
        for line in str(patch or "").splitlines():
            if line.startswith("+") and not line.startswith("+++"):
                if "web.archive.org" in line.lower():
                    return True
    return False


def classify_external_pr(
    *,
    author_association: str,
    changed_files: list[str],
    title: str,
    body: str,
    patches: list[str],
) -> tuple[str, str]:
    """Return ``(action, reason)`` where action is 'auto-close' or 'needs-review'."""
    text = f"{title or ''}\n{body or ''}"
    is_spam = (
        is_docs_only(changed_files)
        and bool(_LINK_FIX_CLAIM.search(text))
        and has_archive_downgrade(patches)
    )
    if is_spam:
        return (
            "auto-close",
            "docs-only PR claiming a link fix that swaps a live link for a "
            "web.archive.org snapshot — the known link-rot spam signature",
        )
    return (
        "needs-review",
        "external PR — labelled for maintainer review, not auto-merged",
    )


def _load_files(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    return data if isinstance(data, list) else []


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--files", required=True, help="JSON from gh api .../pulls/N/files")
    args = ap.parse_args()

    files = _load_files(args.files)
    action, reason = classify_external_pr(
        author_association=os.environ.get("PR_AUTHOR_ASSOCIATION", ""),
        changed_files=[f.get("filename", "") for f in files],
        title=os.environ.get("PR_TITLE", ""),
        body=os.environ.get("PR_BODY", ""),
        patches=[f.get("patch", "") for f in files],
    )
    print(action)
    print(reason, file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
