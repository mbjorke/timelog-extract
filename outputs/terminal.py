"""Terminal report rendering using Rich for a professional CLI experience."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Optional, Sequence

from rich import box
from rich.console import Console
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

from outputs.cli_heroes import print_command_hero
from outputs.terminal_preview import (
    assemble_timeline_event_line,
    pick_session_preview_events,
    session_preview_omitted_summary,
)
from outputs.terminal_report_sections import (
    period_label,
    print_project_hour_review_section,
    print_review_summary_section,
    report_section_spinner,
)
from outputs.terminal_theme import (
    CLR_BERRY_BRIGHT,
    CLR_DIM,
    CLR_GREEN,
    CLR_MUTED,
    CLR_TEXT_SOFT,
    CLR_VALUE_ORANGE,
    STYLE_BORDER,
    display_source_label,
    get_source_color,
)

console = Console()

STYLE_HEADING = f"bold {CLR_BERRY_BRIGHT}"
STYLE_LABEL = f"bold {CLR_MUTED}"
STYLE_BODY = CLR_TEXT_SOFT
STYLE_META = CLR_DIM
STYLE_ACCENT = CLR_BERRY_BRIGHT
STYLE_POSITIVE = CLR_GREEN


def _build_dynamic_legend(source_order: Sequence[str]) -> Text:
    legend = Text()
    legend.append("Evidence legend: ", style=f"bold {STYLE_LABEL}")
    for idx, source in enumerate(source_order):
        legend.append(display_source_label(source), style=f"italic {get_source_color(source)}")
        if idx < len(source_order) - 1:
            legend.append("  ", style=STYLE_META)
    return legend


def print_source_summary(events: List[Dict[str, Any]], source_order: Sequence[str]):
    counts = defaultdict(int)
    for event in events:
        counts[event["source"]] += 1

    table = Table(
        title="Evidence source summary",
        caption="Source summary: observed local traces before project review.",
        box=box.ROUNDED,
    )
    table.border_style = STYLE_BORDER
    table.header_style = f"bold {STYLE_LABEL}"
    table.add_column("Source", style=STYLE_BODY)
    table.add_column("Events", justify="right", style=CLR_VALUE_ORANGE)

    for src in sorted(counts, key=lambda s: source_order.index(s) if s in source_order else 99):
        table.add_row(display_source_label(src), str(counts[src]))
    table.add_section()
    table.add_row(
        f"[bold {STYLE_LABEL}]Total[/bold {STYLE_LABEL}]",
        f"[bold {CLR_VALUE_ORANGE}]{sum(counts.values())}[/bold {CLR_VALUE_ORANGE}]",
    )

    console.print(table)
    console.print(
        f"[{STYLE_META}]Review these counts before trusting attribution or invoice totals.[/{STYLE_META}]"
    )


def _fmt_hours(value: float) -> str:
    """Compact hours: drop trailing zeros, blank for zero."""
    if not value:
        return ""
    text = f"{value:.2f}".rstrip("0").rstrip(".")
    return text


def print_weekly_pivot(pivot) -> None:
    """Render an ISO week × project hours pivot (Pierre-parity view)."""
    if pivot.is_empty:
        console.print(
            f"[{STYLE_META}]No hours to summarize by week for this range.[/{STYLE_META}]"
        )
        return

    table = Table(
        title="Weekly project time summary",
        caption="Hours by ISO week and project (observed/classified, not approved invoice time).",
        box=box.ROUNDED,
    )
    table.border_style = STYLE_BORDER
    table.header_style = f"bold {STYLE_LABEL}"
    table.add_column("Week", style=STYLE_BODY)
    for project in pivot.projects:
        table.add_column(project, justify="right", style=CLR_VALUE_ORANGE)
    table.add_column("Total", justify="right", style=f"bold {CLR_VALUE_ORANGE}")

    for week in pivot.weeks:
        row = [week]
        for project in pivot.projects:
            row.append(_fmt_hours(pivot.cells.get(week, {}).get(project, 0.0)))
        row.append(f"[bold]{_fmt_hours(pivot.week_totals.get(week, 0.0))}[/bold]")
        table.add_row(*row)

    table.add_section()
    totals_row = [f"[bold {STYLE_LABEL}]Total[/bold {STYLE_LABEL}]"]
    for project in pivot.projects:
        totals_row.append(
            f"[bold {CLR_VALUE_ORANGE}]{_fmt_hours(pivot.project_totals.get(project, 0.0))}[/bold {CLR_VALUE_ORANGE}]"
        )
    totals_row.append(
        f"[bold {CLR_VALUE_ORANGE}]{_fmt_hours(pivot.grand_total)}[/bold {CLR_VALUE_ORANGE}]"
    )
    table.add_row(*totals_row)

    console.print(table)


def print_project_source_mix(
    events: List[Dict[str, Any]],
    project_name: str,
    source_order: Sequence[str],
):
    target = (project_name or "").strip().lower()
    if not target:
        return
    project_events = [event for event in events if str(event.get("project", "")).strip().lower() == target]
    if not project_events:
        return

    counts = defaultdict(int)
    for event in project_events:
        counts[str(event.get("source", "Unknown"))] += 1

    first_event = min(project_events, key=lambda event: event["local_ts"])
    last_event = max(project_events, key=lambda event: event["local_ts"])

    console.print()
    console.print(f"[{STYLE_HEADING}]Source mix for {project_name}[/{STYLE_HEADING}]")
    mix_table = Table.grid(padding=(0, 2))
    mix_table.add_column(style=STYLE_BODY)
    mix_table.add_column(justify="right", style=STYLE_BODY)
    for src in sorted(counts, key=lambda s: source_order.index(s) if s in source_order else 99):
        mix_table.add_row(display_source_label(src), str(counts[src]))
    console.print(mix_table)
    console.print(
        f"[{STYLE_META}]Event span: "
        f"{first_event['local_ts'].strftime('%H:%M')} -> {last_event['local_ts'].strftime('%H:%M')} "
        f"({len(project_events)} events)[/{STYLE_META}]"
    )


def print_report(
    overall_days: Dict[str, Any],
    project_reports: Dict[str, Any],
    screen_time_days: Optional[Dict[str, float]],
    profiles: List[Dict[str, Any]],
    args: Any,
    config_path: Optional[str],
    local_tz: Any,
    source_order: Sequence[str],
    uncategorized: str,
    session_duration_hours_fn: Any,
    billable_total_hours_fn: Any,
    timelog_project_totals: Optional[Dict[str, float]] = None,
    git_project_totals: Optional[Dict[str, float]] = None,
    presence_estimated: Any = None,
    presence_edge_gaps: Any = None,
    billable_raw_by_project: Optional[Dict[str, float]] = None,
    reported_billing: bool = False,
):
    print_command_hero(console, "report")
    console.print()

    # Header Info
    header_table = Table.grid(padding=(0, 1))
    header_table.add_column(style=STYLE_LABEL)
    header_table.add_column(style=STYLE_BODY)
    header_table.add_row("Timezone:", str(local_tz))
    if config_path:
        header_table.add_row("Config:", str(config_path))
    header_table.add_row(
        "Projects:",
        ", ".join(p["name"] for p in profiles),
    )
    period = period_label(args)
    if period:
        header_table.add_row("Period:", period)
    console.print(header_table)
    console.print()

    total_h = 0.0
    for day in sorted(overall_days):
        day_payload = overall_days[day]
        total_h += day_payload["hours"]

        # Day header: date plus hours and session count on the tree root label
        day_attended_h = day_payload.get("attended_hours", 0.0) + day_payload.get("mixed_hours", 0.0)
        day_agent_h = day_payload.get("agent_hours", 0.0)
        day_title = Text.assemble(
            ("● ", STYLE_META),
            (day, STYLE_HEADING),
            ("  ", ""),
            (f"{day_payload['hours']:.1f}h", f"bold {CLR_VALUE_ORANGE}"),
        )
        if day_agent_h > 0 or day_payload.get("mixed_hours", 0.0) > 0:
            day_title.append(f" ({day_attended_h:.1f} + {day_agent_h:.1f})", STYLE_META)
        day_title.append(" | ", STYLE_META)
        day_title.append(f"{len(day_payload['sessions'])} sessions", STYLE_LABEL)
        day_tree = Tree(day_title, guide_style=STYLE_META)

        for idx, s_tuple in enumerate(day_payload["sessions"], 1):
            start_ts, end_ts, session_events = s_tuple[:3]
            attendance = s_tuple[3] if len(s_tuple) > 3 else None
            raw_dur = session_duration_hours_fn(
                session_events, start_ts, end_ts, args.min_session, args.min_session_passive
            )
            session_projects = sorted({event["project"] for event in session_events})

            session_text = Text.assemble(
                (f"[{idx}] ", STYLE_META),
                (f"{start_ts.strftime('%H:%M')}-{end_ts.strftime('%H:%M')} ", f"bold {STYLE_POSITIVE}"),
                (f"({raw_dur:.1f}h) ", f"bold {CLR_VALUE_ORANGE}"),
            )
            if attendance and attendance != "attended":
                session_text.append(f"[{attendance}] ", f"italic {STYLE_META}")
            session_text.append(", ".join(session_projects), f"italic {STYLE_META}")

            session_node = day_tree.add(session_text)

            use_compact = getattr(args, "compact", False) and not getattr(args, "all_events", False)
            if use_compact:
                display_events = pick_session_preview_events(session_events, source_order)
            else:
                display_events = session_events

            for event in display_events:
                session_node.add(
                    assemble_timeline_event_line(
                        event,
                        source_label=display_source_label(event["source"], event),
                        source_style=f"italic {get_source_color(event['source'])}",
                        time_style=STYLE_POSITIVE,
                        project_style=STYLE_LABEL,
                        label_style=CLR_VALUE_ORANGE,
                        detail_style=STYLE_META,
                    )
                )

            if use_compact:
                omitted = session_preview_omitted_summary(session_events, display_events)
                if omitted:
                    session_node.add(Text(omitted, style=f"italic {STYLE_META}"))

        console.print(day_tree)

        if screen_time_days and day in screen_time_days:
            screen_h = screen_time_days[day] / 3600
            observed_delta = day_payload["hours"] - screen_h
            presence_day = None
            if presence_estimated is not None and getattr(presence_estimated, "available", False):
                presence_day = float(
                    (getattr(presence_estimated, "overall_days", None) or {}).get(day, 0.0) or 0.0
                )
            if presence_day is not None and presence_day > 0:
                est_delta = presence_day - screen_h
                console.print(
                    f"    [{STYLE_META}]Screen Time: {screen_h:.1f}h "
                    f"(est. delta {est_delta:+.1f}h; evidenced {observed_delta:+.1f}h)[/{STYLE_META}]"
                )
            else:
                console.print(
                    f"    [{STYLE_META}]Screen Time: {screen_h:.1f}h (delta {observed_delta:+.1f}h)[/{STYLE_META}]"
                )
        elif screen_time_days and float(day_payload.get("hours", 0) or 0) >= 0.25:
            console.print(f"    [{STYLE_META}]Screen Time: no macOS usage data for this day[/{STYLE_META}]")
        console.print()

    day_count = len(overall_days)
    with report_section_spinner(
        console,
        f"[{STYLE_META}]Preparing review summary…[/{STYLE_META}]",
        day_count=day_count,
    ):
        print_review_summary_section(
            console,
            args=args,
            total_h=total_h,
            project_reports=project_reports,
            screen_time_days=screen_time_days,
            presence_estimated=presence_estimated,
            presence_edge_gaps=presence_edge_gaps,
            overall_days=overall_days,
            session_duration_hours_fn=session_duration_hours_fn,
            billable_total_hours_fn=billable_total_hours_fn,
            billable_raw_by_project=billable_raw_by_project,
            reported_billing=reported_billing,
        )

    console.print()
    if getattr(args, "only_project", None):
        flat_events: List[Dict[str, Any]] = []
        for day_payload in overall_days.values():
            for s_tuple in day_payload.get("sessions", []):
                session_events = s_tuple[2]
                flat_events.extend(session_events)
        print_project_source_mix(
            events=flat_events,
            project_name=str(args.only_project),
            source_order=source_order,
        )

    with report_section_spinner(
        console,
        f"[{STYLE_META}]Preparing project-hour review…[/{STYLE_META}]",
        day_count=day_count,
    ):
        print_project_hour_review_section(
            console,
            args=args,
            overall_days=overall_days,
            project_reports=project_reports,
            profiles=profiles,
            timelog_project_totals=timelog_project_totals,
            git_project_totals=git_project_totals,
            session_duration_hours_fn=session_duration_hours_fn,
            billable_total_hours_fn=billable_total_hours_fn,
        )

    # Footer legend: derive from canonical source order so new standalone sources
    # are automatically visible without manual output updates.
    legend = _build_dynamic_legend(source_order)
    console.print(legend)
    console.print(
        f"[{STYLE_META}]Nothing in this report is billable until explicitly approved.[/{STYLE_META}]"
    )
    console.print()
