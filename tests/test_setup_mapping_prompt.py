"""Project mapping in `gittan setup` is offered, not imposed (GH-526)."""

from __future__ import annotations

import unittest
from contextlib import ExitStack
from unittest.mock import patch

from rich.console import Console

from core.global_timelog_setup_lib import MAPPING_PROMPT_TEXT, run_setup_wizard


class _FakeConfirm:
    """Stand-in for `questionary.confirm(...)` that records its arguments."""

    def __init__(self, answer: bool, calls: list[tuple[str, bool]]):
        self._answer = answer
        self._calls = calls

    def __call__(self, message, default=True, **_kwargs):
        self._calls.append((message, default))
        return self

    def ask(self):
        return self._answer


def _run_wizard_with_mapping_prompt(answer: bool) -> tuple[Console, list[tuple[str, bool]], list[str]]:
    console = Console(record=True, width=200)
    calls: list[tuple[str, bool]] = []
    mapping_runs: list[str] = []

    def _fake_mapping_wizard(_console, **_kwargs):
        mapping_runs.append("ran")
        return "PASS", "Mapped."

    with ExitStack() as stack:
        for target in (
            "_print_setup_header",
            "_print_environment_status",
            "_print_setup_environment_loaded",
        ):
            stack.enter_context(patch(f"core.global_timelog_setup_lib.{target}"))
        stack.enter_context(
            patch(
                "core.global_timelog_setup_lib.configure_github_env_for_setup",
                return_value=("PASS", "ok", []),
            )
        )
        stack.enter_context(
            patch(
                "core.global_timelog_setup_lib.configure_jira_env_for_setup",
                return_value=("SKIPPED", "skipped", []),
            )
        )
        stack.enter_context(
            patch(
                "core.global_timelog_setup_lib.configure_toggl_env_for_setup",
                return_value=("SKIPPED", "skipped", []),
            )
        )
        stack.enter_context(
            patch(
                "core.global_timelog_setup_lib._ensure_minimal_projects_config",
                return_value=("PASS", "ok", []),
            )
        )
        stack.enter_context(
            patch("core.global_timelog_setup_lib._run_doctor_check", return_value="PASS")
        )
        stack.enter_context(
            patch(
                "core.global_timelog_setup_lib._run_mapping_wizard_with_summary",
                side_effect=_fake_mapping_wizard,
            )
        )
        stack.enter_context(
            patch(
                "core.global_timelog_setup_lib.questionary.confirm",
                new=_FakeConfirm(answer, calls),
            )
        )
        run_setup_wizard(
            console,
            yes=True,
            dry_run=False,
            skip_smoke=True,
            bootstrap_root=None,
            fast=True,
            prompt_project_mapping=True,
        )
    return console, calls, mapping_runs


class SetupMappingPromptTests(unittest.TestCase):
    def test_mapping_prompt_defaults_to_no_and_says_it_is_optional(self):
        _console, calls, _runs = _run_wizard_with_mapping_prompt(answer=False)

        self.assertEqual(len(calls), 1, "mapping should be the only prompt in this path")
        message, default = calls[0]
        self.assertIs(default, False)
        self.assertEqual(message, MAPPING_PROMPT_TEXT)
        self.assertIn("optional", message.lower())
        self.assertIn("gittan map", message)

    def test_declining_mapping_completes_setup_with_a_skipped_row(self):
        console, _calls, mapping_runs = _run_wizard_with_mapping_prompt(answer=False)

        output = console.export_text()
        self.assertEqual(mapping_runs, [])
        self.assertIn("Setup wizard completed.", output)
        self.assertIn("Step 3: Project Mapping", output)
        self.assertIn("SKIPPED", output)
        self.assertNotIn("FAIL", output)
        # Step 4 still runs after the decline.
        self.assertIn("Step 4: Doctor Check", output)

    def test_declining_mapping_does_not_send_the_operator_back_into_setup(self):
        console, _calls, _runs = _run_wizard_with_mapping_prompt(answer=False)

        output = console.export_text()
        self.assertIn("gittan map", output)
        self.assertNotIn("setup` again", output)

    def test_accepting_the_prompt_still_runs_the_mapping_wizard(self):
        console, _calls, mapping_runs = _run_wizard_with_mapping_prompt(answer=True)

        self.assertEqual(mapping_runs, ["ran"])
        self.assertIn("Step 3: Project Mapping", console.export_text())


if __name__ == "__main__":
    unittest.main()
