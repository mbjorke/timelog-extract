"""SQLite read path for the Zed AI chat collector."""

from __future__ import annotations

import json
import sqlite3
import zlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class ZedMessage:
    """Represents a single message from Zed's chat history."""

    thread_id: str
    message_id: str
    timestamp: datetime
    role: str  # 'user' or 'assistant'
    content: str


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
    except ImportError:
        pass
    else:
        try:
            dctx = zstd.ZstdDecompressor()
            with io.BytesIO(data) as stream:
                decompressed = dctx.stream_reader(stream).read()
            return decompressed.decode("utf-8", errors="replace")
        except (zstd.ZstdError, UnicodeDecodeError, AttributeError, OSError):
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


def _quote_sql_ident(name: str) -> str:
    """Quote a SQLite identifier from local schema introspection (not user input)."""
    ident = str(name)
    if not ident or '"' in ident:
        raise ValueError(f"invalid SQL identifier: {name!r}")
    return f'"{ident}"'


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
            parsed = datetime.fromisoformat(ts_str)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed
        except ValueError:
            pass

    return None


def _in_report_window(ts: datetime | None, dt_from: datetime, dt_to: datetime) -> bool:
    if ts is None:
        return False
    return dt_from <= ts <= dt_to


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
                cursor.execute(f"PRAGMA table_info({_quote_sql_ident(table)})")
                schema[table] = [r[1] for r in cursor.fetchall()]
            except sqlite3.OperationalError:
                schema[table] = []
        conn.close()
    except (sqlite3.Error, OSError):
        pass
    return schema


def _parse_zed_message_entry(entry: Any) -> tuple[str, str] | None:
    """Parse a Zed message entry, handling both standard and role-keyed formats.

    Standard format: {"role": "user", "content": "..."}
    Zed format: {"User": {"content": [{"Text": "..."}]}}

    Returns: (role, content) tuple or None if no content found.
    """
    if not isinstance(entry, dict):
        return None

    # Try standard format first
    role = str(entry.get("role") or "").lower()
    content = str(entry.get("content") or entry.get("message") or "")
    if role and content:
        return role, content[:500]

    # Zed format: single key is the role, value contains content
    if len(entry) == 1:
        role_key = next(iter(entry.keys()))
        role = str(role_key).lower()
        role_data = entry.get(role_key, {})
        if isinstance(role_data, dict):
            content_obj = role_data.get("content", [])
            if isinstance(content_obj, list) and content_obj:
                first_content = content_obj[0]
                if isinstance(first_content, dict):
                    content = str(first_content.get("Text") or first_content.get("text") or "")
                    if content:
                        return role, content[:500]
                elif isinstance(first_content, str):
                    if first_content:
                        return role, first_content[:500]
            elif isinstance(content_obj, str):
                if content_obj:
                    return role, content_obj[:500]

    return None


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
        id_col = "id" if "id" in msg_cols else None
        cols = ([id_col] if id_col else []) + [thread_col, ts_col, content_col]
        if role_col:
            cols.append(role_col)
        query = (
            f"SELECT {', '.join(_quote_sql_ident(c) for c in cols)} "
            f"FROM {_quote_sql_ident(msg_table)} "
            f"WHERE {_quote_sql_ident(ts_col)} IS NOT NULL "
            f"ORDER BY {_quote_sql_ident(ts_col)}"
        )
        try:
            for row in conn.execute(query):
                drow = _row_as_dict(row)
                ts = _parse_zed_timestamp(drow.get(ts_col))
                if not ts or not _in_report_window(ts, dt_from, dt_to):
                    continue
                thread_id = str(drow.get(thread_col) or "unknown")
                msg_id = str(drow.get("id") or f"{thread_id}-{len(messages)}") if id_col else f"{thread_id}-{len(messages)}"
                role = str(drow.get(role_col) or "user").lower()
                if role not in ["user", "assistant", "system"]:
                    role = "user"
                raw_content = _decode_blob(drow.get(content_col))
                if raw_content:
                    # Try to parse as JSON first (for role-keyed Zed format)
                    try:
                        parsed = json.loads(raw_content)
                        parsed_msg = _parse_zed_message_entry(parsed)
                        if parsed_msg:
                            role, content = parsed_msg
                        else:
                            content = raw_content
                    except (json.JSONDecodeError, TypeError):
                        content = raw_content
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
                    select_cols.append(f"m.{_quote_sql_ident(col)}")
                elif col in thread_cols:
                    select_cols.append(f"t.{_quote_sql_ident(col)}")
            if not select_cols:
                continue
            ts_col = None
            for col in ["timestamp", "created_at", "updated_at", "date", "ts"]:
                if col in msg_cols:
                    ts_col = f"m.{_quote_sql_ident(col)}"
                    break
                elif col in thread_cols:
                    ts_col = f"t.{_quote_sql_ident(col)}"
                    break
            if not ts_col:
                continue
            ts_key = "__zed_ts"
            select_cols.append(f"{ts_col} AS {_quote_sql_ident(ts_key)}")
            on_clause = (
                f"m.{_quote_sql_ident('thread_id')} = t.{_quote_sql_ident('id')}"
                if "thread_id" in msg_cols
                else ""
            )
            if not on_clause:
                continue
            query = (
                f"SELECT {', '.join(select_cols)} "
                f"FROM {_quote_sql_ident(msg_table)} m "
                f"JOIN {_quote_sql_ident(thread_table)} t ON {on_clause} "
                f"WHERE {ts_col} IS NOT NULL ORDER BY {ts_col}"
            )
            try:
                for row in conn.execute(query):
                    drow = _row_as_dict(row)
                    thread_id = str(drow.get("thread_id") or drow.get("t.id") or "unknown")
                    msg_id = str(drow.get("id") or drow.get("m.id") or "unknown")
                    ts = _parse_zed_timestamp(drow.get(ts_key))
                    if not ts or not _in_report_window(ts, dt_from, dt_to):
                        continue
                    role = str(drow.get("role") or "user").lower()
                    if role not in ["user", "assistant", "system"]:
                        role = "user"
                    raw_content = (
                        _decode_blob(
                            drow.get("content") or drow.get("message") or drow.get("body") or b""
                        )
                        or ""
                    )
                    if raw_content:
                        # Try to parse as JSON first (for role-keyed Zed format)
                        try:
                            parsed = json.loads(raw_content)
                            parsed_msg = _parse_zed_message_entry(parsed)
                            if parsed_msg:
                                role, content = parsed_msg
                            else:
                                content = raw_content
                        except (json.JSONDecodeError, TypeError):
                            content = raw_content
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
        id_col = next((c for c in ["id", "thread_id"] if c in thread_cols), None)
        if not all([ts_col, content_col, id_col]):
            continue
        query = (
            f"SELECT {_quote_sql_ident(id_col)}, {_quote_sql_ident(ts_col)}, {_quote_sql_ident(content_col)} "
            f"FROM {_quote_sql_ident(thread_table)} "
            f"WHERE {_quote_sql_ident(ts_col)} IS NOT NULL "
            f"ORDER BY {_quote_sql_ident(ts_col)}"
        )
        try:
            for row in conn.execute(query):
                drow = _row_as_dict(row)
                thread_ts = _parse_zed_timestamp(drow.get(ts_col))
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
                                        or thread_ts
                                    )
                                    if not _in_report_window(msg_ts, dt_from, dt_to):
                                        continue
                                    parsed_msg = _parse_zed_message_entry(msg)
                                    if parsed_msg:
                                        role, content = parsed_msg
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
                                            or thread_ts
                                        )
                                        if not _in_report_window(msg_ts, dt_from, dt_to):
                                            continue
                                        parsed_msg = _parse_zed_message_entry(msg)
                                        if parsed_msg:
                                            role, content = parsed_msg
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
                                # Direct dict format - use helper for consistency
                                parsed_msg = _parse_zed_message_entry(parsed)
                                if parsed_msg:
                                    role, content = parsed_msg
                                    if content and _in_report_window(thread_ts, dt_from, dt_to):
                                        messages.append(
                                            ZedMessage(
                                                thread_id, f"{thread_id}-0", thread_ts, role, content
                                            )
                                        )
                    except (json.JSONDecodeError, TypeError):
                        content = str(raw_content)[:500]
                        if content and _in_report_window(thread_ts, dt_from, dt_to):
                            messages.append(
                                ZedMessage(thread_id, f"{thread_id}-0", thread_ts, "user", content)
                            )
        except (sqlite3.Error, KeyError):
            continue
    return messages
