"""Tests for the durable JSONL evidence store (GH-151, slice 2 / item 3)."""

import json
import tempfile
import unittest
from pathlib import Path

from core.evidence_store import capture_events, evidence_base_dir, events_dir, load_store_state


def _ev(source, ts, detail, project="Alpha"):
    return {"source": source, "timestamp": ts, "detail": detail, "project": project}


class TestEvidenceStore(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name) / "evidence"

    def tearDown(self):
        self._tmp.cleanup()

    def _lines(self, month):
        path = events_dir(self.base) / f"{month}.jsonl"
        return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]

    def test_appends_and_is_idempotent(self):
        events = [
            _ev("Cursor", "2026-06-18T09:00:00+00:00", "a"),
            _ev("Cursor", "2026-06-18T09:05:00+00:00", "b"),
        ]
        first = capture_events(events, base_dir=self.base, captured_at="2026-06-18T10:00:00+00:00")
        self.assertEqual(first["appended"], 2)
        self.assertEqual(len(self._lines("2026-06")), 2)

        # Re-capturing the same events writes nothing new (dedup on fingerprint).
        second = capture_events(events, base_dir=self.base, captured_at="2026-06-19T10:00:00+00:00")
        self.assertEqual(second["appended"], 0)
        self.assertEqual(second["skipped"], 2)
        self.assertEqual(len(self._lines("2026-06")), 2)

    def test_no_store_created_for_empty_events(self):
        result = capture_events([], base_dir=self.base)
        self.assertEqual(result["appended"], 0)
        self.assertFalse(events_dir(self.base).exists())

    def test_hash_chain_links_records(self):
        events = [
            _ev("Cursor", "2026-06-18T09:00:00+00:00", "a"),
            _ev("Cursor", "2026-06-18T09:05:00+00:00", "b"),
        ]
        capture_events(events, base_dir=self.base, captured_at="2026-06-18T10:00:00+00:00")
        recs = self._lines("2026-06")
        self.assertIsNone(recs[0]["prev_hash"])
        self.assertEqual(recs[1]["prev_hash"], recs[0]["content_hash"])

    def test_chain_continues_across_captures(self):
        capture_events([_ev("Cursor", "2026-06-18T09:00:00+00:00", "a")], base_dir=self.base, captured_at="2026-06-18T10:00:00+00:00")
        capture_events([_ev("Cursor", "2026-06-18T11:00:00+00:00", "c")], base_dir=self.base, captured_at="2026-06-18T12:00:00+00:00")
        recs = self._lines("2026-06")
        self.assertEqual(len(recs), 2)
        self.assertEqual(recs[1]["prev_hash"], recs[0]["content_hash"])

    def test_month_bucketing(self):
        events = [
            _ev("Cursor", "2026-05-30T09:00:00+00:00", "may"),
            _ev("Cursor", "2026-06-01T09:00:00+00:00", "jun"),
        ]
        result = capture_events(events, base_dir=self.base, captured_at="2026-06-02T10:00:00+00:00")
        self.assertEqual(result["months"], ["2026-05", "2026-06"])
        self.assertEqual(len(self._lines("2026-05")), 1)
        self.assertEqual(len(self._lines("2026-06")), 1)

    def test_load_store_state_roundtrip(self):
        capture_events([_ev("Cursor", "2026-06-18T09:00:00+00:00", "a")], base_dir=self.base, captured_at="2026-06-18T10:00:00+00:00")
        fingerprints, last_hash = load_store_state(events_dir(self.base))
        self.assertEqual(len(fingerprints), 1)
        self.assertIn("2026-06", last_hash)

    def test_default_base_dir_is_gittan_home(self):
        self.assertEqual(evidence_base_dir(Path("/home/x")), Path("/home/x/.gittan/evidence"))


if __name__ == "__main__":
    unittest.main()
