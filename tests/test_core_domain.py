from datetime import datetime, timedelta, timezone
import unittest

from core import domain


class CoreDomainTests(unittest.TestCase):
    def test_classify_project_prefers_most_terms(self):
        profiles = [
            {"name": "ProjA", "match_terms": ["apple", "banana"]},
            {"name": "ProjB", "match_terms": ["apple"]},
        ]
        self.assertEqual(
            domain.classify_project("apple banana task", profiles, "Uncategorized"),
            "ProjA",
        )

    def test_compute_sessions_respects_gap_threshold(self):
        base = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
        entries = [
            {"local_ts": base},
            {"local_ts": base + timedelta(minutes=10)},
            {"local_ts": base + timedelta(minutes=25)},
        ]
        sessions = domain.compute_sessions(entries, gap_minutes=15)
        self.assertEqual(len(sessions), 2)

    def test_billable_total_hours_rounds_up(self):
        self.assertEqual(domain.billable_total_hours(1.01, 0.25), 1.25)
        self.assertEqual(domain.billable_total_hours(1.5, 0.25), 1.5)

    def test_session_duration_uses_ai_minimum(self):
        start = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
        end = start + timedelta(minutes=1)
        events = [{"source": "Claude Code CLI"}]
        h = domain.session_duration_hours(
            events,
            start,
            end,
            min_session_minutes=15,
            min_session_passive_minutes=5,
            ai_sources={"Claude Code CLI"},
        )
        self.assertAlmostEqual(h, 0.25)


if __name__ == "__main__":
    unittest.main()
