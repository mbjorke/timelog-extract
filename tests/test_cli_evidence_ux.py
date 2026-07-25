"""Integration and UX regression tests for `gittan evidence` subcommand."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from typer.testing import CliRunner

from core.cli import app


def unwrapped(text: str) -> str:
    """Collapse Rich's terminal wrapping so assertions test copy, not width."""
    return " ".join(text.split())


class CliEvidenceUXTests(unittest.TestCase):
    def test_conflicting_options_outputs_standard_error_pattern(self):
        runner = CliRunner()
        result = runner.invoke(app, ["evidence", "--export", "some_path.jsonl", "--erase"])
        self.assertEqual(result.exit_code, 1)
        self.assertIn(
            "Error: --export, --import, --repair, --prune-older-than, and --erase are mutually exclusive.",
            unwrapped(result.output),
        )
        self.assertIn("Next: Run `gittan evidence` with only one of these options.", unwrapped(result.output))

    def test_import_missing_file_outputs_standard_error_pattern(self):
        runner = CliRunner()
        result = runner.invoke(app, ["evidence", "--import", "no_such_export.jsonl"])
        self.assertEqual(result.exit_code, 1)
        self.assertIn("Error: no such export file", unwrapped(result.output))
        self.assertIn("Next: Point --import at a JSONL file written by", unwrapped(result.output))

    def test_prune_value_error_outputs_standard_error_pattern(self):
        runner = CliRunner()
        with patch("core.evidence_store.prune_older_than", side_effect=ValueError("Prune days must be positive")):
            result = runner.invoke(app, ["evidence", "--prune-older-than", "-5"])
        self.assertEqual(result.exit_code, 1)
        self.assertIn("Error: Prune days must be positive", result.output)
        self.assertIn("Next: Provide a positive integer to prune the shadow log.", result.output)

    def test_erase_aborted_by_user_outputs_orange_aborted(self):
        runner = CliRunner()
        with patch("core.cli_evidence.typer.confirm", return_value=False), \
             patch("core.evidence_store.erase_store") as erase_mock:
            result = runner.invoke(app, ["evidence", "--erase"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Aborted.", result.output)
        erase_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
