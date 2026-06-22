"""Typer commands: report, search."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Optional

import click
import typer

from core.cli_app import app
from core.cli_report_status_helpers import (
    build_report_options as _build_report_options,
    resolve_timeframe_args as _resolve_timeframe_args,
)
from core.config import default_projects_config_option
from core.noise_profiles import DEFAULT_LOVABLE_NOISE_PROFILE, DEFAULT_NOISE_PROFILE


@app.command()
def report(
    ctx: typer.Context,
    date_from: Annotated[Optional[datetime], typer.Option("--from", formats=["%Y-%m-%d"], help="Start date (YYYY-MM-DD)")] = None,
    date_to: Annotated[Optional[datetime], typer.Option("--to", formats=["%Y-%m-%d"], help="End date (YYYY-MM-DD)")] = None,
    today: Annotated[bool, typer.Option(help="Limit to today.")] = False,
    yesterday: Annotated[bool, typer.Option(help="Limit to yesterday.")] = False,
    last_3_days: Annotated[bool, typer.Option(help="Limit to last 3 days.")] = False,
    last_week: Annotated[bool, typer.Option(help="Limit to last 7 days.")] = False,
    last_14_days: Annotated[bool, typer.Option(help="Limit to last 14 days.")] = False,
    last_month: Annotated[bool, typer.Option(help="Limit to last 30 days.")] = False,
    projects_config: Annotated[str, typer.Option(help="JSON config file")] = default_projects_config_option(),
    keywords: Annotated[str, typer.Option(help="Fallback keywords")] = "",
    project: Annotated[str, typer.Option(help="Fallback project name")] = "default-project",
    email: Annotated[str, typer.Option(help="Fallback email")] = "",
    min_session: Annotated[int, typer.Option(help="Min mins per AI session")] = 15,
    min_session_passive: Annotated[int, typer.Option(help="Min mins per passive session")] = 5,
    gap_minutes: Annotated[int, typer.Option(help="Session gap threshold")] = 15,
    chrome_collapse_minutes: Annotated[int, typer.Option(help="Chrome dedupe window")] = 12,
    chrome_source: Annotated[str, typer.Option(help="on/off")] = "on",
    mail_source: Annotated[str, typer.Option(help="auto/on/off")] = "auto",
    github_source: Annotated[str, typer.Option(help="auto/on/off")] = "auto",
    calendar_source: Annotated[str, typer.Option(help="on/off (opt-in; reads local macOS Calendar)")] = "off",
    calendar_names: Annotated[Optional[str], typer.Option(help="Calendars to read with roles, e.g. 'TimeReport:primary_claim,Work:scheduled_context'")] = None,
    github_user: Annotated[
        Optional[str],
        typer.Option(help="GitHub login(s) for public events; comma-separated for multiple accounts"),
    ] = None,
    attribution_mode: Annotated[Optional[str], typer.Option("--attribution-mode", help="Preset for comparisons: commit-first (GitHub-focused; disables worklog unless --worklog is set)")] = None,
    exclude: Annotated[str, typer.Option(help="Exclude keywords")] = "",
    worklog: Annotated[Optional[str], typer.Option(help="Path to a worklog file (legacy fallback may be TIMELOG.md)")] = None,
    worklog_format: Annotated[str, typer.Option(help="auto/md/gtimelog")] = "auto",
    source_strategy: Annotated[str, typer.Option(help="auto/worklog-first/balanced")] = "auto",
    screen_time: Annotated[str, typer.Option(help="auto/on/off")] = "auto",
    include_uncategorized: Annotated[bool, typer.Option(help="Show uncategorized")] = False,
    only_project: Annotated[Optional[str], typer.Option(help="Filter by project")] = None,
    customer: Annotated[Optional[str], typer.Option(help="Filter by customer")] = None,
    all_events: Annotated[bool, typer.Option(help="Legacy alias (full session list is default).")] = False,
    compact: Annotated[
        bool,
        typer.Option("--compact", help="Dense session tree: hide IDE log noise."),
    ] = False,
    source_summary: Annotated[bool, typer.Option(help="Show source counts")] = False,
    weekly: Annotated[bool, typer.Option("--weekly", help="Add an ISO week × project hours pivot")] = False,
    narrative: Annotated[bool, typer.Option(help="Executive summary")] = False,
    invoice_pdf: Annotated[bool, typer.Option(help="Generate PDF")] = False,
    invoice_pdf_file: Annotated[Optional[str], typer.Option(help="PDF path")] = None,
    billable_unit: Annotated[float, typer.Option(help="Round to N hours")] = 0.0,
    output_format: Annotated[str, typer.Option("--format", help="terminal/json")] = "terminal",
    quiet: Annotated[bool, typer.Option(help="Suppress progress")] = False,
    json_file: Annotated[Optional[str], typer.Option(help="Write JSON to path")] = None,
    report_html: Annotated[Optional[str], typer.Option(help="Write HTML to path")] = None,
    noise_profile: Annotated[
        str,
        typer.Option(
            "--noise-profile",
            "--global-noise-profile",
            help="Noise filtering profile for collector diagnostics: lenient, strict, or ultra-strict.",
        ),
    ] = DEFAULT_NOISE_PROFILE,
    lovable_noise_profile: Annotated[
        str,
        typer.Option("--lovable-noise-profile", "--lovable-profile", help="Lovable storage-signal filtering: normal, balanced, or strict."),
    ] = DEFAULT_LOVABLE_NOISE_PROFILE,
    additive_summary: Annotated[
        bool,
        typer.Option(
            "--additive-summary",
            help="Use one primary project per session in report breakdown so rows add up to total.",
        ),
    ] = False,
    map_prompt: Annotated[
        bool,
        typer.Option(
            "--map-prompt/--no-map-prompt",
            help="After a terminal report, offer git-local project mapping suggestions (interactive TTY only).",
        ),
    ] = True,
    invoice_mode: Annotated[
        str,
        typer.Option(
            "--invoice-mode",
            help="Invoice reconciliation mode: baseline or calibrated-a.",
            click_type=click.Choice(["baseline", "calibrated-a"]),
        ),
    ] = "baseline",
    invoice_ground_truth: Annotated[
        Optional[str],
        typer.Option(
            "--invoice-ground-truth",
            help="Path to reconciliation ground-truth JSON used with --invoice-mode calibrated-a.",
        ),
    ] = None,
    git_source: Annotated[
        bool,
        typer.Option(
            "--git",
            help="Show period-scoped Git column (legacy; prefer --history for all-time).",
        ),
    ] = False,
    history_source: Annotated[
        bool,
        typer.Option(
            "--history",
            help="Show all-time Git and TIMELOG historical columns (display-only; does not change period Hours).",
        ),
    ] = False,
    shadow_log: Annotated[str, typer.Option("--shadow-log", help="on/off (opt-in): append observed evidence to a durable local store (~/.gittan/evidence/) that survives source-log rotation.")] = "off",
    shadow_replay: Annotated[str, typer.Option("--shadow-replay", help="on/off (opt-in): for a closed (past) window, restore stored evidence whose upstream source has since rotated.")] = "off",
):
    """Build detailed local evidence reports for a selected timeframe.

    Tips: `--compact` for a dense session tree; `--additive-summary` for one project per session;
    `--invoice-mode calibrated-a --invoice-ground-truth <path>` for invoice reconciliation.
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
            "keywords": keywords,
            "project": project,
            "email": email,
            "min_session": min_session,
            "min_session_passive": min_session_passive,
            "gap_minutes": gap_minutes,
            "chrome_collapse_minutes": chrome_collapse_minutes,
            "exclude": exclude,
            "worklog": worklog,
            "worklog_format": worklog_format,
            "attribution_mode": attribution_mode,
            "source_strategy": source_strategy,
            "screen_time": screen_time,
            "include_uncategorized": include_uncategorized,
            "only_project": only_project,
            "customer": customer,
            "all_events": all_events,
            "compact": compact,
            "source_summary": source_summary,
            "weekly": weekly,
            "narrative": narrative,
            "invoice_pdf": invoice_pdf,
            "invoice_pdf_file": invoice_pdf_file,
            "billable_unit": billable_unit,
            "chrome_source": chrome_source,
            "mail_source": mail_source,
            "github_source": github_source,
            "calendar_source": calendar_source,
            "calendar_names": calendar_names,
            "github_user": github_user,
            "output_format": output_format,
            "quiet": quiet,
            "json_file": json_file,
            "report_html": report_html,
            "noise_profile": noise_profile,
            "lovable_noise_profile": lovable_noise_profile,
            "additive_summary": additive_summary,
            "invoice_mode": invoice_mode,
            "invoice_ground_truth": invoice_ground_truth,
            "map_prompt": map_prompt,
            "git_source": git_source,
            "history_source": history_source,
            "shadow_log": shadow_log,
            "shadow_replay": shadow_replay,
        },
    )
    run_timelog_cli(options)

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

