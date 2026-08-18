"""Calendar title-code classification (Robin persona, P3).

Robin encodes the project as a prefix/code in the calendar event title
(e.g. ``TÖ-ABC``, ``WIDE-ABC``, ``DataForge``). These tests lock the guarantee
that such codes classify to the right project through the **real config path**
(``normalize_profile`` → ``classify_project``), including case-insensitivity and
sloppy titles, so the calendar collector's per-event classification keeps working.

See docs/product/persona-robin-calendar-timereport.md and
docs/skills/gittan-source-collector.md.
"""

from __future__ import annotations

import unittest

from core.config import normalize_profile
from core.domain import classify_project

UNCATEGORIZED = "Uncategorized"


# Profiles built the same way real config loading builds them.
_PROFILES = [
    normalize_profile({"name": "ABC", "match_terms": ["TÖ-ABC", "WIDE-ABC"]}),
    normalize_profile({"name": "MiCo", "match_terms": ["TÖ-MiCo"]}),
    normalize_profile({"name": "DataForge", "match_terms": ["DataForge"]}),
]


def _classify(title: str) -> str:
    return classify_project(title, _PROFILES, UNCATEGORIZED)


class CalendarCodeClassificationTests(unittest.TestCase):
    """Scenario: Calendar title codes classify to their project."""

    def test_prefix_code_classifies(self):
        self.assertEqual(_classify("TÖ-ABC standup"), "ABC")

    def test_second_code_for_same_project(self):
        # Both codes map to one project; either should resolve to it.
        self.assertEqual(_classify("WIDE-ABC review"), "ABC")

    def test_distinct_codes_are_disambiguated(self):
        self.assertEqual(_classify("TÖ-MiCo planning"), "MiCo")

    def test_word_code_classifies(self):
        # "proteomicsdata" is a deliberately sloppy real-world title (no space);
        # classification must still find the "DataForge" code.
        self.assertEqual(_classify("DataForge proteomicsdata"), "DataForge")

    def test_classification_is_case_insensitive(self):
        """Scenario: A user-entered uppercase code still matches."""
        # normalize_profile lowercases match_terms; classify lowercases the title.
        self.assertEqual(_classify("tö-abc lowercase title"), "ABC")
        self.assertEqual(_classify("TÖ-ABC UPPER TITLE"), "ABC")

    def test_code_anywhere_in_title(self):
        """Sloppy titles: the code need not be a prefix."""
        self.assertEqual(_classify("Quick sync about TÖ-ABC before lunch"), "ABC")

    def test_code_embedded_mid_word_is_still_found(self):
        """The 'anywhere' guarantee is true substring match, not word-boundary."""
        self.assertEqual(_classify("meetingTÖ-ABCreview"), "ABC")

    def test_empty_title_falls_back(self):
        self.assertEqual(_classify(""), UNCATEGORIZED)

    def test_whitespace_only_title_falls_back(self):
        self.assertEqual(_classify("   "), UNCATEGORIZED)

    def test_unknown_title_falls_back(self):
        """Scenario: An unrecognized title is not force-fit to a project."""
        self.assertEqual(_classify("Dentist appointment"), UNCATEGORIZED)

    def test_competing_codes_pick_strongest_match(self):
        """Scenario: A title with codes for two projects resolves deterministically.

        When a title carries codes for more than one project, the project with
        more matched terms wins (per classify_project's ranking), rather than
        being left Uncategorized or chosen at random.
        """
        # ABC matches two of its terms here (WIDE-ABC + TÖ-ABC) vs MiCo's one.
        self.assertEqual(
            _classify("WIDE-ABC and TÖ-MiCo and TÖ-ABC joint sync"), "ABC"
        )

    def test_user_configured_uppercase_code_is_normalized(self):
        """The config path stores codes lowercased, so capitalized config works."""
        profile = normalize_profile({"name": "ABC", "match_terms": ["TÖ-ABC"]})
        self.assertIn("tö-abc", profile["match_terms"])
        self.assertEqual(
            classify_project("TÖ-ABC standup", [profile], UNCATEGORIZED), "ABC"
        )


if __name__ == "__main__":
    unittest.main()
