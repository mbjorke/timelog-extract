"""Shared next-step guidance for onboarding-oriented CLI commands."""

from __future__ import annotations

import shlex
from pathlib import Path

PROJECT_STATUS_PASS = "PASS"
PROJECT_STATUS_FAIL = "FAIL"
PROJECT_STATUS_SKIPPED = "SKIPPED"
PROJECT_STATUS_ACTION_REQUIRED = "ACTION_REQUIRED"


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
        if cli_on_path:
            steps.append("Run `gittan setup` for the guided path through config bootstrap, diagnostics, and a smoke report.")
            steps.append(f"Create or repair `{config_path.name}` with `gittan projects --config {shlex.quote(str(config_path))}`.")
        else:
            steps.append(f"Create `{config_path.name}` in this repository with at least one enabled project profile.")
    if not worklog_ok:
        steps.append(
            f"Create `{worklog_path}` or point Gittan at another file with `--worklog {shlex.quote(str(worklog_path))}`."
        )
    if not match_terms_ok:
        if cli_on_path:
            steps.append("Use `gittan projects` to add repo-specific `match_terms` so activity in this repo classifies cleanly.")
        else:
            steps.append("Add repo-specific `match_terms` in your project config so activity in this repo classifies cleanly.")
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
    fast: bool = False,
) -> list[str]:
    steps: list[str] = []
    if dry_run:
        setup_cmd = "gittan setup --fast" if fast else "gittan setup"
        steps.append(f"Next: run `{setup_cmd}` without `--dry-run` when you are ready to apply setup.")
        steps.append("Then: run `gittan report --today --source-summary` for your first real report.")
        steps.append("Optional: run `gittan setup-global-timelog` if you want machine-wide commit-to-worklog automation.")
        return steps

    if doctor_status == PROJECT_STATUS_ACTION_REQUIRED:
        steps.append("Next: rerun `gittan doctor` and resolve any missing PATH, permission, or source hints.")
    if projects_status == PROJECT_STATUS_FAIL:
        steps.append("Then: run `gittan projects` to repair project entries, then verify `match_terms` and worklog path.")
    if projects_status in {PROJECT_STATUS_SKIPPED, PROJECT_STATUS_ACTION_REQUIRED}:
        steps.append("Then: use `gittan projects` to review project names, `match_terms`, and worklog path.")
    if smoke_status in {PROJECT_STATUS_FAIL, PROJECT_STATUS_ACTION_REQUIRED, PROJECT_STATUS_SKIPPED}:
        steps.append("Then: run `gittan report --today --source-summary` to confirm you get a useful local report.")
    if not steps:
        steps.append("Next: run `gittan report --today --source-summary` for your first report.")
        steps.append("Optional: use `gittan projects` later if you want to refine project matching.")
    if fast:
        steps.append("Optional later: run `gittan setup-global-timelog` when you want machine-wide commit-to-worklog automation.")
    return steps


def print_next_steps(console, steps: list[str]) -> None:
    console.print("[bold]Next steps[/bold]")
    for step in steps:
        console.print(f"- {step}")
