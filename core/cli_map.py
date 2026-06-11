"""`gittan map` — workspace + evidence mapping without full setup."""

from __future__ import annotations

import time
from datetime import datetime
from typing import Annotated, Optional

import typer
from rich.console import Console

from core.cli_app import app
from core.cli_report_status_helpers import build_report_options, resolve_timeframe_args
from core.config import default_projects_config_option
from core.mapping_assistant import run_interactive_mapping_flow
from core.mapping_review import build_mapping_review
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
):
    """Map git remotes and new GitHub repos to projects — nothing saved without approval."""
    from core.report_service import run_timelog_report

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
    console.print(f"[{STYLE_LABEL}]Workspace mapping[/]")
    console.print(f"[{STYLE_MUTED}]Nothing is saved without your approval.[/]")

    collect_started = time.perf_counter()
    with console.status(f"[{STYLE_LABEL}]Collecting git and GitHub signals…[/]"):
        report_started = time.perf_counter()
        report = run_timelog_report(options.projects_config, options.date_from, options.date_to, options)
        report_elapsed = time.perf_counter() - report_started
        events = list(getattr(report, "all_events", None) or getattr(report, "included_events", []) or [])
        review_started = time.perf_counter()
        review = build_mapping_review(
            events,
            report.profiles,
            dt_from=getattr(report, "dt_from", None),
            dt_to=getattr(report, "dt_to", None),
            local_tz=getattr(report, "dt_from", None).tzinfo if getattr(report, "dt_from", None) else None,
        )
        review_elapsed = time.perf_counter() - review_started
    collect_elapsed = time.perf_counter() - collect_started
    console.print(
        f"[{STYLE_MUTED}]Signals collected in {collect_elapsed:.1f}s "
        f"(report {report_elapsed:.1f}s, mapping review {review_elapsed:.1f}s).[/]"
    )
    if review.change_count() == 0:
        console.print(f"[{STYLE_MUTED}]No suggested project mapping changes for this window.[/]")
        raise typer.Exit(code=0)

    config = str(getattr(report, "config_path", None) or projects_config)
    applied = run_interactive_mapping_flow(
        console,
        [],
        report.profiles,
        config,
        review=review,
    )
    if applied:
        console.print("[dim]Re-run `gittan report` for the same window to verify project hours.[/dim]")
