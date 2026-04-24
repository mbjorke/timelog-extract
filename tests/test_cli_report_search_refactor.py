from __future__ import annotations

import unittest
from unittest.mock import patch

from typer.testing import CliRunner

from core.cli import app


class ReportSearchRefactorTests(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()

    def test_report_and_search_share_timeframe_resolution(self):
        with patch("core.report_cli.run_timelog_cli") as run_mock:
            report_result = self.runner.invoke(app, ["report", "--today"])
            search_result = self.runner.invoke(app, ["search", "--today"])

        self.assertEqual(report_result.exit_code, 0, msg=report_result.output)
        self.assertEqual(search_result.exit_code, 0, msg=search_result.output)
        report_options = run_mock.call_args_list[0][0][0]
        search_options = run_mock.call_args_list[1][0][0]
        self.assertEqual(getattr(report_options, "today", False), getattr(search_options, "today", False))
        self.assertEqual(getattr(report_options, "yesterday", False), getattr(search_options, "yesterday", False))
        self.assertEqual(getattr(report_options, "last_3_days", False), getattr(search_options, "last_3_days", False))
        self.assertEqual(getattr(report_options, "last_week", False), getattr(search_options, "last_week", False))
        self.assertEqual(getattr(report_options, "last_14_days", False), getattr(search_options, "last_14_days", False))
        self.assertEqual(getattr(report_options, "last_month", False), getattr(search_options, "last_month", False))
        self.assertEqual(getattr(report_options, "date_from", None), getattr(search_options, "date_from", None))
        self.assertEqual(getattr(report_options, "date_to", None), getattr(search_options, "date_to", None))

    def test_search_still_forces_all_events(self):
        with patch("core.report_cli.run_timelog_cli") as run_mock:
            result = self.runner.invoke(app, ["search", "--today"])
        self.assertEqual(result.exit_code, 0, msg=result.output)
        options = run_mock.call_args[0][0]
        self.assertTrue(getattr(options, "all_events", False))

    def test_prompt_path_still_used_when_timeframe_omitted(self):
        picked = {
            "today": False,
            "yesterday": False,
            "last_3_days": False,
            "last_week": True,
            "last_14_days": False,
            "last_month": False,
            "date_from": "2026-04-17",
            "date_to": "2026-04-23",
        }
        with patch("core.cli_report_status.prompt_for_timeframe", return_value=picked) as prompt_mock:
            with patch("core.report_cli.run_timelog_cli") as run_mock:
                result = self.runner.invoke(app, ["search"])

        self.assertEqual(result.exit_code, 0, msg=result.output)
        prompt_mock.assert_called_once()
        options = run_mock.call_args[0][0]
        self.assertTrue(getattr(options, "last_week", False))
        self.assertEqual(getattr(options, "date_from", None), "2026-04-17")
        self.assertEqual(getattr(options, "date_to", None), "2026-04-23")


if __name__ == "__main__":
    unittest.main()
