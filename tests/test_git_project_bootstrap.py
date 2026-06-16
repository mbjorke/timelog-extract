"""Tests for git-aware bootstrap hints and match_terms coverage checks."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from core.git_project_bootstrap import (
    assess_config_git_coverage,
    assess_match_terms_coverage,
    collect_local_github_slugs_from_workspace,
    discover_git_project_hints,
)


class GitProjectBootstrapTests(unittest.TestCase):
    def _init_repo(self, tmp: str, remote_url: str = "https://github.com/example/acme-tools.git") -> Path:
        if not shutil.which("git"):
            self.skipTest("git not available in PATH")
        repo = Path(tmp)
        subprocess.run(["git", "init"], cwd=tmp, check=True, capture_output=True, text=True)
        subprocess.run(["git", "remote", "add", "origin", remote_url], cwd=tmp, check=True, capture_output=True, text=True)
        return repo

    def test_discover_git_project_hints_uses_remote_slug(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = self._init_repo(tmp)
            hints = discover_git_project_hints(repo)
            self.assertIsNotNone(hints)
            assert hints is not None
            self.assertEqual(hints.project_name, "acme-tools")
            self.assertEqual(hints.customer, "example")
            self.assertIn("acme-tools", hints.match_terms)
            self.assertIn("example/acme-tools", hints.match_terms)

    def test_match_terms_coverage_warns_when_repo_cues_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = self._init_repo(tmp)
            coverage = assess_match_terms_coverage(
                repo,
                [{"name": "Internal", "match_terms": ["other-project"]}],
            )
            self.assertEqual(coverage.status, "warn")
            self.assertIn("not covered", coverage.detail)
            self.assertIn("acme-tools", coverage.suggested_terms)

    def test_match_terms_coverage_passes_when_repo_name_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = self._init_repo(tmp)
            coverage = assess_match_terms_coverage(
                repo,
                [{"name": "acme-tools", "match_terms": ["billing"]}],
            )
            self.assertEqual(coverage.status, "ok")
            self.assertIn("acme-tools", coverage.detail)

    def test_config_git_coverage_is_cwd_independent(self):
        profiles = [
            {
                "name": "timelog-extract",
                "match_terms": ["mbjorke/timelog-extract", "timelog-extract"],
            },
            {
                "name": "remote-only",
                "match_terms": ["mbjorke/landsbanken-faq-helper"],
            },
        ]
        with mock.patch(
            "core.git_project_bootstrap.collect_local_github_slugs_from_workspace",
            return_value={"mbjorke/timelog-extract"},
        ):
            coverage = assess_config_git_coverage(profiles)
        self.assertEqual(coverage.status, "warn")
        self.assertIn("1/2", coverage.detail)
        self.assertIn("mbjorke/landsbanken-faq-helper", coverage.suggested_terms)

    def test_config_git_coverage_all_cloned_is_ok(self):
        profiles = [{"name": "demo", "match_terms": ["mbjorke/demo"]}]
        with mock.patch(
            "core.git_project_bootstrap.collect_local_github_slugs_from_workspace",
            return_value={"mbjorke/demo"},
        ):
            coverage = assess_config_git_coverage(profiles)
        self.assertEqual(coverage.status, "ok")
        self.assertIn("All 1 configured", coverage.detail)

    def test_collect_local_github_slugs_includes_home_top_level_clone(self):
        with tempfile.TemporaryDirectory() as home:
            home_path = Path(home)
            workspace = home_path / "Workspace"
            workspace.mkdir()
            repo = home_path / "ax-finans"
            repo.mkdir()
            self._init_repo(str(repo), "https://github.com/ax-finans/financing-portal.git")
            with mock.patch("core.git_project_bootstrap.Path.home", return_value=home_path):
                with mock.patch(
                    "core.git_project_bootstrap._workspace_scan_roots",
                    return_value=[workspace],
                ):
                    slugs = collect_local_github_slugs_from_workspace()
            self.assertIn("ax-finans/financing-portal", slugs)


if __name__ == "__main__":
    unittest.main()