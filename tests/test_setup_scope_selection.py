"""Tests for setup scope selection scan UX and fallback behavior."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rich.console import Console

from core import global_timelog_setup_lib as setup_lib


class SetupScopeSelectionTests(unittest.TestCase):
    def test_discover_git_repos_prints_progress_and_deduplicates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            cwd = root / "cwd"
            workspace = home / "Workspace"
            code = home / "Code"
            projects = home / "Projects"
            developer = home / "Developer"
            for folder in [cwd, workspace, code, projects, developer]:
                folder.mkdir(parents=True, exist_ok=True)
            shared_repo = workspace / "shared-repo"
            shared_repo.mkdir()
            (shared_repo / ".git").mkdir()
            solo_repo = projects / "solo-repo"
            solo_repo.mkdir()
            (solo_repo / ".git").mkdir()
            console = Console(record=True, width=160)
            with patch.object(setup_lib.Path, "home", return_value=home), patch.object(
                setup_lib.Path, "cwd", return_value=cwd
            ):
                repos = setup_lib._discover_git_repos(console)
            self.assertEqual(set(repos), {shared_repo.resolve(), solo_repo.resolve()})
            output = console.export_text()
            self.assertIn("Scanning local directories for git repositories", output)
            self.assertIn("candidate repos", output)
            self.assertIn("Repository scan complete", output)

    def test_choose_specific_with_no_scan_results_falls_back_to_all_scope(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg_dir = root / ".gittan"
            scope_file = cfg_dir / "timelog_repos.txt"
            filename_file = cfg_dir / "timelog_filename"
            console = Console(record=True, width=160)

            answers = iter(
                [
                    "TIMELOG.md",
                    "Choose specific repositories (slower, advanced)",
                ]
            )

            def _fake_text(*_args, **_kwargs):
                class _Prompt:
                    def ask(self_inner):
                        return next(answers)

                return _Prompt()

            def _fake_select(*_args, **_kwargs):
                class _Prompt:
                    def ask(self_inner):
                        return next(answers)

                return _Prompt()

            with patch.object(setup_lib, "GITTAN_CONFIG_DIR", cfg_dir), patch.object(
                setup_lib, "GITTAN_SCOPE_FILE", scope_file
            ), patch.object(setup_lib, "GITTAN_FILENAME_FILE", filename_file), patch.object(
                setup_lib, "_discover_git_repos", return_value=[]
            ), patch.object(
                setup_lib.questionary, "text", side_effect=_fake_text
            ), patch.object(
                setup_lib.questionary, "select", side_effect=_fake_select
            ):
                setup_lib._configure_timelog_scope_and_name(console, yes=False, dry_run=False)

            self.assertTrue(filename_file.exists())
            self.assertEqual(filename_file.read_text(encoding="utf-8").strip(), "TIMELOG.md")
            self.assertFalse(scope_file.exists())
            output = console.export_text()
            self.assertIn("No repositories found during scan", output)
            self.assertIn("Continuing safely with all repositories", output)


if __name__ == "__main__":
    unittest.main()
