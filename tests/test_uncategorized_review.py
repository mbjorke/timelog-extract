"""Tests for uncategorized guided review clustering and config writes."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from core.config import apply_rule_to_project, load_profiles, save_projects_config_payload
from core.domain import classify_project
from core.uncategorized_review import build_uncategorized_clusters


class UncategorizedReviewClusterTests(unittest.TestCase):
    def test_build_clusters_groups_by_domain_and_term(self):
        events = [
            {"source": "Chrome", "detail": "Visited https://github.com/acme/repo pull request", "project": "Uncategorized"},
            {"source": "Chrome", "detail": "Visited https://github.com/acme/repo issues", "project": "Uncategorized"},
            {"source": "Cursor", "detail": "Worked on acme-feature implementation", "project": "Uncategorized"},
        ]

        clusters = build_uncategorized_clusters(events, max_clusters=10, samples_per_cluster=2)
        cluster_keys = {(cluster.rule_type, cluster.rule_value) for cluster in clusters}
        self.assertIn(("tracked_urls", "github.com"), cluster_keys)
        # "acme-feature" is preferred over the generic verb "worked" because
        # hyphenated tokens make more specific match_terms suggestions.
        self.assertIn(("match_terms", "acme-feature"), cluster_keys)

    def test_build_clusters_excludes_marketplace_and_extension_metadata_noise(self):
        events = [
            {
                "source": "Cursor",
                "detail": "loadFromMarketplaceSource id=5d300c892a43513c4c5d3ecb534bf9c78b6d6389",
                "project": "Uncategorized",
            },
            {
                "source": "Cursor",
                "detail": "Updated extensions.json metadata for install state",
                "project": "Uncategorized",
            },
            {
                "source": "Cursor",
                "detail": "Implemented acme-feature review flow",
                "project": "Uncategorized",
            },
        ]

        clusters = build_uncategorized_clusters(events, max_clusters=10, samples_per_cluster=2)
        cluster_keys = {(cluster.rule_type, cluster.rule_value) for cluster in clusters}
        self.assertEqual(cluster_keys, {("match_terms", "acme-feature")})

    def test_build_clusters_excludes_extension_lifecycle_lines_and_tokens(self):
        events = [
            {
                "source": "Cursor",
                "detail": "Started downloading extension: ms-azuretools.vscode-containers",
                "project": "Uncategorized",
            },
            {
                "source": "Cursor",
                "detail": "Extracted extension to file:///Users/example/.cursor/extensions/ms-azuretools.vscode-containers-2.4.4-universal",
                "project": "Uncategorized",
            },
            {
                "source": "Cursor",
                "detail": "Renamed to /Users/example/.cursor/extensions/ms-azuretools.vscode-containers-2.4.4-universal",
                "project": "Uncategorized",
            },
            {
                "source": "Cursor",
                "detail": "ms-azuretools.vscode-containers-2.4.4-universal",
                "project": "Uncategorized",
            },
            {
                "source": "Cursor",
                "detail": "Implemented acme-feature review flow",
                "project": "Uncategorized",
            },
        ]

        clusters = build_uncategorized_clusters(events, max_clusters=10, samples_per_cluster=2)
        cluster_keys = {(cluster.rule_type, cluster.rule_value) for cluster in clusters}
        self.assertNotIn(("match_terms", "ms-azuretools.vscode-containers"), cluster_keys)
        self.assertNotIn(("match_terms", "ms-azuretools.vscode-containers-2.4.4-universal"), cluster_keys)
        self.assertEqual(cluster_keys, {("match_terms", "acme-feature")})

    def test_build_clusters_excludes_date_only_match_term_keys(self):
        events = [
            {"source": "Cursor", "detail": "2026-05-05", "project": "Uncategorized"},
            {"source": "Cursor", "detail": "Worked on acme-feature implementation", "project": "Uncategorized"},
        ]

        clusters = build_uncategorized_clusters(events, max_clusters=10, samples_per_cluster=2)
        cluster_keys = {(cluster.rule_type, cluster.rule_value) for cluster in clusters}
        self.assertNotIn(("match_terms", "2026-05-05"), cluster_keys)
        self.assertIn(("match_terms", "acme-feature"), cluster_keys)

    def test_build_clusters_excludes_iso_like_datetime_match_term_keys(self):
        events = [
            {"source": "Cursor", "detail": "2026-05-05t12", "project": "Uncategorized"},
            {"source": "Cursor", "detail": "2026-05-05T12:30", "project": "Uncategorized"},
            {"source": "Cursor", "detail": "Worked on acme-feature implementation", "project": "Uncategorized"},
        ]

        clusters = build_uncategorized_clusters(events, max_clusters=10, samples_per_cluster=2)
        cluster_keys = {(cluster.rule_type, cluster.rule_value) for cluster in clusters}
        self.assertNotIn(("match_terms", "2026-05-05t12"), cluster_keys)
        self.assertNotIn(("match_terms", "2026-05-05t12:30"), cluster_keys)
        self.assertIn(("match_terms", "acme-feature"), cluster_keys)

    def test_build_clusters_excludes_config_path_metadata_lines(self):
        events = [
            {
                "source": "Cursor",
                "detail": "Claude user config path: /Users/example/.claude/settings.json",
                "project": "Uncategorized",
            },
            {
                "source": "Cursor",
                "detail": "User config path: /Users/example/.cursor/hooks.json",
                "project": "Uncategorized",
            },
            {
                "source": "Cursor",
                "detail": "Implemented acme-feature review flow",
                "project": "Uncategorized",
            },
        ]

        clusters = build_uncategorized_clusters(events, max_clusters=10, samples_per_cluster=2)
        cluster_keys = {(cluster.rule_type, cluster.rule_value) for cluster in clusters}
        self.assertNotIn(("match_terms", "settings.json"), cluster_keys)
        self.assertNotIn(("match_terms", "hooks.json"), cluster_keys)
        self.assertEqual(cluster_keys, {("match_terms", "acme-feature")})

    def test_build_clusters_excludes_worktree_and_file_watcher_noise(self):
        events = [
            {
                "source": "Cursor",
                "detail": (
                    "wt-design-lint-subset — 2026-05-18 11:26:51.385  [Model] Opened repository: "
                    "/Users/example/Workspace/project"
                ),
                "project": "Uncategorized",
            },
            {
                "source": "Cursor",
                "detail": (
                    "wt-design-lint-subset) — 2026-05-18 11:29:30.868  [File Watcher] Events were "
                    "dropped by the FSEvents client."
                ),
                "project": "Uncategorized",
            },
            {
                "source": "Cursor",
                "detail": "Implemented acme-feature review flow",
                "project": "Uncategorized",
            },
        ]

        clusters = build_uncategorized_clusters(events, max_clusters=10, samples_per_cluster=2)
        cluster_keys = {(cluster.rule_type, cluster.rule_value) for cluster in clusters}
        self.assertNotIn(("match_terms", "wt-design-lint-subset"), cluster_keys)
        self.assertIn(("match_terms", "acme-feature"), cluster_keys)

    def test_build_clusters_excludes_skills_cursor_sync_manifest_noise(self):
        events = [
            {
                "source": "Cursor",
                "detail": (
                    "skills-cursor — 2026-05-06 05:58:54.188  Failed to persist sync manifest "
                    '{"skillDir":"/Users/example/.cursor/skills-cursor"}'
                ),
                "project": "Uncategorized",
            },
            {
                "source": "Cursor",
                "detail": "Worked on acme-feature implementation",
                "project": "Uncategorized",
            },
        ]

        clusters = build_uncategorized_clusters(events, max_clusters=10, samples_per_cluster=2)
        cluster_keys = {(cluster.rule_type, cluster.rule_value) for cluster in clusters}
        self.assertNotIn(("match_terms", "skills-cursor"), cluster_keys)
        self.assertIn(("match_terms", "acme-feature"), cluster_keys)

    def test_build_clusters_excludes_lovable_storage_signal_only_host(self):
        events = [
            {
                "source": "Lovable Desktop",
                "detail": "Browser signal tracked_urls='lovable.dev'",
                "project": "Uncategorized",
            },
            {
                "source": "Chrome",
                "detail": "Visited https://github.com/acme/repo issues",
                "project": "Uncategorized",
            },
        ]

        clusters = build_uncategorized_clusters(events, max_clusters=10, samples_per_cluster=2)
        cluster_keys = {(cluster.rule_type, cluster.rule_value) for cluster in clusters}
        self.assertNotIn(("tracked_urls", "lovable.dev"), cluster_keys)
        self.assertIn(("tracked_urls", "github.com"), cluster_keys)


class UncategorizedReviewConfigTests(unittest.TestCase):
    def test_apply_rule_to_project_writes_without_duplicates(self):
        payload = {"projects": [{"name": "alpha", "match_terms": ["alpha"], "tracked_urls": []}]}

        apply_rule_to_project(
            payload,
            project_name="alpha",
            rule_type="match_terms",
            rule_value="acme-feature",
        )
        apply_rule_to_project(
            payload,
            project_name="alpha",
            rule_type="match_terms",
            rule_value="acme-feature",
        )
        project = payload["projects"][0]
        self.assertEqual(project["name"], "alpha")
        self.assertIn("acme-feature", project["match_terms"])
        self.assertEqual(project["match_terms"].count("acme-feature"), 1)

    def test_apply_rule_can_create_project_and_improve_classification(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg_path = Path(tmp) / "timelog_projects.json"
            payload = {"projects": []}
            apply_rule_to_project(
                payload,
                project_name="acme-tools",
                rule_type="match_terms",
                rule_value="acme-tools",
            )
            save_projects_config_payload(cfg_path, payload)

            profiles, loaded_path, _workspace = load_profiles(
                str(cfg_path),
                type("Args", (), {"project": "default-project", "keywords": "", "email": ""})(),
            )
            self.assertEqual(loaded_path, cfg_path)

            classification = classify_project(
                "Implemented acme-tools parser",
                profiles,
                "Uncategorized",
            )
            self.assertEqual(classification, "acme-tools")
            loaded_payload = json.loads(cfg_path.read_text(encoding="utf-8"))
            self.assertEqual(loaded_payload["projects"][0]["name"], "acme-tools")


if __name__ == "__main__":
    unittest.main()
