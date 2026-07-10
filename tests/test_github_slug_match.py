"""Tests for GitHub slug family matching and repo-shift detection."""

from __future__ import annotations

import unittest
from collections import Counter

from core.github_slug_match import (
    collect_profile_activity_from_events,
    collect_slug_activity_from_events,
    discover_active_repo_shift_signals,
    expand_repo_family,
    github_repo_stem,
    github_slugs_in_text,
    is_plausible_github_slug,
    is_successor_repo_slug,
    prefer_billing_project_name,
    profile_for_github_slug,
    same_repo_family,
    suggest_project_from_slug_activity,
)


class GithubSlugMatchTests(unittest.TestCase):
    def test_github_repo_stem_strips_lovable_hash_fork(self):
        self.assertEqual(
            github_repo_stem("financing-portal-dev-31e799cf"),
            "financing-portal-dev",
        )

    def test_profile_matches_hash_fork_to_existing_project(self):
        profiles = [
            {
                "name": "financing-portal",
                "match_terms": [
                    "ax-finans/financing-portal-dev",
                    "financing-portal",
                    "ax-or.com",
                ],
            }
        ]
        self.assertEqual(
            profile_for_github_slug("ax-finans/financing-portal-dev-31e799cf", profiles),
            "financing-portal",
        )

    def test_repo_shift_surfaces_successor_repo_from_chrome_and_github(self):
        profiles = [
            {
                "name": "financing-portal",
                "match_terms": ["ax-finans/financing-portal-dev", "financing-portal"],
            }
        ]
        events = [
            {
                "source": "Chrome",
                "detail": "Pull requests · ax-finans/financing-portal-dev-31e799cf",
                "project": "Uncategorized",
            },
            {
                "source": "GitHub",
                "detail": "push to ax-finans/financing-portal-dev-31e799cf (2 commits, ref main)",
                "project": "Uncategorized",
            },
        ]
        activity = collect_slug_activity_from_events(events)
        signals = discover_active_repo_shift_signals(profiles, activity, min_activity=2)
        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0]["value"], "ax-finans/financing-portal-dev-31e799cf")
        self.assertEqual(signals[0]["suggested_project"], "financing-portal")
        self.assertIn("was financing-portal-dev", signals[0]["display"])

    def test_stale_configured_repo_with_no_activity_does_not_block_shift(self):
        profiles = [
            {
                "name": "financing-portal-dev",
                "match_terms": ["ax-finans/financing-portal-dev"],
            }
        ]
        activity = Counter({"ax-finans/financing-portal-dev-31e799cf": 7})
        signals = discover_active_repo_shift_signals(profiles, activity)
        self.assertEqual(signals[0]["value"], "ax-finans/financing-portal-dev-31e799cf")
        self.assertEqual(signals[0]["suggested_project"], "financing-portal-dev")

    def test_shorter_sibling_repo_is_not_a_successor(self):
        self.assertFalse(
            is_successor_repo_slug("ax-finans/financing-portal", "ax-finans/financing-portal-dev")
        )

    def test_hash_fork_is_successor_of_dev_repo(self):
        self.assertTrue(
            is_successor_repo_slug(
                "ax-finans/financing-portal-dev-31e799cf",
                "ax-finans/financing-portal-dev",
            )
        )

    def test_financing_portal_slug_does_not_false_match_dev_profile(self):
        profiles = [
            {
                "name": "financing-portal-dev",
                "match_terms": ["ax-finans/financing-portal-dev"],
            }
        ]
        self.assertIsNone(profile_for_github_slug("ax-finans/financing-portal", profiles))

    def test_prefer_billing_project_over_dev_alias(self):
        profiles = [
            {"name": "financing-portal", "customer": "ax-or.com", "match_terms": []},
            {"name": "financing-portal-dev", "customer": "ax-or.com", "match_terms": []},
        ]
        self.assertEqual(
            prefer_billing_project_name("financing-portal-dev", profiles),
            "financing-portal",
        )

    def test_github_activity_ranks_main_repo_over_hash_fork(self):
        profiles = [
            {
                "name": "financing-portal",
                "customer": "ax-or.com",
                "match_terms": ["ax-finans/financing-portal", "ax-finans/financing-portal-dev"],
            },
            {
                "name": "financing-portal-dev",
                "customer": "ax-or.com",
                "match_terms": ["ax-finans/financing-portal-dev"],
            },
            {"name": "timelog-extract", "match_terms": ["mbjorke/timelog-extract"]},
        ]
        events = [
            {
                "source": "GitHub",
                "detail": "PR #12 merged: feature (ax-finans/financing-portal)",
                "project": "financing-portal",
            },
            {
                "source": "GitHub",
                "detail": "PR #3 merged: fix (ax-finans/financing-portal)",
                "project": "financing-portal",
            },
            {
                "source": "GitHub",
                "detail": "push to ax-finans/financing-portal-dev-31e799cf (1 commits, ref main)",
                "project": "Uncategorized",
            },
            {
                "source": "Lovable (desktop)",
                "detail": "storage signal — https://810513a4-6676-4f18-ae92-097467e52d98.lovableproject.com/",
                "project": "Uncategorized",
            },
            {
                "source": "Chrome",
                "detail": "Pull requests · ax-finans/financing-portal",
                "project": "financing-portal",
            },
        ]
        self.assertEqual(
            suggest_project_from_slug_activity(events, profiles),
            "financing-portal",
        )
        activity = collect_profile_activity_from_events(events, profiles)
        self.assertGreater(activity["financing-portal"], activity.get("financing-portal-dev", 0))

    def test_dual_profile_config_surfaces_hash_fork_not_sibling(self):
        profiles = [
            {
                "name": "financing-portal",
                "match_terms": [
                    "ax-finans/financing-portal",
                    "ax-finans/financing-portal-dev",
                ],
            },
            {
                "name": "financing-portal-dev",
                "match_terms": ["ax-finans/financing-portal-dev"],
            },
        ]
        activity = Counter(
            {
                "ax-finans/financing-portal-dev-31e799cf": 9,
                "ax-finans/financing-portal": 4,
                "ax-finans/financing-portal-dev": 0,
            }
        )
        signals = discover_active_repo_shift_signals(profiles, activity)
        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0]["value"], "ax-finans/financing-portal-dev-31e799cf")
        self.assertIn("financing-portal-dev", signals[0]["display"])
        self.assertNotIn("31e799cf", signals[0]["display"])
        self.assertEqual(signals[0]["suggested_project"], "financing-portal")

    def test_rejects_reserved_github_site_paths(self):
        self.assertFalse(is_plausible_github_slug("login/oauth"))
        self.assertFalse(is_plausible_github_slug("sponsors/blueberry-maybe"))
        self.assertFalse(is_plausible_github_slug("europe/mariehamn"))

    def test_same_repo_family_groups_financing_portal_variants(self):
        anchors = {"ax-finans/financing-portal"}
        pool = {
            "ax-finans/financing-portal",
            "ax-finans/financing-portal-dev",
            "ax-finans/financing-portal-dev-31e799cf",
            "mbjorke/timelog-extract",
            "sponsors/blueberry-maybe",
        }
        family = expand_repo_family(anchors, pool)
        self.assertEqual(
            family,
            {
                "ax-finans/financing-portal",
                "ax-finans/financing-portal-dev",
                "ax-finans/financing-portal-dev-31e799cf",
            },
        )
        self.assertFalse(same_repo_family("mbjorke/timelog-extract", "mbjorke/time-log-genius"))
        self.assertFalse(same_repo_family("mbjorke/blueberry", "mbjorke/blueberry-fintech"))
        self.assertFalse(same_repo_family("mbjorke/blueberry-fintech", "mbjorke/blueberry-site"))

    def test_rejects_local_path_tokens_as_github_slugs(self):
        noise = [
            "docs/ideas/triage-signal-examples.md",
            ".claude/settings.json",
            ".cursor/hooks.json",
            "timelog-extract/docs/runbooks/ci.md",
            "main...claude/freelance-bridge-dashboard-cefo5",
            "id-preview--80f778b5.lovable.app/auth",
        ]
        for text in noise:
            self.assertEqual(github_slugs_in_text(text), [], msg=text)
        self.assertFalse(is_plausible_github_slug("ideas/triage-signal-examples.md"))
        self.assertFalse(is_plausible_github_slug("axfinans.cloudflareaccess.com/cdn-cgi"))

    def test_rejects_cursor_glass_multitask_product_surface(self):
        """GH-359: Glass/Multitask parentheticals must not invent a fake remote."""
        noise = [
            "issue #348 closed: restore chat title when composerHeaders missing "
            "(Glass/Multitask) (mbjorke/timelog-extract)",
            "switched to glass/multitask",
            "working in glass/multitask mode",
            "https://github.com/glass/multitask",
            "Pull requests · glass/multitask",
        ]
        for text in noise:
            slugs = github_slugs_in_text(text)
            self.assertNotIn("glass/multitask", slugs, msg=text)
        self.assertFalse(is_plausible_github_slug("glass/multitask"))
        # Trailing ``({repo})`` from GitHub IssuesEvent details still parses.
        mixed = (
            "issue #348 labeled: Cursor (agent): missing (Glass/Multitask) "
            "(mbjorke/timelog-extract)"
        )
        self.assertEqual(github_slugs_in_text(mixed), ["mbjorke/timelog-extract"])
        self.assertEqual(
            github_slugs_in_text("PR #1 merged (mbjorke/timelog-extract)"),
            ["mbjorke/timelog-extract"],
        )

    def test_no_shift_when_only_sibling_repo_is_active(self):
        profiles = [
            {
                "name": "financing-portal-dev",
                "match_terms": ["ax-finans/financing-portal-dev"],
            }
        ]
        activity = Counter(
            {
                "ax-finans/financing-portal": 8,
                "ax-finans/financing-portal-dev": 0,
            }
        )
        signals = discover_active_repo_shift_signals(profiles, activity)
        self.assertEqual(signals, [])


if __name__ == "__main__":
    unittest.main()
