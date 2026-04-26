from __future__ import annotations

import unittest

from typer.testing import CliRunner

from core.cli import app


class CliHelpTextTests(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()

    def test_top_level_help_uses_local_first_evidence_language(self):
        result = self.runner.invoke(app, ["--help"])
        self.assertEqual(result.exit_code, 0, msg=result.output)
        self.assertIn("Local-first CLI for reviewable project-hour evidence", result.output)

    def test_suggest_rules_help_mentions_project_prompt_behavior(self):
        result = self.runner.invoke(app, ["suggest-rules", "--help"])
        self.assertEqual(result.exit_code, 0, msg=result.output)
        self.assertIn("prompts for project if omitted", result.output)

    def test_review_help_marks_command_as_advanced_manual_cleanup(self):
        result = self.runner.invoke(app, ["review", "--help"])
        self.assertEqual(result.exit_code, 0, msg=result.output)
        self.assertIn("Advanced manual cleanup", result.output)

    def test_top_level_command_descriptions_are_first_run_oriented(self):
        result = self.runner.invoke(app, ["--help"])
        self.assertEqual(result.exit_code, 0, msg=result.output)
        self.assertIn("Build detailed local evidence reports", result.output)
        self.assertIn("Quick hours snapshot", result.output)
        self.assertIn("Run one-click onboarding", result.output)


if __name__ == "__main__":
    unittest.main()
