from __future__ import annotations

import unittest
from unittest.mock import patch

import typer
from rich.console import Console

from core.global_timelog_setup_lib import _run_mapping_wizard_with_summary, run_setup_wizard


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
            "core.global_timelog_setup_lib.configure_jira_env_for_setup",
            return_value=("SKIPPED", "skipped", []),
        ), patch(
            "core.global_timelog_setup_lib.configure_toggl_env_for_setup",
            return_value=("SKIPPED", "skipped", []),
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

    def test_mapping_summary_maps_skip_outcome(self):
        with patch(
            "core.global_timelog_setup_lib.run_project_identity_wizard",
            return_value="Skip this step",
        ):
            status, notes = _run_mapping_wizard_with_summary(Console(record=True), dry_run=False)
        self.assertEqual(status, "SKIPPED")
        self.assertEqual(notes, "User skipped mapping.")

    def test_setup_keeps_triage_as_optional_follow_up(self):
        console = Console(record=True, width=120)
        with patch("core.global_timelog_setup_lib._print_setup_header"), patch(
            "core.global_timelog_setup_lib._print_environment_status"
        ), patch(
            "core.global_timelog_setup_lib._print_setup_environment_loaded"
        ), patch(
            "core.global_timelog_setup_lib.configure_github_env_for_setup",
            return_value=("PASS", "ok", []),
        ), patch(
            "core.global_timelog_setup_lib.configure_jira_env_for_setup",
            return_value=("SKIPPED", "skipped", []),
        ), patch(
            "core.global_timelog_setup_lib.configure_toggl_env_for_setup",
            return_value=("SKIPPED", "skipped", []),
        ), patch(
            "core.global_timelog_setup_lib._ensure_minimal_projects_config",
            return_value=("PASS", "ok", []),
        ), patch(
            "core.global_timelog_setup_lib._run_doctor_check",
            return_value="PASS",
        ), patch(
            "core.global_timelog_setup_lib.build_setup_next_steps",
            return_value=[],
        ), patch(
            "core.global_timelog_setup_lib.print_next_steps"
        ), patch(
            "core.global_timelog_setup_lib.run_project_identity_wizard",
            return_value="Skip this step",
        ):
            run_setup_wizard(
                console,
                yes=False,
                dry_run=True,
                skip_smoke=True,
                bootstrap_root=None,
                fast=True,
            )
        output = console.export_text()
        self.assertIn("Step 5: Triage Review (optional)", output)
        self.assertIn("Not run inside setup", output)

if __name__ == "__main__":
    unittest.main()

