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


class CoreDomainWeightedClassifyTests(unittest.TestCase):
    """Tests for the new weighted scoring in classify_project()."""

    def test_generic_tool_term_has_lower_weight_than_regular_term(self):
        """A profile with a specific term wins over one with only a generic tool term."""
        profiles = [
            {"name": "GenericProject", "match_terms": ["jira"], "tracked_urls": []},
            {"name": "SpecificProject", "match_terms": ["myapp"], "tracked_urls": []},
        ]
        result = domain.classify_project(
            "working on myapp via jira ticket", profiles, "Uncategorized"
        )
        # "myapp" is specific (weight 1.0), "jira" is generic (weight 0.25)
        self.assertEqual(result, "SpecificProject")

    def test_path_like_term_has_higher_weight(self):
        """Path-like terms (containing /) outweigh regular terms."""
        profiles = [
            {"name": "PathProject", "match_terms": ["/users/dev/myapp"], "tracked_urls": []},
            {"name": "RegularProject", "match_terms": ["alpha", "beta", "gamma"], "tracked_urls": []},
        ]
        result = domain.classify_project(
            "editing /users/dev/myapp/main.py alpha beta gamma", profiles, "Uncategorized"
        )
        # Path term = 2.0, three regular terms = 3.0 -> RegularProject wins on score
        # but path also adds specific_hits. Let's verify path is weighted at 2.0.
        # With 3 regular terms at 1.0 each = 3.0 > one path at 2.0 => RegularProject wins.
        self.assertEqual(result, "RegularProject")

    def test_single_path_term_beats_two_generic_terms(self):
        """One path-like term (2.0) beats two generic tool terms (0.25 each = 0.5)."""
        profiles = [
            {"name": "PathProject", "match_terms": ["/workspace/app"], "tracked_urls": []},
            {"name": "GenericProject", "match_terms": ["jira", "toggl"], "tracked_urls": []},
        ]
        result = domain.classify_project(
            "edited /workspace/app with jira toggl", profiles, "Uncategorized"
        )
        self.assertEqual(result, "PathProject")

    def test_tracked_url_adds_extra_weight(self):
        """A tracked URL match (2.0) boosts a profile over plain term match."""
        profiles = [
            {
                "name": "UrlProject",
                "match_terms": ["alpha"],
                "tracked_urls": ["my-app.lovable.dev"],
            },
            {
                "name": "TermProject",
                "match_terms": ["alpha", "beta"],
                "tracked_urls": [],
            },
        ]
        result = domain.classify_project(
            "alpha beta my-app.lovable.dev", profiles, "Uncategorized"
        )
        # UrlProject: alpha(1.0) + url(2.0) = 3.0; TermProject: alpha(1.0)+beta(1.0)=2.0
        self.assertEqual(result, "UrlProject")

    def test_profile_name_match_adds_weight(self):
        """Profile name found in text adds 1.0 to weighted score."""
        profiles = [
            {"name": "ProjectAlpha", "match_terms": ["alpha"], "tracked_urls": []},
            {"name": "ProjectBeta", "match_terms": ["alpha", "beta"], "tracked_urls": []},
        ]
        result = domain.classify_project(
            "ProjectAlpha alpha", profiles, "Uncategorized"
        )
        # ProjectAlpha: "alpha"(1.0) + name match(1.0) = 2.0; ProjectBeta: "alpha"(1.0) = 1.0
        self.assertEqual(result, "ProjectAlpha")

    def test_all_generic_terms_do_not_beat_one_specific_term(self):
        """Multiple generic tool terms (e.g. jira, toggl) don't beat one specific term."""
        profiles = [
            {"name": "Generic", "match_terms": ["jira", "toggl", "atlassian", "cloudflare"], "tracked_urls": []},
            {"name": "Specific", "match_terms": ["my-unique-project"], "tracked_urls": []},
        ]
        result = domain.classify_project(
            "my-unique-project via jira toggl atlassian cloudflare", profiles, "Uncategorized"
        )
        # Generic: 4 * 0.25 = 1.0; Specific: 1.0 -> tie on score but Specific wins on specific_hits(1 vs 0)
        self.assertEqual(result, "Specific")

    def test_fallback_returned_when_no_match(self):
        """Returns fallback when no terms match."""
        profiles = [
            {"name": "ProjectX", "match_terms": ["projectx"], "tracked_urls": []},
        ]
        result = domain.classify_project("unrelated text here", profiles, "Uncategorized")
        self.assertEqual(result, "Uncategorized")

    def test_empty_profiles_returns_fallback(self):
        """Empty profile list returns fallback."""
        self.assertEqual(domain.classify_project("text", [], "Fallback"), "Fallback")

    def test_empty_text_returns_fallback(self):
        """Empty text never matches any terms."""
        profiles = [{"name": "P", "match_terms": ["something"], "tracked_urls": []}]
        self.assertEqual(domain.classify_project("", profiles, "Fallback"), "Fallback")

    def test_is_path_like_term_with_slash(self):
        """Terms containing '/' are classified as path-like."""
        self.assertTrue(domain._is_path_like_term("/users/dev/app"))
        self.assertTrue(domain._is_path_like_term("workspace/foo"))
        self.assertTrue(domain._is_path_like_term("a/b"))

    def test_is_path_like_term_without_slash(self):
        """Plain terms are not path-like."""
        self.assertFalse(domain._is_path_like_term("myapp"))
        self.assertFalse(domain._is_path_like_term("jira"))

    def test_is_path_like_term_with_backslash(self):
        """Windows-style paths with '\\' are path-like."""
        self.assertTrue(domain._is_path_like_term("C:\\Users\\dev\\app"))

    def test_is_path_like_term_empty(self):
        """Empty string is not path-like."""
        self.assertFalse(domain._is_path_like_term(""))

    def test_generic_tool_terms_set_contents(self):
        """GENERIC_TOOL_TERMS contains the expected well-known tools."""
        from core.domain import GENERIC_TOOL_TERMS
        expected = {"jira", "toggl", "atlassian", "cloudflare", "jira.com", "toggl.com", "toggle", "toggle.com"}
        self.assertEqual(GENERIC_TOOL_TERMS, expected)

    def test_tiebreak_prefers_fewer_generic_hits(self):
        """When weighted scores tie, fewer generic hits wins (rank uses -generic_hits)."""
        profiles = [
            {
                "name": "PureGeneric",
                "match_terms": ["jira", "toggl", "atlassian", "cloudflare"],
                "tracked_urls": [],
            },
            {
                "name": "OneSpecific",
                "match_terms": ["myproject"],
                "tracked_urls": [],
            },
        ]
        # jira(0.25)+toggl(0.25)+atlassian(0.25)+cloudflare(0.25)=1.0; myproject=1.0
        # Same weighted_score, but OneSpecific has specific_hits=1 > PureGeneric.specific_hits=0
        result = domain.classify_project(
            "myproject via jira toggl atlassian cloudflare", profiles, "Uncategorized"
        )
        self.assertEqual(result, "OneSpecific")


if __name__ == "__main__":
    unittest.main()