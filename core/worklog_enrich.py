"""Enrich delivery/worklog rows with nearby AI session titles."""

from __future__ import annotations

import re
from typing import Any

from core.events import event_anchors
from core.sources import GITHUB_SOURCE, WORKLOG_SOURCE

_COMMIT_DETAIL_RE = re.compile(r"^Commit:\s*", re.IGNORECASE)

# Glass PR-tab titles (and sticky Multitask paint) look like ``PR #347`` /
# ``PR #347: …``. Those are unsafe as session titles and must not bleed onto
# GitHub/worklog delivery rows (GH-351).
_PR_NUMBER_SESSION_LABEL_RE = re.compile(
    r"^\s*PR\s*#\s*\d+(?:\s*:.*)?\s*$",
    re.IGNORECASE,
)

# Live shell titles (Glass Multitask terminal tabs, GH-361) are not session
# titles; exact-match on the bare shell name.
_SHELL_TITLE_SESSION_LABELS = frozenset({"zsh", "bash"})

# Chat/IDE sources that carry human-meaningful session titles.
_SESSION_LABEL_SOURCES = frozenset(
    {
        "Claude Code CLI",
        "Claude Desktop",
        "Claude Desktop (Code)",
        "Cursor",
        "Cursor (agent)",
        "Codex IDE",
    }
)

_DEFAULT_LOOKBACK_SECONDS = 2 * 60 * 60


def is_pr_number_session_label(label: str | None) -> bool:
    """True when ``label`` is a PR-number-shaped session title (GH-351).

    Matches whole-string ``PR #<digits>`` with optional ``: …`` suffix.
    Titles that merely mention a PR in prose do not match.
    """
    text = str(label or "").strip()
    if not text:
        return False
    return bool(_PR_NUMBER_SESSION_LABEL_RE.match(text))


def is_shell_title_session_label(label: str | None) -> bool:
    """True when ``label`` is a bare shell name (``zsh``/``bash``) (GH-361).

    Glass Multitask terminal tabs carry the live terminal title; an idle
    terminal reports just the shell name, which must not become a session
    title on delivery rows.
    """
    return str(label or "").strip().lower() in _SHELL_TITLE_SESSION_LABELS


def is_commit_worklog_detail(detail: str) -> bool:
    text = str(detail or "").strip()
    if text.startswith("- "):
        text = text[2:].strip()
    return bool(_COMMIT_DETAIL_RE.match(text))


def normalize_worklog_detail(detail: str) -> str:
    """Drop leading list-marker dash from TIMELOG.md bullet lines."""
    text = str(detail or "").strip()
    if text.startswith("- "):
        return text[2:].strip()
    return text


def enrich_worklog_session_labels(
    events: list[dict[str, Any]],
    *,
    uncategorized: str = "Uncategorized",
    lookback_seconds: int = _DEFAULT_LOOKBACK_SECONDS,
) -> None:
    """Attach the nearest prior AI session title to commit worklog rows (in-place)."""
    ordered = sorted(events, key=lambda e: e["timestamp"])
    for idx, event in enumerate(ordered):
        if str(event.get("source") or "") != WORKLOG_SOURCE:
            continue
        if str(event_anchors(event).get("label") or "").strip():
            continue
        detail = normalize_worklog_detail(str(event.get("detail") or ""))
        if not is_commit_worklog_detail(detail):
            continue
        project = str(event.get("project") or "")
        if project == uncategorized:
            continue
        ts = event["timestamp"]
        label = _nearest_session_label(ordered, idx, project=project, before_ts=ts, lookback_seconds=lookback_seconds)
        if not label:
            continue
        anchors = dict(event_anchors(event))
        anchors["label"] = label
        event["anchors"] = anchors
        if detail != event.get("detail"):
            event["detail"] = detail


def enrich_github_session_labels(
    events: list[dict[str, Any]],
    *,
    uncategorized: str = "Uncategorized",
    lookback_seconds: int = _DEFAULT_LOOKBACK_SECONDS,
) -> None:
    """Attach the nearest prior AI session title to GitHub activity rows (in-place)."""
    ordered = sorted(events, key=lambda e: e["timestamp"])
    for idx, event in enumerate(ordered):
        if str(event.get("source") or "") != GITHUB_SOURCE:
            continue
        if str(event_anchors(event).get("label") or "").strip():
            continue
        project = str(event.get("project") or "")
        if project == uncategorized:
            continue
        ts = event["timestamp"]
        label = _nearest_session_label(ordered, idx, project=project, before_ts=ts, lookback_seconds=lookback_seconds)
        if not label:
            continue
        anchors = dict(event_anchors(event))
        anchors["label"] = label
        event["anchors"] = anchors


def enrich_delivery_session_labels(
    events: list[dict[str, Any]],
    *,
    uncategorized: str = "Uncategorized",
    lookback_seconds: int = _DEFAULT_LOOKBACK_SECONDS,
) -> None:
    """Worklog commits and GitHub rows inherit the nearest prior chat session title."""
    enrich_worklog_session_labels(
        events, uncategorized=uncategorized, lookback_seconds=lookback_seconds
    )
    enrich_github_session_labels(
        events, uncategorized=uncategorized, lookback_seconds=lookback_seconds
    )


def _nearest_session_label(
    ordered: list[dict[str, Any]],
    index: int,
    *,
    project: str,
    before_ts,
    lookback_seconds: int,
) -> str | None:
    for j in range(index - 1, -1, -1):
        prev = ordered[j]
        gap = (before_ts - prev["timestamp"]).total_seconds()
        if gap > lookback_seconds:
            break
        if project and str(prev.get("project") or "") != project:
            continue
        if str(prev.get("source") or "") not in _SESSION_LABEL_SOURCES:
            continue
        label = str(event_anchors(prev).get("label") or "").strip()
        if not label or is_pr_number_session_label(label) or is_shell_title_session_label(label):
            continue
        return label
    return None
