from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from typer.testing import CliRunner

from core.cli import app


class _FakeReport:
    def __init__(self):
        self.included_events = [{"project": "project-alpha", "detail": "alpha", "source": "Chrome"}]
        self.all_events = [
            {
                "source": "Chrome",
                "detail": f"https://unmapped.example.dev/{idx} alpha-token",
                "project": "project-alpha",
            }
            for idx in range(6)
        ]
        self.overall_days = {}
        self.project_reports = {}
        self.screen_time_days = {}
        self.profiles = [{"name": "project-alpha", "match_terms": ["alpha-token"], "tracked_urls": []}]
        self.config_path = None
        self.dt_from = "2026-04-25"
        self.dt_to = "2026-04-25"
        self.collector_status = {}
        self.worklog_path = "."
        self.args = SimpleNamespace(
            output_format="terminal",
            source_summary=False,
            only_project=None,
            only_project_ambiguous=[],
            invoice_pdf=False,
            invoice_pdf_file=None,
            customer=None,
            billable_unit=0.0,
            narrative=False,
            all_events=False,
            min_session=15,
            min_session_passive=5,
            gap_minutes=15,
            source_strategy="auto",
        )


class ReportSuggestionTests(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()

    def test_report_does_not_show_inline_mapping_suggestions(self):
        report = _FakeReport()
        with patch("core.report_cli.run_timelog_report", return_value=report), patch(
            "core.report_cli._print_report", return_value=None
        ):
            result = self.runner.invoke(app, ["report", "--today"])
        self.assertEqual(result.exit_code, 0, msg=result.output)
        self.assertNotIn("Mapping suggestions:", result.output)
        self.assertNotIn("consider adding tracked_urls", result.output)

    def test_report_output_has_no_inline_suggestion_lines(self):
        report = _FakeReport()
        with patch("core.report_cli.run_timelog_report", return_value=report), patch(
            "core.report_cli._print_report", return_value=None
        ):
            result = self.runner.invoke(app, ["report", "--today"])
        self.assertEqual(result.exit_code, 0, msg=result.output)
        self.assertEqual(result.output.count("consider "), 0)


if __name__ == "__main__":
    unittest.main()
