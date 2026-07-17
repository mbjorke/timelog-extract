"""Claude Desktop Code session evidence from the cached events API.

Claude Desktop Code sessions leave no first-class local log; the only local
trace of the full turn-by-turn timeline is the cached response of
``https://claude.ai/v1/sessions/<id>/events`` in the Chromium disk cache
(zstd-compressed JSON). This collector reconstructs honest active spans from
those cached bodies. Spec: ``docs/task-prompts/claude-desktop-chat-code-evidence.md``.

Privacy (mandatory): only ``created_at``, ``type``, ``uuid``, ``session_id``,
and the ``cwd`` attribution field are read. ``message`` content (full chat and
code text) is never accessed, persisted, or surfaced.

Retention: the cache evicts oldest entries, so recent sessions reconstruct
reliably while old sessions degrade to nothing (never fabricated hours).
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from collectors.ai_logs import _anchors, _cwd_leaf, _meaningful_label
from core.chromium_cache import (
    CODEC_REINSTALL_HINT,
    BoundedRawCache,
    codec_available,
    iter_cache_entries,
)
from core.repo_slug import resolve_path_repo_slug, slug_from_remote_url

CLAUDE_DESKTOP_CODE_SOURCE = "Claude Desktop (Code)"

_SESSIONS_KEY_MARKER = "/v1/sessions/"
_SESSION_ID_RE = re.compile(r"/v1/sessions/([^/?]+)/events")

# Event types that represent a real user/model turn (for the turn count in the
# detail line); all evented timestamps still extend the active span.
_TURN_TYPES = frozenset({"user", "assistant"})

# Sessions split into separate active clusters after this idle gap, matching
# the report's default session gap.
_CLUSTER_GAP_SECONDS = 15 * 60
# Within a cluster, keep real turn timestamps at most this far apart so
# compute_sessions() reconstructs the span without emitting every turn.
_THIN_SPACING_SECONDS = 5 * 60


def claude_events_cache_dir(home: Path) -> Path:
    return home / "Library" / "Application Support" / "Claude" / "Cache" / "Cache_Data"


def claude_events_cache_status(home: Path) -> tuple[bool, str]:
    """(usable, reason) for `gittan doctor`: cache dir presence + zstd codec."""
    if not claude_events_cache_dir(home).is_dir():
        return False, "No Claude Desktop cache yet (open Claude Desktop to create one)"
    if not codec_available()["zstd"]:
        return False, f"zstandard codec missing ({CODEC_REINSTALL_HINT})"
    return True, "Events cache readable"


def _parse_created_at(raw) -> Optional[datetime]:
    if not raw:
        return None
    try:
        ts = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts


def _session_id_from_key(key: str) -> str:
    match = _SESSION_ID_RE.search(key)
    return match.group(1) if match else ""


def _clusters(stamps: list[tuple[datetime, bool]]) -> list[list[tuple[datetime, bool]]]:
    """Split (timestamp, is_turn) pairs into active clusters by idle gap."""
    ordered = sorted(stamps, key=lambda pair: pair[0])
    clusters: list[list[tuple[datetime, bool]]] = []
    for pair in ordered:
        if clusters and (pair[0] - clusters[-1][-1][0]).total_seconds() <= _CLUSTER_GAP_SECONDS:
            clusters[-1].append(pair)
        else:
            clusters.append([pair])
    return clusters


def _thin(stamps: list[datetime]) -> list[datetime]:
    """Keep first/last plus intermediates ≥ _THIN_SPACING_SECONDS apart.

    Every kept value is a real event timestamp (nothing is fabricated); the
    spacing just keeps the timeline readable while compute_sessions() still
    sees one continuous span.
    """
    if not stamps:
        return []
    kept = [stamps[0]]
    for ts in stamps[1:-1]:
        if (ts - kept[-1]).total_seconds() >= _THIN_SPACING_SECONDS:
            kept.append(ts)
    # Close the span with the real last timestamp, unless it would render as a
    # duplicate row seconds after the previous kept one.
    if (stamps[-1] - kept[-1]).total_seconds() > 60:
        kept.append(stamps[-1])
    return kept


def _session_repo_slug(obj: dict) -> str:
    """Repo slug from session metadata git outcomes/sources, or ``""``.

    ``session_context.outcomes[].git_info.repo`` carries an explicit
    ``owner/repo`` for sessions bound to a repository; ``sources[].url`` holds
    the clone URL. Both are worktree-invariant attribution keys.
    """
    ctx = obj.get("session_context")
    if not isinstance(ctx, dict):
        return ""
    for outcome in ctx.get("outcomes") or []:
        if not isinstance(outcome, dict):
            continue
        git_info = outcome.get("git_info")
        if isinstance(git_info, dict):
            slug = str(git_info.get("repo") or "").strip().lower()
            if "/" in slug:
                return slug
    for source in ctx.get("sources") or []:
        if isinstance(source, dict) and source.get("url"):
            slug = slug_from_remote_url(source["url"])
            if slug:
                return slug
    return ""


def _session_meta(cache_dir: Path, *, raw_cache: dict | None = None) -> dict[str, dict[str, str]]:
    """Map session id → {title, slug} from cached session metadata.

    Claude Desktop also caches `/v1/sessions/<id>` detail and `/v1/sessions?…`
    list responses: `title` is the human session name shown in the app
    (invoice-readable detail) and the session context carries the repo slug
    (worktree-invariant attribution). Metadata only — never message content.
    """
    meta: dict[str, dict[str, str]] = {}

    def harvest(obj) -> None:
        if not isinstance(obj, dict):
            return
        sid = str(obj.get("id") or "")
        if not sid:
            return
        entry = meta.setdefault(sid, {"title": "", "slug": ""})
        title = str(obj.get("title") or "").strip()
        if title and not entry["title"]:
            entry["title"] = title
        slug = _session_repo_slug(obj)
        if slug and not entry["slug"]:
            entry["slug"] = slug

    for entry in iter_cache_entries(
        cache_dir,
        _SESSIONS_KEY_MARKER.rstrip("/"),
        key_predicate=lambda key: "/events" not in key,
        raw_cache=raw_cache,
    ):
        try:
            payload = json.loads(entry.body)
        except (ValueError, UnicodeDecodeError):
            continue
        harvest(payload)
        if isinstance(payload, dict):
            rows = payload.get("data")
            if isinstance(rows, list):
                for row in rows:
                    harvest(row)
    return meta


def collect_claude_desktop_code(profiles, dt_from, dt_to, home, classify_project, make_event):
    """Reconstruct Claude Desktop Code sessions from cached /events bodies."""
    cache_dir = claude_events_cache_dir(home)
    if not cache_dir.is_dir():
        return []

    # session id -> accumulator; uuid-dedupe spans overlapping cache entries
    # (the app re-fetches /events with after_id pagination).
    sessions: dict[str, dict] = {}
    # Shared with _session_meta below: both scan the same cache_dir (this pass
    # date-filtered for events, that one unfiltered for titles/slugs), so a
    # file read here is reused there instead of hitting disk twice. Bounded
    # so the later unfiltered pass can't retain a very large cache directory's
    # bytes in memory all at once (Qodo review, PR #388).
    raw_cache = BoundedRawCache()
    for entry in iter_cache_entries(
        cache_dir, _SESSIONS_KEY_MARKER, newer_than=dt_from, raw_cache=raw_cache
    ):
        if "/events" not in entry.key:
            continue
        try:
            payload = json.loads(entry.body)
        except (ValueError, UnicodeDecodeError):
            continue
        rows = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(rows, list):
            continue
        key_sid = _session_id_from_key(entry.key)
        for ev in rows:
            if not isinstance(ev, dict):
                continue
            # Prefer the session id from the cache key: it is the public id
            # behind Claude Desktop's "Copy link" (user-verifiable), and it
            # unifies events that carry an internal session_id UUID with those
            # that carry none — otherwise one session splits in two.
            sid = key_sid or str(ev.get("session_id") or "")
            if not sid:
                continue
            acc = sessions.setdefault(
                sid, {"uuids": set(), "stamps": [], "cwd": None, "cwd_path": ""}
            )
            if ev.get("cwd") and not acc["cwd"]:
                acc["cwd"] = _cwd_leaf(ev)
                acc["cwd_path"] = str(ev.get("cwd") or "")
            uuid = str(ev.get("uuid") or "")
            if uuid:
                if uuid in acc["uuids"]:
                    continue
                acc["uuids"].add(uuid)
            ts = _parse_created_at(ev.get("created_at"))
            if ts is None or not (dt_from <= ts <= dt_to):
                continue
            is_turn = str(ev.get("type") or "").strip().lower() in _TURN_TYPES
            acc["stamps"].append((ts, is_turn))

    meta = _session_meta(cache_dir, raw_cache=raw_cache) if sessions else {}

    results = []
    for sid, acc in sessions.items():
        if not acc["stamps"]:
            continue
        cwd = acc["cwd"]
        title = meta.get(sid, {}).get("title", "")
        # Worktree-invariant attribution: explicit slug from session metadata,
        # else resolved from the session cwd when it is a local repo path.
        slug = meta.get(sid, {}).get("slug", "") or resolve_path_repo_slug(acc["cwd_path"])
        meaningful = _meaningful_label(title)
        for cluster in _clusters(acc["stamps"]):
            turns = sum(1 for _ts, is_turn in cluster if is_turn)
            if turns == 0:
                # Background-only cluster (rate-limit pings, env refreshes):
                # no real user/model turn, so no honest hours to claim.
                continue
            detail = f"{turns} turn{'s' if turns != 1 else ''}"
            project = classify_project(f"{slug} {cwd or ''} {title} {detail}", profiles)
            for ts in _thin([pair[0] for pair in cluster]):
                results.append(
                    make_event(
                        CLAUDE_DESKTOP_CODE_SOURCE,
                        ts,
                        detail,
                        project,
                        anchors=_anchors(repo=slug, dir=cwd, label=meaningful),
                    )
                )
    return results
