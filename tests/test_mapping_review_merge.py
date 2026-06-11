"""Tests for mapping review merge helpers and duplicate grouping."""

from __future__ import annotations

import unittest

from core.mapping_repo_status import SlugGitBinding
from core.mapping_review import (
    ProjectChangeProposal,
    RepoDuplicateLine,
    _merge_additions_for_change,
    _merge_removals_for_change,
    build_mapping_review,
    slug_to_github_url,
)


class MappingReviewMergeTests(unittest.TestCase):
    def test_merge_adds_all_slug_variants_including_inactive(self):
        change = ProjectChangeProposal(
            target_project="financing-portal",
            customer="ax-or.com",
            canonical_slug="ax-finans/financing-portal",
            canonical_remote_url=slug_to_github_url("ax-finans/financing-portal"),
            canonical_local_path="~/Workspace/financing-portal",
            canonical_activity_dot="[green]●[/green]",
            lines=[
                RepoDuplicateLine(
                    slug="ax-finans/financing-portal-dev-31e799cf",
                    remote_url=slug_to_github_url("ax-finans/financing-portal-dev-31e799cf"),
                    local_path="~/Workspace/financing-portal-dev-31e799cf",
                    activity_dot="[green]●[/green]",
                    status="Primary — remote activity in window",
                ),
            ],
        )
        additions = _merge_additions_for_change(change)
        values = [value for _project, _rtype, value in additions]
        self.assertIn("ax-finans/financing-portal", values)
        self.assertIn("ax-finans/financing-portal-dev-31e799cf", values)
        self.assertIn("financing-portal-dev", values)

    def test_merge_removes_duplicate_github_slugs_from_sibling_profiles(self):
        profiles = [
            {
                "name": "financing-portal",
                "customer": "ax-or.com",
                "match_terms": ["ax-finans/financing-portal"],
            },
            {
                "name": "financing-portal-dev",
                "customer": "ax-or.com",
                "match_terms": [
                    "ax-finans/financing-portal-dev",
                    "financing-portal-dev",
                    "offer-craft-local-path",
                ],
            },
        ]
        change = ProjectChangeProposal(
            target_project="financing-portal",
            customer="ax-or.com",
            canonical_slug="ax-finans/financing-portal",
            canonical_remote_url=slug_to_github_url("ax-finans/financing-portal"),
            canonical_local_path="~/ax-finans",
            canonical_activity_dot="[green]●[/green]",
            lines=[
                RepoDuplicateLine(
                    slug="ax-finans/financing-portal-dev",
                    remote_url=slug_to_github_url("ax-finans/financing-portal-dev"),
                    local_path="~/financing-portal-dev",
                    activity_dot="[yellow]●[/yellow]",
                    status="Duplicate — remote only",
                ),
                RepoDuplicateLine(
                    slug="ax-finans/financing-portal-dev-31e799cf",
                    remote_url=slug_to_github_url("ax-finans/financing-portal-dev-31e799cf"),
                    local_path="(not found on disk)",
                    activity_dot="[red]●[/red]",
                    status="Duplicate — remote only",
                ),
            ],
        )
        removals = _merge_removals_for_change(change, profiles)
        removed_values = {value for _project, _rtype, value in removals}
        self.assertIn("ax-finans/financing-portal-dev", removed_values)
        self.assertNotIn("offer-craft-local-path", removed_values)

    def test_ignores_path_noise_for_new_projects(self):
        profiles = [{"name": "timelog-extract", "match_terms": ["mbjorke/timelog-extract"]}]
        events = [
            {
                "source": "Cursor",
                "detail": "timelog-extract — read docs/ideas/fast-project-mapping-playbook.md",
                "project": "timelog-extract",
            },
            {
                "source": "GitHub",
                "detail": "created repository in mbjorke/landsbanken-faq-helper",
                "project": "Uncategorized",
            },
            {
                "source": "GitHub",
                "detail": "PR #1 merged (mbjorke/landsbanken-faq-helper)",
                "project": "Uncategorized",
            },
        ]
        review = build_mapping_review(events, profiles, slug_bindings={})
        self.assertEqual(len(review.new_projects), 1)
        self.assertEqual(review.new_projects[0].slug, "mbjorke/landsbanken-faq-helper")

    def test_does_not_group_tracked_url_repo_as_duplicate(self):
        profiles = [
            {
                "name": "timelog-extract",
                "match_terms": ["mbjorke/timelog-extract", "timelog-extract"],
                "tracked_urls": ["https://github.com/mbjorke/time-log-genius"],
            },
        ]
        events = [
            {
                "source": "Chrome",
                "detail": "https://github.com/mbjorke/time-log-genius",
                "project": "Uncategorized",
            },
        ]
        bindings = {
            "mbjorke/timelog-extract": SlugGitBinding(
                slug="mbjorke/timelog-extract",
                remote_url=slug_to_github_url("mbjorke/timelog-extract"),
                local_path="~/Workspace/Project/timelog-extract",
                last_commit_epoch=1_700_000_000,
                git_cmd_hits=3,
            ),
        }
        review = build_mapping_review(events, profiles, slug_bindings=bindings)
        self.assertEqual(review.change_count(), 0)

    def test_does_not_group_unrelated_slugs_with_project(self):
        profiles = [
            {
                "name": "timelog-extract",
                "match_terms": ["mbjorke/timelog-extract", "timelog-extract"],
            },
            {
                "name": "blueberry",
                "match_terms": ["mbjorke/blueberry", "blueberry"],
            },
        ]
        events = [
            {
                "source": "Chrome",
                "detail": "https://github.com/login/oauth",
                "project": "Uncategorized",
            },
            {
                "source": "Chrome",
                "detail": "https://github.com/sponsors/blueberry-maybe",
                "project": "Uncategorized",
            },
            {
                "source": "Chrome",
                "detail": "https://github.com/mbjorke/time-log-genius",
                "project": "Uncategorized",
            },
        ]
        bindings = {
            "mbjorke/timelog-extract": SlugGitBinding(
                slug="mbjorke/timelog-extract",
                remote_url=slug_to_github_url("mbjorke/timelog-extract"),
                local_path="~/Workspace/Project/timelog-extract",
                last_commit_epoch=1_700_000_000,
                git_cmd_hits=3,
            ),
            "mbjorke/blueberry": SlugGitBinding(
                slug="mbjorke/blueberry",
                remote_url=slug_to_github_url("mbjorke/blueberry"),
                local_path="~/Workspace/Lab/blueberry",
                last_commit_epoch=1_700_000_000,
                git_cmd_hits=2,
            ),
        }
        review = build_mapping_review(events, profiles, slug_bindings=bindings)
        self.assertEqual(len(review.changes), 0)

    def test_blueberry_products_are_not_one_duplicate_family(self):
        profiles = [
            {
                "name": "blueberry-fintech",
                "customer": "blueberry.ax",
                "canonical_project": "blueberry-fintech",
                "match_terms": ["mbjorke/blueberry-fintech"],
            },
            {
                "name": "blueberry",
                "customer": "blueberry.ax",
                "canonical_project": "blueberry",
                "match_terms": ["mbjorke/blueberry"],
            },
            {
                "name": "blueberry-vibeops",
                "customer": "blueberry.ax",
                "canonical_project": "blueberry-vibeops",
                "match_terms": ["mbjorke/blueberry-vibeops"],
            },
        ]
        bindings = {
            "mbjorke/blueberry-fintech": SlugGitBinding(
                slug="mbjorke/blueberry-fintech",
                remote_url=slug_to_github_url("mbjorke/blueberry-fintech"),
                local_path="~/Workspace/Lab/blueberry-fintech",
                last_commit_epoch=1_700_000_000,
                git_cmd_hits=2,
            ),
            "mbjorke/blueberry": SlugGitBinding(
                slug="mbjorke/blueberry",
                remote_url=slug_to_github_url("mbjorke/blueberry"),
                local_path="~/Workspace/Lab/blueberry",
                last_commit_epoch=1_700_000_000,
                git_cmd_hits=2,
            ),
            "mbjorke/blueberry-vibeops": SlugGitBinding(
                slug="mbjorke/blueberry-vibeops",
                remote_url=slug_to_github_url("mbjorke/blueberry-vibeops"),
                local_path="~/Workspace/Project/blueberry-vibeops",
                last_commit_epoch=1_700_000_000,
                git_cmd_hits=1,
            ),
        }
        review = build_mapping_review([], profiles, slug_bindings=bindings)
        self.assertEqual(review.change_count(), 0)

    def test_same_customer_unrelated_repos_stay_separate(self):
        profiles = [
            {
                "name": "financing-portal",
                "customer": "ax-or.com",
                "canonical_project": "financing-portal",
                "match_terms": ["ax-finans/financing-portal"],
            },
            {
                "name": "offer-craft-34",
                "customer": "ax-or.com",
                "canonical_project": "offer-craft-34",
                "match_terms": ["joakimlennartisaksson-byte/offer-craft-34"],
            },
        ]
        bindings = {
            "ax-finans/financing-portal": SlugGitBinding(
                slug="ax-finans/financing-portal",
                remote_url=slug_to_github_url("ax-finans/financing-portal"),
                local_path="~/ax-finans",
                last_commit_epoch=1_700_000_000,
                git_cmd_hits=2,
            ),
            "joakimlennartisaksson-byte/offer-craft-34": SlugGitBinding(
                slug="joakimlennartisaksson-byte/offer-craft-34",
                remote_url=slug_to_github_url("joakimlennartisaksson-byte/offer-craft-34"),
                local_path="~/offer-craft-34",
                last_commit_epoch=1_700_000_000,
                git_cmd_hits=2,
            ),
        }
        review = build_mapping_review([], profiles, slug_bindings=bindings)
        self.assertEqual(review.change_count(), 0)

    def test_merged_financing_portal_family_does_not_reappear(self):
        """After merge, active dev fork must not re-open the duplicate prompt."""
        profiles = [
            {
                "name": "financing-portal",
                "customer": "ax-or.com",
                "canonical_project": "financing-portal",
                "match_terms": [
                    "ax-finans/financing-portal",
                    "ax-finans/financing-portal-dev",
                    "ax-finans/financing-portal-dev-31e799cf",
                    "financing-portal-dev",
                ],
            },
            {
                "name": "financing-portal-dev",
                "customer": "ax-or.com",
                "canonical_project": "financing-portal-dev",
                "match_terms": [
                    "financing-portal-dev",
                    "portal-lovable.ax-finans.workers.dev",
                ],
            },
        ]
        bindings = {
            "ax-finans/financing-portal": SlugGitBinding(
                slug="ax-finans/financing-portal",
                remote_url=slug_to_github_url("ax-finans/financing-portal"),
                local_path="~/ax-finans",
                last_commit_epoch=1_700_000_000,
                git_cmd_hits=2,
            ),
        }
        events = [
            {
                "source": "GitHub",
                "detail": "PR merged in ax-finans/financing-portal-dev-31e799cf",
                "project": "Uncategorized",
            },
        ]
        review = build_mapping_review(events, profiles, slug_bindings=bindings)
        self.assertEqual(review.change_count(), 0)

    def test_unmerged_financing_portal_family_still_needs_review(self):
        profiles = [
            {
                "name": "financing-portal",
                "customer": "ax-or.com",
                "canonical_project": "financing-portal",
                "match_terms": ["ax-finans/financing-portal"],
            },
            {
                "name": "financing-portal-dev",
                "customer": "ax-or.com",
                "canonical_project": "financing-portal-dev",
                "match_terms": [
                    "ax-finans/financing-portal-dev",
                    "financing-portal-dev",
                ],
            },
        ]
        bindings = {
            "ax-finans/financing-portal": SlugGitBinding(
                slug="ax-finans/financing-portal",
                remote_url=slug_to_github_url("ax-finans/financing-portal"),
                local_path="~/ax-finans",
                last_commit_epoch=1_700_000_000,
                git_cmd_hits=2,
            ),
        }
        events = [
            {
                "source": "GitHub",
                "detail": "PR merged in ax-finans/financing-portal-dev-31e799cf",
                "project": "Uncategorized",
            },
        ]
        review = build_mapping_review(events, profiles, slug_bindings=bindings)
        self.assertEqual(review.change_count(), 1)
        self.assertEqual(review.changes[0].target_project, "financing-portal")

    def test_host_signals_are_ignored(self):
        profiles = [{"name": "financing-portal", "match_terms": ["ax-finans/financing-portal"]}]
        signals = [
            {
                "kind": "host",
                "value": "76f3aaa7-7437-45c3-871e-a6c1bac9ff02.lovableproject.com",
                "display": "Lovable project 76f3aaa7",
                "suggested_project": "financing-portal",
                "hits": 3,
            }
        ]
        review = build_mapping_review([], profiles, extra_signals=signals, slug_bindings={})
        self.assertEqual(review.change_count(), 0)


if __name__ == "__main__":
    unittest.main()
