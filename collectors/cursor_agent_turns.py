"""Cursor agent chat turns from structured diagnostic logs.

Cursor does not persist per-bubble timestamps in ``state.vscdb``, but
``anysphere.cursor-always-local`` structured logs record ``agent.turn.start`` with
wall time, ``conversation_id`` (same as ``composerId``), and ``workspaceId`` in
the log file name. Composer headers supply title/workspace for classification.

Weaker than Claude Desktop cached events (log rotation, diagnostic channel) but
the only honest per-turn local signal for Composer chats. When turns exist for a
composer, composer-header heartbeats are skipped to avoid double-counting.

Spec context: ``docs/specs/cursor-evidence-ceiling.md``.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Callable

from collectors.ai_logs import _meaningful_label
from collectors.cursor_composer import (
    _branch_reflected_in_label,
    _composer_classification_haystack,
    _composer_event_anchors,
    _composer_git_context,
    _composer_primary_repo_path,
    _composer_workspace_path,
    _path_dir_leaf,
    _read_composer_headers,
    cursor_state_db_path,
    load_cursor_workspaces,
)

CURSOR_AGENT_SOURCE = "Cursor (agent)"

_LOG_LINE_TS = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+)")
_WORKSPACE_ID_RE = re.compile(r"workspaceId-([0-9a-f]{32})")
_JSON_TAIL_RE = re.compile(r"\{.*\}$")

_CLUSTER_GAP_SECONDS = 15 * 60
_THIN_SPACING_SECONDS = 5 * 60


def cursor_structured_logs_dir(home: Path) -> Path:
    return home / "Library" / "Application Support" / "Cursor" / "logs"


def _parse_log_ts(line: str, local_tz) -> datetime | None:
    match = _LOG_LINE_TS.match(line)
    if not match:
        return None
    try:
        naive = datetime.strptime(match.group(1)[:23], "%Y-%m-%d %H:%M:%S.%f")
    except ValueError:
        try:
            naive = datetime.strptime(match.group(1)[:19], "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None
    return naive.replace(tzinfo=local_tz)


def _workspace_id_from_log_path(path: Path) -> str:
    match = _WORKSPACE_ID_RE.search(path.name)
    return match.group(1) if match else ""


def _composer_map(home: Path) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for composer in _read_composer_headers(cursor_state_db_path(home)):
        if not isinstance(composer, dict):
            continue
        cid = str(composer.get("composerId") or "").strip()
        if cid:
            out[cid] = composer
    return out


def _clusters(stamps: list[datetime]) -> list[list[datetime]]:
    ordered = sorted(stamps)
    if not ordered:
        return []
    clusters: list[list[datetime]] = [[ordered[0]]]
    for ts in ordered[1:]:
        if (ts - clusters[-1][-1]).total_seconds() <= _CLUSTER_GAP_SECONDS:
            clusters[-1].append(ts)
        else:
            clusters.append([ts])
    return clusters


def _thin(stamps: list[datetime]) -> list[datetime]:
    if not stamps:
        return []
    ordered = sorted(stamps)
    out = [ordered[0]]
    for ts in ordered[1:]:
        if (ts - out[-1]).total_seconds() >= _THIN_SPACING_SECONDS:
            out.append(ts)
    if out[-1] is not ordered[-1]:
        out.append(ordered[-1])
    return out


def _collect_turn_starts(
    logs_dir: Path,
    dt_from: datetime,
    dt_to: datetime,
    local_tz,
) -> dict[tuple[str, str], list[datetime]]:
    """Map (conversation_id, workspace_id) -> sorted turn-start timestamps."""
    from_ts = dt_from.timestamp()
    buckets: dict[tuple[str, str], list[datetime]] = {}
    if not logs_dir.is_dir():
        return buckets

    for log_file in logs_dir.glob("**/anysphere.cursor-always-local/Cursor Structured Logs*.log"):
        try:
            if log_file.stat().st_mtime < from_ts:
                continue
        except OSError:
            continue
        workspace_id = _workspace_id_from_log_path(log_file)
        try:
            with open(log_file, encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    if "agent.turn.start" not in line:
                        continue
                    ts = _parse_log_ts(line, local_tz)
                    if ts is None or not (dt_from <= ts <= dt_to):
                        continue
                    json_match = _JSON_TAIL_RE.search(line)
                    if not json_match:
                        continue
                    try:
                        payload = json.loads(json_match.group())
                    except json.JSONDecodeError:
                        continue
                    meta = payload.get("metadata") if isinstance(payload, dict) else None
                    if not isinstance(meta, dict):
                        continue
                    conversation_id = str(meta.get("conversation_id") or "").strip()
                    if not conversation_id:
                        continue
                    key = (conversation_id, workspace_id)
                    buckets.setdefault(key, []).append(ts)
        except OSError:
            continue
    return buckets


def collect_cursor_agent_turns(
    profiles,
    dt_from,
    dt_to,
    home: Path,
    local_tz,
    classify_project: Callable,
    make_event: Callable,
) -> tuple[list[dict], set[str]]:
    """Return agent-turn events and composer ids covered (for composer fallback skip)."""
    buckets = _collect_turn_starts(cursor_structured_logs_dir(home), dt_from, dt_to, local_tz)
    if not buckets:
        return [], set()

    composers = _composer_map(home)
    workspace_map = load_cursor_workspaces(home)
    covered: set[str] = set()
    results: list[dict] = []

    for (conversation_id, workspace_id), stamps in buckets.items():
        if not stamps:
            continue
        composer = composers.get(conversation_id, {})
        name = str(composer.get("name") or "").strip()
        workspace = _composer_workspace_path(composer) if composer else ""
        if not workspace and workspace_id:
            workspace = workspace_map.get(workspace_id, "")
        _git_text, branch = _composer_git_context(composer) if composer else ("", None)
        dir_leaf = _path_dir_leaf(workspace) if workspace else None
        if workspace_id and not dir_leaf:
            mapped = workspace_map.get(workspace_id, "")
            if mapped:
                dir_leaf = _path_dir_leaf(mapped)
                if not workspace:
                    workspace = mapped
        label = _meaningful_label(name) or dir_leaf
        if not label:
            continue
        haystack = (
            _composer_classification_haystack(composer, title=name)
            if composer
            else " ".join(part for part in (label, workspace) if part)
        )
        project = classify_project(haystack, profiles)
        anchors = _composer_event_anchors(
            workspace=workspace or None,
            label=label,
            branch=branch,
            repo_path=_composer_primary_repo_path(composer) if composer else None,
        )

        emitted = False
        for cluster in _clusters(stamps):
            cluster_turns = len(cluster)
            cluster_detail = f"{cluster_turns} turn{'s' if cluster_turns != 1 else ''}"
            if branch and not _branch_reflected_in_label(branch, name or label or ""):
                cluster_detail += f" (@{branch})"
            for ts in _thin(cluster):
                results.append(
                    make_event(
                        CURSOR_AGENT_SOURCE,
                        ts,
                        cluster_detail,
                        project,
                        anchors=anchors,
                    )
                )
                emitted = True
        if emitted:
            covered.add(conversation_id)
    return results, covered
