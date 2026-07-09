"""Tests for GH-332 Slice 1 presence edge-gap measurement (diagnostics only)."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from core.presence_edge_gaps import measure_session_edge_gaps


class PresenceEdgeGapTests(unittest.TestCase):
    def test_unavailable_without_spans(self):
        report = measure_session_edge_gaps({"2026-07-09": {"sessions": []}}, None)
        self.assertFalse(report.available)
        payload = report.to_dict()
        self.assertFalse(payload["available"])
        self.assertIn("Diagnostic only", payload["note"])

    def test_lead_and_trail_adjacent_presence(self):
        """Presence that starts before and ends after the session counts both edges."""
        session_start = datetime(2026, 7, 9, 10, 0, tzinfo=timezone.utc)
        session_end = datetime(2026, 7, 9, 11, 0, tzinfo=timezone.utc)
        presence = [
            (
                session_start - timedelta(minutes=5),
                session_end + timedelta(minutes=8),
            )
        ]
        overall = {
            "2026-07-09": {
                "sessions": [(session_start, session_end, [])],
                "hours": 1.0,
            }
        }
        report = measure_session_edge_gaps(overall, presence)
        self.assertTrue(report.available)
        self.assertAlmostEqual(report.total_lead_hours, 5.0 / 60.0, places=4)
        self.assertAlmostEqual(report.total_trail_hours, 8.0 / 60.0, places=4)
        self.assertAlmostEqual(report.total_edge_hours, 13.0 / 60.0, places=4)
        # Default 10-min cap: lead 5 + trail 8 → both under cap → same as uncapped.
        self.assertAlmostEqual(report.capped_edge_hours, 13.0 / 60.0, places=4)
        # Must not mutate session timestamps.
        self.assertEqual(overall["2026-07-09"]["sessions"][0][0], session_start)
        self.assertEqual(overall["2026-07-09"]["sessions"][0][1], session_end)

    def test_unique_totals_do_not_double_count_shared_presence(self):
        """One long presence covering two sessions must not sum to > wall-clock edges."""
        presence = [
            (
                datetime(2026, 7, 9, 8, 0, tzinfo=timezone.utc),
                datetime(2026, 7, 9, 18, 0, tzinfo=timezone.utc),
            )
        ]
        s1 = (
            datetime(2026, 7, 9, 10, 0, tzinfo=timezone.utc),
            datetime(2026, 7, 9, 11, 0, tzinfo=timezone.utc),
            [],
        )
        s2 = (
            datetime(2026, 7, 9, 13, 0, tzinfo=timezone.utc),
            datetime(2026, 7, 9, 14, 0, tzinfo=timezone.utc),
            [],
        )
        overall = {"2026-07-09": {"sessions": [s1, s2]}}
        report = measure_session_edge_gaps(overall, presence)
        # Unique: outer lead [08-10] + between as trail [11-13] + outer trail [14-18] = 8h.
        self.assertAlmostEqual(report.total_edge_hours, 8.0, places=3)
        self.assertAlmostEqual(report.total_lead_hours, 2.0, places=3)
        self.assertAlmostEqual(report.total_trail_hours, 6.0, places=3)
        self.assertAlmostEqual(
            report.total_lead_hours + report.total_trail_hours,
            report.total_edge_hours,
            places=3,
        )
        # Cap 10 min/edge: lead of s1 + trail of s1 + trail of s2 (no lead on s2) = 30 min.
        self.assertAlmostEqual(report.capped_edge_hours, 30.0 / 60.0, places=3)

    def test_presence_inside_session_only_is_zero_edge(self):
        """Presence fully inside the evidenced span is not an edge gap."""
        session_start = datetime(2026, 7, 9, 10, 0, tzinfo=timezone.utc)
        session_end = datetime(2026, 7, 9, 12, 0, tzinfo=timezone.utc)
        presence = [
            (session_start + timedelta(minutes=10), session_end - timedelta(minutes=10))
        ]
        overall = {
            "2026-07-09": {
                "sessions": [(session_start, session_end, [])],
            }
        }
        report = measure_session_edge_gaps(overall, presence)
        self.assertTrue(report.available)
        self.assertAlmostEqual(report.total_edge_hours, 0.0, places=6)
        self.assertEqual(report.to_dict()["session_count_with_edge"], 0)

    def test_disjoint_presence_does_not_count(self):
        session_start = datetime(2026, 7, 9, 10, 0, tzinfo=timezone.utc)
        session_end = datetime(2026, 7, 9, 11, 0, tzinfo=timezone.utc)
        presence = [
            (
                session_start - timedelta(hours=2),
                session_start - timedelta(hours=1),
            )
        ]
        overall = {
            "2026-07-09": {
                "sessions": [(session_start, session_end, [])],
            }
        }
        report = measure_session_edge_gaps(overall, presence)
        self.assertAlmostEqual(report.total_edge_hours, 0.0, places=6)

    def test_exclusive_end_does_not_cover_boundary(self):
        """session_start == end_exclusive is outside the presence span."""
        end_exclusive = datetime(2026, 7, 9, 10, 0, tzinfo=timezone.utc)
        presence = [
            (end_exclusive - timedelta(minutes=30), end_exclusive),
        ]
        overall = {
            "2026-07-09": {
                "sessions": [
                    (
                        end_exclusive,
                        end_exclusive + timedelta(hours=1),
                        [],
                    )
                ],
            }
        }
        report = measure_session_edge_gaps(overall, presence)
        self.assertAlmostEqual(report.total_lead_hours, 0.0, places=6)
        self.assertAlmostEqual(report.total_edge_hours, 0.0, places=6)

    def test_per_session_edges_clamped_to_neighbors(self):
        """Per-session lead/trail must not include time belonging to other sessions."""
        presence = [
            (
                datetime(2026, 7, 9, 8, 0, tzinfo=timezone.utc),
                datetime(2026, 7, 9, 18, 0, tzinfo=timezone.utc),
            )
        ]
        s1_start = datetime(2026, 7, 9, 10, 0, tzinfo=timezone.utc)
        s1_end = datetime(2026, 7, 9, 11, 0, tzinfo=timezone.utc)
        s2_start = datetime(2026, 7, 9, 13, 0, tzinfo=timezone.utc)
        s2_end = datetime(2026, 7, 9, 14, 0, tzinfo=timezone.utc)
        overall = {
            "2026-07-09": {
                "sessions": [
                    (s1_start, s1_end, []),
                    (s2_start, s2_end, []),
                ],
            }
        }
        report = measure_session_edge_gaps(overall, presence)
        by_idx = {s.session_index: s for s in report.sessions}
        # s1: lead from 08:00, trail only to s2 start (not through s2).
        self.assertAlmostEqual(by_idx[1].lead_seconds, 2 * 3600, places=1)
        self.assertAlmostEqual(by_idx[1].trail_seconds, 2 * 3600, places=1)
        # s2: no lead (between-gap owned by s1 trail); trail to 18:00.
        self.assertAlmostEqual(by_idx[2].lead_seconds, 0.0, places=1)
        self.assertAlmostEqual(by_idx[2].trail_seconds, 4 * 3600, places=1)


if __name__ == "__main__":
    unittest.main()
