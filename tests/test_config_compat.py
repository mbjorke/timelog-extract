"""Tests for strict config normalization and project matching."""

import unittest

from timelog_extract import UNCATEGORIZED, classify_project, normalize_profile


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


if __name__ == "__main__":
    unittest.main()
