from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from core.cli import app


class CliCalendarSuggestTests(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()

    @patch("core.cli_calendar_suggest.read_calendar_titles")
    @patch("core.cli_calendar_suggest.load_profiles")
    def test_calendar_suggest_with_suggestions(self, mock_load_profiles, mock_read_titles):
        mock_load_profiles.return_value = ([], Path("/fake/path"), {})
        mock_read_titles.return_value = [
            ("Work", "HÅ-DAA standup"),
            ("Work", "HÅ-DAA deep work"),
            ("Work", "EASE-DAA review"),
        ]

        result = self.runner.invoke(app, ["calendar-suggest", "--min-count", "1"])
        self.assertEqual(result.exit_code, 0, msg=result.output)

        self.assertIn("Scanned 3 calendar event(s)", result.output)
        self.assertIn("Suggested projects", result.output)
        self.assertIn("Code", result.output)
        self.assertIn("Events", result.output)
        self.assertIn("Example", result.output)
        self.assertIn("HÅ-DAA", result.output)
        self.assertIn("EASE-DAA", result.output)
        self.assertIn("To use, add these to your projects config", result.output)
        self.assertIn("Next: edit your config to add the suggested project(s)", result.output)

    @patch("core.cli_calendar_suggest.read_calendar_titles")
    @patch("core.cli_calendar_suggest.load_profiles")
    def test_calendar_suggest_empty_state(self, mock_load_profiles, mock_read_titles):
        mock_load_profiles.return_value = ([], Path("/fake/path"), {})
        mock_read_titles.return_value = []

        result = self.runner.invoke(app, ["calendar-suggest"])
        self.assertEqual(result.exit_code, 0, msg=result.output)
        self.assertIn("Scanned 0 calendar event(s)", result.output)
        self.assertIn("No new project codes found", result.output)

    @patch("core.cli_calendar_suggest.read_calendar_titles")
    @patch("core.cli_calendar_suggest.load_profiles")
    def test_calendar_suggest_load_profiles_value_error_fallback(self, mock_load_profiles, mock_read_titles):
        mock_load_profiles.side_effect = ValueError("invalid config")
        mock_read_titles.return_value = [
            ("Work", "HÅ-DAA standup"),
            ("Work", "HÅ-DAA deep work"),
        ]

        result = self.runner.invoke(app, ["calendar-suggest", "--min-count", "1"])
        self.assertEqual(result.exit_code, 0, msg=result.output)
        self.assertIn("Scanned 2 calendar event(s)", result.output)
        self.assertIn("Suggested projects", result.output)
        self.assertIn("HÅ-DAA", result.output)


if __name__ == "__main__":
    unittest.main()
