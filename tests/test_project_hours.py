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
        self.assertAlmostEqual(sum(split.values()), 1.0, places=2)
        self.assertGreater(split["timelog-extract"], 0.0)
        self.assertLess(split["financing-portal"], 1.0)

    def test_mixed_composer_and_worklog_capped_to_session_wall_clock(self):
        """Overlapping high-signal spans must not exceed one session's wall-clock hours."""
        session_start = datetime(2026, 6, 11, 8, 44, tzinfo=timezone.utc)
        session_end = datetime(2026, 6, 11, 20, 23, tzinfo=timezone.utc)
        events = []
        cursor_ts = datetime(2026, 6, 11, 9, 22, tzinfo=timezone.utc)
        while cursor_ts <= session_end:
            events.append(
                {
                    "source": "Cursor",
                    "project": "timelog-extract",
                    "detail": "Freelance bridge dashboard development",
                    "local_ts": cursor_ts,
                    "anchors": {"label": "freelance bridge dashboard development"},
                }
            )
            cursor_ts += timedelta(minutes=14)
        events.extend(
            [
                {
                    "source": "Worklog (TIMELOG.md)",
                    "project": "financing-portal",
                    "detail": "commit",
                    "local_ts": datetime(2026, 6, 11, 9, 0, tzinfo=timezone.utc),
                },
                {
                    "source": "Worklog (TIMELOG.md)",
                    "project": "financing-portal",
                    "detail": "commit2",
                    "local_ts": datetime(2026, 6, 11, 11, 29, tzinfo=timezone.utc),
                },
                {
                    "source": "Lovable (desktop)",
                    "project": "financing-portal",
                    "detail": "storage signal",
                    "local_ts": datetime(2026, 6, 11, 19, 49, tzinfo=timezone.utc),
                },
            ]
        )
        session_hours = session_duration_hours(
            events,
            session_start,
            session_end,
            15,
            5,
            AI_SOURCES,
        )
        split = allocate_session_hours_by_project(
            events,
            session_hours,
            session_duration_hours_fn=session_duration_hours,
            min_session_minutes=15,
            min_session_passive_minutes=5,
        )
        self.assertLessEqual(sum(split.values()), session_hours + 0.02)
        self.assertGreater(split["timelog-extract"], split["financing-portal"])
        self.assertLess(split["financing-portal"], 2.0)

    def test_cli_heavy_session_remainder_goes_to_dominant_project(self):
        """Claude Code CLI is below high-signal floor but should claim session slack."""
        session_start = datetime(2026, 6, 15, 12, 31, tzinfo=timezone.utc)
        session_end = datetime(2026, 6, 15, 15, 34, tzinfo=timezone.utc)
        events = []
        ts = session_start
        while ts <= session_end:
            events.append(
                {
                    "source": "Claude Code CLI",
                    "project": "timelog-extract",
                    "detail": "diagnostic work",
                    "local_ts": ts,
                }
            )
            ts += timedelta(minutes=2)
        events.append(
            {
                "source": "Cursor (agent)",
                "project": "akturo",
                "detail": "Trial handling · 7 turns",
                "local_ts": datetime(2026, 6, 15, 12, 40, tzinfo=timezone.utc),
                "anchors": {"label": "trial handling"},
            }
        )
        session_hours = session_duration_hours(events, session_start, session_end, 15, 5, AI_SOURCES)
        split = allocate_session_hours_by_project(
            events,
            session_hours,
            session_duration_hours_fn=session_duration_hours,
            min_session_minutes=15,
            min_session_passive_minutes=5,
        )
        self.assertAlmostEqual(sum(split.values()), session_hours, places=2)
        self.assertGreater(split["timelog-extract"], split.get("akturo", 0.0) * 3)

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

    def test_wordpress_weight_above_chrome_below_github(self):
        self.assertGreater(
            event_attribution_weight({"source": "WordPress", "project": "acme-news", "detail": "wp-admin"}),
            event_attribution_weight({"source": "Chrome", "project": "acme-news", "detail": "tab"}),
        )
        self.assertLess(
            event_attribution_weight({"source": "WordPress", "project": "acme-news", "detail": "wp-admin"}),
            event_attribution_weight({"source": "GitHub", "project": "acme-news", "detail": "push"}),
        )
        self.assertLess(
            event_attribution_weight({"source": "Lovable (desktop)", "project": "x", "detail": "ping"}),
            5.0,
        )
        self.assertGreater(
            event_attribution_weight({"source": "Lovable (desktop)", "project": "x", "detail": "ping"}),
            event_attribution_weight({"source": "Lovable (web)", "project": "x", "detail": "lovable.dev"}),
        )
        self.assertGreater(
            event_attribution_weight({"source": "Lovable (web)", "project": "x", "detail": "lovable.dev"}),
            event_attribution_weight({"source": "Chrome", "project": "x", "detail": "tab"}),
        )

    def test_wordpress_dense_session_beats_lone_lovable_ping(self):
        """WordPress sub-span owns the block; Lovable cache hit must not steal half."""
        session_start = datetime(2026, 7, 9, 13, 20, tzinfo=timezone.utc)
        session_end = datetime(2026, 7, 9, 14, 38, tzinfo=timezone.utc)
        events = [
            {
                "source": "Lovable (desktop)",
                "project": "client-alpha",
                "detail": "client-alpha — demo project",
                "local_ts": session_start,
            },
        ]
        ts = datetime(2026, 7, 9, 13, 33, tzinfo=timezone.utc)
        while ts <= session_end:
            events.append(
                {
                    "source": "WordPress",
                    "project": "acme-news",
                    "detail": "Dashboard ‹ Acme News — WordPress",
                    "local_ts": ts,
                }
            )
            ts += timedelta(minutes=5)
        session_hours = session_duration_hours(
            events, session_start, session_end, 15, 5, AI_SOURCES
        )
        split = allocate_session_hours_by_project(
            events,
            session_hours,
            session_duration_hours_fn=session_duration_hours,
            min_session_minutes=15,
            min_session_passive_minutes=5,
        )
        self.assertAlmostEqual(sum(split.values()), session_hours, places=2)
        self.assertGreater(split["acme-news"], split.get("client-alpha", 0.0) * 4)
        self.assertLessEqual(split.get("client-alpha", 0.0), 0.25)

    def test_messenger_ping_does_not_equal_split_wordpress_block(self):
        """A short Messenger Chrome event must not take an equal share of a WP session."""
        session_start = datetime(2026, 7, 9, 7, 17, tzinfo=timezone.utc)
        session_end = datetime(2026, 7, 9, 8, 1, tzinfo=timezone.utc)
        events = [
            {
                "source": "Chrome",
                "project": "client-alpha",
                "detail": "(1) Client Alpha | Messenger",
                "local_ts": session_start,
            },
        ]
        ts = datetime(2026, 7, 9, 7, 25, tzinfo=timezone.utc)
        while ts <= session_end:
            events.append(
                {
                    "source": "WordPress",
                    "project": "acme-news",
                    "detail": "Plugins ‹ Acme News — WordPress",
                    "local_ts": ts,
                }
            )
            ts += timedelta(minutes=4)
        session_hours = session_duration_hours(
            events, session_start, session_end, 15, 5, AI_SOURCES
        )
        split = allocate_session_hours_by_project(
            events,
            session_hours,
            session_duration_hours_fn=session_duration_hours,
            min_session_minutes=15,
            min_session_passive_minutes=5,
        )
        self.assertGreater(split["acme-news"], split.get("client-alpha", 0.0) * 3)
        self.assertLessEqual(split.get("client-alpha", 0.0), 0.3)

    def test_session_duration_with_ai_sources(self):
        base = datetime(2026, 6, 11, 8, 0, tzinfo=timezone.utc)
        end = base + timedelta(minutes=30)
        events = [{"source": "Chrome", "project": "financing-portal", "detail": "x"}]
        hours = session_duration_hours(events, base, end, 15, 5, AI_SOURCES)
        self.assertAlmostEqual(hours, 0.5, places=3)


if __name__ == "__main__":
    unittest.main()
