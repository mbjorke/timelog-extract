"""Tests for map project suggestion helpers."""

from __future__ import annotations

import unittest

from core.map_project_suggest import (
    suggest_project_for_anchor,
    suggest_project_for_duplicate_change,
    suggest_project_for_map_slug,
    suggest_project_for_new_repo,
)
from core.mapping_review import ProjectChangeProposal, RepoDuplicateLine, slug_to_github_url


class MapProjectSuggestTests(unittest.TestCase):
    def _profiles(self):
        return [
            {
                "name": "project-alpha",
                "customer": "customer-a.example",
                "match_terms": ["owner-a/project-alpha"],
            },
            {
                "name": "project-alpha-dev",
                "customer": "customer-a.example",
                "match_terms": ["owner-a/project-alpha-dev", "project-alpha-dev"],
            },
            {
                "name": "customer-Y-faq",
                "customer": "Customer Y",
                "match_terms": ["customer-Y-faq", "owner-a/customer-Y-faq"],
            },
        ]

    def test_map_slug_prefers_dev_profile_for_hash_fork(self):
        match = suggest_project_for_map_slug(
            "owner-a/project-alpha-dev-31e799cf",
            self._profiles(),
        )
        self.assertEqual(match, "project-alpha-dev")

    def test_map_slug_parent_when_not_dev_line(self):
        match = suggest_project_for_map_slug("owner-a/project-alpha", self._profiles())
        self.assertEqual(match, "project-alpha")

    def test_new_repo_suggests_existing_dev_profile(self):
        match = suggest_project_for_new_repo(
            "owner-a/project-alpha-dev-31e799cf",
            "project-alpha-dev-31e799cf",
            self._profiles(),
        )
        self.assertEqual(match, "project-alpha-dev")

    def test_anchor_fuzzy_suggests_faq_project(self):
        match = suggest_project_for_anchor(
            {"kind": "label", "value": "customer-Y-faq-helper", "hits": 12},
            self._profiles(),
        )
        self.assertEqual(match, "customer-Y-faq")

    def test_anchor_exact_dir_leaf(self):
        match = suggest_project_for_anchor(
            {"kind": "dir", "value": "project-alpha-dev", "hits": 40},
            self._profiles(),
        )
        self.assertEqual(match, "project-alpha-dev")

    def test_duplicate_change_suggests_dev_profile(self):
        change = ProjectChangeProposal(
            target_project="project-alpha",
            customer="customer-a.example",
            canonical_slug="owner-a/project-alpha",
            canonical_remote_url=slug_to_github_url("owner-a/project-alpha"),
            canonical_local_path="~/project-alpha",
            canonical_activity_dot="[green]●[/green]",
            lines=[
                RepoDuplicateLine(
                    slug="owner-a/project-alpha-dev-31e799cf",
                    remote_url=slug_to_github_url("owner-a/project-alpha-dev-31e799cf"),
                    local_path="~/project-alpha-dev",
                    activity_dot="[green]●[/green]",
                    status="Primary — remote activity in window",
                ),
            ],
        )
        match = suggest_project_for_duplicate_change(change, self._profiles())
        self.assertEqual(match, "project-alpha-dev")


if __name__ == "__main__":
    unittest.main()
