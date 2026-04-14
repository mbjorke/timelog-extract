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
        self.assertIn(("match_terms", "worked"), cluster_keys)


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
