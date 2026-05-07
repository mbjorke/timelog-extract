"""Integration smoke for `gittan evidence-check` CLI wiring."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from typer.testing import CliRunner

from core.cli_app import app


class CliEvidenceCheckTests(unittest.TestCase):
    def test_evidence_check_invokes_report_and_prints_summary(self):
        report = SimpleNamespace(
            included_events=[
                {"source": "Cursor"},
                {"source": "Chrome"},
            ],
            overall_days={"2026-03-15": {"hours": 2.0}},
            screen_time_days={"2026-03-15": 5.0},
        )
        runner = CliRunner()
        with patch("core.report_service.run_timelog_report", return_value=report) as run_mock:
            result = runner.invoke(
                app,
                ["evidence-check", "--from", "2026-03-01", "--to", "2026-03-31"],
            )
        self.assertEqual(result.exit_code, 0, msg=result.output)
        run_mock.assert_called_once()
        self.assertIn("Evidence check", result.output)
        self.assertIn("Observed timeline hours", result.output)
        self.assertIn("Screen Time hours", result.output)
        self.assertIn("Cursor", result.output)


if __name__ == "__main__":
    unittest.main()
