"""Shared next-step guidance for onboarding-oriented CLI commands."""

from __future__ import annotations

import shlex
from pathlib import Path


def build_doctor_next_steps(
    *,
    cli_on_path: bool,
    projects_config_ok: bool,
    worklog_ok: bool,
    match_terms_ok: bool = True,
    config_path: Path,
    worklog_path: Path,
) -> list[str]:
    steps: list[str] = []
    if not projects_config_ok:
        steps.append("Run `gittan setup` for the guided path through config bootstrap, diagnostics, and a smoke report.")
    if not projects_config_ok:
        steps.append(f"Create or repair `{config_path.name}` with `gittan projects --config {shlex.quote(str(config_path))}`.")
    if not worklog_ok:
        steps.append(
            f"Create `{worklog_path}` or point Gittan at another file with `--worklog {shlex.quote(str(worklog_path))}`."
        )
    if not match_terms_ok:
        steps.append("Use `gittan projects` to add repo-specific `match_terms` so activity in this repo classifies cleanly.")
    if not cli_on_path:
        steps.append("Run `pipx ensurepath`, reload your shell, then rerun `gittan doctor`.")
    if not steps:
        steps.append("Run `gittan report --today --source-summary` for a first local report.")
        steps.append("Use `gittan projects` if you want to refine project matching before reporting.")
    return steps


def build_setup_next_steps(
    *,
    dry_run: bool,
    projects_status: str,
    doctor_status: str,
    smoke_status: str,
) -> list[str]:
    steps: list[str] = []
    if dry_run:
        steps.append("Run `gittan setup` without `--dry-run` when you are ready to apply the recommended setup.")
        steps.append("If you only want commit-to-worklog automation, run `gittan setup-global-timelog`.")
        steps.append("After setup, run `gittan report --today --source-summary` for a first report.")
        return steps

    if doctor_status == "ACTION_REQUIRED":
        steps.append("Rerun `gittan doctor` and follow the missing-path or permission hints it prints.")
    if projects_status in {"PASS", "SKIPPED", "ACTION_REQUIRED"}:
        steps.append("Use `gittan projects` to review project names, match terms, and the configured worklog path.")
    if smoke_status in {"FAIL", "ACTION_REQUIRED", "SKIPPED"}:
        steps.append("Run `gittan report --today --source-summary` to confirm you get a useful local report.")
    if not steps:
        steps.append("Run `gittan report --today --source-summary` for your first report.")
        steps.append("Use `gittan projects` later if you want to refine project matching.")
    return steps


def print_next_steps(console, steps: list[str]) -> None:
    console.print("[bold]Next steps[/bold]")
    for step in steps:
        console.print(f"- {step}")
