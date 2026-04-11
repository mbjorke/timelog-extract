"""Typer commands: report, status."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Annotated, Optional

import typer

from core.cli_app import app
from core.cli_options import TimelogRunOptions
from core.cli_prompts import prompt_for_timeframe


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
):
    """Detailed activity scanning and reporting."""
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
):
    """Quick high-level hours summary."""
    from core.report_service import run_timelog_report
    from rich.console import Console
    from rich.table import Table

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
    )

    console.print(f"[bold blue]Gittan Status - {title_date}[/bold blue]\n")

    try:
        report = run_timelog_report(options.projects_config, options.date_from, options.date_to, options)

        if not report.included_events:
            console.print("[yellow]No activity tracked for this period.[/yellow]")
            return

        table = Table(title=f"Hours Summary ({title_date})")
        table.add_column("Project", style="cyan")
        table.add_column("Hours", justify="right", style="green")
        table.add_column("Sessions", justify="right")

        for project_name, days_data in report.project_reports.items():
            proj_hours = sum(d["hours"] for d in days_data.values())
            proj_sessions = sum(len(d["sessions"]) for d in days_data.values())
            if proj_hours > 0:
                table.add_row(
                    project_name,
                    f"{proj_hours:.1f}h",
                    str(proj_sessions),
                )

        total_h = sum(d.get("hours", 0.0) for d in report.overall_days.values())
        total_sessions = sum(len(d.get("sessions", [])) for d in report.overall_days.values())
        table.add_section()
        table.add_row("[bold]Total[/bold]", f"[bold]{total_h:.1f}h[/bold]", f"[bold]{total_sessions}[/bold]")

        console.print(table)

    except Exception as e:
        console.print(f"[red]Error fetching status: {e}[/red]")
        raise typer.Exit(code=1) from e
