"""Tests for strict config normalization and project matching."""

import unittest

from timelog_extract import UNCATEGORIZED, classify_project, normalize_profile
from core.config import apply_rule_to_project, load_projects_config_payload


class ConfigCompatibilityTests(unittest.TestCase):
    """Validates current config fields produce consistent behavior."""

    def test_normalize_profile_uses_match_terms(self):
        """Uses match_terms as canonical matching field."""
        profile = normalize_profile(
            {
                "name": "Demo",
                "match_terms": ["alpha"],
            }
        )
        self.assertIn("alpha", profile["match_terms"])
        self.assertNotIn("beta", profile["match_terms"])

    def test_normalize_profile_uses_tracked_urls(self):
        """Uses tracked_urls as canonical URL field."""
        profile = normalize_profile(
            {
                "name": "Demo",
                "tracked_urls": ["https://example.com/a"],
            }
        )
        self.assertEqual(profile["tracked_urls"], ["https://example.com/a"])

    def test_normalize_profile_supports_canonical_project_and_aliases(self):
        profile = normalize_profile(
            {
                "name": "project-core",
                "canonical_project": "ProductSuite",
                "aliases": ["project-ui", "project-cli"],
            }
        )
        self.assertEqual(profile["canonical_project"], "ProductSuite")
        self.assertIn("project-core", profile["aliases"])
        self.assertIn("ProductSuite", profile["aliases"])
        self.assertIn("project-ui", profile["aliases"])
        self.assertEqual(profile["ticket_mode"], "optional")
        self.assertEqual(profile["project_id"], "project-core")
        self.assertEqual(profile["default_client"], profile["customer"])

    def test_normalize_profile_accepts_ticket_policy_fields(self):
        profile = normalize_profile(
            {
                "name": "project-core",
                "project_id": "prod-core",
                "ticket_mode": "none",
                "default_client": "Internal Platform",
            }
        )
        self.assertEqual(profile["project_id"], "prod-core")
        self.assertEqual(profile["ticket_mode"], "none")
        self.assertEqual(profile["default_client"], "Internal Platform")

    def test_classify_project_works_with_match_terms(self):
        """Classifies text to the project whose match term appears in input."""
        profiles = [
            normalize_profile(
                {
                    "name": "ProjectA",
                    "match_terms": ["project-a", "alpha-feature"],
                }
            ),
            normalize_profile({"name": "ProjectB", "match_terms": ["project-b"]}),
        ]
        result = classify_project("Working on alpha-feature today", profiles)
        self.assertEqual(result, "ProjectA")

    def test_classify_project_returns_uncategorized_when_no_match(self):
        """Returns the UNCATEGORIZED fallback if no profile terms match."""
        profiles = [normalize_profile({"name": "ProjectA", "match_terms": ["foo"]})]
        result = classify_project("completely unrelated text", profiles)
        self.assertEqual(result, UNCATEGORIZED)

    def test_classify_project_matches_tracked_url_fragment(self):
        """URL fragments in tracked_urls participate in scoring (Chrome-style haystacks)."""
        profiles = [
            normalize_profile(
                {
                    "name": "ClientX",
                    "match_terms": ["clientx"],
                    "tracked_urls": ["app.clientx.io"],
                }
            ),
            normalize_profile({"name": "Other", "match_terms": ["other"]}),
        ]
        result = classify_project("https://app.clientx.io/checkout Other noise", profiles)
        self.assertEqual(result, "ClientX")


class TagsFieldTests(unittest.TestCase):
    """Validates the optional 'tags' field on project profiles."""

    def test_normalize_profile_tags_optional(self):
        """Missing tags field normalizes to empty list."""
        profile = normalize_profile({"name": "Demo"})
        self.assertEqual(profile["tags"], [])

    def test_normalize_profile_tags_preserved(self):
        """Tags are sorted and lowercased."""
        profile = normalize_profile({"name": "Demo", "tags": ["OPS", "tech", "Tech"]})
        self.assertEqual(profile["tags"], ["ops", "tech"])

    def test_apply_rule_preserves_tags(self):
        """apply_rule_to_project does not drop existing tags."""
        payload = {
            "projects": [
                {
                    "name": "Demo",
                    "tags": ["tech"],
                    "match_terms": ["demo"],
                    "tracked_urls": [],
                    "enabled": True,
                }
            ]
        }
        apply_rule_to_project(payload, project_name="Demo", rule_type="match_terms", rule_value="newterm")
        project = payload["projects"][0]
        self.assertEqual(project.get("tags"), ["tech"])

    def test_normalize_profile_tags_deduplicated(self):
        """Duplicate tags after lowercasing are de-duplicated."""
        profile = normalize_profile({"name": "Demo", "tags": ["Tech", "tech", "TECH", "ops", "Ops"]})
        self.assertEqual(profile["tags"], ["ops", "tech"])

    def test_normalize_profile_tags_empty_strings_excluded(self):
        """Blank/empty strings in tags are stripped and excluded."""
        profile = normalize_profile({"name": "Demo", "tags": ["  ", "", "valid"]})
        self.assertEqual(profile["tags"], ["valid"])

    def test_normalize_profile_tags_single_value_as_string(self):
        """A comma-separated string for tags is treated via as_list."""
        profile = normalize_profile({"name": "Demo", "tags": "ops,tech"})
        self.assertIn("ops", profile["tags"])
        self.assertIn("tech", profile["tags"])

    def test_normalize_profile_tags_sorted_alphabetically(self):
        """Tags are sorted alphabetically after normalizing."""
        profile = normalize_profile({"name": "Demo", "tags": ["zebra", "alpha", "middle"]})
        self.assertEqual(profile["tags"], ["alpha", "middle", "zebra"])

    def test_apply_rule_creates_project_with_empty_tags(self):
        """New project created by apply_rule_to_project has an empty tags list (no KeyError)."""
        payload = {"projects": []}
        apply_rule_to_project(payload, project_name="BrandNew", rule_type="match_terms", rule_value="stuff")
        project = payload["projects"][0]
        self.assertIn("tags", project)
        self.assertEqual(project["tags"], [])

    def test_apply_rule_preserves_multiple_tags(self):
        """Multiple existing tags are all preserved after applying a rule."""
        payload = {
            "projects": [
                {
                    "name": "Multi",
                    "tags": ["ops", "tech", "backend"],
                    "match_terms": ["multi"],
                    "tracked_urls": [],
                    "enabled": True,
                }
            ]
        }
        apply_rule_to_project(payload, project_name="Multi", rule_type="tracked_urls", rule_value="app.multi.io")
        project = payload["projects"][0]
        for tag in ["ops", "tech", "backend"]:
            self.assertIn(tag, project.get("tags", []))

    def test_load_projects_config_payload_projects_with_tags(self):
        """load_projects_config_payload preserves tags when loading from file."""
        import json
        import tempfile
        from pathlib import Path

        data = {
            "projects": [
                {"name": "Proj", "tags": ["alpha", "beta"], "match_terms": ["proj"], "tracked_urls": [], "enabled": True}
            ]
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            path = Path(f.name)
        try:
            payload = load_projects_config_payload(path)
            self.assertEqual(payload["projects"][0]["tags"], ["alpha", "beta"])
        finally:
            path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()