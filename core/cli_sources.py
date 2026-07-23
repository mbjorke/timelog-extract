"""Typer commands: sources (analyze data source contributions)."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Annotated, Optional

import typer

from core.cli_app import app
from core.cli_options import TimelogRunOptions
from core.config import default_projects_config_option
from outputs.terminal_theme import (
    CLR_SOURCE_BLUE,
    CLR_VALUE_ORANGE,
    STYLE_BORDER,
    STYLE_DIM,
    STYLE_LABEL,
    STYLE_MUTED,
)


@app.command()
def sources(
    date_from: Annotated[Optional[datetime], typer.Option("--from", formats=["%Y-%m-%d"], help="Start date (YYYY-MM-DD)")] = None,
    date_to: Annotated[Optional[datetime], typer.Option("--to", formats=["%Y-%m-%d"], help="End date (YYYY-MM-DD)")] = None,
    today: Annotated[bool, typer.Option(help="Limit to today.")] = False,
    yesterday: Annotated[bool, typer.Option(help="Limit to yesterday.")] = False,
    last_3_days: Annotated[bool, typer.Option(help="Limit to last 3 days.")] = False,
    last_week: Annotated[bool, typer.Option(help="Limit to last 7 days.")] = False,
    last_14_days: Annotated[bool, typer.Option(help="Limit to last 14 days.")] = False,
    last_month: Annotated[bool, typer.Option(help="Limit to last 30 days.")] = False,
):
    """Analyze which data sources are contributing the most to your reports."""
    from rich import box
    from rich.console import Console
    from rich.table import Table

    from core.analytics import estimate_hours_by_day, group_by_day
    from core.cli_date_range import resolve_date_window
    from core.domain import session_duration_hours
    from core.report_service import (
        LOCAL_TZ,
        _compute_sessions,
        _session_duration_hours,
        run_timelog_report,
    )
    from core.sources import AI_SOURCES

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

    if df_s is None or dt_s is None:
        raise typer.BadParameter("Could not resolve date range for sources.")

    options = TimelogRunOptions(
        date_from=df_s,
        date_to=dt_s,
        today=today,
        yesterday=yesterday,
        last_3_days=last_3_days,
        last_week=last_week,
        last_14_days=last_14_days,
        last_month=last_month,
        projects_config=default_projects_config_option(),
        quiet=True,
    )

    console = Console()
    with console.status(f"[bold {STYLE_LABEL}]Analyzing source importance...", spinner="dots"):
        report = run_timelog_report(options.projects_config, options.date_from, options.date_to, options)

    if not report.all_events:
        console.print(
            f"[{CLR_VALUE_ORANGE}]No data found for this period to analyze.[/{CLR_VALUE_ORANGE}]"
        )
        console.print(
            f"[{STYLE_MUTED}]Next: widen the date range or run `gittan doctor` to verify source access.[/{STYLE_MUTED}]"
        )
        return

    source_counts = defaultdict(int)
    source_hours = defaultdict(float)

    for event in report.all_events:
        source_counts[event["source"]] += 1

    raw_grouped = group_by_day(report.all_events, local_tz=LOCAL_TZ)
    raw_overall = estimate_hours_by_day(
        raw_grouped,
        gap_minutes=15,
        min_session_minutes=15,
        min_session_passive_minutes=5,
        compute_sessions_fn=_compute_sessions,
        session_duration_hours_fn=_session_duration_hours,
    )

    uncategorized_count = defaultdict(int)
    uncategorized_samples = defaultdict(list)
    for day_data in raw_overall.values():
        for session in day_data["sessions"]:
            start, end, session_events = session[:3]
            dur = session_duration_hours(session_events, start, end, 15, 5, AI_SOURCES)

            session_counts = defaultdict(int)
            for e in session_events:
                if e.get("project") == "Uncategorized":
                    src = e["source"]
                    uncategorized_count[src] += 1
                    detail = e.get("detail", "")
                    if detail and detail not in uncategorized_samples[src] and len(uncategorized_samples[src]) < 3:
                        uncategorized_samples[src].append(detail)
                session_counts[e["source"]] += 1

            total_session_events = len(session_events)
            if total_session_events > 0:
                for src, count in session_counts.items():
                    share = dur * (count / total_session_events)
                    source_hours[src] += share

    table = Table(
        title=f"Source Importance Analysis ({options.date_from} to {options.date_to})",
        box=box.ROUNDED,
    )
    table.border_style = STYLE_BORDER
    table.header_style = f"bold {STYLE_LABEL}"
    table.add_column("Source", style=CLR_SOURCE_BLUE)
    table.add_column("Events", justify="right", style=STYLE_MUTED)
    table.add_column("Uncat.", justify="right", style=CLR_VALUE_ORANGE)
    table.add_column("Samples (Uncat)", style=STYLE_DIM, max_width=40)
    table.add_column("Est. Hours Impact", justify="right", style=CLR_VALUE_ORANGE)
    table.add_column("Weight %", justify="right", style=STYLE_DIM)

    total_impact_h = sum(source_hours.values())
    sorted_sources = sorted(source_counts.keys(), key=lambda s: source_hours[s], reverse=True)

    for src in sorted_sources:
        pct = (source_hours[src] / total_impact_h * 100) if total_impact_h > 0 else 0
        samples_text = " | ".join(uncategorized_samples[src])
        table.add_row(
            src,
            str(source_counts[src]),
            str(uncategorized_count[src]),
            samples_text,
            f"{source_hours[src]:.1f}h",
            f"{pct:.1f}%",
        )

    console.print(table)
    console.print(
        f"\n[{STYLE_DIM}]Note: 'Est. Hours Impact' represents how much of your total session time is 'backed' by this "
        f"specific source.[/{STYLE_DIM}]\n"
    )

    total_uncategorized = sum(uncategorized_count.values())
    if total_uncategorized > 0:
        console.print(
            f"[{STYLE_MUTED}]Next: run `gittan review` to map uncategorized domains to project buckets.[/{STYLE_MUTED}]"
        )
    else:
        report_cmd = "gittan report"
        if options.today:
            report_cmd += " --today"
        elif options.yesterday:
            report_cmd += " --yesterday"
        elif options.last_3_days:
            report_cmd += " --last-3-days"
        elif options.last_week:
            report_cmd += " --last-week"
        elif options.last_14_days:
            report_cmd += " --last-14-days"
        elif options.last_month:
            report_cmd += " --last-month"
        elif options.date_from and options.date_to:
            report_cmd += f" --from {options.date_from} --to {options.date_to}"
        console.print(
            f"[{STYLE_MUTED}]Next: run `{report_cmd}` to review your daily project timeline.[/{STYLE_MUTED}]"
        )
