"""macOS Calendar collector (local-first, read-only).

Reads events from the local Calendar SQLite store. A calendar's evidence role is
assigned per calendar name (see docs/specs/scheduled-reported-time-bridge.md):

- a dedicated time-report calendar is a ``primary_claim``;
- a meetings calendar is ``scheduled_context``.

Scope (P1): all-day events are excluded, recurring events are NOT expanded
(only already-materialized instances are read), and the source is opt-in/off by
default. The role is attached to each event's private metadata so the future
reported-time bridge can treat time-report and meetings calendars differently;
this collector does not itself decide how hours are counted.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from collectors.ai_logs import _anchors

CALENDAR_SOURCE = "Calendar"

# Cocoa/CFAbsoluteTime epoch is 2001-01-01 00:00:00 UTC.
_COCOA_EPOCH = datetime(2001, 1, 1, tzinfo=timezone.utc)

ROLE_PRIMARY_CLAIM = "primary_claim"
ROLE_SCHEDULED_CONTEXT = "scheduled_context"
_VALID_ROLES = {ROLE_PRIMARY_CLAIM, ROLE_SCHEDULED_CONTEXT}
DEFAULT_ROLE = ROLE_SCHEDULED_CONTEXT


def calendar_db_path(home: Path) -> Path:
    """Local macOS Calendar SQLite store (subscribed Google/iCloud sync here too)."""
    return (
        home
        / "Library"
        / "Group Containers"
        / "group.com.apple.calendar"
        / "Calendar.sqlitedb"
    )


def detect_calendar_db(home: Path) -> Tuple[Optional[Path], str]:
    """Return (path, status). ``status`` is ``"ok"`` or a human reason.

    Validates that the path is a readable SQLite database with the tables this
    collector reads, so the doctor health row does not report a false "accessible"
    for a corrupt file or an unexpected schema.
    """
    path = calendar_db_path(home)
    if not path.is_file():
        return None, "Calendar database not found"
    try:
        with open(path, "rb"):
            pass
    except PermissionError:
        return None, "Full Disk Access required"
    except OSError as exc:
        return None, f"Calendar database unreadable: {exc}"
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            present = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' "
                    "AND name IN ('Calendar', 'CalendarItem')"
                )
            }
        finally:
            conn.close()
    except sqlite3.Error as exc:
        return None, f"Calendar database invalid: {exc}"
    if {"Calendar", "CalendarItem"} - present:
        return None, "Calendar database missing expected tables"
    return path, "ok"


def parse_calendar_roles(raw: Optional[str]) -> Dict[str, str]:
    """Parse ``"Work:scheduled_context,TimeReport:primary_claim"`` into a map.

    Bare names (``"Work,TimeReport"``) default to ``scheduled_context``. Keys are
    matched case-insensitively against calendar titles. Invalid roles fall back
    to the default rather than raising.
    """
    roles: Dict[str, str] = {}
    if not raw:
        return roles
    for part in str(raw).split(","):
        item = part.strip()
        if not item:
            continue
        if ":" in item:
            name, _, role = item.partition(":")
            name = name.strip()
            role = role.strip().lower()
        else:
            name, role = item, DEFAULT_ROLE
        if not name:
            continue
        roles[name.lower()] = role if role in _VALID_ROLES else DEFAULT_ROLE
    return roles


_COCOA_EPOCH_UNIX = _COCOA_EPOCH.timestamp()


def _cocoa_to_utc(ts: float) -> datetime:
    return datetime.fromtimestamp(_COCOA_EPOCH_UNIX + ts, tz=timezone.utc)


def _iter_calendar_rows(db_path: Path, dt_from: datetime, dt_to: datetime):
    """Yield ``(cal_title, summary, start_dt, end_dt)`` for in-window events.

    Shared read path for the collector and the title reader: opens the DB
    read-only, filters to the requested window, skips all-day events and rows
    with missing start/end (bad data). Iterates the cursor rather than loading
    all rows so a wide window does not blow up memory.
    """
    start_cocoa = dt_from.astimezone(timezone.utc).timestamp() - _COCOA_EPOCH_UNIX
    end_cocoa = dt_to.astimezone(timezone.utc).timestamp() - _COCOA_EPOCH_UNIX
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        cursor = conn.execute(
            """
            SELECT c.title, ci.summary, ci.start_date, ci.end_date, ci.all_day
            FROM CalendarItem ci
            JOIN Calendar c ON c.ROWID = ci.calendar_id
            WHERE ci.start_date >= ? AND ci.start_date <= ?
            ORDER BY ci.start_date
            """,
            (start_cocoa, end_cocoa),
        )
        for cal_title, summary, start_raw, end_raw, all_day in cursor:
            cal_title = cal_title or ""
            if all_day:
                continue  # D2: all-day events excluded in v1
            if start_raw is None or end_raw is None:
                continue  # bad data: skip rather than emit a 0-hour event
            start_dt = _cocoa_to_utc(float(start_raw))
            end_dt = _cocoa_to_utc(float(end_raw))
            if not (dt_from <= start_dt <= dt_to):
                continue
            yield cal_title, (summary or "").strip(), start_dt, end_dt
    finally:
        conn.close()


def read_calendar_titles(
    home: Path,
    dt_from: datetime,
    dt_to: datetime,
    calendar_names: Optional[List[str]] = None,
) -> List[Tuple[str, str]]:
    """Return ``(calendar_name, summary)`` for events in the window.

    Unlike :func:`collect_calendar`, this does not classify events or require a
    role map — it returns raw titles for onboarding / project-code suggestion.
    When ``calendar_names`` is given, only those calendars are included (matched
    case-insensitively); otherwise all calendars are returned.

    Raises:
        RuntimeError: if the Calendar database cannot be opened.
    """
    db_path, status = detect_calendar_db(home)
    if db_path is None:
        raise RuntimeError(status)
    wanted = {n.strip().lower() for n in (calendar_names or []) if n and n.strip()}
    out: List[Tuple[str, str]] = []
    for cal_title, summary, _start, _end in _iter_calendar_rows(db_path, dt_from, dt_to):
        if wanted and cal_title.lower() not in wanted:
            continue
        if summary:
            out.append((cal_title, summary))
    return out


def collect_calendar(
    profiles: List[Dict[str, Any]],
    dt_from: datetime,
    dt_to: datetime,
    home: Path,
    classify_project: Callable,
    make_event: Callable,
    *,
    calendar_roles: Optional[Dict[str, str]] = None,
) -> List[dict]:
    """Collect calendar events within [dt_from, dt_to] from the configured calendars.

    Only calendars present in ``calendar_roles`` are read. All-day events are
    skipped, recurring events are not expanded (only stored instances appear),
    and events without an end time are skipped (treated as bad data rather than
    emitted as misleading zero-duration records).

    Raises:
        RuntimeError: if the Calendar database cannot be opened (not found,
            permission denied / Full Disk Access, or other OS error), so the
            empty result is diagnosable via ``collector_status`` instead of silent.
    """
    results: List[dict] = []
    roles = calendar_roles or {}
    if not roles:
        return results

    db_path, status = detect_calendar_db(home)
    if db_path is None:
        # Surface as a collector error so status is diagnosable, not silent.
        raise RuntimeError(status)

    seen: set[Tuple[str, str, str, str]] = set()
    for cal_title, summary, start_dt, end_dt in _iter_calendar_rows(db_path, dt_from, dt_to):
        role = roles.get(cal_title.lower())
        if role is None:
            continue  # calendar not selected

        # Include end in the key so two same-titled meetings at the same start
        # but different durations are not wrongly collapsed.
        key = (cal_title, summary, start_dt.isoformat(), end_dt.isoformat())
        if key in seen:
            continue
        seen.add(key)

        project = classify_project(f"{cal_title} {summary}", profiles)
        hours = max((end_dt - start_dt).total_seconds() / 3600.0, 0.0)
        title = (summary or "").strip()
        detail = f"[{cal_title}] {hours:.2f}h"
        if not title:
            detail = f"(no title) {detail}"
        event = make_event(
            CALENDAR_SOURCE,
            start_dt,
            detail,
            project,
            anchors=_anchors(label=title) if title else None,
        )
        # Private metadata for the reported-time bridge (not invoice truth here).
        event["calendar_role"] = role
        event["calendar_name"] = cal_title
        event["calendar_end"] = end_dt
        results.append(event)

    return results
