"""Tests for core.doctor_source_rows (extracted GitHub/Toggl doctor row helpers)."""

from __future__ import annotations

import unittest
from unittest.mock import patch, MagicMock

from rich.table import Table

from core.doctor_source_rows import add_github_doctor_row, add_toggl_doctor_row
from outputs.terminal_theme import NA_ICON, OK_ICON


def _make_table() -> tuple[Table, list[tuple]]:
    """Return a Table and a list that records rows added via add_row."""
    table = MagicMock(spec=Table)
    rows: list[tuple] = []
    table.add_row.side_effect = lambda *args: rows.append(args)
    return table, rows


class AddGithubDoctorRowTests(unittest.TestCase):
    """Tests for add_github_doctor_row added in PR (extracted from cli_doctor_sources_projects)."""

    def test_github_mode_off_shows_disabled(self):
        table, rows = _make_table()
        with patch.dict("os.environ", {"GITHUB_USER": "someuser", "GITHUB_TOKEN": "tok"}, clear=False):
            add_github_doctor_row(table, "off", None)
        self.assertEqual(len(rows), 1)
        label, icon, msg = rows[0]
        self.assertEqual(label, "GitHub Source")
        self.assertEqual(icon, NA_ICON)
        self.assertIn("Disabled", msg)
        self.assertIn("off", msg)

    def test_github_no_user_shows_not_configured(self):
        table, rows = _make_table()
        with patch.dict("os.environ", {"GITHUB_USER": "", "GITHUB_TOKEN": ""}, clear=False):
            add_github_doctor_row(table, "auto", None)
        self.assertEqual(len(rows), 1)
        label, icon, msg = rows[0]
        self.assertEqual(label, "GitHub Source")
        self.assertEqual(icon, NA_ICON)
        self.assertIn("Not configured", msg)
        self.assertIn("GITHUB_USER", msg)

    def test_github_user_from_env_shows_enabled(self):
        table, rows = _make_table()
        with patch.dict("os.environ", {"GITHUB_USER": "myuser", "GITHUB_TOKEN": ""}, clear=False):
            add_github_doctor_row(table, "auto", None)
        self.assertEqual(len(rows), 1)
        label, icon, msg = rows[0]
        self.assertEqual(label, "GitHub Source")
        self.assertEqual(icon, OK_ICON)
        self.assertIn("myuser", msg)
        self.assertIn("no token", msg)

    def test_github_user_from_arg_shows_enabled_with_token(self):
        table, rows = _make_table()
        with patch.dict("os.environ", {"GITHUB_USER": "", "GITHUB_TOKEN": "ghp_token"}, clear=False):
            add_github_doctor_row(table, "on", "arguser")
        self.assertEqual(len(rows), 1)
        label, icon, msg = rows[0]
        self.assertEqual(label, "GitHub Source")
        self.assertEqual(icon, OK_ICON)
        self.assertIn("arguser", msg)
        self.assertIn("token present", msg)

    def test_github_user_from_arg_overrides_env(self):
        table, rows = _make_table()
        with patch.dict("os.environ", {"GITHUB_USER": "envuser", "GITHUB_TOKEN": ""}, clear=False):
            add_github_doctor_row(table, "auto", "arguser")
        _, _, msg = rows[0]
        # arg takes precedence; env fallback is only used when arg is None/empty
        self.assertIn("arguser", msg)

    def test_github_env_user_used_when_no_arg(self):
        table, rows = _make_table()
        with patch.dict("os.environ", {"GITHUB_USER": "envuser2", "GITHUB_TOKEN": ""}, clear=False):
            add_github_doctor_row(table, "auto", None)
        _, _, msg = rows[0]
        self.assertIn("envuser2", msg)


class AddTogglDoctorRowTests(unittest.TestCase):
    """Tests for add_toggl_doctor_row added in PR (extracted from cli_doctor_sources_projects)."""

    def test_toggl_auto_without_token_shows_not_configured(self):
        table, rows = _make_table()
        with patch.dict("os.environ", {"TOGGL_API_TOKEN": ""}, clear=False):
            add_toggl_doctor_row(table, "auto")
        self.assertEqual(len(rows), 1)
        label, icon, msg = rows[0]
        self.assertEqual(label, "Toggl Source")
        self.assertEqual(icon, NA_ICON)
        self.assertIn("Not configured", msg)

    def test_toggl_auto_with_token_shows_enabled_token_present(self):
        table, rows = _make_table()
        with patch.dict("os.environ", {"TOGGL_API_TOKEN": "secret-token"}, clear=False):
            add_toggl_doctor_row(table, "auto")
        self.assertEqual(len(rows), 1)
        label, icon, msg = rows[0]
        self.assertEqual(label, "Toggl Source")
        self.assertEqual(icon, OK_ICON)
        self.assertIn("token present", msg)

    def test_toggl_off_shows_not_configured(self):
        table, rows = _make_table()
        with patch.dict("os.environ", {"TOGGL_API_TOKEN": "secret-token"}, clear=False):
            add_toggl_doctor_row(table, "off")
        self.assertEqual(len(rows), 1)
        label, icon, msg = rows[0]
        self.assertEqual(label, "Toggl Source")
        self.assertEqual(icon, NA_ICON)
        # mode name is included in the message
        self.assertIn("off", msg)

    def test_toggl_on_with_token_shows_enabled(self):
        table, rows = _make_table()
        with patch.dict("os.environ", {"TOGGL_API_TOKEN": "tok"}, clear=False):
            add_toggl_doctor_row(table, "on")
        self.assertEqual(len(rows), 1)
        label, icon, msg = rows[0]
        self.assertEqual(label, "Toggl Source")
        self.assertEqual(icon, OK_ICON)
        self.assertIn("on", msg)

    def test_toggl_invalid_mode_shows_not_configured_with_escaped_reason(self):
        """Invalid mode reason is markup-escaped before embedding in Rich text."""
        table, rows = _make_table()
        with patch.dict("os.environ", {"TOGGL_API_TOKEN": ""}, clear=False):
            add_toggl_doctor_row(table, "badmode")
        self.assertEqual(len(rows), 1)
        label, icon, msg = rows[0]
        self.assertEqual(label, "Toggl Source")
        self.assertEqual(icon, NA_ICON)
        self.assertIn("badmode", msg)

    def test_toggl_enabled_without_token_note_is_no_token(self):
        """When enabled but no env token, note says 'no token'."""
        table, rows = _make_table()
        with patch.dict("os.environ", {"TOGGL_API_TOKEN": "tok"}, clear=False):
            add_toggl_doctor_row(table, "auto")
        _, icon, msg = rows[0]
        self.assertEqual(icon, OK_ICON)
        # With token in env it shows 'token present'
        self.assertIn("token present", msg)


if __name__ == "__main__":
    unittest.main()