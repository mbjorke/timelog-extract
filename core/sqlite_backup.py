"""SQLite helpers for WAL-safe database copies."""

from __future__ import annotations

import sqlite3
from pathlib import Path


def backup_sqlite_db(source_path: Path, dest_path: str) -> None:
    """Copy a SQLite database including uncheckpointed WAL frames."""
    uri = f"file:{source_path}?mode=ro"
    with sqlite3.connect(uri, uri=True) as src:
        with sqlite3.connect(dest_path) as dest:
            src.backup(dest)


def sqlite_db_check_detail(path: Path, base: str = "DB query successful") -> str:
    """Return doctor-style DB check detail, noting WAL journal mode when present."""
    try:
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as conn:
            mode = conn.execute("PRAGMA journal_mode").fetchone()
            if mode and str(mode[0]).lower() == "wal":
                return f"{base} (WAL mode)"
    except sqlite3.Error:
        pass
    return base
