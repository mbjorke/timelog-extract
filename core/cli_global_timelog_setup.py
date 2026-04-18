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
    one_click: bool = typer.Option(
        False,
        "--one-click",
        help="Run one-click setup with recommended defaults and no prompts (default behavior).",
    ),
    interactive: bool = typer.Option(
        False,
        "--interactive",
        help="Use interactive prompts instead of default one-click behavior.",
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
):
    """
    Run the full onboarding wizard covering environment setup, timelog automation, configuration, health checks, and a final smoke test.
    
    Parameters:
    	one_click (bool): Use recommended defaults and suppress interactive prompts.
    	interactive (bool): Use interactive prompts instead of default automated choices.
    	yes (bool): Alias to proceed with recommended steps without confirmation prompts.
    	dry_run (bool): Show planned actions without modifying files or git configuration.
    	skip_smoke (bool): Skip the final smoke report step.
    	bootstrap_root (str | None): Root directory to scan for nearby git repositories during project bootstrap.
    
    Raises:
    	typer.BadParameter: If both `interactive` and `one_click` are enabled simultaneously.
    """
    from rich.console import Console

    if interactive and one_click:
        raise typer.BadParameter("Cannot use both --interactive and --one-click; choose one")

    console = Console()
    auto_yes = not interactive
    if yes or one_click:
        auto_yes = True
    run_setup_wizard(console, yes=auto_yes, dry_run=dry_run, skip_smoke=skip_smoke, bootstrap_root=bootstrap_root)
