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

    def test_tracked_url_fragments_respect_word_boundaries(self):
        """Tracked URL fragments should not over-match mid-word."""
        profiles = [
            {
                "name": "Supabase",
                "match_terms": [],
                "tracked_urls": ["supabase"]
            }
        ]
        # "supabase" as a word should match
        self.assertEqual(classify_project("https://supabase.com/dashboard", profiles, "Default"), "Supabase")
        # "supabase" inside another word should NOT match
        self.assertEqual(classify_project("Using the insupabase-tool", profiles, "Default"), "Default")

    def test_swedish_word_boundaries(self):
        """Swedish terms with non-ASCII characters should still respect word boundaries."""
        profiles = [
            {
                "name": "ÅSS",
                "match_terms": ["åss"],
                "tracked_urls": []
            }
        ]
        self.assertEqual(classify_project("Jobbar med ÅSS idag", profiles, "Default"), "ÅSS")
        self.assertEqual(classify_project("Måsar i blåsväder", profiles, "Default"), "Default")

if __name__ == "__main__":
    unittest.main()
