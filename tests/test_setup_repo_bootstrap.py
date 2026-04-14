"""Tests for multi-repo bootstrap discovery, parsing, and merge safety."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from rich.console import Console

from core.git_project_bootstrap import (
    RepoProjectSeed,
    build_repo_project_seed,
    discover_local_git_repos,
    merge_repo_project_seeds,
    parse_github_origin,
)
from core.setup_projects_config_bootstrap import ensure_projects_config


class SetupRepoBootstrapTests(unittest.TestCase):
    def test_parse_github_origin_supports_https_and_ssh(self):
        self.assertEqual(
            parse_github_origin("https://github.com/example/acme-tools.git"),
            ("example", "acme-tools"),
        )
        self.assertEqual(
            parse_github_origin("git@github.com:example/acme-tools.git"),
            ("example", "acme-tools"),
        )
        self.assertIsNone(parse_github_origin("https://gitlab.com/example/acme-tools.git"))

    def test_discover_local_git_repos_stays_shallow(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            direct = root / "direct-repo"
            direct.mkdir()
            (direct / ".git").mkdir()
            nested = root / "group" / "nested-repo"
            nested.mkdir(parents=True)
            (nested / ".git").mkdir()
            too_deep = root / "a" / "b" / "c" / "too-deep"
            too_deep.mkdir(parents=True)
            (too_deep / ".git").mkdir()

            repos = discover_local_git_repos(root)
            self.assertIn(direct.resolve(), repos)
            self.assertIn(nested.resolve(), repos)
            self.assertNotIn(too_deep.resolve(), repos)

    def test_discover_local_git_repos_filters_noise_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            valid_repo = root / "work" / "client-repo"
            valid_repo.mkdir(parents=True)
            (valid_repo / ".git").mkdir()
            noise_vendor = root / "vendor-tools" / "vendor-repo"
            noise_vendor.mkdir(parents=True)
            (noise_vendor / ".git").mkdir()
            noise_tmp = root / "scratch-tmp" / "tmp-repo"
            noise_tmp.mkdir(parents=True)
            (noise_tmp / ".git").mkdir()
            hidden_noise = root / ".claude" / "repo"
            hidden_noise.mkdir(parents=True)
            (hidden_noise / ".git").mkdir()

            repos = discover_local_git_repos(root, max_depth=3)
            self.assertIn(valid_repo.resolve(), repos)
            self.assertNotIn(noise_vendor.resolve(), repos)
            self.assertNotIn(noise_tmp.resolve(), repos)
            self.assertNotIn(hidden_noise.resolve(), repos)

    def test_discover_local_git_repos_avoids_nested_duplicates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            parent_repo = root / "mono"
            (parent_repo / ".git").mkdir(parents=True)
            nested_repo = parent_repo / "services" / "api"
            (nested_repo / ".git").mkdir(parents=True)

            repos = discover_local_git_repos(root, max_depth=4)
            self.assertIn(parent_repo.resolve(), repos)
            self.assertNotIn(nested_repo.resolve(), repos)

    def test_merge_repo_project_seeds_updates_terms_without_overwrite(self):
        payload = {
            "worklog": "TIMELOG.md",
            "projects": [
                {
                    "name": "acme-tools",
                    "customer": "Existing Customer",
                    "match_terms": ["legacy-term"],
                    "tracked_urls": ["https://example.com"],
                }
            ],
        }
        seed = RepoProjectSeed(
            repo_path=Path("/tmp/acme-tools"),
            name="acme-tools",
            customer="example",
            match_terms=["acme-tools", "example/acme-tools"],
            origin_url="https://github.com/example/acme-tools.git",
        )
        merged, summary = merge_repo_project_seeds(payload, [seed], root=Path("/tmp"))
        self.assertEqual(summary.added, 0)
        self.assertEqual(summary.updated, 1)
        project = merged["projects"][0]
        self.assertEqual(project["customer"], "Existing Customer")
        self.assertEqual(project["tracked_urls"], ["https://example.com"])
        self.assertIn("legacy-term", project["match_terms"])
        self.assertIn("example/acme-tools", project["match_terms"])

    def test_fallback_creates_single_profile_when_no_github_repos_found(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = root / "timelog_projects.json"
            result = ensure_projects_config(
                console=Console(record=True),
                yes=True,
                dry_run=False,
                bootstrap_root=str(root),
                config_path=cfg,
                timestamped_backup_path_fn=lambda path: path.with_suffix(".bak"),
                looks_like_projects_config_fn=lambda payload: isinstance(payload, dict) and isinstance(payload.get("projects"), list),
            )
            self.assertEqual(result.status, "PASS")
            self.assertIn("fallback profile used", result.notes)
            payload = json.loads(cfg.read_text(encoding="utf-8"))
            self.assertEqual(len(payload["projects"]), 1)
            self.assertEqual(payload["projects"][0]["name"], "timelog-extract")
            self.assertTrue(payload["projects"][0]["match_terms"])


if __name__ == "__main__":
    unittest.main()
