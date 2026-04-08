import unittest

from timelog_extract import UNCATEGORIZED, classify_project, normalize_profile


class ConfigCompatibilityTests(unittest.TestCase):
    def test_normalize_profile_merges_new_and_legacy_terms(self):
        profile = normalize_profile(
            {
                "name": "Demo",
                "match_terms": ["alpha"],
                "keywords": ["beta"],
                "project_terms": ["gamma"],
            }
        )
        self.assertIn("alpha", profile["match_terms"])
        self.assertIn("beta", profile["match_terms"])
        self.assertIn("gamma", profile["match_terms"])

    def test_normalize_profile_merges_tracked_urls(self):
        profile = normalize_profile(
            {
                "name": "Demo",
                "tracked_urls": ["https://example.com/a"],
                "claude_urls": ["https://claude.ai/chat/abc"],
                "gemini_urls": ["https://gemini.google.com/app/xyz"],
            }
        )
        self.assertEqual(
            profile["tracked_urls"],
            [
                "https://example.com/a",
                "https://claude.ai/chat/abc",
                "https://gemini.google.com/app/xyz",
            ],
        )

    def test_classify_project_works_with_match_terms(self):
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
        profiles = [normalize_profile({"name": "ProjectA", "match_terms": ["foo"]})]
        result = classify_project("completely unrelated text", profiles)
        self.assertEqual(result, UNCATEGORIZED)


if __name__ == "__main__":
    unittest.main()
