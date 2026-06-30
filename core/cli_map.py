"""`gittan map` — workspace + evidence mapping without full setup."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Optional

import typer
from rich.console import Console

from core.cli_app import app
from core.cli_report_status_helpers import build_report_options, resolve_timeframe_args
from core.config import default_projects_config_option
from core.map_command import map_exit_message, run_map_command
from outputs.cli_heroes import print_command_hero
from outputs.terminal_theme import STYLE_LABEL, STYLE_MUTED


@app.command("map")
def map_workspace(
    date_from: Annotated[Optional[datetime], typer.Option("--from", formats=["%Y-%m-%d"], help="Start date")] = None,
    date_to: Annotated[Optional[datetime], typer.Option("--to", formats=["%Y-%m-%d"], help="End date")] = None,
    today: Annotated[bool, typer.Option(help="Limit to today.")] = False,
    yesterday: Annotated[bool, typer.Option(help="Limit to yesterday.")] = False,
    last_week: Annotated[bool, typer.Option(help="Limit to last 7 days.")] = False,
    projects_config: Annotated[str, typer.Option(help="JSON config file")] = default_projects_config_option(),
    scan_repos: Annotated[
        bool,
        typer.Option(
            "--scan-repos",
            help="Scan local git clones and GitHub for new repo mappings (slow; skipped by default).",
        ),
    ] = False,
):
    """Map activity anchors and optionally git/GitHub repos — nothing saved without approval."""
    console = Console()
    timeframe = resolve_timeframe_args(
        date_from=date_from,
        date_to=date_to,
        today=today,
        yesterday=yesterday,
        last_3_days=False,
        last_week=last_week,
        last_14_days=False,
        last_month=False,
    )
    options = build_report_options(
        timeframe=timeframe,
        option_fields={
            "projects_config": projects_config,
            "quiet": True,
            "map_prompt": False,
            "screen_time": "off",
            "chrome_source": "off",
            "mail_source": "off",
            "calendar_source": "off",
            "source_strategy": "balanced",
        },
    )
    console.print("")
    print_command_hero(console, "map")
    console.print(f"[{STYLE_LABEL}]Project mapping[/]")
    console.print(
        f"[{STYLE_MUTED}]Anchors first (dirs, branches, session titles). "
        "Pass --scan-repos for full git/GitHub repo discovery (slow).[/]"
    )
    console.print(f"[{STYLE_MUTED}]Nothing is saved without your approval.[/]")

    anchors_applied, repo_applied, repo_hints, repo_scan_performed = run_map_command(
        console,
        options=options,
        projects_config=projects_config,
        scan_repos=scan_repos,
    )
    console.print(
        map_exit_message(
            anchors_applied=anchors_applied,
            repo_applied=repo_applied,
            had_repo_hints=bool(repo_hints),
            repo_scan_performed=repo_scan_performed,
        )
    )
    raise typer.Exit(code=0)
