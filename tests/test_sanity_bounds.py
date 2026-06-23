"""Accuracy guardrail tests (GH-146 now-item 1).

These lock the regression net that a collector defect once defeated silently:
whole days collapsing into ~24h sessions while CI stayed green.
"""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from core.sanity_bounds import (
    MAX_PLAUSIBLE_SESSION_HOURS,
    days_exceeding_24h,
    find_implausible_sessions,
    over_attribution_ratio,
    plausibility_warnings,
)

# Span-based stand-in for the 5-arg report wrapper: hours = end - start.
def _span_hours(events, start, end, _mn, _mp):
    return (end - start).total_seconds() / 3600.0


def _day(start_hour, end_hour, day="2026-05-29"):
    base = datetime(2026, 5, 29, 0, 0, tzinfo=timezone.utc)
    start = base + timedelta(hours=start_hour)
    end = base + timedelta(hours=end_hour)
    return {day: {"sessions": [(start, end, [{"source": "Cursor"}])]}}


class SanityBoundsTests(unittest.TestCase):
    def test_collapsed_day_session_is_flagged(self):
        # 00:00 → 23:59 == the exact bug shape that slipped through before.
        overall = _day(0, 23.98)
        flagged = find_implausible_sessions(
            overall,
            _span_hours,
            min_session_minutes=15,
            min_session_passive_minutes=5,
        )
        self.assertEqual(len(flagged), 1)
        self.assertGreater(flagged[0][1], MAX_PLAUSIBLE_SESSION_HOURS)

    def test_normal_session_is_not_flagged(self):
        overall = _day(9, 11.5)  # 2.5h session
        flagged = find_implausible_sessions(
            overall,
            _span_hours,
            min_session_minutes=15,
            min_session_passive_minutes=5,
        )
        self.assertEqual(flagged, [])

    def test_day_exceeding_24h_is_a_hard_violation(self):
        project_reports = {
            "Alpha": {"2026-05-29": {"hours": 13.0}},
            "Beta": {"2026-05-29": {"hours": 12.5}},
        }
        violations = days_exceeding_24h(project_reports)
        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0][0], "2026-05-29")
        self.assertAlmostEqual(violations[0][1], 25.5)

    def test_day_within_24h_is_clean(self):
        project_reports = {
            "Alpha": {"2026-05-29": {"hours": 6.0}},
            "Beta": {"2026-05-29": {"hours": 3.0}},
        }
        self.assertEqual(days_exceeding_24h(project_reports), [])

    def test_over_attribution_ratio(self):
        self.assertAlmostEqual(over_attribution_ratio(672.0, 46.8), 14.358974, places=4)
        self.assertIsNone(over_attribution_ratio(10.0, 0.0))

    def test_plausibility_warnings_flag_over_attribution(self):
        warnings = plausibility_warnings(
            overall_days=_day(9, 10),
            project_reports={"Alpha": {"2026-05-29": {"hours": 1.0}}},
            observed_hours=672.0,
            screen_time_hours=46.8,
            session_duration_hours_fn=_span_hours,
            min_session_minutes=15,
            min_session_passive_minutes=5,
        )
        self.assertTrue(any("over-attribution" in w for w in warnings))
        self.assertTrue(any("observed (evidenced)" in w for w in warnings))

    def test_plausibility_warnings_flags_inflated_observed_week(self):
        warnings = plausibility_warnings(
            overall_days=_day(9, 11.5),
            project_reports={"Alpha": {"2026-05-29": {"hours": 2.5}}},
            observed_hours=30.3,
            screen_time_hours=10.0,
            session_duration_hours_fn=_span_hours,
            min_session_minutes=15,
            min_session_passive_minutes=5,
        )
        self.assertTrue(any("observed (evidenced) 30.3h" in w for w in warnings))

    def test_plausibility_warnings_silent_when_observed_near_screen_time(self):
        """After worker-noise fix, 14.6h vs 10h Screen Time stays below 1.5× threshold."""
        warnings = plausibility_warnings(
            overall_days=_day(9, 11.5),
            project_reports={"Alpha": {"2026-05-29": {"hours": 2.5}}},
            observed_hours=14.6,
            screen_time_hours=10.0,
            session_duration_hours_fn=_span_hours,
            min_session_minutes=15,
            min_session_passive_minutes=5,
        )
        self.assertFalse(any("over-attribution" in w for w in warnings))

    def test_plausibility_warnings_clean_report_is_silent(self):
        warnings = plausibility_warnings(
            overall_days=_day(9, 11.5),
            project_reports={"Alpha": {"2026-05-29": {"hours": 2.5}}},
            observed_hours=2.5,
            screen_time_hours=3.0,
            session_duration_hours_fn=_span_hours,
            min_session_minutes=15,
            min_session_passive_minutes=5,
        )
        self.assertEqual(warnings, [])

    def test_plausibility_warnings_no_screen_time_still_flags_collapse(self):
        # Even without Screen Time, a 24h session must be surfaced.
        warnings = plausibility_warnings(
            overall_days=_day(0, 23.98),
            project_reports={"Alpha": {"2026-05-29": {"hours": 12.0}}},
            observed_hours=24.0,
            screen_time_hours=None,
            session_duration_hours_fn=_span_hours,
            min_session_minutes=15,
            min_session_passive_minutes=5,
        )
        self.assertTrue(any("session-merge artifact" in w for w in warnings))


if __name__ == "__main__":
    unittest.main()
