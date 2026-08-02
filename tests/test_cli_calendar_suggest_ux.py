from __future__ import annotations

import unittest
from unittest.mock import patch

from typer.testing import CliRunner

from core.cli import app
from tests.cli_output_helpers import strip_ansi as _plain


class CliCalendarSuggestUXTests(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()

    @patch("core.cli_calendar_suggest.read_calendar_titles")
    def test_calendar_suggest_with_suggestions(self, mock_read_titles):
        """Should run calendar-suggest and show beautiful Rich table suggestions."""
        mock_read_titles.return_value = [
            ("TimeReport", "HÅ-DAA standup"),
            ("TimeReport", "HÅ-DAA deep work"),
            ("Work", "KidneySign proteomics"),
        ]

        # Use an empty config by pointing to a non-existent file
        # which will cause load_profiles to catch ValueError and fallback to profiles=[]
        result = self.runner.invoke(app, ["calendar-suggest", "--projects-config", "nonexistent.json", "--min-count", "1"])
        self.assertEqual(result.exit_code, 0, msg=result.output)

        output = _plain(result.output)
        self.assertIn("Scanned 3 calendar event(s)", output)
        self.assertIn("Suggested projects", output)
        self.assertIn("HÅ-DAA", output)
        self.assertIn("KidneySign", output)
        self.assertIn("To use, add these to your projects config", output)
        self.assertIn("projects", output)
        self.assertIn("Next: Run `gittan report` once config is updated to re-analyze.", output)

    @patch("core.cli_calendar_suggest.read_calendar_titles")
    def test_calendar_suggest_empty_state(self, mock_read_titles):
        """Should show a friendly empty state when no suggestions are found."""
        mock_read_titles.return_value = [
            ("TimeReport", "lunch with team"),
        ]

        result = self.runner.invoke(app, ["calendar-suggest", "--projects-config", "nonexistent.json"])
        self.assertEqual(result.exit_code, 0, msg=result.output)

        output = _plain(result.output)
        self.assertIn("Scanned 1 calendar event(s)", output)
        self.assertIn("No new project codes found", output)
        self.assertIn("Next: Check your config or widen the scanned window / calendars.", output)

    @patch("core.cli_calendar_suggest.read_calendar_titles")
    def test_calendar_suggest_json_format(self, mock_read_titles):
        """Should output clean JSON when requested."""
        mock_read_titles.return_value = [
            ("Work", "KidneySign proteomics"),
        ]

        result = self.runner.invoke(app, ["calendar-suggest", "--projects-config", "nonexistent.json", "--min-count", "1", "--format", "json"])
        self.assertEqual(result.exit_code, 0, msg=result.output)

        # Verify it's valid JSON list
        import json
        data = json.loads(result.output)
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["code"], "KidneySign")


if __name__ == "__main__":
    unittest.main()
