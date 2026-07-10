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

    Folder names encode the *app launch* time, not the log-entry day: a
    long-lived Cursor process appends to the same folder for days (GH-363).
    So only folders named after the window end (+1 day pad) are excluded —
    they cannot contain in-window entries. Older folders are always kept;
    the per-file ``st_mtime`` checks in the scanners skip stale files cheaply,
    which preserves the GH-353 perf goal for old-window reports.
    Unknown folder layouts are kept so a Cursor rename does not go silent.
    """
    del dt_from  # lower bound intentionally not applied (GH-363)
    if not logs_dir.is_dir():
        return []
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
        if day <= end:
            matched.append(entry)
    return matched + unknown
