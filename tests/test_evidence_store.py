"""Tests for the durable JSONL evidence store (GH-151, slice 2 / item 3)."""

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from core.evidence_store import (
    capture_events,
    erase_store,
    evidence_base_dir,
    events_dir,
    export_store,
    load_store_state,
    maybe_replay,
    prune_older_than,
    replay_into_events,
    store_health,
)


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
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

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

    def test_store_health_disabled_when_no_store(self):
        health = store_health(base_dir=self.base)
        self.assertFalse(health["enabled"])

    def test_store_health_reports_totals_and_ok_chain(self):
        capture_events(
            [
                _ev("Cursor", "2026-06-18T09:00:00+00:00", "a"),
                _ev("Chrome", "2026-06-18T09:05:00+00:00", "b"),
            ],
            base_dir=self.base,
            captured_at="2026-06-22T10:00:00+00:00",
        )
        health = store_health(base_dir=self.base, today="2026-06-22")
        self.assertTrue(health["enabled"])
        self.assertEqual(health["total_records"], 2)
        self.assertEqual(health["records_captured_today"], 2)
        self.assertEqual(health["last_captured_at"], "2026-06-22T10:00:00+00:00")
        self.assertTrue(health["chain_ok"])
        self.assertEqual(health["per_source"], {"Chrome": 1, "Cursor": 1})
        self.assertEqual(health["retention_span"], "2026-06..2026-06")

    def test_store_health_detects_tampering(self):
        capture_events(
            [_ev("Cursor", "2026-06-18T09:00:00+00:00", "a")],
            base_dir=self.base,
            captured_at="2026-06-22T10:00:00+00:00",
        )
        path = events_dir(self.base) / "2026-06.jsonl"
        rec = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
        rec["detail"] = "tampered after the fact"  # content changed, content_hash stale
        path.write_text(json.dumps(rec) + "\n", encoding="utf-8")
        health = store_health(base_dir=self.base, today="2026-06-22")
        self.assertFalse(health["chain_ok"])
        self.assertTrue(health["chain_breaks"])


class TestEvidenceDataControls(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name) / "evidence"

    def tearDown(self):
        self._tmp.cleanup()

    def _seed(self):
        capture_events(
            [
                _ev("Cursor", "2026-01-10T09:00:00+00:00", "old"),
                _ev("Cursor", "2026-06-18T09:00:00+00:00", "recent-a"),
                _ev("Cursor", "2026-06-18T09:05:00+00:00", "recent-b"),
            ],
            base_dir=self.base,
            captured_at="2026-06-18T10:00:00+00:00",
        )

    def test_export_writes_all_records(self):
        self._seed()
        dest = Path(self._tmp.name) / "out" / "export.jsonl"
        result = export_store(dest, base_dir=self.base)
        self.assertEqual(result["records"], 3)
        lines = [l for l in dest.read_text(encoding="utf-8").splitlines() if l.strip()]
        self.assertEqual(len(lines), 3)

    def test_erase_removes_store(self):
        self._seed()
        self.assertTrue(self.base.exists())
        result = erase_store(base_dir=self.base)
        self.assertTrue(result["removed"])
        self.assertFalse(self.base.exists())

    def test_erase_absent_store_is_noop(self):
        result = erase_store(base_dir=self.base)
        self.assertFalse(result["removed"])

    def test_prune_drops_old_and_rechains(self):
        self._seed()
        # now=2026-06-20, keep 30 days -> 2026-01-10 dropped, June kept.
        result = prune_older_than(30, base_dir=self.base, now=datetime(2026, 6, 20, tzinfo=timezone.utc))
        self.assertEqual(result["removed"], 1)
        self.assertEqual(result["kept"], 2)
        # The emptied January file is gone; June survivors keep a valid chain.
        self.assertFalse((events_dir(self.base) / "2026-01.jsonl").exists())
        health = store_health(base_dir=self.base, today="2026-06-20")
        self.assertTrue(health["chain_ok"])
        self.assertEqual(health["total_records"], 2)


class TestEvidenceReplay(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name) / "evidence"
        capture_events(
            [
                _ev("Cursor", "2026-03-10T09:00:00+00:00", "stored-a"),
                _ev("Cursor", "2026-03-10T09:05:00+00:00", "stored-b"),
            ],
            base_dir=self.base,
            captured_at="2026-03-10T10:00:00+00:00",
        )
        self.win_from = datetime(2026, 3, 1, tzinfo=timezone.utc)
        self.win_to = datetime(2026, 3, 31, tzinfo=timezone.utc)

    def tearDown(self):
        self._tmp.cleanup()

    def test_restores_stored_events_not_present_live(self):
        events, restored = replay_into_events([], self.win_from, self.win_to, base_dir=self.base)
        self.assertEqual(restored, 2)
        self.assertTrue(all(e.get("replayed") for e in events))
        self.assertEqual({e["detail"] for e in events}, {"stored-a", "stored-b"})

    def test_does_not_duplicate_live_events(self):
        live = [_ev("Cursor", datetime(2026, 3, 10, 9, 0, tzinfo=timezone.utc), "stored-a")]
        events, restored = replay_into_events(live, self.win_from, self.win_to, base_dir=self.base)
        self.assertEqual(restored, 1)  # only stored-b is new
        self.assertEqual(len(events), 2)

    def test_window_filter_excludes_out_of_range(self):
        events, restored = replay_into_events(
            [], datetime(2026, 4, 1, tzinfo=timezone.utc), datetime(2026, 4, 30, tzinfo=timezone.utc), base_dir=self.base
        )
        self.assertEqual(restored, 0)

    def test_maybe_replay_off_does_nothing(self):
        args = SimpleNamespace(shadow_replay="off")
        events = maybe_replay([], args=args, dt_from=self.win_from, dt_to=self.win_to, base_dir=self.base)
        self.assertEqual(events, [])
        self.assertEqual(args.shadow_replay_restored, 0)

    def test_maybe_replay_skips_open_window(self):
        # A window whose end is today/future must not replay.
        args = SimpleNamespace(shadow_replay="on")
        future_to = datetime.now(timezone.utc) + timedelta(days=1)
        events = maybe_replay([], args=args, dt_from=self.win_from, dt_to=future_to, local_tz=timezone.utc, base_dir=self.base)
        self.assertEqual(events, [])
        self.assertEqual(args.shadow_replay_restored, 0)

    def test_maybe_replay_closed_window_restores(self):
        args = SimpleNamespace(shadow_replay="on")
        events = maybe_replay([], args=args, dt_from=self.win_from, dt_to=self.win_to, local_tz=timezone.utc, base_dir=self.base)
        self.assertEqual(args.shadow_replay_restored, 2)
        self.assertEqual(len(events), 2)


if __name__ == "__main__":
    unittest.main()
