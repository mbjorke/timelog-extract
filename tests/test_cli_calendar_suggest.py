from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from typer.testing import CliRunner

from core.cli import app


class CliCalendarSuggestTests(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()

    @patch("core.cli_calendar_suggest.read_calendar_titles")
    @patch("core.cli_calendar_suggest._configured_profiles", return_value=[])
    def test_calendar_suggest_with_suggestions(self, _mock_profiles, mock_read_titles):
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
    @patch("core.cli_calendar_suggest._configured_profiles", return_value=[])
    def test_calendar_suggest_empty_state(self, _mock_profiles, mock_read_titles):
        mock_read_titles.return_value = []

        result = self.runner.invoke(app, ["calendar-suggest"])
        self.assertEqual(result.exit_code, 0, msg=result.output)
        self.assertIn("Scanned 0 calendar event(s)", result.output)
        self.assertIn("No new project codes found", result.output)

    @patch("core.cli_calendar_suggest.read_calendar_titles")
    def test_malformed_config_yields_no_covered_terms(self, mock_read_titles):
        """A real malformed file, not a mocked ValueError.

        load_profiles() catches its own OSError/JSONDecodeError/ValueError and
        returns a synthetic fallback profile, so the previous `side_effect =
        ValueError` could never happen in production and the `except` it
        exercised was dead code. Drive the CLI with an actually broken config
        instead, and assert the behaviour that matters: nothing is treated as
        already covered, so the codes still surface.
        """
        mock_read_titles.return_value = [
            ("Work", "HÅ-DAA standup"),
            ("Work", "HÅ-DAA deep work"),
        ]
        with TemporaryDirectory() as tmp:
            bad = Path(tmp) / "timelog_projects.json"
            bad.write_text("{ this is not json", encoding="utf-8")
            result = self.runner.invoke(
                app,
                ["calendar-suggest", "--min-count", "1", "--projects-config", str(bad)],
            )
        self.assertEqual(result.exit_code, 0, msg=result.output)
        self.assertIn("Scanned 2 calendar event(s)", result.output)
        self.assertIn("Suggested projects", result.output)
        self.assertIn("HÅ-DAA", result.output)

    @patch("core.cli_calendar_suggest.read_calendar_titles")
    def test_malformed_config_still_produces_parseable_json(self, mock_read_titles):
        """--format json must stay machine-readable when the config is broken."""
        mock_read_titles.return_value = [("Work", "HÅ-DAA standup")]
        with TemporaryDirectory() as tmp:
            bad = Path(tmp) / "timelog_projects.json"
            bad.write_text("[[[", encoding="utf-8")
            result = self.runner.invoke(
                app,
                ["calendar-suggest", "--min-count", "1", "--format", "json",
                 "--projects-config", str(bad)],
            )
        self.assertEqual(result.exit_code, 0, msg=result.output)
        payload = json.loads(result.output)
        self.assertEqual([entry["code"] for entry in payload], ["HÅ-DAA"])

    @patch("core.cli_calendar_suggest.read_calendar_titles")
    def test_configured_terms_are_still_excluded(self, mock_read_titles):
        """The fallback must not become "ignore the config entirely"."""
        mock_read_titles.return_value = [("Work", "HÅ-DAA standup")]
        with TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "timelog_projects.json"
            cfg.write_text(
                json.dumps({"projects": [{"name": "project-alpha", "match_terms": ["HÅ-DAA"]}]}),
                encoding="utf-8",
            )
            result = self.runner.invoke(
                app,
                ["calendar-suggest", "--min-count", "1", "--projects-config", str(cfg)],
            )
        self.assertEqual(result.exit_code, 0, msg=result.output)
        self.assertIn("No new project codes found", result.output)

    @patch("core.cli_calendar_suggest.read_calendar_titles")
    @patch("core.cli_calendar_suggest._configured_profiles", return_value=[])
    def test_style_named_bracket_in_a_title_does_not_eat_the_example(self, _mock_profiles, mock_read_titles):
        """Bracketed text that collides with a Rich style name is consumed.

        Measured against Rich rather than assumed: "[PROJECT-123] Standup"
        happens to render raw, because Rich leaves an unresolvable tag alone.
        But "[bold] sprint review" loses its tag and "[/] retro" raises
        MarkupError outright — and a calendar owner picks those strings, not us.
        The Example column carries the whole untrusted title, so it is escaped.
        """
        mock_read_titles.return_value = [
            ("Work", "[bold] sprint review BOLDCODE"),
            ("Work", "[bold] sprint planning BOLDCODE"),
        ]
        result = self.runner.invoke(app, ["calendar-suggest", "--min-count", "1"])
        self.assertEqual(result.exit_code, 0, msg=result.output)
        self.assertIn("[bold]", result.output, "the literal tag text must survive rendering")

    @patch("core.cli_calendar_suggest.read_calendar_titles")
    @patch("core.cli_calendar_suggest._configured_profiles", return_value=[])
    def test_closing_tag_in_a_title_does_not_crash_the_render(self, _mock_profiles, mock_read_titles):
        """An unmatched "[/]" is a MarkupError, i.e. the command dies on a calendar entry."""
        mock_read_titles.return_value = [
            ("Work", "[/] retro SLASHCODE"),
            ("Work", "[/] retro follow-up SLASHCODE"),
        ]
        result = self.runner.invoke(app, ["calendar-suggest", "--min-count", "1"])
        self.assertEqual(result.exit_code, 0, msg=result.output)
        self.assertIsNone(result.exception, msg=repr(result.exception))
        self.assertIn("SLASHCODE", result.output)


if __name__ == "__main__":
    unittest.main()
