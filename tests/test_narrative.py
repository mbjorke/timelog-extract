"""Tests for rule-based executive narrative."""

from datetime import datetime, timezone
import unittest

from outputs.narrative import build_narrative_lines


class NarrativeTests(unittest.TestCase):
    """Builds plain-English summary lines from aggregated report data."""

    def test_no_activity_fallback(self):
        dt0 = datetime(2026, 4, 8, 0, 0, tzinfo=timezone.utc)
        dt1 = datetime(2026, 4, 8, 23, 59, tzinfo=timezone.utc)
        lines = build_narrative_lines(
            overall_days={},
            project_reports={},
            included_events=[],
            uncategorized="Uncategorized",
            source_order=[],
            dt_from=dt0,
            dt_to=dt1,
        )
        self.assertTrue(any("nothing to summarize" in ln.lower() for ln in lines))

    def test_single_day_includes_totals_and_projects(self):
        day = "2026-04-08"
        overall_days = {
            day: {
                "hours": 2.5,
                "sessions": [1, 2],
                "entries": [],
            }
        }
        project_reports = {
            "Proj A": {day: {"hours": 1.5, "sessions": [], "entries": []}},
            "Proj B": {day: {"hours": 1.0, "sessions": [], "entries": []}},
        }
        events = [
            {"source": "Cursor", "project": "Proj A"},
            {"source": "Chrome", "project": "Proj B"},
        ]
        dt0 = datetime(2026, 4, 8, 0, 0, tzinfo=timezone.utc)
        dt1 = datetime(2026, 4, 8, 23, 59, tzinfo=timezone.utc)
        lines = build_narrative_lines(
            overall_days,
            project_reports,
            events,
            "Uncategorized",
            ["Cursor", "Chrome"],
            dt0,
            dt1,
        )
        joined = " ".join(lines)
        self.assertIn("2.5 h", joined)
        self.assertIn("Proj A", joined)
        self.assertIn("Cursor", joined)

    def test_multi_day_finds_busiest(self):
        overall_days = {
            "2026-04-07": {"hours": 1.0, "sessions": [1], "entries": []},
            "2026-04-08": {"hours": 4.0, "sessions": [1, 2], "entries": []},
        }
        project_reports = {
            "P": {
                "2026-04-07": {"hours": 1.0, "sessions": [], "entries": []},
                "2026-04-08": {"hours": 4.0, "sessions": [], "entries": []},
            }
        }
        dt0 = datetime(2026, 4, 7, 0, 0, tzinfo=timezone.utc)
        dt1 = datetime(2026, 4, 8, 23, 59, tzinfo=timezone.utc)
        lines = build_narrative_lines(
            overall_days,
            project_reports,
            [{"source": "TIMELOG.md", "project": "P"}],
            "Uncategorized",
            ["TIMELOG.md"],
            dt0,
            dt1,
        )
        self.assertTrue(any("2026-04-08" in ln and "busiest" in ln for ln in lines))


if __name__ == "__main__":
    unittest.main()
