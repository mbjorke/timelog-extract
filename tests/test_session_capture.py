"""Tests for device-agnostic session capture (core/session_capture.py)."""

from __future__ import annotations

import json
import socket
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from core import session_capture
from core.evidence_store import events_dir, read_records
from core.session_capture import (
    capture_device_evidence,
    device_name,
    events_from_records,
    import_records,
    read_records_file,
    records_from_events,
    tag_device,
    write_records_file,
)

PROFILES = [
    {
        "name": "gittan",
        "project_id": "gittan",
        "match_terms": ["timelog-extract", "gittan"],
        "tracked_urls": [],
        "aliases": [],
        "canonical_project": "gittan",
        "customer": "internal",
        "email": "",
        "tags": [],
    }
]

DT_FROM = datetime(2026, 7, 25, tzinfo=timezone.utc)
DT_TO = datetime(2026, 7, 26, tzinfo=timezone.utc)


def write_transcript(home: Path, *, stamps: list[str], project_dir: str = "-work-gittan") -> None:
    """Write a minimal Claude Code transcript the collector can parse."""
    proj = home / ".claude" / "projects" / project_dir
    proj.mkdir(parents=True, exist_ok=True)
    lines = [
        json.dumps({"timestamp": stamp, "type": "user", "message": {"content": "gittan work"}})
        for stamp in stamps
    ]
    (proj / "session.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")


class DeviceNameTests(unittest.TestCase):
    def test_explicit_name_wins(self):
        self.assertEqual(device_name("phone"), "phone")

    def test_blank_falls_back_to_hostname(self):
        self.assertEqual(device_name("   "), socket.gethostname().strip() or "unknown-device")

    def test_hostname_failure_still_yields_a_label(self):
        original = session_capture.socket.gethostname
        session_capture.socket.gethostname = lambda: (_ for _ in ()).throw(OSError("no host"))
        try:
            self.assertEqual(device_name(None), "unknown-device")
        finally:
            session_capture.socket.gethostname = original


class TagDeviceTests(unittest.TestCase):
    def test_tag_does_not_mutate_the_original(self):
        event = {"source": "Claude Code CLI", "detail": "x"}
        tagged = tag_device(event, "laptop", captured_via="claude-code")
        self.assertNotIn("source_provenance", event)
        self.assertEqual(tagged["source_provenance"]["device"], "laptop")
        self.assertEqual(tagged["source_provenance"]["captured_via"], "claude-code")

    def test_existing_provenance_keys_are_kept(self):
        event = {"source": "s", "detail": "d", "source_provenance": {"origin": "hook"}}
        tagged = tag_device(event, "phone", captured_via="claude-code")
        self.assertEqual(tagged["source_provenance"]["origin"], "hook")
        self.assertEqual(tagged["source_provenance"]["device"], "phone")


class RecordRoundTripTests(unittest.TestCase):
    def test_records_and_events_round_trip(self):
        events = [
            {
                "source": "Claude Code CLI",
                "timestamp": datetime(2026, 7, 25, 9, 0, tzinfo=timezone.utc),
                "detail": "worked on gittan",
                "project": "gittan",
                "source_provenance": {"device": "laptop"},
            }
        ]
        records = records_from_events(events)
        self.assertEqual(len(records), 1)
        self.assertIsNone(records[0]["prev_hash"], "chain belongs to the accepting store")
        back = events_from_records(records)
        self.assertEqual(back[0]["source"], "Claude Code CLI")
        self.assertEqual(back[0]["detail"], "worked on gittan")
        self.assertEqual(back[0]["project"], "gittan")
        self.assertEqual(back[0]["source_provenance"]["device"], "laptop")

    def test_file_round_trip_skips_blank_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "export.jsonl"
            records = records_from_events(
                [
                    {
                        "source": "Claude Code CLI",
                        "timestamp": datetime(2026, 7, 25, 9, 0, tzinfo=timezone.utc),
                        "detail": "d",
                        "project": "gittan",
                    }
                ]
            )
            write_records_file(records, path)
            path.write_text(path.read_text(encoding="utf-8") + "\n\n", encoding="utf-8")
            self.assertEqual(len(read_records_file(path)), 1)

    def test_malformed_line_names_the_line_number(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.jsonl"
            path.write_text('{"a": 1}\nnot json\n', encoding="utf-8")
            with self.assertRaises(ValueError) as ctx:
                read_records_file(path)
            self.assertIn("line 2", str(ctx.exception))

    def test_missing_file_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError):
                read_records_file(Path(tmp) / "nope.jsonl")


class CaptureDeviceEvidenceTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.store = self.tmp / "store"
        write_transcript(
            self.home,
            stamps=["2026-07-25T09:00:00Z", "2026-07-25T09:20:00Z", "2026-07-25T10:00:00Z"],
        )

    def tearDown(self):
        self._tmp.cleanup()

    def _capture(self, **kwargs):
        return capture_device_evidence(
            PROFILES, DT_FROM, DT_TO, home=self.home, base_dir=self.store, **kwargs
        )

    def test_dry_run_writes_nothing_anywhere(self):
        summary = self._capture(device="laptop", dry_run=True)
        self.assertGreater(summary["collected"], 0)
        self.assertEqual(summary["appended"], 0)
        self.assertFalse(self.store.exists(), "dry run must not create the store")

    def test_capture_appends_and_is_idempotent(self):
        first = self._capture(device="laptop")
        self.assertGreater(first["appended"], 0)
        self.assertEqual(first["device"], "laptop")
        second = self._capture(device="laptop")
        self.assertEqual(second["appended"], 0)
        self.assertEqual(second["skipped"], first["appended"])

    def test_same_session_from_two_devices_lands_once(self):
        """The identity of an event is what happened, not which device saw it."""
        first = self._capture(device="laptop")
        second = self._capture(device="phone")
        self.assertGreater(first["appended"], 0)
        self.assertEqual(second["appended"], 0, "a second device must not double-count")

    def test_captured_records_carry_the_device(self):
        self._capture(device="phone")
        records = [rec for _month, rec in read_records(events_dir(self.store))]
        self.assertTrue(records)
        for record in records:
            self.assertEqual(record["source_provenance"]["device"], "phone")
            self.assertEqual(record["source_provenance"]["captured_via"], "claude-code")

    def test_export_writes_records_instead_of_the_store(self):
        dest = self.tmp / "out" / "session.jsonl"
        summary = self._capture(device="container", export_to=dest)
        self.assertGreater(summary["appended"], 0)
        self.assertFalse(self.store.exists(), "export must not touch the local store")
        self.assertEqual(len(read_records_file(dest)), summary["appended"])

    def test_export_then_import_merges_and_dedupes(self):
        dest = self.tmp / "session.jsonl"
        exported = self._capture(device="container", export_to=dest)
        merged = import_records(dest, base_dir=self.store)
        self.assertEqual(merged["appended"], exported["appended"])
        self.assertEqual(merged["read"], exported["appended"])
        self.assertEqual(merged["devices"], ["container"])
        again = import_records(dest, base_dir=self.store)
        self.assertEqual(again["appended"], 0)
        self.assertEqual(again["skipped"], merged["appended"])

    def test_unknown_source_is_rejected_by_name(self):
        with self.assertRaises(ValueError) as ctx:
            self._capture(device="laptop", sources=["telepathy"])
        self.assertIn("telepathy", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
