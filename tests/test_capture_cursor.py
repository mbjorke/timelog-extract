"""Cursor is a capture source — durable ledger with device provenance."""

from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from core.evidence_store import events_dir, read_records
from core.session_capture import CAPTURE_SOURCES, capture_device_evidence

PROFILES = [
    {
        "name": "timelog-extract",
        "project_id": "timelog-extract",
        "match_terms": ["timelog-extract"],
        "tracked_urls": [],
        "aliases": [],
        "canonical_project": "timelog-extract",
        "customer": "internal",
        "email": "",
        "tags": [],
    }
]

DT_FROM = datetime(2026, 6, 11, 0, 0, tzinfo=timezone.utc)
DT_TO = datetime(2026, 6, 11, 23, 59, tzinfo=timezone.utc)


def write_cursor_composer(home: Path) -> None:
    created_ms = int(datetime(2026, 6, 11, 9, 22, tzinfo=timezone.utc).timestamp() * 1000)
    updated_ms = int(datetime(2026, 6, 11, 9, 58, tzinfo=timezone.utc).timestamp() * 1000)
    payload = {
        "allComposers": [
            {
                "composerId": "capture-cursor-1",
                "name": "Capture cursor fixture session",
                "createdAt": created_ms,
                "lastUpdatedAt": updated_ms,
                "workspaceIdentifier": {
                    "uri": {
                        "fsPath": "/tmp/workspaces/timelog-extract",
                    }
                },
            }
        ]
    }
    cursor_dir = home / "Library" / "Application Support" / "Cursor" / "User" / "globalStorage"
    cursor_dir.mkdir(parents=True)
    db_path = cursor_dir / "state.vscdb"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE ItemTable (key TEXT PRIMARY KEY, value TEXT)")
    conn.execute(
        "INSERT INTO ItemTable VALUES (?, ?)",
        ("composer.composerHeaders", json.dumps(payload)),
    )
    conn.commit()
    conn.close()


class CursorCaptureRegistryTests(unittest.TestCase):
    def test_cursor_is_in_default_capture_sources(self):
        self.assertIn("cursor", CAPTURE_SOURCES)
        self.assertEqual(CAPTURE_SOURCES["cursor"], "Cursor")


class CursorCaptureTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.store = self.tmp / "store"

    def tearDown(self):
        self._tmp.cleanup()

    def _capture(self, **kwargs):
        return capture_device_evidence(
            PROFILES,
            DT_FROM,
            DT_TO,
            home=self.home,
            base_dir=self.store,
            device="Mac",
            **kwargs,
        )

    def test_source_cursor_captures_composer_session(self):
        write_cursor_composer(self.home)
        summary = self._capture(sources=["cursor"])
        self.assertGreater(summary["appended"], 0)
        self.assertEqual(summary["sources"], ["cursor"])
        records = [rec for _month, rec in read_records(events_dir(self.store))]
        self.assertTrue(records)
        for record in records:
            self.assertEqual(record["source"], "Cursor")
            self.assertEqual(record["source_provenance"]["captured_via"], "cursor")
            self.assertEqual(record["source_provenance"]["device"], "Mac")

    def test_default_capture_includes_cursor_when_present(self):
        write_cursor_composer(self.home)
        summary = self._capture()
        self.assertIn("cursor", summary["sources"])


if __name__ == "__main__":
    unittest.main()
