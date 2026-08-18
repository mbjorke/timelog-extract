from __future__ import annotations

import unittest

from core.calendar_suggest import (
    extract_codes,
    suggest_projects_from_titles,
)


class ExtractCodesTests(unittest.TestCase):
    def test_hyphenated_caps_code(self):
        self.assertEqual(extract_codes("TÖ-ABC standup"), ["TÖ-ABC"])

    def test_camelcase_code(self):
        self.assertEqual(extract_codes("DataForge proteomics data"), ["DataForge"])

    def test_allcaps_code(self):
        self.assertEqual(extract_codes("ACME prodsättning"), ["ACME"])

    def test_dotted_domain_code(self):
        self.assertEqual(extract_codes("examplelab.test sync"), ["examplelab.test"])

    def test_leading_generic_word_is_ignored(self):
        # Real example: "Avbruten: ACME - ..." — the Swedish word must not be a code.
        codes = extract_codes("Avbruten: ACME prodsättning")
        self.assertIn("ACME", codes)
        self.assertNotIn("Avbruten", codes)

    def test_plain_words_yield_nothing(self):
        self.assertEqual(extract_codes("lunch with the team"), [])

    def test_short_uppercase_is_not_a_code(self):
        # Avoid noise like "OK", "PR".
        self.assertEqual(extract_codes("OK PR done"), [])

    def test_punctuation_is_stripped(self):
        self.assertEqual(extract_codes("TÖ-ABC: planning"), ["TÖ-ABC"])


class SuggestProjectsTests(unittest.TestCase):
    def _titles(self):
        return [
            "TÖ-ABC standup",
            "TÖ-ABC deep work",
            "WIDE-ABC review",
            "DataForge proteomics data",
            "lunch",
            "Dentist appointment",
        ]

    def test_ranks_by_frequency(self):
        out = suggest_projects_from_titles(self._titles())
        codes = [s.code for s in out]
        # TÖ-ABC appears twice → first.
        self.assertEqual(codes[0], "TÖ-ABC")
        self.assertEqual(out[0].count, 2)
        self.assertIn("WIDE-ABC", codes)
        self.assertIn("DataForge", codes)

    def test_excludes_already_covered_codes(self):
        existing = [{"name": "ABC", "match_terms": ["tö-abc", "wide-abc"]}]
        out = suggest_projects_from_titles(self._titles(), existing)
        codes = [s.code for s in out]
        self.assertNotIn("TÖ-ABC", codes)   # covered (case-insensitive)
        self.assertNotIn("WIDE-ABC", codes)
        self.assertIn("DataForge", codes)  # still new

    def test_min_count_filter(self):
        out = suggest_projects_from_titles(self._titles(), min_count=2)
        self.assertEqual([s.code for s in out], ["TÖ-ABC"])

    def test_suggestion_profile_shape(self):
        out = suggest_projects_from_titles(["DataForge x"])
        self.assertEqual(out[0].as_profile(), {"name": "DataForge", "match_terms": ["DataForge"]})

    def test_examples_captured_and_capped(self):
        titles = [f"TÖ-ABC item {i}" for i in range(10)]
        out = suggest_projects_from_titles(titles, max_examples=3)
        self.assertEqual(out[0].count, 10)
        self.assertEqual(len(out[0].examples), 3)

    def test_deterministic_order_for_ties(self):
        out = suggest_projects_from_titles(["ZEBRA a", "ACME b"])
        # Both count 1 → alphabetical by lowercased code.
        self.assertEqual([s.code for s in out], ["ACME", "ZEBRA"])

    def test_plain_capitalized_word_is_not_suggested(self):
        # Known v1 limitation: a bare capitalized project name (e.g. "Strike",
        # "Bimelix") is indistinguishable from an ordinary word, so it is not
        # proposed. Distinctive codes (hyphen/CamelCase/ALLCAPS/dotted) are.
        out = suggest_projects_from_titles(["Strike planning", "Bimelix sync"])
        self.assertEqual(out, [])

    def test_empty_input(self):
        self.assertEqual(suggest_projects_from_titles([]), [])


if __name__ == "__main__":
    unittest.main()
