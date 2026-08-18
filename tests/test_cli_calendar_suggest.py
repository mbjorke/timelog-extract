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
            ("Work", "TÖ-ABC standup"),
            ("Work", "TÖ-ABC deep work"),
            ("Work", "WIDE-ABC review"),
            ("Work", "Unrelated meeting"),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "timelog_projects.json"
            # Valid config containing an existing profile covering TÖ-ABC
            config_file.write_text(
                json.dumps({
                    "projects": [
                        {
                            "name": "ABC Project",
                            "match_terms": ["tö-abc"],
                            "enabled": True,
                        }
                    ]
                }),
                encoding="utf-8"
            )

            # We should only get suggestions for codes not covered, so WIDE-ABC should be suggested,
            # but TÖ-ABC should be excluded!
            result = self.runner.invoke(app, [
                "calendar-suggest",
                "--projects-config", str(config_file),
                "--min-count", "1",
            ])
            self.assertEqual(result.exit_code, 0, msg=result.output)
            self.assertIn("WIDE-ABC", result.output)
            self.assertNotIn("TÖ-ABC", result.output)

    @patch("core.cli_calendar_suggest.read_calendar_titles")
    def test_calendar_suggest_unparseable_json_config_fallback(self, mock_read_titles):
        mock_read_titles.return_value = [
            ("Work", "TÖ-ABC standup"),
            ("Work", "WIDE-ABC review"),
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
            self.assertIn("TÖ-ABC", result.output)
            self.assertIn("WIDE-ABC", result.output)

    @patch("core.cli_calendar_suggest.read_calendar_titles")
    def test_calendar_suggest_unparseable_json_config_json_format(self, mock_read_titles):
        mock_read_titles.return_value = [
            ("Work", "TÖ-ABC standup"),
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
            self.assertEqual(data[0]["code"], "TÖ-ABC")

    @patch("core.cli_calendar_suggest.read_calendar_titles")
    @patch("core.cli_calendar_suggest._configured_profiles")
    def test_calendar_suggest_escaping_brackets(self, mock_configured, mock_read_titles):
        mock_configured.return_value = []
        # Title contains bracket sequences and valid codes
        mock_read_titles.return_value = [
            ("Work", "[bold] ACME-CODE standup"),
            ("Work", "[bold] ACME-CODE coding"),
            ("Work", "[/] BOLD-CODE retro"),
            ("Work", "[/] BOLD-CODE retro2"),
        ]

        result = self.runner.invoke(app, ["calendar-suggest", "--min-count", "1"])
        self.assertEqual(result.exit_code, 0, msg=result.output)
        # Should render correctly with literally escaped markup inside the console output
        self.assertIn("[bold]", result.output)
        self.assertIn("[/]", result.output)
        self.assertIn("ACME-CODE", result.output)
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
    """The direct config reader that replaced load_profiles()."""

    def _write(self, tmp: str, payload) -> Path:
        path = Path(tmp) / "timelog_projects.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_tilde_path_is_expanded(self):
        """A quoted --projects-config '~/…' must resolve, not read as a literal."""
        from core.cli_calendar_suggest import _configured_profiles

        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            home.mkdir()
            self._write(str(home), {"projects": [{"name": "project-alpha"}]})
            with patch("pathlib.Path.home", return_value=home), patch.dict(
                "os.environ", {"HOME": str(home)}
            ):
                profiles = _configured_profiles("~/timelog_projects.json")
        self.assertEqual(len(profiles), 1)
        self.assertEqual(profiles[0]["name"], "project-alpha")

    def test_one_unnamed_profile_does_not_discard_the_others(self):
        """normalize_profile raises on a missing name; that must not empty the list."""
        from core.cli_calendar_suggest import _configured_profiles

        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(
                tmp,
                {"projects": [{"match_terms": ["orphan"]}, {"name": "project-beta"}]},
            )
            profiles = _configured_profiles(str(path))
        self.assertEqual([p["name"] for p in profiles], ["project-beta"])

    def test_name_alone_covers_its_own_code(self):
        """normalize_profile folds the name into match_terms, so it counts as covered."""
        from core.cli_calendar_suggest import _configured_profiles

        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(tmp, {"projects": [{"name": "TÖ-ABC"}]})
            profiles = _configured_profiles(str(path))
        self.assertIn("tö-abc", profiles[0]["match_terms"])

    def test_disabled_profile_does_not_suppress_its_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            from core.cli_calendar_suggest import _configured_profiles

            path = self._write(
                tmp, {"projects": [{"name": "project-alpha", "enabled": False}]}
            )
            self.assertEqual(_configured_profiles(str(path)), [])


if __name__ == "__main__":
    unittest.main()
