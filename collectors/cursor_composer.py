"""Cursor composer session titles from local state.vscdb (activity anchor: label)."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from collectors.ai_logs import _GENERIC_BRANCHES, _anchors, _meaningful_label

SOURCE_NAME = "Cursor"
_COMPOSER_HEADERS_KEY = "composer.composerHeaders"


def cursor_state_db_path(home: Path) -> Path:
    return home / "Library" / "Application Support" / "Cursor" / "User" / "globalStorage" / "state.vscdb"


def _composer_timestamp_ms(composer: dict) -> int | None:
    for key in ("lastUpdatedAt", "conversationCheckpointLastUpdatedAt", "createdAt"):
        raw = composer.get(key)
        if raw is None:
            continue
        try:
            return int(raw)
        except (TypeError, ValueError):
            continue
    return None


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
):
    """One event per composer chat active in the date window (session title anchor)."""
    best_by_id: dict[str, tuple[int, dict]] = {}
    for composer in _read_composer_headers(cursor_state_db_path(home)):
        if not isinstance(composer, dict):
            continue
        composer_id = str(composer.get("composerId") or "").strip()
        if not composer_id:
            continue
        ms = _composer_timestamp_ms(composer)
        if ms is None:
            continue
        try:
            ts = datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc)
        except (OSError, OverflowError, ValueError):
            continue
        if not (dt_from <= ts <= dt_to):
            continue
        prev = best_by_id.get(composer_id)
        if prev is None or ms >= prev[0]:
            best_by_id[composer_id] = (ms, composer)

    results = []
    for _ms, composer in best_by_id.values():
        name = str(composer.get("name") or "").strip()
        label = _meaningful_label(name)
        if not label:
            continue
        ms = _composer_timestamp_ms(composer) or 0
        ts = datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc)
        workspace = _composer_workspace_path(composer)
        _git_text, branch = _composer_git_context(composer)
        dir_leaf = _path_dir_leaf(workspace) if workspace else None
        haystack = _composer_classification_haystack(composer, title=name)
        project = classify_project(haystack, profiles)
        detail = name[:70]
        results.append(
            make_event(
                SOURCE_NAME,
                ts,
                detail,
                project,
                anchors=_anchors(label=label, dir=dir_leaf, branch=branch),
            )
        )
    return results
