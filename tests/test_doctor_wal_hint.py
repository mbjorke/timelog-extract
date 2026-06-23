"""Tests for WAL journal-mode hints in doctor DB checks."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from core.sqlite_backup import sqlite_db_check_detail


class DoctorWalHintTests(unittest.TestCase):
    def test_wal_database_shows_wal_mode_detail(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "sample.db"
            conn = sqlite3.connect(str(db_path))
            conn.execute("CREATE TABLE urls (id INTEGER PRIMARY KEY)")
            conn.execute("PRAGMA journal_mode=WAL")
            conn.close()

            detail = sqlite_db_check_detail(db_path)
            self.assertEqual(detail, "DB query successful (WAL mode)")

    def test_non_wal_database_shows_standard_detail(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "sample.db"
            conn = sqlite3.connect(str(db_path))
            conn.execute("CREATE TABLE urls (id INTEGER PRIMARY KEY)")
            conn.execute("PRAGMA journal_mode=DELETE")
            conn.close()

            detail = sqlite_db_check_detail(db_path)
            self.assertEqual(detail, "DB query successful")


if __name__ == "__main__":
    unittest.main()
