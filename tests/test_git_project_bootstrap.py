"""Tests for git-aware bootstrap hints and match_terms coverage checks."""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from core.git_project_bootstrap import assess_match_terms_coverage, discover_git_project_hints


class GitProjectBootstrapTests(unittest.TestCase):
    def _init_repo(self, tmp: str, remote_url: str = "https://github.com/example/acme-tools.git") -> Path:
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


if __name__ == "__main__":
    unittest.main()
