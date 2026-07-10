from __future__ import annotations

import re
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from typer.testing import CliRunner

from core.cli import app

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _plain(output: str) -> str:
    """Strip ANSI color codes; Rich colorizes in color-capable terminals."""
    return _ANSI_RE.sub("", output)


class _FakeReport:
    def __init__(self, *, only_project: str | None = None, ambiguous: list[str] | None = None):
        self.included_events = []
        self.overall_days = {}
        self.project_reports = {}
        self.screen_time_days = {}
        self.profiles = []
        self.config_path = None
        self.dt_from = "2026-04-25"
        self.dt_to = "2026-04-25"
        self.args = SimpleNamespace(
            only_project=only_project,
            only_project_ambiguous=ambiguous or [],
            invoice_pdf=False,
            invoice_pdf_file=None,
            customer=None,
            billable_unit=0.0,
            source_summary=False,
            narrative=False,
        )


class ReportEmptyStateUxTests(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()

    def test_report_empty_state_shows_next_step_tip(self):
        report = _FakeReport()
        with patch("core.report_cli.run_timelog_report", return_value=report):
            result = self.runner.invoke(app, ["report", "--today"])
        self.assertEqual(result.exit_code, 0, msg=result.output)
        output = _plain(result.output)
        self.assertIn("No events found.", output)
        self.assertIn("gittan doctor", output)
        flat = " ".join(output.split())
        self.assertIn("gittan report --today --source-summary", flat)

    def test_report_ambiguous_project_message_unchanged(self):
        report = _FakeReport(only_project="Ax", ambiguous=["AX Finans", "Axon"])
        with patch("core.report_cli.run_timelog_report", return_value=report):
            result = self.runner.invoke(app, ["report", "--today", "--only-project", "Ax"])
        self.assertEqual(result.exit_code, 0, msg=result.output)
        output = _plain(result.output)
        self.assertIn("Project filter 'Ax' is ambiguous.", output)
        self.assertNotIn("No events found.", output)


if __name__ == "__main__":
    unittest.main()
