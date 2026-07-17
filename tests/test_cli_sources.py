from __future__ import annotations

import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from core.cli import app
from tests.cli_output_helpers import strip_ansi as _plain


class CliSourcesTests(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()

    @patch("core.cli_doctor_sources_projects.prompt_for_timeframe")
    @patch("core.report_service.run_timelog_report")
    @patch("core.analytics.group_by_day")
    @patch("core.analytics.estimate_hours_by_day")
    def test_sources_with_uncategorized_events(
        self, mock_estimate, mock_group, mock_report, mock_prompt
    ):
        """Should show source table and suggest 'gittan review'."""
        mock_prompt.return_value = {
            "date_from": "2026-05-01",
            "date_to": "2026-05-01",
            "today": True,
        }

        # Setup report
        report = MagicMock()
        report.all_events = [
            {"source": "Chrome", "project": "Uncategorized", "detail": "site.com"},
            {"source": "GitHub", "project": "project-alpha", "detail": "commit"},
        ]
        mock_report.return_value = report

        # Setup estimate hours by day
        mock_group.return_value = {}
        mock_estimate.return_value = {
            "2026-05-01": {
                "sessions": [
                    (
                        datetime(2026, 5, 1, 9, 0),
                        datetime(2026, 5, 1, 10, 0),
                        [
                            {"source": "Chrome", "project": "Uncategorized", "detail": "site.com"},
                            {"source": "GitHub", "project": "project-alpha", "detail": "commit"},
                        ],
                    )
                ]
            }
        }

        result = self.runner.invoke(app, ["sources"])
        self.assertEqual(result.exit_code, 0, msg=result.output)
        output = _plain(result.output)

        self.assertIn("Source Importance Analysis (2026-05-01 to 2026-05-01)", output)
        self.assertIn("Chrome", output)
        self.assertIn("GitHub", output)
        # Check Next steps guidance suggests review
        self.assertIn("Next: run `gittan review` to map uncategorized domains to project buckets.", output)

    @patch("core.cli_doctor_sources_projects.prompt_for_timeframe")
    @patch("core.report_service.run_timelog_report")
    @patch("core.analytics.group_by_day")
    @patch("core.analytics.estimate_hours_by_day")
    def test_sources_all_categorized_events(
        self, mock_estimate, mock_group, mock_report, mock_prompt
    ):
        """Should show source table and suggest 'gittan report --today'."""
        mock_prompt.return_value = {
            "date_from": "2026-05-01",
            "date_to": "2026-05-01",
            "today": True,
        }

        # Setup report
        report = MagicMock()
        report.all_events = [
            {"source": "GitHub", "project": "project-alpha", "detail": "commit"},
        ]
        mock_report.return_value = report

        # Setup estimate hours by day
        mock_group.return_value = {}
        mock_estimate.return_value = {
            "2026-05-01": {
                "sessions": [
                    (
                        datetime(2026, 5, 1, 9, 0),
                        datetime(2026, 5, 1, 10, 0),
                        [
                            {"source": "GitHub", "project": "project-alpha", "detail": "commit"},
                        ],
                    )
                ]
            }
        }

        result = self.runner.invoke(app, ["sources"])
        self.assertEqual(result.exit_code, 0, msg=result.output)
        output = _plain(result.output)

        self.assertIn("Source Importance Analysis (2026-05-01 to 2026-05-01)", output)
        self.assertIn("GitHub", output)
        # Check Next steps guidance suggests report
        self.assertIn("Next: run `gittan report --today` to review your daily project timeline.", output)

    @patch("core.cli_doctor_sources_projects.prompt_for_timeframe")
    @patch("core.report_service.run_timelog_report")
    def test_sources_empty_state(self, mock_report, mock_prompt):
        """Should show empty state warning and suggestion to run 'gittan doctor'."""
        mock_prompt.return_value = {
            "date_from": "2026-05-01",
            "date_to": "2026-05-01",
            "today": True,
        }

        report = MagicMock()
        report.all_events = []
        mock_report.return_value = report

        result = self.runner.invoke(app, ["sources"])
        self.assertEqual(result.exit_code, 0, msg=result.output)
        output = _plain(result.output)

        self.assertIn("No data found for this period to analyze.", output)
        self.assertIn("Next: widen the date range or run `gittan doctor` to verify source access.", output)


if __name__ == "__main__":
    unittest.main()
