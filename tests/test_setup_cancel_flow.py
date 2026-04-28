from __future__ import annotations

import unittest
from unittest.mock import patch

import typer
from rich.console import Console

from core.global_timelog_setup_lib import run_setup_wizard


class SetupCancelFlowTests(unittest.TestCase):
    def test_cancel_in_project_mapping_exits_with_code_130(self):
        console = Console(record=True, width=120)
        with patch("core.global_timelog_setup_lib._print_setup_header"), patch(
            "core.global_timelog_setup_lib._print_environment_status"
        ), patch(
            "core.global_timelog_setup_lib._print_setup_environment_loaded"
        ), patch(
            "core.global_timelog_setup_lib.configure_github_env_for_setup",
            return_value=("PASS", "ok", []),
        ), patch(
            "core.global_timelog_setup_lib._ensure_minimal_projects_config",
            return_value=("PASS", "ok", []),
        ), patch(
            "core.global_timelog_setup_lib.run_project_identity_wizard",
            side_effect=KeyboardInterrupt("cancel"),
        ):
            with self.assertRaises(typer.Exit) as ctx:
                run_setup_wizard(
                    console,
                    yes=False,
                    dry_run=True,
                    skip_smoke=True,
                    bootstrap_root=None,
                    fast=True,
                )
        self.assertEqual(ctx.exception.exit_code, 130)


if __name__ == "__main__":
    unittest.main()

