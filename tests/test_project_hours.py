"""Tests for proportional project-hour allocation."""

import unittest
from datetime import datetime, timedelta, timezone

from core.domain import session_duration_hours
from core.project_hours import allocate_session_hours_by_project, event_attribution_weight
from core.sources import AI_SOURCES


class ProjectHoursTests(unittest.TestCase):
    def test_high_signal_worklog_not_whole_chrome_session(self):
        base = datetime(2026, 6, 11, 9, 0, tzinfo=timezone.utc)
        events = [
            {"source": "Chrome", "project": "financing-portal", "detail": "tab", "local_ts": base},
            {"source": "Chrome", "project": "financing-portal", "detail": "tab2", "local_ts": base},
            {
                "source": "Worklog (TIMELOG.md)",
                "project": "financing-portal",
                "detail": "commit",
                "local_ts": base,
            },
            {
                "source": "GitHub",
                "project": "timelog-extract",
                "detail": "push",
                "local_ts": base.replace(minute=30),
            },
        ]
        split = allocate_session_hours_by_project(
            events,
            1.0,
            session_duration_hours_fn=session_duration_hours,
            min_session_minutes=15,
            min_session_passive_minutes=5,
        )
        self.assertLess(split["financing-portal"], 0.5)
        self.assertGreater(split["timelog-extract"], 0.0)

    def test_label_anchor_gets_high_weight(self):
        self.assertGreater(
            event_attribution_weight(
                {
                    "source": "Cursor",
                    "project": "timelog-extract",
                    "detail": "Bridge dashboard",
                    "anchors": {"label": "bridge dashboard"},
                }
            ),
            event_attribution_weight({"source": "Chrome", "project": "timelog-extract", "detail": "docs"}),
        )

    def test_session_duration_with_ai_sources(self):
        base = datetime(2026, 6, 11, 8, 0, tzinfo=timezone.utc)
        end = base + timedelta(minutes=30)
        events = [{"source": "Chrome", "project": "financing-portal", "detail": "x"}]
        hours = session_duration_hours(events, base, end, 15, 5, AI_SOURCES)
        self.assertAlmostEqual(hours, 0.5, places=3)


if __name__ == "__main__":
    unittest.main()
