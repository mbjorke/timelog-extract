"""Tests for doctor SQLite probe helpers."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.doctor_table_checks import DoctorCheckStyle, doctor_probe_sqlite, sqlite_db_probe_ok


class DoctorTableChecksTests(unittest.TestCase):
    def test_sqlite_db_probe_ok_false_when_urls_table_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "history.db"
            conn = sqlite3.connect(db)
            conn.execute("CREATE TABLE other (id INTEGER)")
            conn.commit()
            conn.close()
            self.assertFalse(sqlite_db_probe_ok(db, table_name="urls"))

    def test_live_lock_surfaces_before_copy_probe(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "live.db"
            conn = sqlite3.connect(db)
            conn.execute("CREATE TABLE urls (id INTEGER)")
            conn.commit()
            conn.close()

            captured: list[tuple[str, str, str]] = []

            class _Table:
                def add_row(self, source: str, status: str, detail: str) -> None:
                    captured.append((source, status, detail))

            style = DoctorCheckStyle(ok_icon="OK", warn_icon="WARN", fail_icon="FAIL", style_muted="dim")
            with patch("core.doctor_table_checks._sqlite_live_locked", return_value=True):
                ok = doctor_probe_sqlite(_Table(), db, "Chrome", style)
            self.assertFalse(ok)
            self.assertEqual(captured[0][1], "WARN")
            self.assertIn("DB locked", captured[0][2])

    def test_copy_failure_adds_probe_failed_row(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "live.db"
            db.write_bytes(b"SQLite format 3\x00" + b"\x00" * 100)
            captured: list[tuple[str, str, str]] = []

            class _Table:
                def add_row(self, source: str, status: str, detail: str) -> None:
                    captured.append((source, status, detail))

            style = DoctorCheckStyle(ok_icon="OK", warn_icon="WARN", fail_icon="FAIL", style_muted="dim")
            with patch("core.doctor_table_checks.shutil.copy2", side_effect=OSError("disk full")):
                ok = doctor_probe_sqlite(_Table(), db, "Zed", style)
            self.assertFalse(ok)
            self.assertIn("Probe failed", captured[0][2])


if __name__ == "__main__":
    unittest.main()
