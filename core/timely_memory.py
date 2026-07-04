"""Timely Memory local-buffer presence helpers (opt-in, read-only).

The Timely Memory desktop tracker keeps a local SQLite buffer of foreground
samples (~1 row/second) that persists on disk after its own cloud upload.
Read locally and read-only, it is a high-resolution presence/duration signal.

Evidence role: ``coverage_comparator`` (same class as Screen Time) — presence
context for gap/coverage comparison. It never creates classified project time
and never contributes toward billable hours.

This module lives under ``core/`` (not ``collectors/``) because it mirrors
``core.screen_time.collect_screen_time``: a presence-summary read path wired
through ``core.presence_sources`` and ``collector_status``, not the event
pipeline that expects ``source``/``timestamp``/``detail``/``project`` dicts.

Privacy posture: reads **timestamps only**. Window titles, app names, and URLs
in the buffer are never read, and nothing leaves the machine. Access is
WAL-safe read-only (SQLite backup of the file into a temp copy); the third-party
database is never written to.
"""

from __future__ import annotations

import os
import sqlite3
import tempfile
from collections import defaultdict
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from core.screen_time import split_duration_by_local_day
from core.sqlite_backup import backup_sqlite_db

TIMELY_MEMORY_SOURCE = "Timely Memory"

# Consecutive foreground samples arrive ~1/second; bridge short stalls but
# break a presence span when samples stop for longer than this.
DEFAULT_SPAN_GAP_SECONDS = 30


def timely_memory_db_candidates(home: Path) -> list[Path]:
    """Default locations of the locally persisted Memory sample buffer."""
    return [home / "Library" / "Application Support" / "com.TimelyApp.Memory" / "db.sqlite"]


def detect_timely_memory_db(candidates: list[Path]) -> Optional[Path]:
    for path in candidates:
        if path.exists():
            return path
    return None


def timely_memory_source_enabled(args: Any) -> tuple[bool, Optional[str]]:
    """Strictly opt-in: only ``--timely-memory-source on`` enables reads."""
    mode = str(getattr(args, "timely_memory_source", "off") or "off").strip().lower()
    if mode == "on":
        return True, None
    return False, "Consent/source setting disabled (opt-in: --timely-memory-source on)"


def _parse_utc(ts_raw: Any) -> Optional[datetime]:
    """Parse the buffer's UTC timestamp strings (``YYYY-MM-DD HH:MM:SS``)."""
    if ts_raw is None:
        return None
    text = str(ts_raw).strip().replace("T", " ")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _fold_samples_into_spans(
    timestamps: list[datetime], gap_seconds: int
) -> list[tuple[datetime, datetime]]:
    """Fold ~1 Hz samples into contiguous presence spans."""
    spans: list[tuple[datetime, datetime]] = []
    span_start: Optional[datetime] = None
    prev: Optional[datetime] = None
    for ts in timestamps:
        if span_start is None:
            span_start = prev = ts
            continue
        assert prev is not None
        if (ts - prev).total_seconds() > gap_seconds:
            spans.append((span_start, prev))
            span_start = ts
        prev = ts
    if span_start is not None and prev is not None:
        spans.append((span_start, prev))
    return spans


def collect_timely_memory(
    dt_from: datetime,
    dt_to: datetime,
    *,
    candidates: list[Path],
    local_tz,
    gap_seconds: int = DEFAULT_SPAN_GAP_SECONDS,
):
    """Return per-day presence seconds for coverage comparison, not event dicts.

    Success: ``(daily_seconds_by_local_day, detail)`` where ``detail`` is the
    buffer path. Failure: ``(None, reason)``. Mirrors
    ``core.screen_time.collect_screen_time``; wired via
    ``collect_timely_memory_status`` in ``core.report_runtime``.

    Only the timestamp column is queried — never titles, app names, or URLs.
    """
    db_path = detect_timely_memory_db(candidates)
    if not db_path:
        return None, "Timely Memory buffer not found"

    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()

    timestamps: list[datetime] = []
    try:
        backup_sqlite_db(db_path, tmp.name)
        with closing(sqlite3.connect(f"file:{tmp.name}?mode=ro", uri=True)) as conn:
            rows = conn.execute(
                "SELECT captured_at_utc FROM captured_entries "
                "WHERE captured_at_utc >= ? AND captured_at_utc <= ? "
                "ORDER BY captured_at_utc",
                (
                    dt_from.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                    dt_to.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                ),
            ).fetchall()
    except sqlite3.Error as exc:
        return None, f"could not read Timely Memory buffer: {exc}"
    except PermissionError:
        return None, "no access to Timely Memory buffer"
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass

    for (ts_raw,) in rows:
        ts = _parse_utc(ts_raw)
        if ts is not None and dt_from <= ts <= dt_to:
            timestamps.append(ts)

    daily_seconds: dict[str, float] = defaultdict(float)
    for span_start, span_end in _fold_samples_into_spans(timestamps, gap_seconds):
        # Each ~1 Hz sample evidences its own second, so the span covers
        # [first sample, last sample + 1s) — a lone sample counts as 1s.
        span_end_exclusive = span_end + timedelta(seconds=1)
        for day, seconds in split_duration_by_local_day(span_start, span_end_exclusive, local_tz):
            daily_seconds[day] += seconds

    return daily_seconds, str(db_path)
