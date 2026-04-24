"""Tests for prompt hint wording in `gittan projects`."""

from __future__ import annotations

import unittest

from core.cli_projects import _match_terms_prompt_message


class ProjectsPromptHintsTests(unittest.TestCase):
    def test_prompt_hint_mentions_enter_when_defaults_exist(self):
        msg = _match_terms_prompt_message(["alpha", "beta"])
        self.assertIn("press Enter", msg)
        self.assertIn("keep current/suggested terms", msg)

    def test_prompt_hint_is_plain_when_no_defaults(self):
        msg = _match_terms_prompt_message([])
        self.assertEqual(msg, "Match Terms (comma separated):")


if __name__ == "__main__":
    unittest.main()
