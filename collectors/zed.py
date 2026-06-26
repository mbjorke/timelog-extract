"""Zed AI chat collector.

Reads AI conversation history from Zed's local SQLite database.
Zed stores chat threads in a SQLite database, typically at:
- macOS: ~/Library/Application Support/zed/db/threads.db
- Linux: ~/.local/share/zed/db/threads.db
- Windows: %APPDATA%\\zed\\db\\threads.db

The database schema is not officially documented, so we use best-effort
querying to extract conversation metadata and messages.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List

from collectors import zed_db
from collectors.zed_db import ZedMessage, _extract_messages_from_db

# Re-exported for tests and backward-compatible imports.
_parse_zed_message_entry = zed_db._parse_zed_message_entry
_parse_zed_timestamp = zed_db._parse_zed_timestamp

SOURCE = "Zed"

# Common Zed data directory locations
_ZED_DB_PATHS = [
    # macOS (primary location - Zed 0.150+)
    "~/Library/Application Support/zed/threads/threads.db",
    # macOS (legacy location)
    "~/Library/Application Support/zed/db/threads.db",
    # Linux
    "~/.local/share/zed/db/threads.db",
    "~/.local/share/zed/threads/threads.db",
    # Windows
    "~/AppData/Roaming/zed/db/threads.db",
]


def _expand_path(path: str, home: Path) -> Path:
    """Expand ~ and environment variables in a path."""
    path = path.replace("~", str(home))
    return Path(path).expanduser().resolve()


def _find_zed_db(home: Path) -> Path | None:
    """Find Zed's threads database by checking known locations."""
    for db_path in _ZED_DB_PATHS:
        full_path = _expand_path(db_path, home)
        if full_path.exists():
            return full_path
    return None


def _format_detail(message: ZedMessage) -> str:
    """Format a Zed message into a detail string."""
    role_prefix = "[assistant]" if message.role == "assistant" else "[user]"
    content_preview = message.content[:80].replace("\n", " ")
    return f"{role_prefix} {content_preview}"


def _extract_project_anchors(message: ZedMessage) -> dict[str, str] | None:
    """Extract project anchors from message content."""
    content_lower = message.content.lower()
    anchors = {}
    # Repository path patterns
    repo_match = re.search(
        r"(?:/|\\\\)([a-z0-9_-]+\\.[a-z0-9_-]+(?:\\.[a-z0-9_-]+)*)", content_lower
    )
    if repo_match:
        anchors["repo"] = repo_match.group(1)
    # Project name patterns (match lowercase since content is already lowercased)
    project_match = re.search(r"\b([a-z][a-z0-9_-]*(?: [a-z][a-z0-9_-]*){0,2})\b", content_lower)
    if project_match:
        anchors["project"] = project_match.group(1).lower()
    return anchors if anchors else None


def collect_zed(
    profiles: List[Dict[str, Any]],
    dt_from: datetime,
    dt_to: datetime,
    home: Path,
    classify_project: Callable[..., str],
    make_event: Callable[..., Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Collect Zed AI chat events from local SQLite database.

    Best-effort collection: if the DB exists but schema doesn't match expected
    patterns, we gracefully return no events rather than crashing.
    """
    db_path = _find_zed_db(home)
    if db_path is None:
        return []
    messages = _extract_messages_from_db(db_path, dt_from, dt_to)
    if not messages:
        return []
    results = []
    for message in messages:
        detail = _format_detail(message)
        project = classify_project(message.content, profiles)
        anchors = _extract_project_anchors(message)
        event = make_event(SOURCE, message.timestamp, detail, project, anchors=anchors)
        results.append(event)
    return results
