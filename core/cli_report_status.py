"""Typer commands: report, status."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Annotated, Optional

import typer

from core.cli_app import app
from core.cli_options import TimelogRunOptions
from core.cli_prompts import prompt_for_timeframe
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
    projects_config: Annotated[str, typer.Option(help="JSON config file")] = "timelog_projects.json",
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
    github_user: Annotated[Optional[str], typer.Option(help="GitHub login")] = None,
    exclude: Annotated[str, typer.Option(help="Exclude keywords")] = "",
    worklog: Annotated[Optional[str], typer.Option(help="Path to TIMELOG.md")] = None,
    worklog_format: Annotated[str, typer.Option(help="auto/md/gtimelog")] = "auto",
    source_strategy: Annotated[str, typer.Option(help="auto/worklog-first/balanced")] = "auto",
    screen_time: Annotated[str, typer.Option(help="auto/on/off")] = "auto",
    include_uncategorized: Annotated[bool, typer.Option(help="Show uncategorized")] = False,
    only_project: Annotated[Optional[str], typer.Option(help="Filter by project")] = None,
    customer: Annotated[Optional[str], typer.Option(help="Filter by customer")] = None,
    all_events: Annotated[bool, typer.Option(help="Verbose events")] = False,
    source_summary: Annotated[bool, typer.Option(help="Show source counts")] = False,
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
    invoice_mode: Annotated[
        str,
        typer.Option(
            "--invoice-mode",
            help="Invoice reconciliation mode: baseline or calibrated-a.",
        ),
    ] = "baseline",
    invoice_ground_truth: Annotated[
        Optional[str],
        typer.Option(
            "--invoice-ground-truth",
            help="Path to reconciliation ground-truth JSON used with --invoice-mode calibrated-a.",
        ),
    ] = None,
):
    """Detailed activity scanning and reporting.

    Common use cases:
    - Daily overview: `gittan report --today --noise-profile strict --lovable-noise-profile balanced`
    - Investigate why time was counted: `gittan report --today --all-events --noise-profile lenient`
    - Conservative reporting baseline: `gittan report --today --noise-profile ultra-strict --lovable-noise-profile strict`
    - Additive breakdown in summary: add `--additive-summary`
    - Invoice calibration against approved hours: add `--invoice-mode calibrated-a --invoice-ground-truth <path>`
    """
    from core.report_cli import run_timelog_cli

    df_s, dt_s = None, None
    if not (
        today
        or yesterday
        or last_3_days
        or last_week
        or last_14_days
        or last_month
        or date_from
        or date_to
    ):
        picked = prompt_for_timeframe()
        today = picked.get("today", False)
        yesterday = picked.get("yesterday", False)
        last_3_days = picked.get("last_3_days", False)
        last_week = picked.get("last_week", False)
        last_14_days = picked.get("last_14_days", False)
        last_month = picked.get("last_month", False)
        df_s = picked.get("date_from")
        dt_s = picked.get("date_to")
    else:
        df_s = date_from.strftime("%Y-%m-%d") if date_from else None
        dt_s = date_to.strftime("%Y-%m-%d") if date_to else None

    options = TimelogRunOptions(
        date_from=df_s,
        date_to=dt_s,
        today=today,
        yesterday=yesterday,
        last_3_days=last_3_days,
        last_week=last_week,
        last_14_days=last_14_days,
        last_month=last_month,
        projects_config=projects_config,
        keywords=keywords,
        project=project,
        email=email,
        min_session=min_session,
        min_session_passive=min_session_passive,
        gap_minutes=gap_minutes,
        chrome_collapse_minutes=chrome_collapse_minutes,
        exclude=exclude,
        worklog=worklog,
        worklog_format=worklog_format,
        source_strategy=source_strategy,
        screen_time=screen_time,
        include_uncategorized=include_uncategorized,
        only_project=only_project,
        customer=customer,
        all_events=all_events,
        source_summary=source_summary,
        narrative=narrative,
        invoice_pdf=invoice_pdf,
        invoice_pdf_file=invoice_pdf_file,
        billable_unit=billable_unit,
        chrome_source=chrome_source,
        mail_source=mail_source,
        github_source=github_source,
        github_user=github_user,
        output_format=output_format,
        quiet=quiet,
        json_file=json_file,
        report_html=report_html,
        noise_profile=noise_profile,
        lovable_noise_profile=lovable_noise_profile,
        additive_summary=additive_summary,
        invoice_mode=invoice_mode,
        invoice_ground_truth=invoice_ground_truth,
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
    projects_config: Annotated[str, typer.Option(help="JSON config file")] = "timelog_projects.json",
    project: Annotated[Optional[str], typer.Option("--project", help="Filter to one project name")] = None,
    customer: Annotated[Optional[str], typer.Option(help="Filter by customer")] = None,
    source_summary: Annotated[bool, typer.Option(help="Show source counts")] = False,
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
    """Search timeline quickly with all events shown (wrapper around report).

    Common use cases:
    - Why did project X get time? `gittan search --today --project "X" --noise-profile lenient --lovable-noise-profile balanced`
    - Conservative audit view: `gittan search --today --project "X" --noise-profile ultra-strict --lovable-noise-profile strict`
    """
    from core.report_cli import run_timelog_cli

    df_s, dt_s = None, None
    if not (
        today
        or yesterday
        or last_3_days
        or last_week
        or last_14_days
        or last_month
        or date_from
        or date_to
    ):
        picked = prompt_for_timeframe()
        today = picked.get("today", False)
        yesterday = picked.get("yesterday", False)
        last_3_days = picked.get("last_3_days", False)
        last_week = picked.get("last_week", False)
        last_14_days = picked.get("last_14_days", False)
        last_month = picked.get("last_month", False)
        df_s = picked.get("date_from")
        dt_s = picked.get("date_to")
    else:
        df_s = date_from.strftime("%Y-%m-%d") if date_from else None
        dt_s = date_to.strftime("%Y-%m-%d") if date_to else None

    options = TimelogRunOptions(
        date_from=df_s,
        date_to=dt_s,
        today=today,
        yesterday=yesterday,
        last_3_days=last_3_days,
        last_week=last_week,
        last_14_days=last_14_days,
        last_month=last_month,
        projects_config=projects_config,
        only_project=project,
        customer=customer,
        source_summary=source_summary,
        all_events=True,
        output_format=output_format,
        noise_profile=noise_profile,
        lovable_noise_profile=lovable_noise_profile,
        quiet=quiet,
    )
    run_timelog_cli(options)


@app.command()
def status(
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
):
    """Quick high-level hours summary.

    Common use cases:
    - Daily check (recommended default): `gittan status --today --additive --noise-profile strict --lovable-noise-profile balanced`
    - Conservative reporting view: `gittan status --today --additive --noise-profile ultra-strict --lovable-noise-profile strict`
    - Strict totals per project: use `--additive` (project rows sum exactly to Total)
    """
    from collections import defaultdict

    from core.domain import session_duration_hours
    from core.report_service import AI_SOURCES, run_timelog_report
    from outputs.cli_heroes import print_command_hero
    from rich import box
    from rich.console import Console
    from rich.table import Table

    from outputs.terminal_theme import (
        CLR_TEXT_SOFT,
        CLR_VALUE_ORANGE,
        STYLE_BORDER,
        STYLE_LABEL,
        STYLE_MUTED,
    )

    df_s, dt_s = None, None
    if not (today or yesterday or last_3_days or last_week or last_14_days or last_month):
        picked = prompt_for_timeframe()
        today = picked.get("today", False)
        yesterday = picked.get("yesterday", False)
        last_3_days = picked.get("last_3_days", False)
        last_week = picked.get("last_week", False)
        last_14_days = picked.get("last_14_days", False)
        last_month = picked.get("last_month", False)
        df_s = picked.get("date_from")
        dt_s = picked.get("date_to")
    else:
        now = datetime.now()
        end_d = now.date()
        end_s = end_d.isoformat()
        if today:
            df_s = dt_s = end_s
        elif yesterday:
            yest = (end_d - timedelta(days=1)).isoformat()
            df_s = dt_s = yest
        elif last_3_days:
            df_s, dt_s = (end_d - timedelta(days=2)).isoformat(), end_s
        elif last_week:
            df_s, dt_s = (end_d - timedelta(days=6)).isoformat(), end_s
        elif last_14_days:
            df_s, dt_s = (end_d - timedelta(days=13)).isoformat(), end_s
        elif last_month:
            df_s, dt_s = (end_d - timedelta(days=29)).isoformat(), end_s

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
        projects_config="timelog_projects.json",
        quiet=True,
        noise_profile=noise_profile,
        lovable_noise_profile=lovable_noise_profile,
    )

    print_command_hero(console, "status")
    console.print(f"[bold {CLR_TEXT_SOFT}]Gittan Status — {title_date}[/bold {CLR_TEXT_SOFT}]\n")

    try:
        report = run_timelog_report(options.projects_config, options.date_from, options.date_to, options)

        if not report.included_events:
            console.print("[yellow]No activity tracked for this period.[/yellow]")
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
            project_hours: dict[str, float] = defaultdict(float)
            project_sessions: dict[str, int] = defaultdict(int)
            for day_data in report.overall_days.values():
                for start_ts, end_ts, session_events in day_data.get("sessions", []):
                    counts: dict[str, int] = defaultdict(int)
                    for event in session_events:
                        name = str(event.get("project") or "").strip()
                        if name:
                            counts[name] += 1
                    if not counts:
                        continue
                    primary_project = sorted(counts.items(), key=lambda item: (-item[1], item[0].lower()))[0][0]
                    h = session_duration_hours(
                        session_events,
                        start_ts,
                        end_ts,
                        report.args.min_session,
                        report.args.min_session_passive,
                        AI_SOURCES,
                    )
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
            for project_name, days_data in report.project_reports.items():
                proj_hours = sum(d["hours"] for d in days_data.values())
                proj_sessions = sum(len(d["sessions"]) for d in days_data.values())
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
        if str(getattr(report.args, "noise_profile", "strict") or "strict").lower() == "ultra-strict":
            console.print(
                "[dim]Note: ultra-strict removes extra diagnostic/repository churn noise. "
                "Total hours may decrease and session boundaries/primary project attribution can shift.[/dim]"
            )
        if (not additive) and (shown_project_hours > total_h + 0.01 or shown_project_sessions > total_sessions):
            console.print(
                f"[dim]Note: project rows can overlap attribution. "
                f"Shown rows sum to {shown_project_hours:.1f}h/{shown_project_sessions} sessions; "
                f"Total is unique timeline time: {total_h:.1f}h/{total_sessions} sessions.[/dim]"
            )

    except Exception as e:
        console.print(f"[red]Error fetching status: {e}[/red]")
        raise typer.Exit(code=1) from e
