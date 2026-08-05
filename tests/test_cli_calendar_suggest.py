from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from core.cli import app


class CliCalendarSuggestTests(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()

    @patch("core.cli_calendar_suggest.read_calendar_titles")
    def test_calendar_suggest_with_suggestions_and_valid_config(self, mock_read_titles):
        mock_read_titles.return_value = [
            ("Work", "HÅ-DAA standup"),
            ("Work", "HÅ-DAA deep work"),
            ("Work", "EASE-DAA review"),
            ("Work", "Unrelated meeting"),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "timelog_projects.json"
            # Valid config containing an existing profile covering HÅ-DAA
            config_file.write_text(
                json.dumps({
                    "projects": [
                        {
                            "name": "DAA Project",
                            "match_terms": ["hå-daa"],
                            "enabled": True,
                        }
                    ]
                }),
                encoding="utf-8"
            )

            # We should only get suggestions for codes not covered, so EASE-DAA should be suggested,
            # but HÅ-DAA should be excluded!
            result = self.runner.invoke(app, [
                "calendar-suggest",
                "--projects-config", str(config_file),
                "--min-count", "1",
            ])
            self.assertEqual(result.exit_code, 0, msg=result.output)
            self.assertIn("EASE-DAA", result.output)
            self.assertNotIn("HÅ-DAA", result.output)

    @patch("core.cli_calendar_suggest.read_calendar_titles")
    def test_calendar_suggest_unparseable_json_config_fallback(self, mock_read_titles):
        mock_read_titles.return_value = [
            ("Work", "HÅ-DAA standup"),
            ("Work", "EASE-DAA review"),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "timelog_projects.json"
            # Write invalid JSON
            config_file.write_text("{ invalid json: ", encoding="utf-8")

            result = self.runner.invoke(app, [
                "calendar-suggest",
                "--projects-config", str(config_file),
                "--min-count", "1",
            ])
            self.assertEqual(result.exit_code, 0, msg=result.output)
            # Since the config is unparseable, it should fallback to empty list and suggest both codes!
            self.assertIn("HÅ-DAA", result.output)
            self.assertIn("EASE-DAA", result.output)

    @patch("core.cli_calendar_suggest.read_calendar_titles")
    def test_calendar_suggest_unparseable_json_config_json_format(self, mock_read_titles):
        mock_read_titles.return_value = [
            ("Work", "HÅ-DAA standup"),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "timelog_projects.json"
            config_file.write_text("{ unparseable", encoding="utf-8")

            result = self.runner.invoke(app, [
                "calendar-suggest",
                "--projects-config", str(config_file),
                "--min-count", "1",
                "--format", "json",
            ])
            self.assertEqual(result.exit_code, 0, msg=result.output)
            # Output should be valid parseable JSON list
            data = json.loads(result.output)
            self.assertEqual(len(data), 1)
            self.assertEqual(data[0]["code"], "HÅ-DAA")

    @patch("core.cli_calendar_suggest.read_calendar_titles")
    @patch("core.cli_calendar_suggest._configured_profiles")
    def test_calendar_suggest_escaping_brackets(self, mock_configured, mock_read_titles):
        mock_configured.return_value = []
        # Title contains bracket sequences and valid codes
        mock_read_titles.return_value = [
            ("Work", "[bold] AXOR-CODE standup"),
            ("Work", "[bold] AXOR-CODE coding"),
            ("Work", "[/] BOLD-CODE retro"),
            ("Work", "[/] BOLD-CODE retro2"),
        ]

        result = self.runner.invoke(app, ["calendar-suggest", "--min-count", "1"])
        self.assertEqual(result.exit_code, 0, msg=result.output)
        # Should render correctly with literally escaped markup inside the console output
        self.assertIn("[bold]", result.output)
        self.assertIn("[/]", result.output)
        self.assertIn("AXOR-CODE", result.output)
        self.assertIn("BOLD-CODE", result.output)

    @patch("core.cli_calendar_suggest.read_calendar_titles")
    @patch("core.cli_calendar_suggest._configured_profiles")
    def test_calendar_suggest_empty_state(self, mock_configured, mock_read_titles):
        mock_configured.return_value = []
        mock_read_titles.return_value = []

        result = self.runner.invoke(app, ["calendar-suggest"])
        self.assertEqual(result.exit_code, 0, msg=result.output)
        self.assertIn("Scanned 0 calendar event(s)", result.output)
        self.assertIn("No new project codes found", result.output)


class ConfiguredProfilesTests(unittest.TestCase):
    def test_tilde_expansion_resolves_correctly(self):
        from core.cli_calendar_suggest import _configured_profiles
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "timelog_projects.json"
            config_file.write_text(json.dumps({"projects": [{"name": "A"}]}), encoding="utf-8")

            with patch("pathlib.Path.expanduser", return_value=config_file):
                profiles = _configured_profiles("~/timelog_projects.json")
                self.assertEqual(len(profiles), 1)
                self.assertEqual(profiles[0]["name"], "A")

    def test_skip_malformed_unnamed_profile_gracefully(self):
        from core.cli_calendar_suggest import _configured_profiles
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "timelog_projects.json"
            config_file.write_text(
                json.dumps({
                    "projects": [
                        {"project_id": "malformed_unnamed_profile"},  # missing "name"
                        {"name": "B", "enabled": True}
                    ]
                }),
                encoding="utf-8"
            )
            profiles = _configured_profiles(str(config_file))
            self.assertEqual(len(profiles), 1)
            self.assertEqual(profiles[0]["name"], "B")


if __name__ == "__main__":
    unittest.main()
