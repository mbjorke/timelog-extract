from __future__ import annotations

import unittest
from unittest.mock import patch

from typer.testing import CliRunner

from core.cli import app


class ReportAdditiveSummaryOptionTests(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()

    def test_report_forwards_additive_summary_flag(self):
        with patch("core.report_cli.run_timelog_cli") as run_mock:
            result = self.runner.invoke(app, ["report", "--yesterday", "--additive-summary"])
        self.assertEqual(result.exit_code, 0, msg=result.output)
        self.assertTrue(run_mock.called)
        options = run_mock.call_args[0][0]
        self.assertTrue(getattr(options, "additive_summary", False))

    def test_report_forwards_noise_profile(self):
        with patch("core.report_cli.run_timelog_cli") as run_mock:
            result = self.runner.invoke(app, ["report", "--yesterday", "--noise-profile", "lenient"])
        self.assertEqual(result.exit_code, 0, msg=result.output)
        options = run_mock.call_args[0][0]
        self.assertEqual(getattr(options, "noise_profile", ""), "lenient")

    def test_report_forwards_ultra_strict_noise_profile(self):
        with patch("core.report_cli.run_timelog_cli") as run_mock:
            result = self.runner.invoke(app, ["report", "--yesterday", "--noise-profile", "ultra-strict"])
        self.assertEqual(result.exit_code, 0, msg=result.output)
        options = run_mock.call_args[0][0]
        self.assertEqual(getattr(options, "noise_profile", ""), "ultra-strict")

    def test_report_forwards_lovable_noise_profile(self):
        with patch("core.report_cli.run_timelog_cli") as run_mock:
            result = self.runner.invoke(app, ["report", "--yesterday", "--lovable-noise-profile", "strict"])
        self.assertEqual(result.exit_code, 0, msg=result.output)
        options = run_mock.call_args[0][0]
        self.assertEqual(getattr(options, "lovable_noise_profile", ""), "strict")

    def test_report_accepts_alias_global_and_lovable_profile_flags(self):
        with patch("core.report_cli.run_timelog_cli") as run_mock:
            result = self.runner.invoke(
                app,
                ["report", "--yesterday", "--global-noise-profile", "ultra-strict", "--lovable-profile", "strict"],
            )
        self.assertEqual(result.exit_code, 0, msg=result.output)
        options = run_mock.call_args[0][0]
        self.assertEqual(getattr(options, "noise_profile", ""), "ultra-strict")
        self.assertEqual(getattr(options, "lovable_noise_profile", ""), "strict")

    def test_report_forwards_invoice_mode(self):
        with patch("core.report_cli.run_timelog_cli") as run_mock:
            result = self.runner.invoke(app, ["report", "--yesterday", "--invoice-mode", "calibrated-a"])
        self.assertEqual(result.exit_code, 0, msg=result.output)
        options = run_mock.call_args[0][0]
        self.assertEqual(getattr(options, "invoice_mode", ""), "calibrated-a")

    def test_report_forwards_invoice_ground_truth(self):
        with patch("core.report_cli.run_timelog_cli") as run_mock:
            result = self.runner.invoke(
                app,
                ["report", "--yesterday", "--invoice-mode", "calibrated-a", "--invoice-ground-truth", "march_invoice_ground_truth.json"],
            )
        self.assertEqual(result.exit_code, 0, msg=result.output)
        options = run_mock.call_args[0][0]
        self.assertEqual(getattr(options, "invoice_mode", ""), "calibrated-a")
        self.assertEqual(getattr(options, "invoice_ground_truth", ""), "march_invoice_ground_truth.json")


if __name__ == "__main__":
    unittest.main()
