from __future__ import annotations

import unittest

from core.triage_code_repos import build_code_repo_candidates, code_repo_candidate, github_repo_slug


class TriageCodeRepoTests(unittest.TestCase):
    def test_extracts_provider_neutral_repo_candidates(self):
        self.assertEqual(
            code_repo_candidate("https://github.com/Octo-Org/Service-API/pulls/1"),
            {"provider": "github", "value": "github.com/octo-org/service-api"},
        )

    def test_github_extractor_requires_repo_evidence(self):
        cases = [
            (
                "https://github.com/octo-org/service-api/pulls/1",
                "",
                "github.com/octo-org/service-api",
            ),
            (
                "https://github.com/octo-org/service-api/tree/main",
                "",
                "github.com/octo-org/service-api",
            ),
            (
                "https://github.com/octo-org/service-api",
                "GitHub - octo-org/service-api: API service",
                "github.com/octo-org/service-api",
            ),
        ]
        for url, title, expected in cases:
            with self.subTest(url=url):
                self.assertEqual(github_repo_slug(url, title=title), expected)

    def test_ignores_paths_without_repo_evidence(self):
        cases = [
            ("https://github.com/octo-org/service-api", ""),
            ("https://github.com/octo-org/service-api", "Service API docs"),
            ("https://github.com/search?q=service-api", ""),
            ("https://github.com/users/octo-org", ""),
            ("https://github.com/auth/github_editor", ""),
            ("https://github.com/contact/report-content", ""),
            ("https://github.com/octo-org", ""),
            ("https://github.com/octo-org/service-api/unknown/tool", ""),
        ]
        for url, title in cases:
            with self.subTest(url=url):
                self.assertEqual(github_repo_slug(url, title=title), "")

    def test_build_candidates_counts_repo_visits(self):
        rows = [
            (1, "https://github.com/octo-org/service-api", "GitHub - octo-org/service-api"),
            (2, "https://github.com/Octo-Org/Service-API/pulls", "Pull requests"),
            (3, "https://github.com/octo-org/service-api", "Generic tab title"),
            (4, "https://github.com/customer-co/billing-portal/tree/main", "Repository tree"),
        ]
        candidates = build_code_repo_candidates(rows)
        self.assertEqual(
            candidates[0],
            {"provider": "github", "value": "github.com/octo-org/service-api", "visits": 2},
        )
        self.assertEqual(
            candidates[1],
            {"provider": "github", "value": "github.com/customer-co/billing-portal", "visits": 1},
        )


if __name__ == "__main__":
    unittest.main()
