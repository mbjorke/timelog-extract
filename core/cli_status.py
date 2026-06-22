"""Typer command: gittan status."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Optional

import typer

from core.cli_app import app
from core.cli_date_range import (
    has_explicit_date_window,
    resolve_all_available_window,
    resolve_date_window,
)
from core.cli_options import TimelogRunOptions
from core.cli_report_status_helpers import capture_shadow_log_line
from core.cli_status_history import (
    HISTORY_LEGEND,
    historical_project_names,
    history_git_cell,
    sorted_status_projects,
)
from core.config import default_projects_config_option
from core.noise_profiles import DEFAULT_LOVABLE_NOISE_PROFILE, DEFAULT_NOISE_PROFILE
from core.report_nudges import build_unexplained_gap_nudge


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
    history_source: Annotated[
        bool,
        typer.Option(
            "--history",
            help="All available logs: Total (observed) per project + Git estimate (no period prompt).",
        ),
    ] = False,
    git_source: Annotated[
        bool,
        typer.Option(
            "--git",
            help="Show period-scoped Git column (legacy; prefer --history).",
        ),
    ] = False,
    shadow_log: Annotated[
        str,
        typer.Option(
            "--shadow-log",
            help="on/off (opt-in): append observed evidence to a durable local store (~/.gittan/evidence/) that survives source-log rotation.",
        ),
    ] = "off",
):
    """Quick hours snapshot with project totals and session counts.

    Common use cases:
    - Daily check: `gittan status --today --additive` (default noise is lenient)
    - Strict totals per project: use `--additive` (project rows sum exactly to Total)
    - Historical totals: `gittan status --history` (all available logs + Git estimate)
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

    explicit_period = has_explicit_date_window(
        date_from=date_from,
        date_to=date_to,
        today=today,
        yesterday=yesterday,
        last_3_days=last_3_days,
        last_week=last_week,
        last_14_days=last_14_days,
        last_month=last_month,
    )
    if history_source and not explicit_period:
        df_s, dt_s = resolve_all_available_window()
        title_date = "All available logs"
    else:
        df_s, dt_s = resolve_date_window(
            date_from=date_from,
            date_to=date_to,
            today=today,
            yesterday=yesterday,
            last_3_days=last_3_days,
            last_week=last_week,
            last_14_days=last_14_days,
            last_month=last_month,
            prompt_if_missing=not history_source
            and not (
                date_from or date_to or today or yesterday or last_3_days or last_week or last_14_days or last_month
            ),
        )
        if df_s is None or dt_s is None:
            raise typer.BadParameter("Could not resolve date range for status.")
        title_date = f"{df_s} to {dt_s}" if df_s != dt_s else str(df_s)

    console = Console()

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
        history_source=history_source,
        git_source=git_source,
        shadow_log=shadow_log,
    )

    print_command_hero(console, "status")
    console.print(f"[bold {CLR_TEXT_SOFT}]Gittan Status — {title_date}[/bold {CLR_TEXT_SOFT}]\n")

    try:
        report = run_timelog_report(options.projects_config, options.date_from, options.date_to, options)
        shadow_line = capture_shadow_log_line(shadow_log, report.all_events)

        show_history = bool(history_source)
        git_totals = report.git_project_totals or {}
        historical_projects = historical_project_names(report, show_history=show_history)
        hours_header = "Total (observed)" if show_history else "Hours"

        if not report.included_events and not historical_projects:
            console.print(f"[{CLR_VALUE_ORANGE}]No activity tracked for this period. No local evidence found.[/{CLR_VALUE_ORANGE}]")
            console.print(
                f"[{STYLE_MUTED}]Next: run `gittan doctor` to verify source access, then "
                f"`gittan report --today --source-summary` to inspect collection.[/{STYLE_MUTED}]"
            )
            if show_history:
                console.print(
                    f"[{STYLE_MUTED}]Tip: configure `git_repo` on project profiles for Git "
                    f"bootstrap via `--history`.[/{STYLE_MUTED}]"
                )
            if shadow_line:
                console.print(f"[{STYLE_MUTED}]{shadow_line}[/{STYLE_MUTED}]")
            return

        title_suffix = " — additive (primary project per session)" if additive else ""
        table = Table(title=f"Hours Summary ({title_date}){title_suffix}", box=box.ROUNDED)
        table.border_style = STYLE_BORDER
        table.header_style = f"bold {STYLE_LABEL}"
        table.add_column("Project", style=STYLE_LABEL)
        table.add_column(hours_header, justify="right", style=CLR_VALUE_ORANGE)
        table.add_column("Sessions", justify="right", style=STYLE_MUTED)
        if show_history:
            table.add_column("Git estimate", justify="right", style=STYLE_MUTED)

        def _git_cell(project_name: str) -> list[str]:
            if not show_history:
                return []
            return [history_git_cell(project_name, show_history=True, git_totals=git_totals)]

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
                table.add_row(
                    project_name,
                    f"{proj_hours:.1f}h",
                    str(proj_sessions),
                    *_git_cell(project_name),
                )
        else:
            session_counts = count_project_sessions_from_overall_days(report.overall_days)
            listed_projects = sorted_status_projects(
                report.project_reports,
                historical_projects,
                show_history=show_history,
            )
            for project_name in listed_projects:
                days_data = report.project_reports.get(project_name, {})
                proj_hours = sum(d.get("hours", 0.0) for d in days_data.values())
                proj_sessions = session_counts.get(project_name, 0)
                if proj_sessions == 0:
                    proj_sessions = sum(len(d.get("sessions", [])) for d in days_data.values())
                if proj_hours > 0 or (show_history and project_name in historical_projects):
                    if proj_hours > 0:
                        shown_project_hours += proj_hours
                        shown_project_sessions += proj_sessions
                    table.add_row(
                        project_name,
                        f"{proj_hours:.1f}h" if proj_hours else "—",
                        str(proj_sessions) if proj_sessions else "—",
                        *_git_cell(project_name),
                    )

        total_h = sum(d.get("hours", 0.0) for d in report.overall_days.values())
        total_sessions = sum(len(d.get("sessions", [])) for d in report.overall_days.values())
        table.add_section()
        total_row = [
            f"[bold {STYLE_LABEL}]Total[/bold {STYLE_LABEL}]",
            f"[bold {CLR_VALUE_ORANGE}]{total_h:.1f}h[/bold {CLR_VALUE_ORANGE}]",
            f"[bold {STYLE_MUTED}]{total_sessions}[/bold {STYLE_MUTED}]",
        ]
        if show_history:
            total_row.append("")
        table.add_row(*total_row)

        console.print(table)
        if show_history:
            console.print(f"[{STYLE_MUTED}]{HISTORY_LEGEND}[/{STYLE_MUTED}]")
            if not git_totals:
                console.print(
                    f"[{STYLE_MUTED}]Tip: configure `git_repo` on project profiles for the "
                    f"Git estimate column.[/{STYLE_MUTED}]"
                )
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
        if shadow_line:
            console.print(f"[{STYLE_MUTED}]{shadow_line}[/{STYLE_MUTED}]")
        console.print(f"[{CLR_GREEN}]Review complete: nothing is billable until you approve it.[/{CLR_GREEN}]")
    except Exception as e:
        console.print(f"[red]Error fetching status: {e}[/red]")
        raise typer.Exit(code=1) from e
