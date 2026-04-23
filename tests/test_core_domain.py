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


class ClassifyProjectWeightedScoringTests(unittest.TestCase):
    """Tests for the weighted scoring improvements added in this PR."""

    def _make_profile(self, name, match_terms=None, tracked_urls=None, customer=None):
        p = {"name": name, "match_terms": match_terms or [], "tracked_urls": tracked_urls or []}
        if customer is not None:
            p["customer"] = customer
        return p

    def test_generic_tool_term_scores_lower_than_specific_term(self):
        """A profile with only a generic tool term loses to one with a real project term."""
        profiles = [
            self._make_profile("GenericProject", match_terms=["jira"]),
            self._make_profile("RealProject", match_terms=["myproject"]),
        ]
        # haystack has both terms
        result = domain.classify_project("jira myproject task", profiles, "Uncategorized")
        self.assertEqual(result, "RealProject")

    def test_path_like_term_scores_higher_than_regular_term(self):
        """A path-like match term receives 2.0 weight vs 1.0 for regular terms."""
        profiles = [
            self._make_profile("PathProject", match_terms=["/users/dev/special-repo"]),
            self._make_profile("TermProject", match_terms=["special-repo"]),
        ]
        # haystack contains the path, which outweighs the plain term match
        result = domain.classify_project("/users/dev/special-repo", profiles, "Uncategorized")
        self.assertEqual(result, "PathProject")

    def test_tracked_url_scores_highest(self):
        """tracked_urls match adds 2.0 weight, outranking generic terms."""
        profiles = [
            self._make_profile("UrlProject", tracked_urls=["myapp.lovable.app"]),
            self._make_profile("TermProject", match_terms=["myapp"]),
        ]
        result = domain.classify_project("myapp.lovable.app/dashboard", profiles, "Uncategorized")
        self.assertEqual(result, "UrlProject")

    def test_profile_name_match_adds_score(self):
        """Profile name appearing in haystack adds 1.0 to weighted score."""
        profiles = [
            self._make_profile("AlphaProject", match_terms=["alpha"]),
            self._make_profile("BetaProject", match_terms=[]),
        ]
        # "betaproject" appears in haystack -> BetaProject gets 1.0 from name match
        result = domain.classify_project("working on betaproject tasks", profiles, "Uncategorized")
        self.assertEqual(result, "BetaProject")

    def test_multiple_generic_terms_still_lose_to_one_specific_term(self):
        """Multiple generic terms (each 0.25) cannot outrank one specific term (1.0)."""
        # 4 generic terms = 1.0 weighted score; one specific = 1.0 specific_hits bonus
        profiles = [
            self._make_profile("GenericHeavy", match_terms=["jira", "toggl", "cloudflare", "atlassian"]),
            self._make_profile("SpecificProject", match_terms=["uniqueprojectname"]),
        ]
        text = "jira toggl cloudflare atlassian uniqueprojectname"
        result = domain.classify_project(text, profiles, "Uncategorized")
        # SpecificProject has 1.0 weighted + 1 specific_hit; GenericHeavy has 1.0 weighted + 0 specific_hits
        # Rank tuple comparison: (1.0, 1, 0, 1) > (1.0, 0, -4, 4)
        self.assertEqual(result, "SpecificProject")

    def test_is_path_like_term_slash(self):
        """Terms containing a slash are treated as path-like."""
        self.assertTrue(domain._is_path_like_term("/users/dev/myrepo"))

    def test_is_path_like_term_backslash(self):
        """Terms containing a backslash are treated as path-like."""
        self.assertTrue(domain._is_path_like_term("C:\\users\\dev"))

    def test_is_path_like_term_users_prefix(self):
        """Terms starting with 'users/' are path-like."""
        self.assertTrue(domain._is_path_like_term("users/dev/repo"))

    def test_is_path_like_term_workspace_prefix(self):
        """Terms starting with 'workspace/' are path-like."""
        self.assertTrue(domain._is_path_like_term("workspace/project-x"))

    def test_is_path_like_term_plain_word_is_false(self):
        """Plain word terms are not path-like."""
        self.assertFalse(domain._is_path_like_term("myproject"))
        self.assertFalse(domain._is_path_like_term("jira"))

    def test_generic_tool_terms_set_contains_expected_entries(self):
        """GENERIC_TOOL_TERMS includes known generic tools."""
        self.assertIn("jira", domain.GENERIC_TOOL_TERMS)
        self.assertIn("toggl", domain.GENERIC_TOOL_TERMS)
        self.assertIn("cloudflare", domain.GENERIC_TOOL_TERMS)
        self.assertIn("atlassian", domain.GENERIC_TOOL_TERMS)

    def test_fallback_returned_when_no_profile_matches(self):
        """Fallback is returned when haystack matches no profile terms."""
        profiles = [
            self._make_profile("ProjectX", match_terms=["zebra"]),
        ]
        result = domain.classify_project("no match here at all", profiles, "Fallback")
        self.assertEqual(result, "Fallback")

    def test_tie_broken_by_specific_hits(self):
        """When weighted scores tie, the profile with more specific_hits wins."""
        profiles = [
            # 2 specific terms = 2.0 weighted + 2 specific_hits
            self._make_profile("TwoTerms", match_terms=["alpha", "beta"]),
            # 1 tracked URL = 2.0 weighted + 1 specific_hit
            self._make_profile("OneUrl", tracked_urls=["alpha"]),
        ]
        # haystack contains both "alpha" and "beta"
        result = domain.classify_project("alpha beta task", profiles, "Uncategorized")
        self.assertEqual(result, "TwoTerms")

    def test_generic_terms_negative_score_in_tiebreaker(self):
        """Profiles with generic hits are penalised in the -generic_hits tiebreaker slot."""
        profiles = [
            self._make_profile("PureGeneric", match_terms=["jira"]),   # 0 specific, 1 generic
            self._make_profile("PureSpecific", match_terms=["projectx"]),  # 1 specific, 0 generic
        ]
        result = domain.classify_project("jira projectx", profiles, "Uncategorized")
        self.assertEqual(result, "PureSpecific")

    def test_empty_match_terms_handled_gracefully(self):
        """Profile with empty match_terms list is handled without error."""
        profiles = [self._make_profile("EmptyTerms", match_terms=[])]
        result = domain.classify_project("anything", profiles, "Default")
        self.assertEqual(result, "Default")

    def test_none_text_returns_fallback(self):
        """None text input returns fallback gracefully."""
        profiles = [self._make_profile("P", match_terms=["x"])]
        result = domain.classify_project(None, profiles, "Fallback")
        self.assertEqual(result, "Fallback")


if __name__ == "__main__":
    unittest.main()