"""Integration and UX regression tests for `gittan evidence` subcommand."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from typer.testing import CliRunner

from core.cli import app


class CliEvidenceUXTests(unittest.TestCase):
    def test_conflicting_options_outputs_standard_error_pattern(self):
        runner = CliRunner()
        result = runner.invoke(app, ["evidence", "--export", "some_path.jsonl", "--erase"])
        self.assertEqual(result.exit_code, 1)
        self.assertIn("Error: --export, --prune-older-than, and --erase are mutually exclusive.", result.output)
        self.assertIn("Next: Run `gittan evidence` with only one of these options.", result.output)

    def test_prune_value_error_outputs_standard_error_pattern(self):
        runner = CliRunner()
        with patch("core.evidence_store.prune_older_than", side_effect=ValueError("Prune days must be positive")):
            result = runner.invoke(app, ["evidence", "--prune-older-than", "-5"])
        self.assertEqual(result.exit_code, 1)
        self.assertIn("Error: Prune days must be positive", result.output)
        self.assertIn("Next: Provide a positive integer to prune the shadow log.", result.output)

    def test_erase_aborted_by_user_outputs_orange_aborted(self):
        runner = CliRunner()
        with patch("core.cli_evidence.typer.confirm", return_value=False):
            result = runner.invoke(app, ["evidence", "--erase"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Aborted.", result.output)


if __name__ == "__main__":
    unittest.main()
