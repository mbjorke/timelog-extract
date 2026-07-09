"""Cursor agent chat turns from structured diagnostic logs.

Cursor does not persist per-bubble timestamps in ``state.vscdb``. Through
Cursor 3.9.x, ``anysphere.cursor-always-local`` structured logs recorded
``agent.turn.start`` with wall time, ``conversation_id`` (same as
``composerId``), and ``workspaceId`` in the log file name.

Cursor 3.10+ stopped emitting those turns on the always-local channel. The
honest replacement is ``beforeSubmitPrompt`` payloads in
``cursor.hooks.workspaceId-*.log`` (same ``conversation_id``, plus
``workspace_roots``), timestamped by the preceding ``[ISO-8601]`` log line.

Composer headers still supply title/workspace for classification. When turns
exist for a composer, composer-header heartbeats are skipped to avoid
double-counting.

Spec context: ``docs/specs/cursor-evidence-ceiling.md`` (GH-345).
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from collectors.ai_logs import _anchors, _meaningful_label
from collectors.cursor_composer import (
    _branch_reflected_in_label,
    _composer_classification_haystack,
    _composer_git_context,
    _composer_workspace_path,
    _path_dir_leaf,
    _read_composer_headers,
    cursor_state_db_path,
    load_cursor_workspaces,
)

CURSOR_AGENT_SOURCE = "Cursor (agent)"

_LOG_LINE_TS = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+)")
_HOOKS_BRACKET_TS = re.compile(r"^\[(\d{4}-\d{2}-\d{2}T[^\]]+)\]")
_WORKSPACE_ID_RE = re.compile(r"workspaceId-([0-9a-f]{32})")
_HOOKS_WORKSPACE_ID_RE = re.compile(r"workspaceId-([0-9a-f]{32}|empty-window)")
_JSON_TAIL_RE = re.compile(r"\{.*\}$")

_CLUSTER_GAP_SECONDS = 15 * 60
_THIN_SPACING_SECONDS = 5 * 60
_HOOKS_TURN_EVENT = "beforeSubmitPrompt"
# Match Zed/Conductor report snippets — never store full prompts in detail.
_PROMPT_SNIPPET_LEN = 80


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


def _parse_hooks_bracket_ts(line: str, local_tz) -> datetime | None:
    match = _HOOKS_BRACKET_TS.match(line)
    if not match:
        return None
    raw = match.group(1).replace("Z", "+00:00")
    try:
        aware = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if aware.tzinfo is None:
        aware = aware.replace(tzinfo=timezone.utc)
    return aware.astimezone(local_tz)


def _workspace_id_from_log_path(path: Path) -> str:
    match = _WORKSPACE_ID_RE.search(path.name)
    return match.group(1) if match else ""


def _workspace_id_from_hooks_path(path: Path) -> str:
    match = _HOOKS_WORKSPACE_ID_RE.search(path.name)
    if not match:
        return ""
    wid = match.group(1)
    return "" if wid == "empty-window" else wid


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


def _dedupe_stamps(stamps: list[datetime]) -> list[datetime]:
    """Drop duplicate wall-clock stamps (hooks logs are copied per window)."""
    seen: set[datetime] = set()
    out: list[datetime] = []
    for ts in sorted(stamps):
        if ts in seen:
            continue
        seen.add(ts)
        out.append(ts)
    return out


def _merge_stamp_buckets(
    *bucket_maps: dict[tuple[str, str], list[datetime]],
) -> dict[tuple[str, str], list[datetime]]:
    """Union sources, then collapse to one bucket per conversation_id.

    Hooks logs are duplicated across Cursor windows; always-local and hooks may
    also overlap on residual 3.9 files. Collapsing by conversation keeps one
    thinned timeline per agent chat.
    """
    by_cid: dict[str, list[datetime]] = {}
    workspace_for: dict[str, str] = {}
    for buckets in bucket_maps:
        for (conversation_id, workspace_id), stamps in buckets.items():
            by_cid.setdefault(conversation_id, []).extend(stamps)
            if workspace_id and not workspace_for.get(conversation_id):
                workspace_for[conversation_id] = workspace_id
    return {
        (cid, workspace_for.get(cid, "")): _dedupe_stamps(stamps)
        for cid, stamps in by_cid.items()
    }


def _collect_always_local_turn_starts(
    logs_dir: Path,
    dt_from: datetime,
    dt_to: datetime,
    local_tz,
) -> dict[tuple[str, str], list[datetime]]:
    """Map (conversation_id, workspace_id) from always-local ``agent.turn.start``."""
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


_JSON_DECODER = json.JSONDecoder()


def _iter_hooks_json_objects(lines: list[str]):
    """Yield (last_bracket_ts_line_or_none, obj) for hook INPUT payloads.

    Cursor writes each hook as a banner + ``INPUT:`` + pretty-printed JSON.
    Brace-counting across lines is unsafe: ``tool_output`` strings embed JSON
    with many ``{``/``}``, so a naive depth counter desyncs and later
    ``beforeSubmitPrompt`` objects are skipped (GH-345 follow-up).
    """
    last_ts_line: str | None = None
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        if _HOOKS_BRACKET_TS.match(line):
            last_ts_line = line
        if line.strip() == "INPUT:":
            j = i + 1
            while j < n and not lines[j].strip():
                j += 1
            if j >= n or not lines[j].lstrip().startswith("{"):
                i += 1
                continue
            blob = "\n".join(lines[j:])
            try:
                obj, end = _JSON_DECODER.raw_decode(blob)
            except json.JSONDecodeError:
                i += 1
                continue
            if isinstance(obj, dict):
                yield last_ts_line, obj
            # Advance past the consumed JSON (end is a character offset in blob).
            i = j + blob[:end].count("\n") + 1
            continue
        i += 1


def _prompt_preview(text: str, *, limit: int = _PROMPT_SNIPPET_LEN) -> str:
    """Short single-line user prompt for report detail (privacy-capped)."""
    snippet = " ".join(str(text or "").split())
    return snippet[:limit] if snippet else ""


def _prompt_for_stamp(
    prompts: list[tuple[datetime, str]],
    ts: datetime,
) -> str:
    """Exact stamp match, else nearest earlier prompt in the conversation."""
    if not prompts:
        return ""
    exact = ""
    earlier = ""
    for stamp, preview in prompts:
        if stamp == ts and preview:
            exact = preview
            break
        if stamp <= ts and preview:
            earlier = preview
    return exact or earlier


def _collect_hooks_turn_starts(
    logs_dir: Path,
    dt_from: datetime,
    dt_to: datetime,
    local_tz,
) -> tuple[
    dict[tuple[str, str], list[datetime]],
    dict[str, str],
    dict[str, list[tuple[datetime, str]]],
]:
    """Map turns from ``beforeSubmitPrompt`` in cursor.hooks logs (Cursor 3.10+).

    Returns buckets, conversation_id → workspace_roots path, and per-conversation
    ``(timestamp, prompt_preview)`` pairs for report detail (capped snippets only).
    """
    from_ts = dt_from.timestamp()
    buckets: dict[tuple[str, str], list[datetime]] = {}
    workspace_paths: dict[str, str] = {}
    prompts: dict[str, list[tuple[datetime, str]]] = {}
    if not logs_dir.is_dir():
        return buckets, workspace_paths, prompts

    for log_file in logs_dir.glob("**/output_*/cursor.hooks.workspaceId-*.log"):
        try:
            if log_file.stat().st_mtime < from_ts:
                continue
        except OSError:
            continue
        workspace_id = _workspace_id_from_hooks_path(log_file)
        try:
            text = log_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for ts_line, obj in _iter_hooks_json_objects(text.splitlines()):
            if obj.get("hook_event_name") != _HOOKS_TURN_EVENT:
                continue
            conversation_id = str(obj.get("conversation_id") or obj.get("session_id") or "").strip()
            if not conversation_id:
                continue
            roots = obj.get("workspace_roots")
            if isinstance(roots, list):
                for root in roots:
                    path = str(root or "").strip()
                    if path:
                        workspace_paths.setdefault(conversation_id, path)
                        break
            if ts_line is None:
                continue
            ts = _parse_hooks_bracket_ts(ts_line, local_tz)
            if ts is None or not (dt_from <= ts <= dt_to):
                continue
            key = (conversation_id, workspace_id)
            buckets.setdefault(key, []).append(ts)
            preview = _prompt_preview(str(obj.get("prompt") or ""))
            if preview:
                prompts.setdefault(conversation_id, []).append((ts, preview))
    for cid, rows in prompts.items():
        # Dedupe identical (ts, preview) from multi-window hook copies.
        seen: set[tuple[datetime, str]] = set()
        ordered: list[tuple[datetime, str]] = []
        for row in sorted(rows, key=lambda item: item[0]):
            if row in seen:
                continue
            seen.add(row)
            ordered.append(row)
        prompts[cid] = ordered
    return buckets, workspace_paths, prompts


def _collect_turn_starts(
    logs_dir: Path,
    dt_from: datetime,
    dt_to: datetime,
    local_tz,
) -> tuple[
    dict[tuple[str, str], list[datetime]],
    dict[str, str],
    dict[str, list[tuple[datetime, str]]],
]:
    """Union always-local (≤3.9) and hooks (3.10+) turn signals."""
    always_local = _collect_always_local_turn_starts(logs_dir, dt_from, dt_to, local_tz)
    hooks, workspace_paths, prompts = _collect_hooks_turn_starts(
        logs_dir, dt_from, dt_to, local_tz
    )
    return _merge_stamp_buckets(always_local, hooks), workspace_paths, prompts


def _turn_detail(
    *,
    ts: datetime,
    cluster_turns: int,
    branch: str | None,
    label: str,
    prompts: list[tuple[datetime, str]],
) -> str:
    preview = _prompt_for_stamp(prompts, ts)
    if preview:
        detail = f"[user] {preview}"
    else:
        detail = f"{cluster_turns} turn{'s' if cluster_turns != 1 else ''}"
    if branch and not _branch_reflected_in_label(branch, label or ""):
        detail += f" (@{branch})"
    return detail


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
    buckets, hooks_workspace_paths, prompts_by_cid = _collect_turn_starts(
        cursor_structured_logs_dir(home), dt_from, dt_to, local_tz
    )
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
        if not workspace:
            workspace = hooks_workspace_paths.get(conversation_id, "")
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
        anchors = _anchors(label=label, dir=dir_leaf, branch=branch)
        prompts = prompts_by_cid.get(conversation_id, [])

        emitted = False
        for cluster in _clusters(stamps):
            cluster_turns = len(cluster)
            for ts in _thin(cluster):
                results.append(
                    make_event(
                        CURSOR_AGENT_SOURCE,
                        ts,
                        _turn_detail(
                            ts=ts,
                            cluster_turns=cluster_turns,
                            branch=branch,
                            label=name or label or "",
                            prompts=prompts,
                        ),
                        project,
                        anchors=anchors,
                    )
                )
                emitted = True
        if emitted:
            covered.add(conversation_id)
    return results, covered
