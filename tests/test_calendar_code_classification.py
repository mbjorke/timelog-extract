"""Calendar title-code classification (Pierre persona, P3).

Pierre encodes the project as a prefix/code in the calendar event title
(e.g. ``HÅ-DAA``, ``EASE-DAA``, ``KidneySign``). These tests lock the guarantee
that such codes classify to the right project through the **real config path**
(``normalize_profile`` → ``classify_project``), including case-insensitivity and
sloppy titles, so the calendar collector's per-event classification keeps working.

See docs/product/persona-pierre-calendar-timereport.md and
docs/skills/gittan-source-collector.md.
"""

from __future__ import annotations

import unittest

from core.config import normalize_profile
from core.domain import classify_project

UNCATEGORIZED = "Uncategorized"


def _profiles():
    """Profiles built the same way real config loading builds them."""
    return [
        normalize_profile({"name": "DAA", "match_terms": ["HÅ-DAA", "EASE-DAA"]}),
        normalize_profile({"name": "EuCo", "match_terms": ["HÅ-EuCo"]}),
        normalize_profile({"name": "KidneySign", "match_terms": ["KidneySign"]}),
    ]


def _classify(title: str) -> str:
    return classify_project(title, _profiles(), UNCATEGORIZED)


class CalendarCodeClassificationTests(unittest.TestCase):
    """Scenario: Calendar title codes classify to their project."""

    def test_prefix_code_classifies(self):
        self.assertEqual(_classify("HÅ-DAA standup"), "DAA")

    def test_second_code_for_same_project(self):
        # Both codes map to one project; either should resolve to it.
        self.assertEqual(_classify("EASE-DAA review"), "DAA")

    def test_distinct_codes_are_disambiguated(self):
        self.assertEqual(_classify("HÅ-EuCo planning"), "EuCo")

    def test_word_code_classifies(self):
        self.assertEqual(_classify("KidneySign proteomicsdata"), "KidneySign")

    def test_classification_is_case_insensitive(self):
        """Scenario: A user-entered uppercase code still matches."""
        # normalize_profile lowercases match_terms; classify lowercases the title.
        self.assertEqual(_classify("hå-daa lowercase title"), "DAA")
        self.assertEqual(_classify("HÅ-DAA UPPER TITLE"), "DAA")

    def test_code_anywhere_in_title(self):
        """Sloppy titles: the code need not be a prefix."""
        self.assertEqual(_classify("Quick sync about HÅ-DAA before lunch"), "DAA")

    def test_unknown_title_falls_back(self):
        """Scenario: An unrecognized title is not force-fit to a project."""
        self.assertEqual(_classify("Dentist appointment"), UNCATEGORIZED)

    def test_user_configured_uppercase_code_is_normalized(self):
        """The config path stores codes lowercased, so capitalized config works."""
        profile = normalize_profile({"name": "DAA", "match_terms": ["HÅ-DAA"]})
        self.assertIn("hå-daa", profile["match_terms"])
        self.assertEqual(
            classify_project("HÅ-DAA standup", [profile], UNCATEGORIZED), "DAA"
        )


if __name__ == "__main__":
    unittest.main()
