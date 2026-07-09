"""Tests for GH-332 Slice 2 presence bracketing (capped session edge extension)."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from core.domain import session_duration_hours
from core.presence_bracketing import apply_presence_bracketing
from core.sources import AI_SOURCES


def _duration(events, start, end, min_s, min_p):
    return session_duration_hours(events, start, end, min_s, min_p, AI_SOURCES)


class PresenceBracketingTests(unittest.TestCase):
    def test_no_spans_does_not_apply(self):
        overall = {
            "2026-07-09": {
                "sessions": [
                    (
                        datetime(2026, 7, 9, 10, 0, tzinfo=timezone.utc),
                        datetime(2026, 7, 9, 11, 0, tzinfo=timezone.utc),
                        [{"source": "WordPress", "project": "acme"}],
                    )
                ],
                "hours": 1.0,
            }
        }
        result = apply_presence_bracketing(
            overall,
            None,
            session_duration_hours_fn=_duration,
            min_session_minutes=15,
            min_session_passive_minutes=5,
        )
        self.assertFalse(result.applied)
        self.assertIsNone(result.overall_days)

    def test_extends_edges_with_cap_and_labels_hours(self):
        session_start = datetime(2026, 7, 9, 10, 0, tzinfo=timezone.utc)
        session_end = datetime(2026, 7, 9, 11, 0, tzinfo=timezone.utc)
        events = [{"source": "WordPress", "project": "acme", "local_ts": session_start}]
        overall = {
            "2026-07-09": {
                "sessions": [(session_start, session_end, events, "attended")],
                "hours": 1.0,
                "attended_hours": 1.0,
            }
        }
        presence = [
            (
                session_start - timedelta(minutes=30),
                session_end + timedelta(minutes=30),
            )
        ]
        result = apply_presence_bracketing(
            overall,
            presence,
            session_duration_hours_fn=_duration,
            min_session_minutes=5,
            min_session_passive_minutes=5,
            edge_cap_minutes=10,
        )
        self.assertTrue(result.applied)
        assert result.overall_days is not None
        # Original overall_days must stay untouched.
        self.assertEqual(overall["2026-07-09"]["sessions"][0][0], session_start)
        day = result.overall_days["2026-07-09"]
        new_start, new_end, _events, attendance = day["sessions"][0]
        self.assertEqual(attendance, "attended")
        self.assertEqual(new_start, session_start - timedelta(minutes=10))
        self.assertEqual(new_end, session_end + timedelta(minutes=10))
        self.assertAlmostEqual(day["bracketed_hours"], 20.0 / 60.0, places=3)
        self.assertAlmostEqual(day["hours"], 1.0 + 20.0 / 60.0, places=3)
        self.assertAlmostEqual(result.total_bracketed_hours, 20.0 / 60.0, places=3)

    def test_does_not_invent_sessions_from_presence_alone(self):
        overall = {"2026-07-09": {"sessions": [], "hours": 0.0}}
        presence = [
            (
                datetime(2026, 7, 9, 9, 0, tzinfo=timezone.utc),
                datetime(2026, 7, 9, 17, 0, tzinfo=timezone.utc),
            )
        ]
        result = apply_presence_bracketing(
            overall,
            presence,
            session_duration_hours_fn=_duration,
            min_session_minutes=15,
            min_session_passive_minutes=5,
        )
        self.assertFalse(result.applied)


if __name__ == "__main__":
    unittest.main()
