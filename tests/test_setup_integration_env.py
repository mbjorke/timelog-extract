"""Tests for Jira + Toggl credential env bootstrap."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from rich.console import Console

from core import setup_integration_env as sie


class AlreadySetTests(unittest.TestCase):
    def test_pass_when_all_present(self):
        env = {
            "JIRA_BASE_URL": "https://x.atlassian.net",
            "JIRA_EMAIL": "a@b.c",
            "JIRA_API_TOKEN": "tok",
        }
        with patch.dict("os.environ", env, clear=True):
            status, note, steps = sie.configure_jira_env_for_setup(
                Console(record=True), yes=False, dry_run=True
            )
        self.assertEqual(status, "PASS")
        self.assertEqual(steps, [])

    def test_yes_mode_skips_without_prompting(self):
        with patch.dict("os.environ", {}, clear=True), patch.object(
            sie, "questionary"
        ) as q:
            status, _note, steps = sie.configure_toggl_env_for_setup(
                Console(record=True), yes=True, dry_run=True
            )
        q.confirm.assert_not_called()
        self.assertEqual(status, "SKIPPED")
        self.assertTrue(any("TOGGL_API_TOKEN" in s for s in steps))


class InteractiveTests(unittest.TestCase):
    def test_declined_confirm_skips(self):
        console = Console(record=True)
        with patch.dict("os.environ", {}, clear=True), patch.object(
            sie.questionary, "confirm"
        ) as q_confirm:
            q_confirm.return_value.ask.return_value = False
            status, _note, steps = sie.configure_toggl_env_for_setup(
                console, yes=False, dry_run=True
            )
        self.assertEqual(status, "SKIPPED")
        self.assertTrue(any("toggl-sync" in s for s in steps))

    def test_toggl_dry_run_reports_actions_and_warns_on_secret(self):
        console = Console(record=True)
        with patch.dict("os.environ", {}, clear=True), patch.object(
            sie.questionary, "confirm"
        ) as q_confirm, patch.object(
            sie.questionary, "password"
        ) as q_pwd, patch.object(
            sie.questionary, "text"
        ) as q_text, patch.object(sie, "upsert_export") as upsert:
            q_confirm.return_value.ask.return_value = True
            q_pwd.return_value.ask.return_value = "secret-token"
            q_text.return_value.ask.return_value = "123456"
            status, note, steps = sie.configure_toggl_env_for_setup(
                console, yes=False, dry_run=True
            )
        self.assertEqual(status, "PASS")
        self.assertIn("dry-run", note)
        # Both fields would be written.
        self.assertEqual(upsert.call_count, 2)
        # Plaintext warning shown for the secret.
        self.assertIn("plaintext", console.export_text())
        self.assertTrue(any("gittan doctor --toggl-source auto" in s for s in steps))

    def test_partial_input_is_action_required(self):
        console = Console(record=True)
        with patch.dict("os.environ", {}, clear=True), patch.object(
            sie.questionary, "confirm"
        ) as q_confirm, patch.object(
            sie.questionary, "password"
        ) as q_pwd, patch.object(
            sie.questionary, "text"
        ) as q_text, patch.object(sie, "upsert_export"):
            q_confirm.return_value.ask.return_value = True
            q_pwd.return_value.ask.return_value = "secret-token"
            q_text.return_value.ask.return_value = ""  # workspace id left blank
            status, _note, steps = sie.configure_toggl_env_for_setup(
                console, yes=False, dry_run=True
            )
        self.assertEqual(status, "ACTION_REQUIRED")
        self.assertTrue(any("TOGGL_WORKSPACE_ID" in s for s in steps))


if __name__ == "__main__":
    unittest.main()
