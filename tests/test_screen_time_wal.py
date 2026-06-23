"""Tests for WAL-safe Screen Time (knowledgeC) database reads."""

from __future__ import annotations

import shutil
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from core.screen_time import collect_screen_time
from core.sqlite_backup import backup_sqlite_db

APPLE_EPOCH = 978307200


def _make_knowledgec_db(path: Path) -> None:
    conn = sqlite3.connect(str(path))
    conn.execute(
        """
        CREATE TABLE ZOBJECT (
            ZSTARTDATE REAL,
            ZENDDATE REAL,
            ZSTREAMNAME TEXT,
            ZVALUESTRING TEXT
        )
        """
    )
    conn.execute("PRAGMA journal_mode=WAL")
    conn.close()


def _insert_usage(conn: sqlite3.Connection, start_apple: float, end_apple: float) -> None:
    conn.execute(
        """
        INSERT INTO ZOBJECT (ZSTARTDATE, ZENDDATE, ZSTREAMNAME, ZVALUESTRING)
        VALUES (?, ?, '/app/usage', 'com.example.app')
        """,
        (start_apple, end_apple),
    )


def _apple_seconds(unix_ts: float) -> float:
    return unix_ts - APPLE_EPOCH


class ScreenTimeWalTests(unittest.TestCase):
    def test_backup_includes_wal_frames_while_writer_open(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "knowledgeC.db"
            _make_knowledgec_db(db_path)

            start_apple = _apple_seconds(
                datetime(2026, 6, 23, 10, 0, 0, tzinfo=timezone.utc).timestamp()
            )
            end_apple = start_apple + 3600.0

            writer = sqlite3.connect(str(db_path))
            writer.execute("PRAGMA journal_mode=WAL")
            _insert_usage(writer, start_apple, end_apple)
            writer.commit()

            copy_path = Path(tmpdir) / "copy2.db"
            backup_path = Path(tmpdir) / "backup.db"
            shutil.copy2(db_path, copy_path)
            backup_sqlite_db(db_path, str(backup_path))

            with sqlite3.connect(str(copy_path)) as conn:
                copy_count = conn.execute("SELECT count(*) FROM ZOBJECT").fetchone()[0]
            with sqlite3.connect(str(backup_path)) as conn:
                backup_count = conn.execute("SELECT count(*) FROM ZOBJECT").fetchone()[0]

            writer.close()
            self.assertEqual(copy_count, 0)
            self.assertEqual(backup_count, 1)

    def test_collect_screen_time_reads_wal_backed_database(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "knowledgeC.db"
            _make_knowledgec_db(db_path)

            start_apple = _apple_seconds(
                datetime(2026, 6, 23, 10, 0, 0, tzinfo=timezone.utc).timestamp()
            )
            end_apple = start_apple + 3600.0

            writer = sqlite3.connect(str(db_path))
            writer.execute("PRAGMA journal_mode=WAL")
            _insert_usage(writer, start_apple, end_apple)
            writer.commit()

            dt_from = datetime(2026, 6, 23, 0, 0, tzinfo=ZoneInfo("UTC"))
            dt_to = datetime(2026, 6, 24, 0, 0, tzinfo=ZoneInfo("UTC"))
            daily, msg = collect_screen_time(
                dt_from,
                dt_to,
                candidates=[db_path],
                apple_epoch=APPLE_EPOCH,
                local_tz=ZoneInfo("UTC"),
            )
            writer.close()

            self.assertIsNotNone(daily)
            self.assertIn(str(db_path), msg)
            self.assertAlmostEqual(daily["2026-06-23"], 3600.0, places=3)

    def test_collect_screen_time_returns_error_when_db_missing(self):
        missing = Path("/nonexistent/knowledgeC.db")
        dt_from = datetime(2026, 6, 23, 0, 0, tzinfo=ZoneInfo("UTC"))
        dt_to = datetime(2026, 6, 24, 0, 0, tzinfo=ZoneInfo("UTC"))
        daily, msg = collect_screen_time(
            dt_from,
            dt_to,
            candidates=[missing],
            apple_epoch=APPLE_EPOCH,
            local_tz=ZoneInfo("UTC"),
        )
        self.assertIsNone(daily)
        self.assertIn("not found", msg)

    def test_collect_screen_time_handles_corrupted_database(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "knowledgeC.db"
            db_path.write_bytes(b"not-a-sqlite-database")

            dt_from = datetime(2026, 6, 23, 0, 0, tzinfo=ZoneInfo("UTC"))
            dt_to = datetime(2026, 6, 24, 0, 0, tzinfo=ZoneInfo("UTC"))
            daily, msg = collect_screen_time(
                dt_from,
                dt_to,
                candidates=[db_path],
                apple_epoch=APPLE_EPOCH,
                local_tz=ZoneInfo("UTC"),
            )
            self.assertIsNone(daily)
            self.assertIn("Screen Time", msg)


if __name__ == "__main__":
    unittest.main()
