import unittest

from core.domain import classify_project


class DomainClassificationBugTests(unittest.TestCase):
    def test_substring_overmatching_bug(self):
        """Short terms should not match inside larger unrelated words."""
        profiles = [
            {
                "name": "Cat Project",
                "match_terms": ["cat"],
                "tracked_urls": []
            }
        ]

        # Currently these fail (they return "Cat Project" but should return "Default")
        self.assertEqual(classify_project("Reviewing the category list", profiles, "Default"), "Default")
        self.assertEqual(classify_project("Working on the catalog", profiles, "Default"), "Default")
        self.assertEqual(classify_project("certificate", profiles, "Default"), "Default")

    def test_ranking_prefers_specific_long_match_over_multiple_fragments(self):
        """A single long specific match should outrank multiple short fragments."""
        profiles = [
            {
                "name": "Short",
                "match_terms": ["sh", "or", "rt"],
                "tracked_urls": []
            },
            {
                "name": "Short Project",
                "match_terms": ["short project"],
                "tracked_urls": []
            }
        ]

        # Currently returns "Short" because it has 3 hits vs 1 hit
        self.assertEqual(classify_project("Working on short project", profiles, "Default"), "Short Project")

    def test_exact_word_match_wins_over_substring(self):
        """Exact word matches should be favored."""
        profiles = [
            {
                "name": "Log",
                "match_terms": ["log"],
                "tracked_urls": []
            },
            {
                "name": "Worklog",
                "match_terms": ["worklog"],
                "tracked_urls": []
            }
        ]
        # "worklog" should match "Worklog" project, not "Log"
        self.assertEqual(classify_project("writing a worklog entry", profiles, "Default"), "Worklog")

if __name__ == "__main__":
    unittest.main()
