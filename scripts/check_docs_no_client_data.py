#!/usr/bin/env python3
"""Block real client/customer data from leaking into committed docs (#429).

On 2026-07-21 a spec + PR body committed real client identifiers. The
SAFE/NEEDS_HUMAN merge classifier does not treat ``docs/`` as a judgment
surface, so this leak class had no automated defense.

The sensitive strings live in ``~/.gittan/timelog_projects.json``, which is
gitignored and never committed. This checker reads them from the *local*
config at runtime and hardcodes nothing — so the guard itself never leaks.

Right layer is **pre-commit** (it has the local config; CI does not, since the
config is gitignored). Matched terms are partially masked in output so a
captured log never reproduces the full name.

Usage:
    python3 scripts/check_docs_no_client_data.py --staged
    python3 scripts/check_docs_no_client_data.py docs/task-prompts/foo.md
    GITTAN_PROJECTS_CONFIG=/path/config.json python3 scripts/... --staged
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

# Self-references that are expected in docs (the tool + the operator's own org).
# Extend via GITTAN_PRIVACY_ALLOWLIST (comma-separated), never with client names.
DEFAULT_ALLOW = {"timelog-extract", "gittan", "gittan-home", "blueberry", "mbjorke"}
MIN_TERM_LEN = 4  # shorter terms cause too many false positives
# Paths that legitimately never carry client data and should be scanned.
SCAN_PREFIXES = ("docs/",)
SCAN_SUFFIXES = (".md",)


def _config_path() -> Path:
    env = os.environ.get("GITTAN_PROJECTS_CONFIG")
    if env:
        return Path(env).expanduser()
    # Prefer the repo's canonical resolver so the guard reads the exact config
    # the tool uses (it honours GITTAN_HOME and the profile-home fallback).
    try:
        repo_root = Path(__file__).resolve().parent.parent
        if str(repo_root) not in sys.path:
            sys.path.insert(0, str(repo_root))
        from core.config import resolve_projects_config_path

        return Path(resolve_projects_config_path())
    except Exception:
        home = os.environ.get("GITTAN_HOME")
        base = Path(home).expanduser() if home else Path.home() / ".gittan"
        return base / "timelog_projects.json"


def _allowlist() -> set[str]:
    allow = set(DEFAULT_ALLOW)
    extra = os.environ.get("GITTAN_PRIVACY_ALLOWLIST", "")
    allow.update(t.strip().lower() for t in extra.split(",") if t.strip())
    return allow


def _is_self_reference(term: str, allow: set[str]) -> bool:
    """True when an allowlisted word appears as a whole word in the term.

    Lets a multi-word operator org ("Blueberry Maybe Ab Ltd") be allowed via
    a single allowlist entry ("blueberry") without allowlisting every variant.
    """
    words = set(re.split(r"[^a-z0-9]+", term.lower()))
    return bool(words & allow) or term.lower() in allow


class ConfigError(Exception):
    """The config exists but could not be read/parsed (fail closed, not skip)."""


def load_sensitive_terms(config_path: Path) -> set[str]:
    """Client/customer identifiers to keep out of committed docs.

    A genuinely absent config (e.g. CI, where it is gitignored) yields an empty
    set → the caller skips. A config that *exists* but is unreadable or invalid
    raises ConfigError so the caller can fail closed — a broken config must not
    silently disable the guard.
    """
    if not config_path.exists():
        return set()
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ConfigError(f"cannot read/parse {config_path}: {exc}") from exc
    profiles = data.get("projects", data) if isinstance(data, dict) else data
    if not isinstance(profiles, list):
        return set()
    allow = _allowlist()
    terms: set[str] = set()
    for prof in profiles:
        if not isinstance(prof, dict):
            continue
        for field in ("customer", "default_client", "name", "canonical_project", "project_id"):
            val = str(prof.get(field, "")).strip()
            if val:
                terms.add(val)
        for alias in prof.get("aliases") or []:
            if str(alias).strip():
                terms.add(str(alias).strip())
        email = str(prof.get("email", "")).strip()
        if "@" in email:
            terms.add(email.split("@", 1)[0])  # local-part only
    # Drop self-references and too-short/too-generic terms.
    return {
        t for t in terms
        if len(t) >= MIN_TERM_LEN and not _is_self_reference(t, allow)
    }


def _mask(term: str) -> str:
    if len(term) <= 3:
        return "***"
    return term[:2] + "***" + term[-1:]


def scan_file(path: Path, terms: set[str]) -> list[tuple[int, str]]:
    """Return (line_no, masked_term) for each sensitive hit in the file."""
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    # Pre-compile word-boundary patterns (terms may contain spaces/hyphens).
    patterns = [(t, re.compile(rf"(?<![\w-]){re.escape(t)}(?![\w-])", re.IGNORECASE)) for t in terms]
    hits: list[tuple[int, str]] = []
    for i, line in enumerate(lines, 1):
        for term, pat in patterns:
            if pat.search(line):
                hits.append((i, _mask(term)))
    return hits


def _staged_files() -> list[str]:
    try:
        # Include R (renames): a renamed docs file must still be scanned;
        # --name-only reports the new path for a rename.
        out = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
            capture_output=True, text=True, check=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        return []
    return [ln for ln in out.splitlines() if ln.strip()]


def _should_scan(name: str) -> bool:
    return name.startswith(SCAN_PREFIXES) and name.endswith(SCAN_SUFFIXES)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("files", nargs="*", help="files to scan (default: use --staged)")
    ap.add_argument("--staged", action="store_true", help="scan git-staged docs files")
    ns = ap.parse_args(argv)

    try:
        terms = load_sensitive_terms(_config_path())
    except ConfigError as exc:
        # Fail closed: a present-but-broken config must not silently disable
        # the guard (that would let a leak through on a bad edit / permissions).
        print(f"check-docs-no-client-data: config unreadable — blocking: {exc}", file=sys.stderr)
        return 1
    if not terms:
        # No local config (e.g. CI) → nothing client-specific to check. Not a
        # failure: the pre-commit layer is where this guard has teeth.
        print("check-docs-no-client-data: no local client config; skipping.", file=sys.stderr)
        return 0

    if ns.files:
        # Explicitly named files are scanned as-is (the caller chose them).
        targets = ns.files
    else:
        # --staged auto-selection: only the docs surfaces that carry prose.
        targets = [f for f in _staged_files() if _should_scan(f)] if ns.staged else []
    if not targets:
        return 0

    failed = False
    for f in targets:
        hits = scan_file(Path(f), terms)
        if hits:
            failed = True
            for line_no, masked in hits:
                print(
                    f"{f}:{line_no}: possible client/customer identifier "
                    f"({masked}) — must not be committed",
                    file=sys.stderr,
                )
    if failed:
        print(
            "\nReal client data must stay out of committed docs. Remove the names "
            "or describe them generically (see docs shape conventions).",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
