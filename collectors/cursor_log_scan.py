"""Cursor diagnostic log day-folder scan helpers.

Cursor stores logs under ``~/Library/Application Support/Cursor/logs/<YYYYMMDDTHHMMSS>/``.
Scanning the whole tree with ``**`` is too slow on a large live HOME (hundreds of
MB) when the report window is old — mtime filters still open every recent file.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from pathlib import Path

# Cursor log day folders: ``20260709T162324`` (local wall clock of the session).
_LOG_DAY_FOLDER_RE = re.compile(r"^(\d{8})T\d{6}$")


def cursor_structured_logs_dir(home: Path) -> Path:
    return home / "Library" / "Application Support" / "Cursor" / "logs"


def iter_log_day_dirs(
    logs_dir: Path,
    dt_from: datetime,
    dt_to: datetime,
    local_tz,
) -> list[Path]:
    """Restrict scans to Cursor day folders that can overlap the report window.

    Day-folder names encode the session calendar day; pad ±1 day for spill.
    Unknown folder layouts are kept so a Cursor rename does not go silent.
    """
    if not logs_dir.is_dir():
        return []
    start = dt_from.astimezone(local_tz).date() - timedelta(days=1)
    end = dt_to.astimezone(local_tz).date() + timedelta(days=1)
    matched: list[Path] = []
    unknown: list[Path] = []
    try:
        entries = list(logs_dir.iterdir())
    except OSError:
        return []
    for entry in entries:
        if not entry.is_dir():
            continue
        m = _LOG_DAY_FOLDER_RE.match(entry.name)
        if not m:
            unknown.append(entry)
            continue
        try:
            day = datetime.strptime(m.group(1), "%Y%m%d").date()
        except ValueError:
            unknown.append(entry)
            continue
        if start <= day <= end:
            matched.append(entry)
    return matched + unknown
