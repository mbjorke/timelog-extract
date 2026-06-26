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

import json
import re
import sqlite3
import zlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List

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


@dataclass
class ZedMessage:
    """Represents a single message from Zed's chat history."""

    thread_id: str
    message_id: str
    timestamp: datetime
    role: str  # 'user' or 'assistant'
    content: str


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


def _decode_blob(data: bytes | str | None) -> str | None:
    """Attempt to decode a potentially compressed blob from Zed's database."""
    if data is None:
        return None
    if isinstance(data, str):
        return data

    # Try zstd decompression first (Zed 0.150+ uses zstd with frame header)
    try:
        import io

        import zstandard as zstd

        dctx = zstd.ZstdDecompressor()
        with io.BytesIO(data) as stream:
            decompressed = dctx.stream_reader(stream).read()
        return decompressed.decode("utf-8", errors="replace")
    except (ImportError, zstd.ZstdError, UnicodeDecodeError, AttributeError, OSError):
        pass

    # Try zlib decompression (legacy Zed versions)
    try:
        decompressed = zlib.decompress(data)
        return decompressed.decode("utf-8", errors="replace")
    except (zlib.error, UnicodeDecodeError, AttributeError):
        pass

    # Try raw UTF-8
    try:
        return data.decode("utf-8", errors="replace")
    except (UnicodeDecodeError, AttributeError):
        pass

    return None


def _parse_zed_timestamp(ts_value: Any) -> datetime | None:
    """Parse various timestamp formats that Zed might use."""
    if ts_value is None:
        return None

    # Integer timestamp (seconds or milliseconds)
    if isinstance(ts_value, int):
        try:
            return datetime.fromtimestamp(ts_value, tz=timezone.utc)  # try seconds first
        except (OSError, ValueError):
            pass
        if ts_value > 1_000_000_000_000:  # milliseconds
            try:
                return datetime.fromtimestamp(ts_value / 1000.0, tz=timezone.utc)
            except (OSError, ValueError):
                pass

    # String timestamp (ISO format)
    if isinstance(ts_value, str):
        ts_str = ts_value.strip()
        if ts_str.endswith("Z"):
            ts_str = ts_str[:-1] + "+00:00"
        try:
            return datetime.fromisoformat(ts_str)
        except ValueError:
            pass

    return None


def _row_as_dict(row: sqlite3.Row | dict) -> dict:
    """Convert sqlite3.Row to dict for .get() support."""
    if isinstance(row, dict):
        return row
    return dict(row)


def _inspect_db_schema(db_path: Path) -> dict[str, list[str]]:
    """Inspect SQLite schema: returns {table: [columns]}."""
    schema: dict[str, list[str]] = {}
    try:
        conn = sqlite3.connect(str(db_path), timeout=5)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cursor.fetchall()]
        for table in tables:
            try:
                cursor.execute(f"PRAGMA table_info({table})")
                schema[table] = [r[1] for r in cursor.fetchall()]
            except sqlite3.OperationalError:
                schema[table] = []
        conn.close()
    except (sqlite3.Error, OSError):
        pass
    return schema


def _extract_messages_from_db(
    db_path: Path, dt_from: datetime, dt_to: datetime
) -> list[ZedMessage]:
    """Extract chat messages from Zed's SQLite DB using best-effort schema detection."""
    messages: list[ZedMessage] = []
    schema = _inspect_db_schema(db_path)
    if not schema:
        return messages

    message_tables = [t for t in schema if "message" in t.lower()]
    thread_tables = [t for t in schema if "thread" in t.lower()]

    strategies = [_query_messages_direct, _query_messages_join_threads, _query_threads_with_content]

    conn = None
    try:
        conn = sqlite3.connect(str(db_path), timeout=5)
        conn.row_factory = sqlite3.Row
        for strategy in strategies:
            result = strategy(conn, schema, message_tables, thread_tables, dt_from, dt_to)
            if result:
                messages.extend(result)
                if messages:
                    break
    except (sqlite3.Error, OSError):
        pass
    finally:
        if conn:
            conn.close()
    return messages


def _query_messages_direct(conn, schema, message_tables, thread_tables, dt_from, dt_to):
    """Query messages table directly."""
    messages = []
    for msg_table in message_tables:
        msg_cols = schema.get(msg_table, [])
        has_thread = any(c in msg_cols for c in ["thread_id", "thread"])
        has_ts = any(c in msg_cols for c in ["timestamp", "created_at", "date", "ts"])
        has_content = any(c in msg_cols for c in ["content", "message", "body", "text"])
        if not (has_thread and has_ts and has_content):
            continue
        thread_col = next((c for c in ["thread_id", "thread"] if c in msg_cols), None)
        ts_col = next((c for c in ["timestamp", "created_at", "date", "ts"] if c in msg_cols), None)
        content_col = next(
            (c for c in ["content", "message", "body", "text"] if c in msg_cols), None
        )
        role_col = next((c for c in ["role", "sender", "author"] if c in msg_cols), None)
        if not all([thread_col, ts_col, content_col]):
            continue
        cols = ["id", thread_col, ts_col, content_col]
        if role_col:
            cols.append(role_col)
        query = f"SELECT {', '.join(cols)} FROM {msg_table} WHERE {ts_col} IS NOT NULL ORDER BY {ts_col}"
        try:
            for row in conn.execute(query):
                drow = _row_as_dict(row)
                ts = _parse_zed_timestamp(drow.get(ts_col))
                if not ts or not (dt_from <= ts <= dt_to):
                    continue
                thread_id = str(drow.get(thread_col) or "unknown")
                msg_id = str(drow.get("id") or "unknown")
                role = str(drow.get(role_col) or "user").lower()
                if role not in ["user", "assistant", "system"]:
                    role = "user"
                content = _decode_blob(drow.get(content_col)) or ""
                if content:
                    messages.append(ZedMessage(thread_id, msg_id, ts, role, content[:500]))
        except (sqlite3.Error, KeyError):
            continue
    return messages


def _query_messages_join_threads(conn, schema, message_tables, thread_tables, dt_from, dt_to):
    """Query with JOIN between messages and threads."""
    messages = []
    if not message_tables or not thread_tables:
        return messages
    for msg_table in message_tables:
        for thread_table in thread_tables:
            msg_cols = schema.get(msg_table, [])
            thread_cols = schema.get(thread_table, [])
            if not all(c in msg_cols + thread_cols for c in ["id", "thread_id", "timestamp"]):
                continue
            select_cols = []
            for col in ["id", "thread_id", "timestamp", "role", "content", "message", "body"]:
                if col in msg_cols:
                    select_cols.append(f"m.{col}")
                elif col in thread_cols:
                    select_cols.append(f"t.{col}")
            if not select_cols:
                continue
            ts_col = None
            for col in ["timestamp", "created_at", "updated_at", "date", "ts"]:
                if col in msg_cols:
                    ts_col = f"m.{col}"
                    break
                elif col in thread_cols:
                    ts_col = f"t.{col}"
                    break
            if not ts_col:
                continue
            on_clause = "m.thread_id = t.id" if "thread_id" in msg_cols else ""
            if not on_clause:
                continue
            query = f"SELECT {', '.join(select_cols)} FROM {msg_table} m JOIN {thread_table} t ON {on_clause} WHERE {ts_col} IS NOT NULL ORDER BY {ts_col}"
            try:
                for row in conn.execute(query):
                    drow = _row_as_dict(row)
                    thread_id = str(drow.get("thread_id") or drow.get("t.id") or "unknown")
                    msg_id = str(drow.get("id") or drow.get("m.id") or "unknown")
                    ts = _parse_zed_timestamp(
                        drow.get("timestamp") or drow.get("m.timestamp") or drow.get("t.timestamp")
                    )
                    if not ts or not (dt_from <= ts <= dt_to):
                        continue
                    role = str(drow.get("role") or "user").lower()
                    if role not in ["user", "assistant", "system"]:
                        role = "user"
                    content = (
                        _decode_blob(
                            drow.get("content") or drow.get("message") or drow.get("body") or b""
                        )
                        or ""
                    )
                    if content:
                        messages.append(ZedMessage(thread_id, msg_id, ts, role, content[:500]))
            except (sqlite3.Error, KeyError):
                continue
    return messages


def _query_threads_with_content(conn, schema, message_tables, thread_tables, dt_from, dt_to):
    """Query threads table with embedded message content."""
    messages = []
    for thread_table in thread_tables:
        thread_cols = schema.get(thread_table, [])
        has_ts = any(c in thread_cols for c in ["timestamp", "created_at", "updated_at", "date"])
        has_content = any(c in thread_cols for c in ["content", "messages", "history", "data"])
        if not (has_ts and has_content):
            continue
        ts_col = next(
            (c for c in ["timestamp", "created_at", "updated_at", "date"] if c in thread_cols), None
        )
        content_col = next(
            (c for c in ["content", "messages", "history", "data"] if c in thread_cols), None
        )
        id_col = next((c for c in ["id", "thread_id"] if c in thread_cols), "id")
        if not all([ts_col, content_col, id_col]):
            continue
        query = f"SELECT {id_col}, {ts_col}, {content_col} FROM {thread_table} WHERE {ts_col} IS NOT NULL ORDER BY {ts_col}"
        try:
            for row in conn.execute(query):
                drow = _row_as_dict(row)
                ts = _parse_zed_timestamp(drow.get(ts_col))
                if not ts or not (dt_from <= ts <= dt_to):
                    continue
                thread_id = str(drow.get(id_col) or "unknown")
                raw_content = drow.get(content_col)
                if isinstance(raw_content, bytes):
                    raw_content = _decode_blob(raw_content)
                if raw_content:
                    try:
                        parsed = json.loads(raw_content)
                        if isinstance(parsed, list):
                            for i, msg in enumerate(parsed):
                                if isinstance(msg, dict):
                                    msg_ts = (
                                        _parse_zed_timestamp(
                                            msg.get("timestamp") or msg.get("created_at")
                                        )
                                        or ts
                                    )
                                    role = str(msg.get("role") or "user").lower()
                                    content = str(msg.get("content") or msg.get("message") or "")[
                                        :500
                                    ]
                                    if content:
                                        messages.append(
                                            ZedMessage(
                                                thread_id, f"{thread_id}-{i}", msg_ts, role, content
                                            )
                                        )
                        elif isinstance(parsed, dict):
                            # Handle dict with nested messages array
                            messages_list = parsed.get("messages", [])
                            if messages_list and isinstance(messages_list, list):
                                for i, msg in enumerate(messages_list):
                                    if isinstance(msg, dict):
                                        msg_ts = (
                                            _parse_zed_timestamp(
                                                msg.get("timestamp") or msg.get("created_at")
                                            )
                                            or ts
                                        )
                                        role = str(msg.get("role") or "user").lower()
                                        content = str(
                                            msg.get("content") or msg.get("message") or ""
                                        )[:500]
                                        if content:
                                            messages.append(
                                                ZedMessage(
                                                    thread_id,
                                                    f"{thread_id}-{i}",
                                                    msg_ts,
                                                    role,
                                                    content,
                                                )
                                            )
                                        else:
                                            # Zed format: {"User": {...}, "Agent": {...}}
                                            # The dict has a single key which is the role
                                            if len(msg) == 1:
                                                role_key = next(iter(msg.keys()))
                                                role = str(role_key).lower()
                                                role_data = msg.get(role_key, {})
                                                if isinstance(role_data, dict):
                                                    # Extract content from role_data
                                                    content_obj = role_data.get("content", [])
                                                    if (
                                                        isinstance(content_obj, list)
                                                        and content_obj
                                                    ):
                                                        # Zed uses list of content objects, get Text from first
                                                        first_content = content_obj[0]
                                                        if isinstance(first_content, dict):
                                                            content = str(
                                                                first_content.get("Text")
                                                                or first_content.get("text")
                                                                or ""
                                                            )[:500]
                                                        else:
                                                            content = str(content_obj[0])[:500]
                                                    elif isinstance(content_obj, str):
                                                        content = content_obj[:500]
                                                    else:
                                                        continue
                                                    if content:
                                                        messages.append(
                                                            ZedMessage(
                                                                thread_id,
                                                                f"{thread_id}-{i}",
                                                                msg_ts,
                                                                role,
                                                                content,
                                                            )
                                                        )
                            else:
                                # Direct dict format
                                role = str(parsed.get("role") or "user").lower()
                                content = str(parsed.get("content") or parsed.get("message") or "")[
                                    :500
                                ]
                                if content:
                                    messages.append(
                                        ZedMessage(thread_id, f"{thread_id}-0", ts, role, content)
                                    )
                    except (json.JSONDecodeError, TypeError):
                        content = str(raw_content)[:500]
                        if content:
                            messages.append(
                                ZedMessage(thread_id, f"{thread_id}-0", ts, "user", content)
                            )
        except (sqlite3.Error, KeyError):
            continue
    return messages


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
