"""Regression checks for landing-page command language."""

from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
LANDING_PAGE = REPO_ROOT / "gittan.html"


class LandingCommandLanguageTests(unittest.TestCase):
    def test_how_section_uses_canonical_cli_commands(self):
        content = LANDING_PAGE.read_text(encoding="utf-8")

        self.assertIn("gittan doctor", content)
        self.assertIn("gittan report --today --source-summary", content)
        self.assertIn("gittan triage --json", content)

    def test_landing_page_does_not_market_unimplemented_capture_flow(self):
        content = LANDING_PAGE.read_text(encoding="utf-8")

        self.assertNotIn("gittan capture --repo my-project", content)
        self.assertNotIn("gittan review 1 --project", content)


if __name__ == "__main__":
    unittest.main()
