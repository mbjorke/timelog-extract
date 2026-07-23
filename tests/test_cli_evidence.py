"""Integration and formatting tests for `gittan evidence` CLI command."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from typer.testing import CliRunner

from core.cli import app


class CliEvidenceTests(unittest.TestCase):
    def test_evidence_mutually_exclusive_flags(self):
        runner = CliRunner()
        result = runner.invoke(app, ["evidence", "--export", "/tmp/export.jsonl", "--erase"])
        self.assertEqual(result.exit_code, 1)
        # Check that FAIL_ICON (with its color tag if styled) or at least its plain content is printed
        # Since CliRunner preserves ANSI/tags depending on console setups, we can check for plain text
        self.assertIn("Error:", result.output)
        self.assertIn("mutually exclusive", result.output)
        self.assertIn("Next:", result.output)
        self.assertIn("use only one of these data control options", result.output)

    @patch("core.evidence_store.store_health")
    def test_evidence_disabled_store(self, mock_health):
        mock_health.return_value = {
            "enabled": False,
            "base_dir": "/tmp/fake-evidence-dir",
        }
        runner = CliRunner()
        result = runner.invoke(app, ["evidence"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Shadow log: off", result.output)

    @patch("core.evidence_store.store_health")
    def test_evidence_chain_broken(self, mock_health):
        mock_health.return_value = {
            "enabled": True,
            "base_dir": "/tmp/fake-evidence-dir",
            "total_records": 42,
            "records_captured_today": 5,
            "last_captured_at": "2026-07-23T12:00:00Z",
            "retention_span": "10 days",
            "chain_ok": False,
            "chain_breaks": ["Break at record #10", "Break at record #20"],
            "per_source": {"Cursor": 30, "Chrome": 12},
        }
        runner = CliRunner()
        result = runner.invoke(app, ["evidence"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Evidence shadow log", result.output)
        self.assertIn("Records: 42", result.output)
        self.assertIn("Chain integrity:", result.output)
        self.assertIn("BROKEN", result.output)
        self.assertIn("Break at record #10", result.output)
        self.assertIn("Break at record #20", result.output)


if __name__ == "__main__":
    unittest.main()
