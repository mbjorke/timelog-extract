"""Typer command: search (fast all-events timeline view; shares report path)."""
from __future__ import annotations

from datetime import datetime
from typing import Annotated, Optional

import typer

from core.cli_app import app
from core.cli_report_status_helpers import (
    build_report_options as _build_report_options,
    resolve_timeframe_args as _resolve_timeframe_args,
)
from core.config import default_projects_config_option
from core.noise_profiles import DEFAULT_LOVABLE_NOISE_PROFILE, DEFAULT_NOISE_PROFILE


@app.command()
def search(
    date_from: Annotated[Optional[datetime], typer.Option("--from", formats=["%Y-%m-%d"], help="Start date (YYYY-MM-DD)")] = None,
    date_to: Annotated[Optional[datetime], typer.Option("--to", formats=["%Y-%m-%d"], help="End date (YYYY-MM-DD)")] = None,
    today: Annotated[bool, typer.Option(help="Limit to today.")] = False,
    yesterday: Annotated[bool, typer.Option(help="Limit to yesterday.")] = False,
    last_3_days: Annotated[bool, typer.Option(help="Limit to last 3 days.")] = False,
    last_week: Annotated[bool, typer.Option(help="Limit to last 7 days.")] = False,
    last_14_days: Annotated[bool, typer.Option(help="Limit to last 14 days.")] = False,
    last_month: Annotated[bool, typer.Option(help="Limit to last 30 days.")] = False,
    projects_config: Annotated[str, typer.Option(help="JSON config file")] = default_projects_config_option(),
    project: Annotated[Optional[str], typer.Option("--project", help="Filter to one project name")] = None,
    customer: Annotated[Optional[str], typer.Option(help="Filter by customer")] = None,
    source_summary: Annotated[bool, typer.Option(help="Show source counts")] = False,
    chrome_raw: Annotated[
        bool,
        typer.Option(
            "--chrome-raw",
            help=(
                "Near-complete Chrome history for triage (still excludes claude.ai and gemini.google.com "
                "URLs covered by other collectors). Sensitive URLs may appear in terminal output; "
                "--format json redacts Chrome detail text to titles only while this flag is on."
            ),
        ),
    ] = False,
    chrome_contains_url: Annotated[
        Optional[str],
        typer.Option(
            "--chrome-contains-url",
            "--contains-url",
            help="With --chrome-raw: keep visits whose URL contains this substring (case-insensitive).",
        ),
    ] = None,
    attribution_mode: Annotated[Optional[str], typer.Option("--attribution-mode", help="Preset for comparisons: commit-first (GitHub-focused; disables worklog unless --worklog is set)")] = None,
    output_format: Annotated[str, typer.Option("--format", help="terminal/json")] = "terminal",
    noise_profile: Annotated[
        str,
        typer.Option("--noise-profile", "--global-noise-profile", help="Noise filtering profile for collector diagnostics: lenient, strict, or ultra-strict."),
    ] = DEFAULT_NOISE_PROFILE,
    lovable_noise_profile: Annotated[
        str,
        typer.Option("--lovable-noise-profile", "--lovable-profile", help="Lovable storage-signal filtering: normal, balanced, or strict."),
    ] = DEFAULT_LOVABLE_NOISE_PROFILE,
    quiet: Annotated[bool, typer.Option(help="Suppress progress")] = False,
):
    """Search timeline quickly with all events shown (shares report execution path).

    Common use cases:
    - Why did project X get time? `gittan search --today --project "X" --noise-profile lenient --lovable-noise-profile balanced`
    - Conservative audit view: `gittan search --today --project "X" --noise-profile ultra-strict --lovable-noise-profile strict`
    - Raw Chrome triage: `gittan search --chrome-raw` (see `--chrome-raw` help for privacy / JSON behavior).
    """
    from core.report_cli import run_timelog_cli

    timeframe = _resolve_timeframe_args(
        date_from=date_from,
        date_to=date_to,
        today=today,
        yesterday=yesterday,
        last_3_days=last_3_days,
        last_week=last_week,
        last_14_days=last_14_days,
        last_month=last_month,
    )
    options = _build_report_options(
        timeframe=timeframe,
        option_fields={
            "projects_config": projects_config,
            "only_project": project,
            "customer": customer,
            "source_summary": source_summary,
            "chrome_raw": chrome_raw,
            "chrome_contains_url": chrome_contains_url,
            "output_format": output_format,
            "noise_profile": noise_profile,
            "lovable_noise_profile": lovable_noise_profile,
            "attribution_mode": attribution_mode,
            "quiet": quiet,
        },
        overrides={"all_events": True},
    )
    run_timelog_cli(options)
