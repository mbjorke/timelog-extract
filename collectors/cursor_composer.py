"""Cursor composer session titles from local state.vscdb (activity anchor: label)."""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from collectors.ai_logs import _GENERIC_BRANCHES, _meaningful_label
from core.repo_slug import path_attribution_anchor

SOURCE_NAME = "Cursor"
from urllib.parse import unquote, urlparse

_COMPOSER_HEADERS_KEY = "composer.composerHeaders"
# Stay below default session gap (15 min in core.domain.compute_sessions).
_COMPOSER_HEARTBEAT_MINUTES = 14
# Touches closer than this merge into one continuous burst; wider gaps between
# createdAt and lastUpdatedAt are left empty instead of fabricated as work.
_COMPOSER_TOUCH_MERGE_MINUTES = 14
# When lastUpdated spills to a later day, extend same-day metadata span modestly.
_COMPOSER_SPILLED_DAY_EXTENSION_MS = 4 * 60 * 60 * 1000
# Branch touches shortly after midnight imply the session ran through the evening.
_COMPOSER_SPILLED_GRACE_MS = 6 * 60 * 60 * 1000


def _branch_reflected_in_label(branch: str, text: str) -> bool:
    """True when branch is already represented in the session title/label text."""
    token = branch.lower().strip()
    if not token or not text:
        return False
    low = text.lower().strip()
    if f"@{token}" in low:
        return True
    if token == low:
        return True
    text_parts = {part for part in re.split(r"[\s·/\-_]+", low) if part}
    branch_parts = [part for part in re.split(r"[\s·/\-_]+", token) if part]
    if not branch_parts:
        return False
    return all(part in text_parts for part in branch_parts)

# Credit most of the remaining calendar day (not full midnight fabricate).
_COMPOSER_SPILLED_DAY_FRACTION = 0.88


def cursor_state_db_path(home: Path) -> Path:
    return home / "Library" / "Application Support" / "Cursor" / "User" / "globalStorage" / "state.vscdb"


def load_cursor_workspaces(home: Path):
    storage_dir = home / "Library" / "Application Support" / "Cursor" / "User" / "workspaceStorage"
    workspace_map: dict[str, str] = {}
    if not storage_dir.exists():
        return workspace_map
    for workspace_json in storage_dir.glob("*/workspace.json"):
        workspace_id = workspace_json.parent.name
        try:
            data = json.loads(workspace_json.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        raw_uri = data.get("folder") or data.get("workspace")
        if not raw_uri:
            continue
        parsed = urlparse(raw_uri)
        path = unquote(parsed.path) if parsed.scheme == "file" else raw_uri
        workspace_map[workspace_id] = path
    return workspace_map


def _composer_created_ms(composer: dict) -> int | None:
    raw = composer.get("createdAt")
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _composer_in_window_touch_ms(composer: dict, from_ms: int, to_ms: int) -> list[int]:
    """Same-day composer activity timestamps already present in local metadata."""
    stamps: list[int] = []
    for key in ("createdAt", "lastUpdatedAt", "conversationCheckpointLastUpdatedAt"):
        raw = composer.get(key)
        if raw is None:
            continue
        try:
            ms = int(raw)
        except (TypeError, ValueError):
            continue
        if from_ms <= ms <= to_ms:
            stamps.append(ms)
    for repo in composer.get("trackedGitRepos") or []:
        if not isinstance(repo, dict):
            continue
        for branch in repo.get("branches") or []:
            if not isinstance(branch, dict):
                continue
            raw = branch.get("lastInteractionAt")
            if raw is None:
                continue
            try:
                ms = int(raw)
            except (TypeError, ValueError):
                continue
            if from_ms <= ms <= to_ms:
                stamps.append(ms)
    return sorted(set(stamps))


def _composer_grace_touch_ms(composer: dict, to_ms: int) -> list[int]:
    """Branch interactions just after the report day (session spill signal)."""
    grace_end = to_ms + _COMPOSER_SPILLED_GRACE_MS
    stamps: list[int] = []
    for repo in composer.get("trackedGitRepos") or []:
        if not isinstance(repo, dict):
            continue
        for branch in repo.get("branches") or []:
            if not isinstance(branch, dict):
                continue
            raw = branch.get("lastInteractionAt")
            if raw is None:
                continue
            try:
                ms = int(raw)
            except (TypeError, ValueError):
                continue
            if to_ms < ms <= grace_end:
                stamps.append(ms)
    return sorted(set(stamps))


def _composer_end_ms(composer: dict) -> int | None:
    best: int | None = None
    for key in ("lastUpdatedAt", "conversationCheckpointLastUpdatedAt"):
        raw = composer.get(key)
        if raw is None:
            continue
        try:
            ms = int(raw)
        except (TypeError, ValueError):
            continue
        if best is None or ms > best:
            best = ms
    return best


def _composer_activity_span_ms(
    composer: dict,
    dt_from: datetime,
    dt_to: datetime,
) -> tuple[int, int] | None:
    """Return the composer activity span clipped to the report window.

    Uses overlap (not end-in-window) so sessions still open after midnight
    count on the earlier day up to ``dt_to``. Stale threads created long before
    the window emit a single point at their in-window touch.
    """
    end_ms = _composer_end_ms(composer)
    if end_ms is None:
        return None
    created_ms = _composer_created_ms(composer)
    if created_ms is None:
        created_ms = end_ms
    if end_ms < created_ms:
        created_ms, end_ms = end_ms, created_ms

    from_ms = int(dt_from.timestamp() * 1000)
    to_ms = int(dt_to.timestamp() * 1000)
    if end_ms < from_ms or created_ms > to_ms:
        return None

    clipped_start = max(created_ms, from_ms)
    clipped_end = min(end_ms, to_ms)
    if clipped_end < clipped_start:
        clipped_start = clipped_end

    # Threads that predate this report day: credit the in-window touch only.
    if created_ms < from_ms:
        return clipped_end, clipped_end

    # lastUpdated moved to a later calendar day (typical for retrospective runs).
    # Do not fabricate heartbeats through midnight — bound to same-day metadata.
    if end_ms > to_ms:
        touches = _composer_in_window_touch_ms(composer, from_ms, to_ms)
        if not touches:
            return clipped_start, clipped_start
        activity_start = min(min(touches), clipped_start)
        latest_day = max(touches)
        if latest_day < activity_start:
            activity_start = latest_day
        grace_touches = _composer_grace_touch_ms(composer, to_ms)
        if grace_touches:
            remaining = to_ms - latest_day
            if remaining > 0:
                activity_end = min(
                    to_ms,
                    latest_day + int(remaining * _COMPOSER_SPILLED_DAY_FRACTION),
                )
            else:
                activity_end = latest_day
        else:
            activity_end = min(
                to_ms,
                latest_day + _COMPOSER_SPILLED_DAY_EXTENSION_MS,
            )
        return activity_start, activity_end

    return clipped_start, clipped_end


def _composer_span_overlaps_window(
    start_ms: int,
    end_ms: int,
    dt_from: datetime,
    dt_to: datetime,
) -> bool:
    try:
        start_ts = datetime.fromtimestamp(start_ms / 1000.0, tz=timezone.utc)
        end_ts = datetime.fromtimestamp(end_ms / 1000.0, tz=timezone.utc)
    except (OSError, OverflowError, ValueError):
        return False
    return start_ts <= dt_to and end_ts >= dt_from


def _composer_touch_burst_ms(touches: list[int]) -> list[int]:
    """Grid heartbeats only within bounded bursts anchored on real touches.

    ``createdAt``/``lastUpdatedAt`` are two discrete points; a long-lived thread
    can span days between them. Filling that gap with a heartbeat grid fabricates
    work that never happened. Instead, touches within ``_COMPOSER_TOUCH_MERGE_MINUTES``
    merge into one continuous burst (genuine back-to-back activity still grids),
    while wider idle gaps are left empty. A lone touch emits a single point.
    """
    ordered = sorted({int(t) for t in touches})
    if not ordered:
        return []
    merge_ms = _COMPOSER_TOUCH_MERGE_MINUTES * 60 * 1000
    step_ms = _COMPOSER_HEARTBEAT_MINUTES * 60 * 1000
    clusters: list[list[int]] = [[ordered[0], ordered[0]]]
    for ms in ordered[1:]:
        if ms - clusters[-1][1] <= merge_ms:
            clusters[-1][1] = ms
        else:
            clusters.append([ms, ms])
    stamps: list[int] = []
    for start_ms, end_ms in clusters:
        if end_ms <= start_ms:
            stamps.append(start_ms)
            continue
        cursor = start_ms
        while cursor < end_ms:
            stamps.append(cursor)
            cursor += step_ms
        stamps.append(end_ms)
    return sorted(set(stamps))


def _uri_fs_path(block: dict | None) -> str:
    if not isinstance(block, dict):
        return ""
    env = block.get("environment")
    if not isinstance(env, dict):
        env = block
    uri = env.get("uri")
    if not isinstance(uri, dict):
        return ""
    return str(uri.get("fsPath") or uri.get("path") or "").strip()


def _composer_primary_repo_path(composer: dict) -> str:
    """First tracked git repo path from composer metadata, if any."""
    for repo in composer.get("trackedGitRepos") or []:
        if not isinstance(repo, dict):
            continue
        repo_path = str(repo.get("repoPath") or "").strip()
        if repo_path:
            return repo_path
    return ""


def _composer_event_anchors(
    *,
    workspace: str | None,
    label: str | None,
    branch: str | None,
    repo_path: str | None = None,
) -> dict[str, str]:
    """Anchors for composer/agent sessions — repo slug before ephemeral dir leaves."""
    anchors: dict[str, str] = dict(path_attribution_anchor(workspace or "") or {})
    if "repo" not in anchors and repo_path:
        fallback = path_attribution_anchor(repo_path)
        if fallback and "repo" in fallback:
            anchors = dict(fallback)
    if label:
        anchors["label"] = label
    if branch and "repo" not in anchors:
        leaf = str(branch).rsplit("/", 1)[-1].strip().lower()
        if leaf and leaf not in _GENERIC_BRANCHES:
            anchors["branch"] = leaf
    return anchors


def _composer_workspace_path(composer: dict) -> str:
    for key in ("workspaceIdentifier", "agentLocation"):
        path = _uri_fs_path(composer.get(key))
        if path:
            return path
    history = composer.get("agentLocationHistory")
    if isinstance(history, list):
        for entry in reversed(history):
            if not isinstance(entry, dict):
                continue
            location = entry.get("location")
            path = _uri_fs_path(location if isinstance(location, dict) else None)
            if path:
                return path
    return ""


def _composer_git_context(composer: dict) -> tuple[str, str | None]:
    """Repo paths, branch names for classify haystack, and latest branch leaf anchor."""
    parts: list[str] = []
    branch_anchor: str | None = None
    latest_ms = -1
    for repo in composer.get("trackedGitRepos") or []:
        if not isinstance(repo, dict):
            continue
        repo_path = str(repo.get("repoPath") or "").strip()
        if repo_path:
            parts.append(repo_path)
            parts.append(Path(repo_path).name)
        for branch in repo.get("branches") or []:
            if not isinstance(branch, dict):
                continue
            name = str(branch.get("branchName") or "").strip()
            if not name:
                continue
            parts.append(name)
            try:
                ms = int(branch.get("lastInteractionAt") or -1)
            except (TypeError, ValueError):
                ms = -1
            if ms < latest_ms:
                continue
            latest_ms = ms
            leaf = name.rsplit("/", 1)[-1].strip().lower()
            if leaf and leaf not in _GENERIC_BRANCHES:
                branch_anchor = leaf
    return " ".join(parts), branch_anchor


def _path_dir_leaf(path: str) -> str | None:
    leaf = Path(path).name.strip().lower()
    return leaf or None


def _composer_classification_haystack(composer: dict, *, title: str) -> str:
    workspace = _composer_workspace_path(composer)
    git_text, _branch = _composer_git_context(composer)
    return " ".join(part for part in (title, workspace, git_text) if part)


def _read_composer_headers(db_path: Path) -> list[dict]:
    if not db_path.is_file():
        return []
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        row = conn.execute(
            "SELECT value FROM ItemTable WHERE key = ?",
            (_COMPOSER_HEADERS_KEY,),
        ).fetchone()
        conn.close()
    except sqlite3.Error:
        return []
    if not row or not row[0]:
        return []
    try:
        payload = json.loads(row[0])
    except json.JSONDecodeError:
        return []
    composers = payload.get("allComposers")
    return composers if isinstance(composers, list) else []


def collect_cursor_composer_sessions(
    profiles,
    dt_from,
    dt_to,
    home: Path,
    classify_project: Callable,
    make_event: Callable,
    *,
    exclude_composer_ids: set[str] | None = None,
):
    """Emit bounded heartbeat bursts anchored on each composer's real touches."""
    skip = exclude_composer_ids or set()
    from_ms = int(dt_from.timestamp() * 1000)
    to_ms = int(dt_to.timestamp() * 1000)
    best_by_id: dict[str, tuple[int, int, dict]] = {}
    for composer in _read_composer_headers(cursor_state_db_path(home)):
        if not isinstance(composer, dict):
            continue
        composer_id = str(composer.get("composerId") or "").strip()
        if not composer_id or composer_id in skip:
            continue
        span = _composer_activity_span_ms(composer, dt_from, dt_to)
        if span is None:
            continue
        start_ms, end_ms = span
        if not _composer_span_overlaps_window(start_ms, end_ms, dt_from, dt_to):
            continue
        prev = best_by_id.get(composer_id)
        if prev is None or end_ms >= prev[1]:
            best_by_id[composer_id] = (start_ms, end_ms, composer)

    results = []
    for start_ms, end_ms, composer in best_by_id.values():
        name = str(composer.get("name") or "").strip()
        workspace = _composer_workspace_path(composer)
        _git_text, branch = _composer_git_context(composer)
        dir_leaf = _path_dir_leaf(workspace) if workspace else None
        label = _meaningful_label(name) or dir_leaf
        if not label:
            continue
        haystack = _composer_classification_haystack(composer, title=name)
        project = classify_project(haystack, profiles)
        context_bits: list[str] = []
        if branch and not _branch_reflected_in_label(branch, name or label or ""):
            context_bits.append(f"@{branch}")
        detail = " · ".join(context_bits)[:100]
        anchors = _composer_event_anchors(
            workspace=workspace or None,
            label=label,
            branch=branch,
            repo_path=_composer_primary_repo_path(composer) or None,
        )
        touches = _composer_in_window_touch_ms(composer, from_ms, to_ms)
        if not touches:
            # Predate/spill threads with no in-window metadata touch: credit the
            # single bounded anchor the span resolved to, not a fabricated grid.
            touches = [min(max(end_ms, from_ms), to_ms)]
        for ms in _composer_touch_burst_ms(touches):
            try:
                ts = datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc)
            except (OSError, OverflowError, ValueError):
                continue
            if not (dt_from <= ts <= dt_to):
                continue
            results.append(
                make_event(
                    SOURCE_NAME,
                    ts,
                    detail,
                    project,
                    anchors=anchors,
                )
            )
    return results
