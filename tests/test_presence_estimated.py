from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from core.presence_estimated import compute_presence_estimated


def _ev(day: str, hour: int, minute: int = 0, project: str = "project-alpha") -> dict:
    ts = datetime(2026, 6, 11, hour, minute, tzinfo=timezone.utc)
    return {
        "source": "Cursor",
        "timestamp": ts,
        "local_ts": ts,
        "detail": "work",
        "project": project,
    }


class PresenceEstimatedTests(unittest.TestCase):
    def test_no_screen_time_returns_empty(self):
        overall = {
            "2026-06-11": {
                "entries": [_ev("2026-06-11", 9)],
                "sessions": [],
                "hours": 1.0,
            }
        }
        result = compute_presence_estimated(
            overall,
            {"project-alpha": {"2026-06-11": {"hours": 1.0}}},
            screen_time_days=None,
        )
        self.assertFalse(result.available)
        self.assertEqual(result.total_hours, 0.0)

    def test_estimate_never_exceeds_screen_time(self):
        events = [
            _ev("2026-06-11", 9, 0),
            _ev("2026-06-11", 12, 0),
            _ev("2026-06-11", 16, 0),
        ]
        overall = {
            "2026-06-11": {
                "entries": events,
                "sessions": [],
                "hours": 2.0,
            }
        }
        project_reports = {"project-alpha": {"2026-06-11": {"hours": 2.0}}}
        screen_seconds = 6 * 3600.0
        result = compute_presence_estimated(
            overall,
            project_reports,
            screen_time_days={"2026-06-11": screen_seconds},
            max_fill_gap_minutes=45,
        )
        self.assertLessEqual(result.overall_days["2026-06-11"], 6.0 + 1e-6)
        self.assertGreater(result.overall_days["2026-06-11"], 2.0)

    def test_fill_only_between_project_events_not_before_or_after(self):
        events = [
            _ev("2026-06-11", 10, 0),
            _ev("2026-06-11", 11, 0),
        ]
        overall = {
            "2026-06-11": {
                "entries": events,
                "sessions": [],
                "hours": 1.0,
            }
        }
        project_reports = {"project-alpha": {"2026-06-11": {"hours": 1.0}}}
        result = compute_presence_estimated(
            overall,
            project_reports,
            screen_time_days={"2026-06-11": 8 * 3600.0},
            session_gap_minutes=15,
            max_fill_gap_minutes=45,
        )
        # One 60-minute gap → 45 min fill cap → 1.0h evidenced + 0.75h fill = 1.75h
        self.assertAlmostEqual(result.overall_days["2026-06-11"], 1.75, places=2)

    def test_evidenced_hours_unchanged_in_underlying_reports(self):
        """Presence estimate is computed separately; project_reports input is read-only."""
        events = [_ev("2026-06-11", 9), _ev("2026-06-11", 14)]
        project_reports = {"project-alpha": {"2026-06-11": {"hours": 3.5}}}
        overall = {
            "2026-06-11": {
                "entries": events,
                "sessions": [],
                "hours": 3.5,
            }
        }
        compute_presence_estimated(
            overall,
            project_reports,
            screen_time_days={"2026-06-11": 15 * 3600.0},
        )
        self.assertAlmostEqual(project_reports["project-alpha"]["2026-06-11"]["hours"], 3.5)

    def test_gap_fill_respects_session_gap_floor(self):
        ts_a = datetime(2026, 6, 11, 9, 0, tzinfo=timezone.utc)
        ts_b = ts_a + timedelta(minutes=20)
        events = [
            {"source": "Cursor", "timestamp": ts_a, "local_ts": ts_a, "detail": "a", "project": "p"},
            {"source": "Cursor", "timestamp": ts_b, "local_ts": ts_b, "detail": "b", "project": "p"},
        ]
        overall = {"2026-06-11": {"entries": events, "sessions": [], "hours": 0.5}}
        result = compute_presence_estimated(
            overall,
            {"p": {"2026-06-11": {"hours": 0.5}}},
            screen_time_days={"2026-06-11": 8 * 3600.0},
            session_gap_minutes=15,
            max_fill_gap_minutes=45,
        )
        # 20 min gap → 5 min fill above 15 min session floor
        self.assertAlmostEqual(result.overall_days["2026-06-11"], 0.5 + (5 / 60), places=3)

    def test_multi_project_day_scales_fill_to_screen_cap(self):
        day = "2026-06-11"
        alpha = [_ev(day, 9), _ev(day, 15)]
        beta = [_ev(day, 10, project="project-beta"), _ev(day, 16, project="project-beta")]
        overall = {
            day: {
                "entries": alpha + beta,
                "sessions": [],
                "hours": 4.0,
            }
        }
        project_reports = {
            "project-alpha": {day: {"hours": 2.0}},
            "project-beta": {day: {"hours": 2.0}},
        }
        result = compute_presence_estimated(
            overall,
            project_reports,
            screen_time_days={day: 7 * 3600.0},
            max_fill_gap_minutes=45,
        )
        self.assertLessEqual(result.overall_days[day], 7.0 + 1e-6)
        self.assertGreaterEqual(result.overall_days[day], 4.0)


if __name__ == "__main__":
    unittest.main()
