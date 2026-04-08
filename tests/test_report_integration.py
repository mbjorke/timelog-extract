"""Integration-style tests for report aggregation from synthetic events."""

from datetime import datetime, timedelta, timezone
import unittest

from timelog_extract import LOCAL_TZ, estimate_hours_by_day, group_by_day


class ReportIntegrationTests(unittest.TestCase):
    """Verifies end-to-end day and project totals from event inputs."""

    def test_synthetic_events_produce_expected_day_and_project_totals(self):
        """Aggregates synthetic events into expected overall and project hours."""
        base = datetime(2026, 4, 8, 10, 0, tzinfo=timezone.utc)
        events = [
            {
                "source": "TIMELOG.md",
                "timestamp": base,
                "detail": "Project A kickoff",
                "project": "Project A",
            },
            {
                "source": "TIMELOG.md",
                "timestamp": base + timedelta(minutes=5),
                "detail": "Project A follow-up",
                "project": "Project A",
            },
            {
                "source": "Chrome",
                "timestamp": base + timedelta(minutes=30),
                "detail": "Project B research",
                "project": "Project B",
            },
        ]

        grouped = group_by_day(events)
        overall_days = estimate_hours_by_day(
            grouped,
            gap_minutes=15,
            min_session_minutes=15,
            min_session_passive_minutes=5,
        )

        project_reports = {}
        for project_name in sorted({event["project"] for event in events}):
            project_events = [event for event in events if event["project"] == project_name]
            project_grouped = group_by_day(project_events)
            project_reports[project_name] = estimate_hours_by_day(
                project_grouped,
                gap_minutes=15,
                min_session_minutes=15,
                min_session_passive_minutes=5,
            )

        day = base.astimezone(LOCAL_TZ).date().isoformat()
        self.assertIn(day, overall_days)
        self.assertEqual(len(overall_days[day]["sessions"]), 2)
        self.assertAlmostEqual(overall_days[day]["hours"], (15 + 5) / 60, places=6)

        self.assertEqual(sorted(project_reports.keys()), ["Project A", "Project B"])
        self.assertAlmostEqual(project_reports["Project A"][day]["hours"], 15 / 60, places=6)
        self.assertAlmostEqual(project_reports["Project B"][day]["hours"], 5 / 60, places=6)


if __name__ == "__main__":
    unittest.main()
