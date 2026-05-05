"""Tests for managed global timelog hook refresh behavior."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rich.console import Console

from core import global_timelog_machine_setup as machine_setup


class GlobalTimelogMachineSetupTests(unittest.TestCase):
    def test_updates_stale_managed_hook_to_latest_body(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            hooks_dir = home / ".githooks"
            hook_path = hooks_dir / "post-commit"
            ignore_path = home / ".gitignore_global"
            cfg_dir = home / ".gittan"
            hooks_dir.mkdir(parents=True, exist_ok=True)
            cfg_dir.mkdir(parents=True, exist_ok=True)
            hook_path.write_text(
                "#!/bin/zsh\n# managed-by-gittan: global-timelog\nset -e\nTIMELOG_FILE=\"$ROOT_DIR/TIMELOG.md\"\n",
                encoding="utf-8",
            )
            ignore_path.write_text("", encoding="utf-8")
            (cfg_dir / "timelog_filename").write_text("TIMELOG.md\n", encoding="utf-8")
            console = Console(record=True, width=160)

            with patch.object(machine_setup.Path, "home", return_value=home), patch.object(
                machine_setup, "_run_git_config", return_value=None
            ), patch.object(
                machine_setup, "_read_global_git_config", return_value=""
            ), patch.object(
                machine_setup, "_configure_timelog_scope_and_name", return_value=None
            ):
                machine_setup.run_global_timelog_setup(console, yes=True, dry_run=False)

            self.assertEqual(hook_path.read_text(encoding="utf-8"), machine_setup.HOOK_BODY)
            output = console.export_text()
            self.assertIn("updating to latest script", output)


if __name__ == "__main__":
    unittest.main()
