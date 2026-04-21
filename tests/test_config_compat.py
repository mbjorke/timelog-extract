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


if __name__ == "__main__":
    unittest.main()
