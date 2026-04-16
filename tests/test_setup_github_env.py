"""Tests for setup GitHub env bootstrap helper."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rich.console import Console

from core import setup_github_env as ghe


class SetupGithubEnvTests(unittest.TestCase):
    def test_upsert_export_replaces_existing_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            profile = Path(tmp) / ".zshrc"
            profile.write_text("export GITHUB_USER=old\nexport OTHER=1\n", encoding="utf-8")
            changed = ghe._upsert_export(profile, "GITHUB_USER", "new-user", dry_run=False)
            self.assertTrue(changed)
            text = profile.read_text(encoding="utf-8")
            self.assertIn("export GITHUB_USER=new-user", text)
            self.assertIn("export OTHER=1", text)

    def test_configure_github_env_dry_run_reports_actions(self):
        console = Console(record=True)
        with patch.dict("os.environ", {}, clear=True), patch.object(
            ghe.questionary, "confirm"
        ) as q_confirm, patch.object(
            ghe, "_gh_read_token", return_value="tok"
        ), patch.object(
            ghe, "_gh_read_user", return_value="mbjorke"
        ):
            q_confirm.return_value.ask.return_value = True
            status, note, steps = ghe.configure_github_env_for_setup(console, yes=False, dry_run=True)
        self.assertEqual(status, "PASS")
        self.assertIn("dry-run", note)
        self.assertTrue(any("gittan doctor --github-source auto" in step for step in steps))

    def test_configure_github_env_requires_user_for_pass(self):
        console = Console(record=True)
        with patch.dict("os.environ", {}, clear=True), patch.object(
            ghe, "_gh_read_token", return_value="tok"
        ), patch.object(
            ghe, "_gh_read_user", return_value=""
        ):
            status, note, _steps = ghe.configure_github_env_for_setup(console, yes=True, dry_run=True)
        self.assertEqual(status, "ACTION_REQUIRED")
        self.assertIn("dry-run", note)

    def test_configure_github_env_does_not_persist_token_by_default(self):
        console = Console(record=True)
        with patch.dict("os.environ", {}, clear=True), patch.object(
            ghe, "_gh_read_token", return_value="tok"
        ), patch.object(
            ghe, "_gh_read_user", return_value="mbjorke"
        ), patch.object(ghe, "_upsert_export") as upsert:
            status, note, _steps = ghe.configure_github_env_for_setup(console, yes=True, dry_run=False)
        self.assertEqual(status, "PASS")
        self.assertIn("GITHUB_USER", note)
        self.assertEqual(upsert.call_count, 1)
        _profile_path, key, value = upsert.call_args.args
        self.assertEqual(key, "GITHUB_USER")
        self.assertEqual(value, "mbjorke")
        self.assertEqual(upsert.call_args.kwargs.get("dry_run"), False)

    def test_configure_github_env_missing_user_adds_actionable_step(self):
        console = Console(record=True)
        with patch.dict("os.environ", {}, clear=True), patch.object(
            ghe, "_gh_read_token", return_value="tok"
        ), patch.object(
            ghe, "_gh_read_user", return_value=""
        ):
            status, _note, steps = ghe.configure_github_env_for_setup(console, yes=True, dry_run=True)
        self.assertEqual(status, "ACTION_REQUIRED")
        self.assertTrue(any("Set GITHUB_USER manually" in step for step in steps))


if __name__ == "__main__":
    unittest.main()

