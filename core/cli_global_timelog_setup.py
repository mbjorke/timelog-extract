"""Typer commands: interactive setup and global timelog automation."""

from __future__ import annotations

import typer

from core.cli_app import app
from core.global_timelog_setup_lib import run_global_timelog_setup, run_setup_wizard


@app.command("setup-global-timelog")
def setup_global_timelog(
    yes: bool = typer.Option(
        False,
        "--yes",
        help="Apply setup without interactive confirmation prompts.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show planned actions without changing files or git config.",
    ),
):
    """Interactive guide to configure machine-wide TIMELOG automation."""
    from rich.console import Console

    console = Console()
    run_global_timelog_setup(console, yes=yes, dry_run=dry_run)


@app.command("setup")
def setup_wizard(
    fast: bool = typer.Option(
        False,
        "--fast",
        help="Run a faster onboarding path focused on project config + doctor (skips global timelog and smoke).",
    ),
    one_click: bool = typer.Option(
        False,
        "--one-click",
        help="Run one-click setup with recommended defaults and no prompts (default behavior).",
    ),
    interactive: bool = typer.Option(
        False,
        "--interactive",
        help="Force interactive prompts; default mode may still prompt for setup choices unless --yes/--one-click/--fast is used.",
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        help="Run recommended setup steps without interactive confirmation prompts (legacy alias for default).",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show planned actions without changing files or git config.",
    ),
    skip_smoke: bool = typer.Option(
        False,
        "--skip-smoke",
        help="Skip final smoke report step.",
    ),
    bootstrap_root: str | None = typer.Option(
        None,
        "--bootstrap-root",
        help="Root directory to scan for nearby git repositories during project bootstrap.",
    ),
    bootstrap_repos: bool = typer.Option(
        False,
        "--bootstrap-repos",
        help=(
            "Opt in to repo bootstrap merge-write when project config already exists. "
            "Creates a backup and requires confirmation before overwriting timelog_projects.json."
        ),
    ),
):
    """
    Run one-click onboarding: setup, top project/customer seeds, doctor, and a first smoke report.
    
    Parameters:
        fast (bool): Use the streamlined onboarding path focused on quick first-report readiness.
    	one_click (bool): Use recommended defaults and suppress interactive prompts.
    	interactive (bool): Use interactive prompts instead of default automated choices.
    	yes (bool): Alias to proceed with recommended steps without confirmation prompts.
    	dry_run (bool): Show planned actions without modifying files or git configuration.
    	skip_smoke (bool): Skip the final smoke report step.
    	bootstrap_root (str | None): Root directory to scan for nearby git repositories during project bootstrap.
    	bootstrap_repos (bool): When set, allow repo bootstrap merge-write on existing valid project config (backup + confirmation).
    
    Raises:
    	typer.BadParameter: If both `interactive` and `one_click` are enabled simultaneously.
    """
    from rich.console import Console

    if interactive and (one_click or fast or yes):
        raise typer.BadParameter("Cannot use --interactive together with --one-click/--fast/--yes; choose one mode")

    console = Console()
    explicit_non_interactive = yes or one_click or fast
    auto_yes = explicit_non_interactive or not interactive
    prompt_project_mapping = (not interactive) and (not explicit_non_interactive)
    run_setup_wizard(
        console,
        yes=auto_yes,
        dry_run=dry_run,
        skip_smoke=skip_smoke,
        bootstrap_root=bootstrap_root,
        bootstrap_repos=bootstrap_repos,
        fast=fast,
        prompt_project_mapping=prompt_project_mapping,
    )
