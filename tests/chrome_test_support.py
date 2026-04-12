"""Shared fixtures for Chrome collector tests (not a test module)."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

# Chrome stores time as microseconds since 1601-01-01 00:00:00 UTC.
EPOCH_DELTA_US = 11_644_473_600_000_000


def make_chrome_db(path: Path) -> None:
    """Create a minimal Chrome History SQLite database at *path*."""
    conn = sqlite3.connect(str(path))
    conn.executescript(
        """
        CREATE TABLE urls (
            id    INTEGER PRIMARY KEY,
            url   TEXT NOT NULL,
            title TEXT
        );
        CREATE TABLE visits (
            id         INTEGER PRIMARY KEY,
            url        INTEGER NOT NULL,
            visit_time INTEGER NOT NULL
        );
        """
    )
    conn.commit()
    conn.close()


def insert_visit(db_path: Path, url: str, title: str, ts: datetime) -> None:
    """Insert one visit row into *db_path*."""
    visit_time_cu = int(ts.timestamp() * 1_000_000) + EPOCH_DELTA_US
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    cur.execute("INSERT INTO urls (url, title) VALUES (?, ?)", (url, title))
    url_id = cur.lastrowid
    cur.execute("INSERT INTO visits (url, visit_time) VALUES (?, ?)", (url_id, visit_time_cu))
    conn.commit()
    conn.close()


def make_event(source, ts, detail, project):
    return {"source": source, "ts": ts, "detail": detail, "project": project}
