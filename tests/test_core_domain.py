"""Unit tests for core domain time and classification helpers."""

from datetime import datetime, timedelta, timezone
import unittest

from core import domain


class CoreDomainTests(unittest.TestCase):
    """Covers deterministic behavior in core domain utilities."""

    def test_classify_project_prefers_most_terms(self):
        """Chooses the profile with the highest number of matched terms."""
        profiles = [
            {"name": "ProjA", "match_terms": ["apple", "banana"]},
            {"name": "ProjB", "match_terms": ["apple"]},
        ]
        self.assertEqual(
            domain.classify_project("apple banana task", profiles, "Uncategorized"),
            "ProjA",
        )

    def test_compute_sessions_respects_gap_threshold(self):
        """Splits sessions when event gap reaches the configured threshold."""
        base = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
        entries = [
            {"local_ts": base},
            {"local_ts": base + timedelta(minutes=10)},
            {"local_ts": base + timedelta(minutes=25)},
        ]
        sessions = domain.compute_sessions(entries, gap_minutes=15)
        self.assertEqual(len(sessions), 2)

    def test_billable_total_hours_rounds_up(self):
        """Rounds up to the next billable unit when needed."""
        self.assertEqual(domain.billable_total_hours(1.01, 0.25), 1.25)
        self.assertEqual(domain.billable_total_hours(1.5, 0.25), 1.5)

    def test_session_duration_uses_ai_minimum(self):
        """Uses AI minimum session duration for sessions with AI sources."""
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

    def test_session_duration_uses_passive_minimum(self):
        """Uses the passive minimum when no AI sources are present."""
        start = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
        end = start + timedelta(minutes=1)
        events = [{"source": "Chrome"}]
        h = domain.session_duration_hours(
            events,
            start,
            end,
            min_session_minutes=15,
            min_session_passive_minutes=5,
            ai_sources={"Claude Code CLI"},
        )
        self.assertAlmostEqual(h, 5 / 60)

    def test_session_duration_uses_actual_when_longer_than_minimum(self):
        """Returns the actual duration when it exceeds the minimum."""
        start = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
        end = start + timedelta(hours=2)
        events = [{"source": "Claude Code CLI"}]
        h = domain.session_duration_hours(
            events,
            start,
            end,
            min_session_minutes=15,
            min_session_passive_minutes=5,
            ai_sources={"Claude Code CLI"},
        )
        self.assertAlmostEqual(h, 2.0)

    def test_compute_sessions_merges_close_entries(self):
        """Entries within the gap threshold are merged into a single session."""
        base = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
        entries = [
            {"local_ts": base},
            {"local_ts": base + timedelta(minutes=5)},
            {"local_ts": base + timedelta(minutes=10)},
        ]
        sessions = domain.compute_sessions(entries, gap_minutes=15)
        self.assertEqual(len(sessions), 1)
        self.assertEqual(len(sessions[0][2]), 3)

    def test_billable_total_hours_no_unit(self):
        """Returns raw hours unchanged when unit is None or zero."""
        self.assertAlmostEqual(domain.billable_total_hours(1.37, None), 1.37)
        self.assertAlmostEqual(domain.billable_total_hours(1.37, 0), 1.37)

    def test_classify_project_returns_fallback_with_no_profiles(self):
        """Returns the fallback when the profile list is empty."""
        result = domain.classify_project("any text here", [], "Uncategorized")
        self.assertEqual(result, "Uncategorized")

    def test_classify_project_prefers_repo_path_over_generic_tool_term(self):
        profiles = [
            {"name": "AX Finans", "match_terms": ["ax-finans", "/users/me/ax-finans"]},
            {"name": "Akturo", "match_terms": ["cloudflare", "akturo"]},
        ]
        text = "Cloudflare Dashboard /Users/me/ax-finans"
        self.assertEqual(domain.classify_project(text, profiles, "Uncategorized"), "AX Finans")

    def test_classify_project_prefers_tracked_url_over_generic_tool_term(self):
        profiles = [
            {"name": "AX Finans", "match_terms": ["cloudflare"], "tracked_urls": ["dash.cloudflare.com/accounts/ax"]},
            {"name": "Akturo", "match_terms": ["cloudflare"], "tracked_urls": []},
        ]
        text = "https://dash.cloudflare.com/accounts/ax overview"
        self.assertEqual(domain.classify_project(text, profiles, "Uncategorized"), "AX Finans")


if __name__ == "__main__":
    unittest.main()
