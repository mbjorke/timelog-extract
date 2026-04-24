"""Tests for smart default values in `gittan projects` prompts."""

from __future__ import annotations

import unittest

from core.cli_projects import _suggest_match_terms


class ProjectsDefaultsTests(unittest.TestCase):
    def test_suggest_match_terms_prefers_full_phrase_then_tokens(self):
        terms = _suggest_match_terms("Time Log Genius", "Time Log Genius AB")
        self.assertEqual(
            terms,
            ["time log genius", "time", "log", "genius", "time log genius ab"],
        )

    def test_suggest_match_terms_deduplicates_and_skips_short_tokens(self):
        terms = _suggest_match_terms("TLG-api", "TLG")
        self.assertEqual(terms, ["tlg-api", "tlg", "api"])


if __name__ == "__main__":
    unittest.main()
