"""Unit tests for core domain time and classification helpers."""

from datetime import datetime, timedelta, timezone
import unittest

from core import domain
from core.domain import GENERIC_TOOL_TERMS, _is_path_like_term


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


class IsPathLikeTermTests(unittest.TestCase):
    """Direct unit tests for _is_path_like_term()."""

    def test_forward_slash_is_path_like(self):
        self.assertTrue(_is_path_like_term("/users/me/project"))

    def test_backslash_is_path_like(self):
        self.assertTrue(_is_path_like_term("c:\\users\\me\\project"))

    def test_starts_with_users_slash(self):
        self.assertTrue(_is_path_like_term("users/me/project"))

    def test_starts_with_workspace_slash(self):
        self.assertTrue(_is_path_like_term("workspace/project-x"))

    def test_plain_term_is_not_path_like(self):
        self.assertFalse(_is_path_like_term("akturo"))

    def test_empty_string_is_not_path_like(self):
        self.assertFalse(_is_path_like_term(""))

    def test_none_treated_as_empty(self):
        self.assertFalse(_is_path_like_term(None))  # type: ignore[arg-type]

    def test_domain_like_term_is_not_path_like(self):
        self.assertFalse(_is_path_like_term("cloudflare"))

    def test_case_insensitive_users_prefix(self):
        self.assertTrue(_is_path_like_term("USERS/me/project"))


class GenericToolTermsTests(unittest.TestCase):
    """Tests for GENERIC_TOOL_TERMS constant and its effect on classification."""

    def test_generic_tool_terms_contains_known_entries(self):
        for term in ("cloudflare", "jira", "atlassian", "toggl"):
            self.assertIn(term, GENERIC_TOOL_TERMS, msg=f"Expected '{term}' in GENERIC_TOOL_TERMS")

    def test_classify_project_generic_term_alone_loses_to_specific_term(self):
        """A generic tool term alone should score less than a specific project term."""
        profiles = [
            {"name": "CloudProject", "match_terms": ["cloudflare"], "tracked_urls": []},
            {"name": "SpecificProject", "match_terms": ["specific-keyword"], "tracked_urls": []},
        ]
        result = domain.classify_project("cloudflare specific-keyword task", profiles, "Uncategorized")
        self.assertEqual(result, "SpecificProject")

    def test_classify_project_generic_term_tie_broken_by_specifics(self):
        """When both profiles match same generic term, profile with additional specific term wins."""
        profiles = [
            {"name": "A", "match_terms": ["cloudflare"], "tracked_urls": []},
            {"name": "B", "match_terms": ["cloudflare", "project-b"], "tracked_urls": []},
        ]
        result = domain.classify_project("cloudflare project-b work", profiles, "Uncategorized")
        self.assertEqual(result, "B")

    def test_classify_project_path_like_term_outranks_generic(self):
        """A path-like match_term should get 2.0 weight vs 0.25 for generic tool term."""
        profiles = [
            {"name": "PathProject", "match_terms": ["/users/me/path-project"], "tracked_urls": []},
            {"name": "GenericProject", "match_terms": ["cloudflare", "jira", "atlassian"], "tracked_urls": []},
        ]
        text = "/users/me/path-project cloudflare jira atlassian"
        result = domain.classify_project(text, profiles, "Uncategorized")
        self.assertEqual(result, "PathProject")

    def test_classify_project_returns_fallback_when_no_match(self):
        profiles = [
            {"name": "Alpha", "match_terms": ["alpha"], "tracked_urls": []},
        ]
        result = domain.classify_project("no matching text here", profiles, "Fallback")
        self.assertEqual(result, "Fallback")

    def test_classify_project_tracked_url_scores_2(self):
        """A tracked URL hit should contribute 2.0 to weighted score."""
        profiles = [
            {"name": "UrlProject", "match_terms": [], "tracked_urls": ["special.example.com/project"]},
            {"name": "TermProject", "match_terms": ["special"], "tracked_urls": []},
        ]
        text = "visiting special.example.com/project and special"
        result = domain.classify_project(text, profiles, "Fallback")
        self.assertEqual(result, "UrlProject")

    def test_classify_project_name_match_contributes_to_score(self):
        """Profile name appearing in text adds 1.0 to weighted score."""
        profiles = [
            {"name": "SpecialProject", "match_terms": [], "tracked_urls": []},
            {"name": "OtherProject", "match_terms": ["other"], "tracked_urls": []},
        ]
        # "specialproject" in haystack but not "other" — profile name match wins
        result = domain.classify_project("SpecialProject task done", profiles, "Fallback")
        self.assertEqual(result, "SpecialProject")

    def test_classify_project_deterministic_ordering(self):
        """Equal-ranked profiles should resolve deterministically each call."""
        profiles = [
            {"name": "Alpha", "match_terms": ["shared"], "tracked_urls": []},
            {"name": "Beta", "match_terms": ["shared"], "tracked_urls": []},
        ]
        # Equal score — result should be consistent across calls
        r1 = domain.classify_project("shared context", profiles, "Fallback")
        r2 = domain.classify_project("shared context", profiles, "Fallback")
        self.assertEqual(r1, r2)


if __name__ == "__main__":
    unittest.main()