from __future__ import annotations

import re
import unittest

from typer.testing import CliRunner

from core.cli import app

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _plain_cli_output(text: str) -> str:
    return _ANSI_RE.sub("", text)


class CliHelpTextTests(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()

    def test_top_level_help_uses_local_first_evidence_language(self):
        result = self.runner.invoke(app, ["--help"])
        self.assertEqual(result.exit_code, 0, msg=result.output)
        self.assertIn("Local-first CLI for reviewable project-hour evidence", result.output)

    def test_review_help_describes_url_mapping_default(self):
        result = self.runner.invoke(app, ["review", "--help"])
        self.assertEqual(result.exit_code, 0, msg=result.output)
        plain = _plain_cli_output(result.output)
        self.assertIn("Map URL hosts to projects", plain)
        self.assertIn("--uncategorized", plain)

    def test_top_level_command_descriptions_are_first_run_oriented(self):
        result = self.runner.invoke(app, ["--help"])
        self.assertEqual(result.exit_code, 0, msg=result.output)
        self.assertIn("Build detailed local evidence reports", result.output)
        self.assertIn("Quick hours snapshot", result.output)
        self.assertIn("Run one-click onboarding", result.output)


if __name__ == "__main__":
    unittest.main()
