"""Tests for the reported_time record + local store (Phase 1)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.reported_time import (
    ReportedTimeRecord,
    append_record,
    compute_reported_id,
    latest_by_id,
    load_records,
    query,
    reported_hours_by_project_day,
)


class RecordValidationTests(unittest.TestCase):
    def test_manual_requires_note(self):
        with self.assertRaises(ValueError):
            ReportedTimeRecord(date="2026-06-18", project="P", hours=3.0, source="manual", state="confirmed")

    def test_manual_rejects_origin_ref(self):
        with self.assertRaises(ValueError):
            ReportedTimeRecord(date="2026-06-18", project="P", hours=3.0, source="manual", state="confirmed",
                               note="SFTP work", origin_ref=["s1"])

    def test_non_manual_requires_origin_ref(self):
        with self.assertRaises(ValueError):
            ReportedTimeRecord(date="2026-06-18", project="P", hours=1.0, source="session", state="proposed")

    def test_manual_with_note_is_valid_without_origin(self):
        rec = ReportedTimeRecord(
            date="2026-06-18", project="P", hours=3.0, source="manual", state="confirmed",
            note="SFTP + server work",
        )
        self.assertEqual(rec.origin_ref, [])
        self.assertTrue(rec.id)
        self.assertTrue(rec.confirmed_at)  # set for reported states

    def test_invalid_state_and_source_rejected(self):
        with self.assertRaises(ValueError):
            ReportedTimeRecord(date="d", project="p", hours=1, source="session", state="bogus", origin_ref=["x"])
        with self.assertRaises(ValueError):
            ReportedTimeRecord(date="d", project="p", hours=1, source="bogus", state="proposed", origin_ref=["x"])

    def test_id_is_deterministic(self):
        a = compute_reported_id("2026-06-18", "P", "session", ["s2", "s1"], "")
        b = compute_reported_id("2026-06-18", "P", "session", ["s1", "s2"], "")
        self.assertEqual(a, b)  # origin order does not matter


class StoreRoundTripTests(unittest.TestCase):
    def test_append_and_query_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            rec = ReportedTimeRecord(
                date="2026-06-18", project="timelog-extract", hours=2.5, source="session",
                state="confirmed", origin_ref=["2026-06-18-1"],
            )
            append_record(rec, home=home)
            found = query(home, project="timelog-extract", date="2026-06-18", states={"confirmed"})
            self.assertEqual(len(found), 1)
            self.assertEqual(found[0].hours, 2.5)
            self.assertEqual(found[0].origin_ref, ["2026-06-18-1"])

    def test_latest_write_wins_per_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            base = dict(date="2026-06-18", project="P", source="session", origin_ref=["s1"])
            append_record(ReportedTimeRecord(hours=2.0, state="proposed", **base), home=home)
            append_record(ReportedTimeRecord(hours=1.5, state="edited", edited_from_hours=2.0, **base), home=home)
            current = latest_by_id(load_records(home))
            self.assertEqual(len(current), 1)  # same id collapsed
            rec = next(iter(current.values()))
            self.assertEqual(rec.state, "edited")
            self.assertEqual(rec.hours, 1.5)
            self.assertEqual(rec.edited_from_hours, 2.0)

    def test_garbled_lines_are_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            rec = ReportedTimeRecord(date="2026-06-18", project="P", hours=1.0, source="manual",
                                     state="confirmed", note="x")
            path = append_record(rec, home=home)
            with path.open("a", encoding="utf-8") as fh:
                fh.write("{not json\n\n")
            self.assertEqual(len(load_records(home)), 1)


class AggregationTests(unittest.TestCase):
    def test_reported_hours_sums_confirmed_and_edited_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            append_record(ReportedTimeRecord(date="2026-06-18", project="P", hours=2.0, source="session",
                                             state="confirmed", origin_ref=["a"]), home=home)
            append_record(ReportedTimeRecord(date="2026-06-18", project="P", hours=3.0, source="manual",
                                             state="confirmed", note="SFTP"), home=home)
            append_record(ReportedTimeRecord(date="2026-06-18", project="P", hours=9.0, source="session",
                                             state="proposed", origin_ref=["b"]), home=home)
            append_record(ReportedTimeRecord(date="2026-06-18", project="Q", hours=1.0, source="session",
                                             state="dismissed", origin_ref=["c"]), home=home)
            totals = reported_hours_by_project_day(home)
            # Confirmed session (2.0) + manual (3.0) for P; proposed and dismissed excluded.
            self.assertEqual(totals[("P", "2026-06-18")], 5.0)
            self.assertNotIn(("Q", "2026-06-18"), totals)

    def test_empty_store_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(reported_hours_by_project_day(Path(tmp)), {})
            self.assertEqual(load_records(Path(tmp)), [])


if __name__ == "__main__":
    unittest.main()
