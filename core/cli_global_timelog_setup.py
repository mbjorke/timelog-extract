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
    yes: bool = typer.Option(
        False,
        "--yes",
        help="Run recommended setup steps without interactive confirmation prompts.",
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
):
    """Run full onboarding: environment, timelog automation, config, doctor, and smoke test."""
    from rich.console import Console

    console = Console()
    run_setup_wizard(console, yes=yes, dry_run=dry_run, skip_smoke=skip_smoke)
