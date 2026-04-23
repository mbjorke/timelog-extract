from __future__ import annotations

import unittest
from unittest.mock import patch

from typer.testing import CliRunner

from core.cli import app


class SearchCommandTests(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()

    def test_search_forwards_all_events_and_project(self):
        with patch("core.report_cli.run_timelog_cli") as run_mock:
            result = self.runner.invoke(app, ["search", "--yesterday", "--project", "Akturo"])
        self.assertEqual(result.exit_code, 0, msg=result.output)
        options = run_mock.call_args[0][0]
        self.assertTrue(getattr(options, "all_events", False))
        self.assertEqual(getattr(options, "only_project", None), "Akturo")

    def test_search_supports_json_format(self):
        with patch("core.report_cli.run_timelog_cli") as run_mock:
            result = self.runner.invoke(app, ["search", "--yesterday", "--format", "json"])
        self.assertEqual(result.exit_code, 0, msg=result.output)
        options = run_mock.call_args[0][0]
        self.assertEqual(getattr(options, "output_format", ""), "json")

    def test_search_forwards_noise_profile(self):
        with patch("core.report_cli.run_timelog_cli") as run_mock:
            result = self.runner.invoke(app, ["search", "--yesterday", "--noise-profile", "lenient"])
        self.assertEqual(result.exit_code, 0, msg=result.output)
        options = run_mock.call_args[0][0]
        self.assertEqual(getattr(options, "noise_profile", ""), "lenient")

    def test_search_forwards_ultra_strict_noise_profile(self):
        with patch("core.report_cli.run_timelog_cli") as run_mock:
            result = self.runner.invoke(app, ["search", "--yesterday", "--noise-profile", "ultra-strict"])
        self.assertEqual(result.exit_code, 0, msg=result.output)
        options = run_mock.call_args[0][0]
        self.assertEqual(getattr(options, "noise_profile", ""), "ultra-strict")

    def test_search_forwards_lovable_noise_profile(self):
        with patch("core.report_cli.run_timelog_cli") as run_mock:
            result = self.runner.invoke(app, ["search", "--yesterday", "--lovable-noise-profile", "strict"])
        self.assertEqual(result.exit_code, 0, msg=result.output)
        options = run_mock.call_args[0][0]
        self.assertEqual(getattr(options, "lovable_noise_profile", ""), "strict")

    def test_search_accepts_alias_global_and_lovable_profile_flags(self):
        with patch("core.report_cli.run_timelog_cli") as run_mock:
            result = self.runner.invoke(
                app,
                ["search", "--yesterday", "--global-noise-profile", "ultra-strict", "--lovable-profile", "strict"],
            )
        self.assertEqual(result.exit_code, 0, msg=result.output)
        options = run_mock.call_args[0][0]
        self.assertEqual(getattr(options, "noise_profile", ""), "ultra-strict")
        self.assertEqual(getattr(options, "lovable_noise_profile", ""), "strict")


if __name__ == "__main__":
    unittest.main()
