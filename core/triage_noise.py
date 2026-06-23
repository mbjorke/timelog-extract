"""Noise filtering helpers shared by triage flows."""

from __future__ import annotations

import re
from urllib.parse import urlparse

TRIAGE_NOISE_DOMAINS = {
    "cursor.com",
    "www.cursor.com",
    "cursor.sh",
    "www.cursor.sh",
}

TRIAGE_NOISE_TITLE_MARKERS = (
    "canvas sdk mirror failed",
    "skills-cursor",
    "cursor sdk",
    "mcp tool schema",
    "cursor extension host",
    "cursor diagnostics",
)

# Shared with uncategorized `gittan review` clustering (Cursor/IDE log lines, not customer work).
UNCATEGORIZED_NOISE_DETAIL_MARKERS = TRIAGE_NOISE_TITLE_MARKERS + (
    "failed to persist sync manifest",
    "persist sync manifest",
    '"skilldir"',
    "loadfrommarketplacesource",
    "[file watcher]",
    "fsevents",
    "events were dropped",
    "opened repository",
    "bootstrapping repository index",
    "cursor_agent_exec.startup",
    "browser_click.json",
    "error writing serv",
)

# Precompiled alternation: one regex search per line instead of scanning every
# marker, which matters across millions of Cursor/IDE log lines.
_UNCATEGORIZED_NOISE_DETAIL_RE = re.compile(
    "|".join(re.escape(marker) for marker in UNCATEGORIZED_NOISE_DETAIL_MARKERS)
)

NOISE_MATCH_TERM_VALUES = frozenset(
    {
        "skills-cursor",
        "skills_cursor",
    }
)

# Cursor parallel worktree folder names (wt-*) are IDE scaffolding, not billable project tokens.
_WORKTREE_TERM_PREFIX = "wt-"


def extract_domain(url: str) -> str:
    if not url:
        return ""
    try:
        host = urlparse(url).netloc.lower().strip()
    except Exception:
        return ""
    return host[4:] if host.startswith("www.") else host


def is_triage_noise_row(url: str, title: str) -> bool:
    domain = extract_domain(url)
    if domain in TRIAGE_NOISE_DOMAINS:
        return True
    text = (title or "").strip().lower()
    if not text:
        return False
    return any(marker in text for marker in TRIAGE_NOISE_TITLE_MARKERS)


def is_uncategorized_noise_detail(detail: str) -> bool:
    lower = (detail or "").lower()
    if not lower.strip():
        return True
    return _UNCATEGORIZED_NOISE_DETAIL_RE.search(lower) is not None


def is_uncategorized_noise_term(term: str) -> bool:
    lower = (term or "").strip().lower().rstrip(")")
    if not lower:
        return True
    if lower in NOISE_MATCH_TERM_VALUES:
        return True
    if lower.startswith(_WORKTREE_TERM_PREFIX) and len(lower) > len(_WORKTREE_TERM_PREFIX):
        return True
    return any(marker in lower for marker in TRIAGE_NOISE_TITLE_MARKERS)


def filter_triage_noise_rows(
    chrome_rows: list[tuple[int, str, str]],
) -> tuple[list[tuple[int, str, str]], int]:
    filtered: list[tuple[int, str, str]] = []
    dropped = 0
    for row in chrome_rows:
        _visit_time_cu, url, title = row
        if is_triage_noise_row(url, title):
            dropped += 1
            continue
        filtered.append(row)
    return filtered, dropped
