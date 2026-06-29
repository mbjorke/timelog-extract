"""Conductor session collector.

Reads agent session activity from Conductor's local SQLite database. Conductor
(https://conductor.build) orchestrates many parallel coding agents (Claude Code,
Codex) in per-workspace git branches; its underlying agent binaries do not always
write to the per-tool global logs (e.g. Conductor's bundled Codex does not update
``~/.codex/session_index.jsonl``), so session activity is otherwise invisible to
the per-tool collectors. The session metadata — title, agent, model, per-message
prompts/replies — lives only in Conductor's database, typically at:

- macOS: ~/Library/Application Support/com.conductor.app/conductor.db

Project attribution comes from the workspace's repository row (``repos.remote_url``
/ ``repos.name``), so events land on the right project even when a message body
does not mention the repo. The database is opened read-only/immutable because
Conductor keeps it open (WAL mode) while running.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List

SOURCE = "Conductor"

# Known Conductor database locations.
_CONDUCTOR_DB_PATHS = [
    # macOS
    "~/Library/Application Support/com.conductor.app/conductor.db",
    # Linux (Electron app data)
    "~/.config/com.conductor.app/conductor.db",
    "~/.config/Conductor/conductor.db",
]

# Roles we surface as events. Conductor stores a lot of assistant-side bookkeeping
# (thinking-token meters, system notices, tool calls) that carries no readable
# detail; those are dropped because they extract no text below.
_KEPT_ROLES = {"user", "assistant"}

# Detail snippet length, matched to the other AI collectors (Zed/Codex).
_SNIPPET_LEN = 80


@dataclass
class ConductorMessage:
    """One readable message from a Conductor session, with attribution context."""

    timestamp: datetime
    role: str
    text: str
    session_title: str
    agent_type: str
    repo_slug: str | None
    classify_text: str


def _expand_path(path: str, home: Path) -> Path:
    return Path(path.replace("~", str(home))).expanduser()


def _find_conductor_db(home: Path) -> Path | None:
    """Return the first existing Conductor database, or None when not installed."""
    for candidate in _CONDUCTOR_DB_PATHS:
        full = _expand_path(candidate, home)
        if full.exists():
            return full
    return None


def _parse_timestamp(value: Any) -> datetime | None:
    """Parse Conductor's ISO-8601 timestamps (e.g. ``2026-06-29T11:47:25.944Z``)."""
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _repo_slug(remote_url: str | None) -> str | None:
    """Extract an ``owner/repo`` slug from a git remote URL, else None."""
    if not remote_url:
        return None
    cleaned = remote_url.strip()
    for prefix in ("https://github.com/", "git@github.com:", "http://github.com/"):
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix) :]
            break
    if cleaned.endswith(".git"):
        cleaned = cleaned[: -len(".git")]
    cleaned = cleaned.strip("/")
    return cleaned or None


def _message_text(role: str, content: str | None) -> str | None:
    """Readable text for a message.

    User messages are stored as plain text. Assistant messages are stored as the
    raw SDK envelope JSON (``{"type": "assistant", "message": {"content": [...]}}``);
    we join the ``text`` blocks and ignore thinking/tool/system payloads. Returns
    None when there is nothing human-readable to show.
    """
    if not content:
        return None
    raw = content.strip()
    if not raw:
        return None
    if role == "user":
        # Plain prompt text; not a JSON envelope.
        return raw
    # assistant: parse the envelope and keep text blocks only.
    try:
        obj = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(obj, dict):
        return None
    message = obj.get("message")
    if not isinstance(message, dict):
        return None
    blocks = message.get("content")
    if not isinstance(blocks, list):
        return None
    parts = [
        str(block.get("text", "")).strip()
        for block in blocks
        if isinstance(block, dict) and block.get("type") == "text"
    ]
    joined = " ".join(part for part in parts if part)
    return joined or None


def _format_detail(message: ConductorMessage) -> str:
    """Render the session name + role + message snippet for the report tree."""
    snippet = " ".join(message.text.split())[:_SNIPPET_LEN]
    role_label = f"[{message.role}]"
    title = message.session_title.strip()
    if title and title.lower() != "untitled":
        return f"{title}: {role_label} {snippet}"
    return f"{role_label} {snippet}"


def _read_messages(
    db_path: Path, dt_from: datetime, dt_to: datetime
) -> List[ConductorMessage]:
    """Best-effort read of in-window session messages from the Conductor DB."""
    # Read-only so we never lock or mutate Conductor's live (WAL-mode) database;
    # mode=ro still reads committed WAL pages, unlike immutable=1 which would skip them.
    uri = f"file:{db_path}?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True, timeout=5)
    except sqlite3.Error:
        return []
    messages: List[ConductorMessage] = []
    try:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT m.role          AS role,
                   m.content       AS content,
                   m.sent_at       AS sent_at,
                   m.created_at    AS created_at,
                   s.title         AS title,
                   s.agent_type    AS agent_type,
                   w.directory_name AS directory_name,
                   w.branch        AS branch,
                   r.name          AS repo_name,
                   r.remote_url    AS remote_url
            FROM session_messages m
            JOIN sessions s ON m.session_id = s.id
            LEFT JOIN workspaces w ON s.workspace_id = w.id
            LEFT JOIN repos r ON w.repository_id = r.id
            """
        ).fetchall()
    except sqlite3.Error:
        return []
    finally:
        conn.close()

    for row in rows:
        role = str(row["role"] or "").lower()
        if role not in _KEPT_ROLES:
            continue
        ts = _parse_timestamp(row["sent_at"]) or _parse_timestamp(row["created_at"])
        if ts is None or not (dt_from <= ts <= dt_to):
            continue
        text = _message_text(role, row["content"])
        if not text:
            continue
        remote_url = row["remote_url"]
        slug = _repo_slug(remote_url)
        # Attribution context: repo signal first so events land on the right
        # project even when the message body never names the repo.
        classify_text = " ".join(
            part
            for part in (
                remote_url,
                row["repo_name"],
                slug,
                row["directory_name"],
                row["branch"],
                row["title"],
            )
            if part
        )
        messages.append(
            ConductorMessage(
                timestamp=ts,
                role=role,
                text=text,
                session_title=str(row["title"] or ""),
                agent_type=str(row["agent_type"] or ""),
                repo_slug=slug,
                classify_text=classify_text,
            )
        )
    return messages


def collect_conductor(
    profiles: List[Dict[str, Any]],
    dt_from: datetime,
    dt_to: datetime,
    home: Path,
    classify_project: Callable[..., str],
    make_event: Callable[..., Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Collect Conductor agent-session events from the local SQLite database.

    Best-effort: a missing database, a schema mismatch, or unreadable rows yield
    no events rather than raising.
    """
    db_path = _find_conductor_db(home)
    if db_path is None:
        return []
    results: List[Dict[str, Any]] = []
    for message in _read_messages(db_path, dt_from, dt_to):
        project = classify_project(message.classify_text, profiles)
        anchors = {"repo": message.repo_slug} if message.repo_slug else None
        results.append(
            make_event(SOURCE, message.timestamp, _format_detail(message), project, anchors=anchors)
        )
    return results
