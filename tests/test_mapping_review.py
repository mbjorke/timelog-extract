"""Tests for batch mapping review builder."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from core.mapping_repo_status import SlugGitBinding
from core.mapping_review import (
    build_mapping_review,
    merge_target_for_customer,
    slug_to_github_url,
)


class MappingReviewTests(unittest.TestCase):
    def test_local_clone_beats_remote_fork_for_active_status(self):
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
        ]
        recent = datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc)
        events = [
            {
                "source": "GitHub",
                "timestamp": recent,
                "detail": "push to ax-finans/financing-portal-dev-31e799cf (2 commits, ref main)",
                "project": "Uncategorized",
            },
        ]
        bindings = {
            "ax-finans/financing-portal": SlugGitBinding(
                slug="ax-finans/financing-portal",
                remote_url=slug_to_github_url("ax-finans/financing-portal"),
                local_path="~/ax-finans",
                last_commit_epoch=1_700_000_000,
                git_cmd_hits=0,
            ),
            "ax-finans/financing-portal-dev": SlugGitBinding(
                slug="ax-finans/financing-portal-dev",
                remote_url=slug_to_github_url("ax-finans/financing-portal-dev"),
                local_path="~/financing-portal-dev",
                last_commit_epoch=1_700_000_100,
                git_cmd_hits=1,
            ),
        }
        review = build_mapping_review(events, profiles, slug_bindings=bindings)
        change = review.changes[0]
        statuses = {line.remote_url: line.status for line in change.lines}
        self.assertEqual(
            statuses[slug_to_github_url("ax-finans/financing-portal-dev")],
            "Primary — local working copy",
        )
        self.assertEqual(
            statuses[slug_to_github_url("ax-finans/financing-portal-dev-31e799cf")],
            "Duplicate — remote only",
        )
        inactive_line = next(
            line
            for line in change.lines
            if line.slug == "ax-finans/financing-portal-dev-31e799cf"
        )
        self.assertIn("dim", inactive_line.activity_dot)

    def test_financing_portal_duplicate_group_uses_git_activity(self):
        profiles = [
            {
                "name": "financing-portal",
                "customer": "ax-or.com",
                "match_terms": [
                    "ax-finans/financing-portal",
                    "ax-finans/financing-portal-dev",
                ],
            },
            {
                "name": "financing-portal-dev",
                "customer": "ax-or.com",
                "match_terms": ["ax-finans/financing-portal-dev"],
            },
        ]
        events = [
            {
                "source": "GitHub",
                "detail": "PR #9 merged (ax-finans/financing-portal)",
                "project": "financing-portal",
            },
            {
                "source": "GitHub",
                "detail": "push to ax-finans/financing-portal-dev-31e799cf (2 commits, ref main)",
                "project": "Uncategorized",
            },
        ]
        bindings = {
            "ax-finans/financing-portal": SlugGitBinding(
                slug="ax-finans/financing-portal",
                remote_url=slug_to_github_url("ax-finans/financing-portal"),
                local_path="~/Workspace/financing-portal",
                last_commit_epoch=1_700_000_000,
                git_cmd_hits=0,
            ),
            "ax-finans/financing-portal-dev": SlugGitBinding(
                slug="ax-finans/financing-portal-dev",
                remote_url=slug_to_github_url("ax-finans/financing-portal-dev"),
                local_path="~/Workspace/financing-portal-dev",
                last_commit_epoch=1_700_000_100,
                git_cmd_hits=1,
            ),
            "ax-finans/financing-portal-dev-31e799cf": SlugGitBinding(
                slug="ax-finans/financing-portal-dev-31e799cf",
                remote_url=slug_to_github_url("ax-finans/financing-portal-dev-31e799cf"),
                local_path="~/Workspace/financing-portal-dev-31e799cf",
                last_commit_epoch=1_700_000_200,
                git_cmd_hits=8,
            ),
        }
        review = build_mapping_review(events, profiles, slug_bindings=bindings)
        self.assertEqual(review.change_count(), 1)
        change = review.changes[0]
        self.assertEqual(change.customer, "ax-or.com")
        self.assertEqual(change.target_project, "financing-portal")
        self.assertEqual(
            merge_target_for_customer("ax-or.com", profiles),
            "financing-portal",
        )
        self.assertEqual(change.canonical_remote_url, slug_to_github_url("ax-finans/financing-portal"))
        self.assertEqual(change.canonical_local_path, "~/Workspace/financing-portal")
        statuses = {line.remote_url: line.status for line in change.lines}
        self.assertEqual(
            statuses[slug_to_github_url("ax-finans/financing-portal-dev-31e799cf")],
            "Primary — local working copy",
        )
        self.assertEqual(
            statuses[slug_to_github_url("ax-finans/financing-portal-dev")],
            "Duplicate variant",
        )

    def test_chrome_only_repo_is_not_new_project_without_local_clone(self):
        profiles = [{"name": "timelog-extract", "match_terms": ["mbjorke/timelog-extract"]}]
        events = [
            {
                "source": "Chrome",
                "detail": "https://github.com/mbjorke/landsbanken-faq-helper",
                "project": "Uncategorized",
            },
            {
                "source": "Chrome",
                "detail": "Pull requests · mbjorke/landsbanken-faq-helper",
                "project": "Uncategorized",
            },
        ]
        review = build_mapping_review(events, profiles, slug_bindings={})
        self.assertEqual(len(review.new_projects), 0)

    def test_new_project_from_gh_repo_list(self):
        profiles = [{"name": "timelog-extract", "match_terms": ["mbjorke/timelog-extract"]}]
        dt_from = datetime(2026, 6, 10, tzinfo=timezone.utc)
        dt_to = datetime(2026, 6, 12, tzinfo=timezone.utc)
        gh_times = {"mbjorke/landsbanken-faq-helper": "2026-06-11 10:15"}
        with patch("core.mapping_review.collect_gh_repo_list_data", return_value=(gh_times, {})):
            review = build_mapping_review(
                [],
                profiles,
                slug_bindings={},
                dt_from=dt_from,
                dt_to=dt_to,
            )
        self.assertEqual(len(review.new_projects), 1)
        self.assertEqual(review.new_projects[0].slug, "mbjorke/landsbanken-faq-helper")
        self.assertEqual(review.new_projects[0].created_at, "2026-06-11 10:15")

    def test_new_project_from_local_clone(self):
        profiles = [{"name": "timelog-extract", "match_terms": ["mbjorke/timelog-extract"]}]
        bindings = {
            "mbjorke/landsbanken-faq-helper": SlugGitBinding(
                slug="mbjorke/landsbanken-faq-helper",
                remote_url=slug_to_github_url("mbjorke/landsbanken-faq-helper"),
                local_path="~/Workspace/landsbanken-faq-helper",
                last_commit_epoch=1_700_000_000,
                git_cmd_hits=1,
            ),
        }
        review = build_mapping_review([], profiles, slug_bindings=bindings)
        self.assertEqual(len(review.new_projects), 1)
        self.assertEqual(review.new_projects[0].slug, "mbjorke/landsbanken-faq-helper")

    def test_rejects_chrome_noise_as_new_project(self):
        profiles = [{"name": "timelog-extract", "match_terms": ["mbjorke/timelog-extract"]}]
        events = [
            {
                "source": "Chrome",
                "detail": "https://github.com/europe/mariehamn",
                "project": "Uncategorized",
            },
        ]
        review = build_mapping_review(events, profiles, slug_bindings={})
        self.assertEqual(len(review.new_projects), 0)

    def test_new_project_from_github_create_event(self):
        profiles = [{"name": "timelog-extract", "match_terms": ["mbjorke/timelog-extract"]}]
        ts = datetime(2026, 6, 11, 14, 0, tzinfo=timezone.utc)
        events = [
            {
                "source": "GitHub",
                "timestamp": ts,
                "detail": "created repository in mbjorke/landsbanken-faq-helper",
                "project": "Uncategorized",
            },
            {
                "source": "GitHub",
                "timestamp": ts,
                "detail": "PR #1 merged (mbjorke/landsbanken-faq-helper)",
                "project": "Uncategorized",
            },
        ]
        review = build_mapping_review(events, profiles, slug_bindings={})
        self.assertEqual(len(review.new_projects), 1)
        self.assertEqual(review.new_projects[0].slug, "mbjorke/landsbanken-faq-helper")
        self.assertTrue(review.new_projects[0].created_at.startswith("2026-06-11"))


if __name__ == "__main__":
    unittest.main()
