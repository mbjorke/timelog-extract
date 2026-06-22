"""Typer commands: report, status."""
from __future__ import annotations

from datetime import datetime
from typing import Annotated, Optional

import click
import typer

from core.cli_app import app
from core.cli_date_range import resolve_date_window
from core.cli_options import TimelogRunOptions
from core.cli_report_status_helpers import (
    build_report_options as _build_report_options,
    capture_shadow_log_line as _capture_shadow_log_line,
    resolve_timeframe_args as _resolve_timeframe_args,
)
from core.config import default_projects_config_option
from core.noise_profiles import DEFAULT_LOVABLE_NOISE_PROFILE, DEFAULT_NOISE_PROFILE
from core.report_nudges import build_unexplained_gap_nudge


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
    git_source: Annotated[bool, typer.Option("--git", help="Show Git-only column (requires git_repo in project config).")] = False,
    shadow_log: Annotated[str, typer.Option("--shadow-log", help="on/off (opt-in): append observed evidence to a durable local store (~/.gittan/evidence/) that survives source-log rotation.")] = "off",
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
            "shadow_log": shadow_log,
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

@app.command()
def status(
    date_from: Annotated[Optional[datetime], typer.Option("--from", formats=["%Y-%m-%d"], help="Start date (YYYY-MM-DD)")] = None,
    date_to: Annotated[Optional[datetime], typer.Option("--to", formats=["%Y-%m-%d"], help="End date (YYYY-MM-DD)")] = None,
    today: Annotated[bool, typer.Option(help="Today's status.")] = False,
    yesterday: Annotated[bool, typer.Option(help="Yesterday's status.")] = False,
    last_3_days: Annotated[bool, typer.Option(help="Last 3 days status.")] = False,
    last_week: Annotated[bool, typer.Option(help="Last 7 days status.")] = False,
    last_14_days: Annotated[bool, typer.Option(help="Last 14 days status.")] = False,
    last_month: Annotated[bool, typer.Option(help="Last 30 days status.")] = False,
    additive: Annotated[
        bool,
        typer.Option(
            "--additive",
            help="Partition sessions by one primary project so project rows add up exactly to Total.",
        ),
    ] = False,
    noise_profile: Annotated[
        str,
        typer.Option("--noise-profile", "--global-noise-profile", help="Noise filtering profile for collector diagnostics: lenient, strict, or ultra-strict."),
    ] = DEFAULT_NOISE_PROFILE,
    lovable_noise_profile: Annotated[
        str,
        typer.Option("--lovable-noise-profile", "--lovable-profile", help="Lovable storage-signal filtering: normal, balanced, or strict."),
    ] = DEFAULT_LOVABLE_NOISE_PROFILE,
    anchor_nudge: Annotated[
        bool,
        typer.Option(
            "--anchor-nudge/--no-anchor-nudge",
            help="Warn about unmapped activity anchors (dir/branch/title) and offer to map them (interactive).",
        ),
    ] = True,
    shadow_log: Annotated[str, typer.Option("--shadow-log", help="on/off (opt-in): append observed evidence to a durable local store (~/.gittan/evidence/) that survives source-log rotation.")] = "off",
):
    """Quick hours snapshot with project totals and session counts.

    Common use cases:
    - Daily check: `gittan status --today --additive` (default noise is lenient)
    - Strict totals per project: use `--additive` (project rows sum exactly to Total)
    """
    from collections import defaultdict

    from core.domain import session_duration_hours
    from core.project_hours import count_project_sessions_from_overall_days
    from core.report_service import AI_SOURCES, run_timelog_report
    from outputs.cli_heroes import print_command_hero
    from rich import box
    from rich.console import Console
    from rich.table import Table

    from outputs.terminal_theme import (
        CLR_GREEN,
        CLR_TEXT_SOFT,
        CLR_VALUE_ORANGE,
        STYLE_BORDER,
        STYLE_LABEL,
        STYLE_MUTED,
    )

    df_s, dt_s = resolve_date_window(
        date_from=date_from,
        date_to=date_to,
        today=today,
        yesterday=yesterday,
        last_3_days=last_3_days,
        last_week=last_week,
        last_14_days=last_14_days,
        last_month=last_month,
        prompt_if_missing=not (
            date_from or date_to or today or yesterday or last_3_days or last_week or last_14_days or last_month
        ),
    )

    console = Console()
    if df_s is None or dt_s is None:
        raise typer.BadParameter("Could not resolve date range for status.")
    title_date = f"{df_s} to {dt_s}" if df_s != dt_s else str(df_s)

    options = TimelogRunOptions(
        today=today,
        yesterday=yesterday,
        last_3_days=last_3_days,
        last_week=last_week,
        last_14_days=last_14_days,
        last_month=last_month,
        date_from=df_s,
        date_to=dt_s,
        projects_config=default_projects_config_option(),
        quiet=True,
        noise_profile=noise_profile,
        lovable_noise_profile=lovable_noise_profile,
    )

    print_command_hero(console, "status")
    console.print(f"[bold {CLR_TEXT_SOFT}]Gittan Status — {title_date}[/bold {CLR_TEXT_SOFT}]\n")

    try:
        report = run_timelog_report(options.projects_config, options.date_from, options.date_to, options)

        if not report.included_events:
            console.print(f"[{CLR_VALUE_ORANGE}]No activity tracked for this period. No local evidence found.[/{CLR_VALUE_ORANGE}]")
            console.print(
                f"[{STYLE_MUTED}]Next: run `gittan doctor` to verify source access, then "
                f"`gittan report --today --source-summary` to inspect collection.[/{STYLE_MUTED}]"
            )
            return

        title_suffix = " — additive (primary project per session)" if additive else ""
        table = Table(title=f"Hours Summary ({title_date}){title_suffix}", box=box.ROUNDED)
        table.border_style = STYLE_BORDER
        table.header_style = f"bold {STYLE_LABEL}"
        table.add_column("Project", style=STYLE_LABEL)
        table.add_column("Hours", justify="right", style=CLR_VALUE_ORANGE)
        table.add_column("Sessions", justify="right", style=STYLE_MUTED)

        shown_project_hours = 0.0
        shown_project_sessions = 0
        if additive:
            uncategorized_label = "Uncategorized"
            project_hours: dict[str, float] = defaultdict(float)
            project_sessions: dict[str, int] = defaultdict(int)
            for day_data in report.overall_days.values():
                for start_ts, end_ts, session_events in day_data.get("sessions", []):
                    weighted_counts: dict[str, float] = defaultdict(float)
                    for event in session_events:
                        name = str(event.get("project") or "").strip()
                        if name:
                            weight = float(event.get("weight") or event.get("score") or 1.0)
                            weighted_counts[name] += weight
                    h = session_duration_hours(
                        session_events,
                        start_ts,
                        end_ts,
                        report.args.min_session,
                        report.args.min_session_passive,
                        AI_SOURCES,
                    )
                    if not weighted_counts:
                        project_hours[uncategorized_label] += h
                        project_sessions[uncategorized_label] += 1
                        continue
                    primary_project = sorted(
                        weighted_counts.items(),
                        key=lambda item: (-item[1], item[0].lower()),
                    )[0][0]
                    project_hours[primary_project] += h
                    project_sessions[primary_project] += 1
            for project_name in sorted(project_hours.keys(), key=lambda n: (-project_hours[n], n.lower())):
                proj_hours = project_hours[project_name]
                proj_sessions = project_sessions.get(project_name, 0)
                if proj_hours <= 0:
                    continue
                shown_project_hours += proj_hours
                shown_project_sessions += proj_sessions
                table.add_row(project_name, f"{proj_hours:.1f}h", str(proj_sessions))
        else:
            session_counts = count_project_sessions_from_overall_days(report.overall_days)
            for project_name, days_data in report.project_reports.items():
                proj_hours = sum(d.get("hours", 0.0) for d in days_data.values())
                proj_sessions = session_counts.get(project_name, 0)
                if proj_sessions == 0:
                    proj_sessions = sum(len(d.get("sessions", [])) for d in days_data.values())
                if proj_hours > 0:
                    shown_project_hours += proj_hours
                    shown_project_sessions += proj_sessions
                    table.add_row(
                        project_name,
                        f"{proj_hours:.1f}h",
                        str(proj_sessions),
                    )

        total_h = sum(d.get("hours", 0.0) for d in report.overall_days.values())
        total_sessions = sum(len(d.get("sessions", [])) for d in report.overall_days.values())
        table.add_section()
        table.add_row(
            f"[bold {STYLE_LABEL}]Total[/bold {STYLE_LABEL}]",
            f"[bold {CLR_VALUE_ORANGE}]{total_h:.1f}h[/bold {CLR_VALUE_ORANGE}]",
            f"[bold {STYLE_MUTED}]{total_sessions}[/bold {STYLE_MUTED}]",
        )

        console.print(table)
        resolved_profile = str(
            getattr(report.args, "noise_profile", DEFAULT_NOISE_PROFILE) or DEFAULT_NOISE_PROFILE
        ).lower()
        if resolved_profile == "ultra-strict":
            console.print(
                f"[{STYLE_MUTED}]Note: ultra-strict removes extra diagnostic/repository churn noise. "
                f"Totals and primary-project attribution may shift.[/{STYLE_MUTED}]"
            )
        if (not additive) and (shown_project_hours > total_h + 0.01 or shown_project_sessions > total_sessions):
            console.print(
                f"[{STYLE_MUTED}]Note: project rows can overlap attribution. "
                f"Shown rows sum to {shown_project_hours:.1f}h/{shown_project_sessions} sessions; "
                f"Total is unique timeline time: {total_h:.1f}h/{total_sessions} sessions.[/{STYLE_MUTED}]"
            )
        nudge = build_unexplained_gap_nudge(report)
        if nudge:
            console.print(f"[{STYLE_MUTED}]{nudge}[/{STYLE_MUTED}]")
        if anchor_nudge:
            from core.anchor_nudge import status_anchor_line
            from core.report_nudges import unanchored_anchors_for_report

            unmapped_anchors = unanchored_anchors_for_report(report)
            warn_line = status_anchor_line(unmapped_anchors)
            if warn_line:
                # Interactive mapping lives in `gittan map`; status stays a read-only snapshot.
                console.print(f"[{CLR_VALUE_ORANGE}]{warn_line}[/{CLR_VALUE_ORANGE}]")
                console.print(
                    f"[{STYLE_MUTED}]Run `gittan map` to review and apply project mappings.[/{STYLE_MUTED}]"
                )
        timelog_projects = sorted(
            {
                str(event.get("project", "")).strip()
                for event in report.included_events
                if "timelog" in str(event.get("source", "")).lower() and str(event.get("project", "")).strip()
            },
            key=lambda name: name.lower(),
        )
        if timelog_projects:
            console.print(
                f"[{STYLE_MUTED}]TIMELOG evidence projects in window: {', '.join(timelog_projects)}[/{STYLE_MUTED}]"
            )
        shadow_line = _capture_shadow_log_line(shadow_log, report.all_events)
        if shadow_line:
            console.print(f"[{STYLE_MUTED}]{shadow_line}[/{STYLE_MUTED}]")
        console.print(f"[{CLR_GREEN}]Review complete: nothing is billable until you approve it.[/{CLR_GREEN}]")
    except Exception as e:
        console.print(f"[red]Error fetching status: {e}[/red]")
        raise typer.Exit(code=1) from e
