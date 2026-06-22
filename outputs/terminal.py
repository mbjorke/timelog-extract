"""Terminal report rendering using Rich for a professional CLI experience."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Sequence, Optional
from rich import box
from rich.console import Console
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

from outputs.cli_heroes import print_command_hero
from outputs.terminal_preview import (
    format_event_detail,
    pick_session_preview_events,
    session_preview_omitted_summary,
)
from outputs.terminal_history import git_column_label, print_history_legend
from outputs.terminal_theme import (
    CLR_BERRY_BRIGHT,
    CLR_DIM,
    CLR_GREEN,
    CLR_SOURCE_BLUE,
    CLR_TEXT_SOFT,
    CLR_VALUE_ORANGE,
    CLR_MUTED,
    STYLE_BORDER,
    WARN_ICON,
)
from outputs.terminal_warnings import print_report_warnings

console = Console()

STYLE_HEADING = f"bold {CLR_BERRY_BRIGHT}"
STYLE_LABEL = f"bold {CLR_MUTED}"
STYLE_BODY = CLR_TEXT_SOFT
STYLE_META = CLR_DIM
STYLE_ACCENT = CLR_BERRY_BRIGHT
STYLE_POSITIVE = CLR_GREEN


def _display_source_label(source: str) -> str:
    """Render neutral source labels without changing underlying source keys."""
    if source == "TIMELOG.md":
        return "Worklog (TIMELOG.md)"
    return source


def _build_dynamic_legend(source_order: Sequence[str]) -> Text:
    legend = Text()
    legend.append("Evidence legend: ", style=f"bold {STYLE_LABEL}")
    for idx, source in enumerate(source_order):
        legend.append(_display_source_label(source), style=f"italic {get_source_color(source)}")
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
        table.add_row(_display_source_label(src), str(counts[src]))
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
        mix_table.add_row(_display_source_label(src), str(counts[src]))
    console.print(mix_table)
    console.print(
        f"[{STYLE_META}]Event span: "
        f"{first_event['local_ts'].strftime('%H:%M')} -> {last_event['local_ts'].strftime('%H:%M')} "
        f"({len(project_events)} events)[/{STYLE_META}]"
    )


def get_source_color(source: str) -> str:
    return CLR_SOURCE_BLUE


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
    console.print(header_table)
    console.print()

    total_h = 0.0
    for day in sorted(overall_days):
        day_payload = overall_days[day]
        total_h += day_payload["hours"]

        # Day header: date plus hours and session count on the tree root label
        day_title = Text.assemble(
            ("● ", STYLE_META),
            (day, STYLE_HEADING),
            ("  ", ""),
            (f"{day_payload['hours']:.1f}h", f"bold {CLR_VALUE_ORANGE}"),
            (" | ", STYLE_META),
            (f"{len(day_payload['sessions'])} sessions", STYLE_LABEL),
        )
        day_tree = Tree(day_title, guide_style=STYLE_META)

        for idx, (start_ts, end_ts, session_events) in enumerate(day_payload["sessions"], 1):
            raw_dur = session_duration_hours_fn(
                session_events, start_ts, end_ts, args.min_session, args.min_session_passive
            )
            session_projects = sorted({event["project"] for event in session_events})

            session_text = Text.assemble(
                (f"[{idx}] ", STYLE_META),
                (f"{start_ts.strftime('%H:%M')}-{end_ts.strftime('%H:%M')} ", f"bold {STYLE_POSITIVE}"),
                (f"({raw_dur:.1f}h) ", f"bold {CLR_VALUE_ORANGE}"),
                (", ".join(session_projects), f"italic {STYLE_META}"),
            )

            session_node = day_tree.add(session_text)

            use_compact = getattr(args, "compact", False) and not getattr(args, "all_events", False)
            if use_compact:
                display_events = pick_session_preview_events(session_events, source_order)
            else:
                display_events = session_events

            for event in display_events:
                src_color = get_source_color(event["source"])
                event_line = Text.assemble(
                    (f"{event['local_ts'].strftime('%H:%M')} ", STYLE_POSITIVE),
                    (f"{_display_source_label(event['source'])} ", f"italic {src_color}"),
                    (f"{event['project']} ", STYLE_LABEL),
                    (format_event_detail(event), STYLE_META),
                )
                session_node.add(event_line)

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
        console.print()

    # Review summary dashboard
    console.print(f"[{STYLE_HEADING}]Review summary[/{STYLE_HEADING}]")
    summary_table = Table.grid(padding=(0, 2))
    summary_table.add_column(style=f"bold {STYLE_BODY}", no_wrap=True)
    summary_table.add_column(justify="right", style=STYLE_BODY, no_wrap=True)

    summary_table.add_row(
        "Observed timeline hours",
        f"[bold {CLR_VALUE_ORANGE}]{total_h:.1f}h[/bold {CLR_VALUE_ORANGE}]",
    )

    if presence_estimated is not None and getattr(presence_estimated, "available", False):
        est_total = float(getattr(presence_estimated, "total_hours", 0.0) or 0.0)
        summary_table.add_row(
            "Est. (presence)",
            f"[italic {STYLE_META}]{est_total:.1f}h[/italic {STYLE_META}]",
        )

    if args.billable_unit and args.billable_unit > 0:
        grand_billable = sum(
            billable_total_hours_fn(
                sum(day_payload["hours"] for day_payload in project_reports[pn].values()),
                args.billable_unit,
            )
            for pn in project_reports
        )
        summary_table.add_row(
            f"Billable Total (up to {args.billable_unit:g}h)",
            f"[bold {CLR_VALUE_ORANGE}]{grand_billable:.2f}h[/bold {CLR_VALUE_ORANGE}]",
        )

    screen_total_h: Optional[float] = None
    if screen_time_days:
        screen_total_h = sum(screen_time_days.values()) / 3600
        summary_table.add_row("Screen Time Comparison", f"{screen_total_h:.1f}h")
        observed_delta = total_h - screen_total_h
        if presence_estimated is not None and getattr(presence_estimated, "available", False):
            est_total = float(getattr(presence_estimated, "total_hours", 0.0) or 0.0)
            est_delta = est_total - screen_total_h
            summary_table.add_row(
                "Delta (est.)",
                f"[bold {CLR_VALUE_ORANGE}]{est_delta:+.1f}h[/bold {CLR_VALUE_ORANGE}]",
            )
            summary_table.add_row(
                "Delta (evidenced)",
                f"[italic {STYLE_META}]{observed_delta:+.1f}h[/italic {STYLE_META}]",
            )
        else:
            summary_table.add_row("Delta", f"{observed_delta:+.1f}h")

    console.print(summary_table)
    if presence_estimated is not None and getattr(presence_estimated, "available", False):
        console.print(
            f"[{STYLE_META}]Est. (presence): soft-work fill between evidenced events, "
            f"capped by Screen Time — not billable. Delta (est.) compares estimate to "
            f"Screen Time; Delta (evidenced) is the honest event floor.[/{STYLE_META}]"
        )

    print_report_warnings(
        console,
        overall_days=overall_days,
        project_reports=project_reports,
        observed_hours=total_h,
        screen_time_hours=screen_total_h,
        session_duration_hours_fn=session_duration_hours_fn,
        args=args,
    )

    console.print()
    if getattr(args, "only_project", None):
        flat_events: List[Dict[str, Any]] = []
        for day_payload in overall_days.values():
            for _start_ts, _end_ts, session_events in day_payload.get("sessions", []):
                flat_events.extend(session_events)
        print_project_source_mix(
            events=flat_events,
            project_name=str(args.only_project),
            source_order=source_order,
        )

    additive_summary = bool(getattr(args, "additive_summary", False))
    additive_project_hours: Dict[str, float] = {}
    additive_project_days: Dict[str, set[str]] = {}
    if additive_summary:
        per_project_hours = defaultdict(float)
        per_project_days = defaultdict(set)
        for day, day_payload in overall_days.items():
            for start_ts, end_ts, session_events in day_payload["sessions"]:
                counts = defaultdict(int)
                for event in session_events:
                    project_name = str(event.get("project", "")).strip()
                    if project_name:
                        counts[project_name] += 1
                if not counts:
                    continue
                primary_project = sorted(counts.items(), key=lambda item: (-item[1], item[0].lower()))[0][0]
                raw_dur = session_duration_hours_fn(
                    session_events, start_ts, end_ts, args.min_session, args.min_session_passive
                )
                per_project_hours[primary_project] += raw_dur
                per_project_days[primary_project].add(day)
        additive_project_hours = dict(per_project_hours)
        additive_project_days = dict(per_project_days)

    # Customer/project review breakdown
    heading = "Project-hour review"
    if additive_summary:
        heading += " (additive: primary project per session)"
    console.print(f"[{STYLE_HEADING}]{heading}[/{STYLE_HEADING}]")
    show_history = bool(getattr(args, "history_source", False))
    show_git = bool(git_project_totals)
    show_totals = bool(timelog_project_totals) and not show_history
    breakdown_table = Table.grid(padding=(0, 2))
    breakdown_table.add_column(style=STYLE_BODY)
    breakdown_table.add_column(justify="right", style=STYLE_BODY, no_wrap=True)
    if show_totals:
        breakdown_table.add_column(justify="right", style=STYLE_BODY, no_wrap=True)
    if show_git:
        breakdown_table.add_column(justify="right", style=STYLE_BODY, no_wrap=True)
    breakdown_table.add_column(justify="right", style=STYLE_BODY, no_wrap=True)
    breakdown_table.add_column(justify="right", style=STYLE_META, no_wrap=True)
    header_row = ["", f"[{STYLE_META}]Hours[/{STYLE_META}]"]
    if show_totals:
        header_row.append(f"[{STYLE_META}]TIMELOG (all-time)[/{STYLE_META}]")
    if show_git:
        header_row.append(f"[{STYLE_META}]{git_column_label(args)}[/{STYLE_META}]")
    header_row += [f"[{STYLE_META}]Billable[/{STYLE_META}]", f"[{STYLE_META}]Days[/{STYLE_META}]"]
    breakdown_table.add_row(*header_row)

    profile_by_name = {p["name"]: p for p in profiles}
    projects_by_customer = defaultdict(list)
    project_names = sorted(project_reports)
    if additive_summary:
        project_names = sorted(additive_project_hours)
    for project_name in project_names:
        customer = str(profile_by_name.get(project_name, {}).get("customer") or project_name)
        projects_by_customer[customer].append(project_name)

    for customer_name in sorted(projects_by_customer, key=lambda name: name.lower()):
        customer_projects = projects_by_customer[customer_name]
        customer_hours = sum(
            (additive_project_hours[p] if additive_summary else sum(day_payload["hours"] for day_payload in project_reports[p].values()))
            for p in customer_projects
        )

        cust_b_text = "-"
        if args.billable_unit and args.billable_unit > 0:
            cust_b = sum(
                billable_total_hours_fn(
                    additive_project_hours[p]
                    if additive_summary
                    else sum(day_payload["hours"] for day_payload in project_reports[p].values()),
                    args.billable_unit,
                )
                for p in customer_projects
            )
            cust_b_text = f"{cust_b:.2f}h"

        cust_row = [
            f"[bold {STYLE_BODY}]{customer_name}[/bold {STYLE_BODY}]",
            f"[bold {CLR_VALUE_ORANGE}]{customer_hours:.1f}h[/bold {CLR_VALUE_ORANGE}]",
        ]
        if show_totals:
            cust_total = sum((timelog_project_totals or {}).get(p, 0.0) for p in customer_projects)
            cust_total_text = f"{cust_total:.1f}h" if cust_total else "—"
            cust_row.append(f"[bold {CLR_VALUE_ORANGE}]{cust_total_text}[/bold {CLR_VALUE_ORANGE}]")
        if show_git:
            cust_git = sum((git_project_totals or {}).get(p, 0.0) for p in customer_projects)
            cust_git_text = f"{cust_git:.1f}h" if cust_git else "—"
            cust_row.append(f"[bold {CLR_VALUE_ORANGE}]{cust_git_text}[/bold {CLR_VALUE_ORANGE}]")
        cust_row += [f"[bold {CLR_VALUE_ORANGE}]{cust_b_text}[/bold {CLR_VALUE_ORANGE}]", ""]
        breakdown_table.add_row(*cust_row)

        for project_name in customer_projects:
            hours = (
                additive_project_hours[project_name]
                if additive_summary
                else sum(day_payload["hours"] for day_payload in project_reports[project_name].values())
            )
            days = (
                len(additive_project_days.get(project_name, set()))
                if additive_summary
                else len(project_reports[project_name])
            )
            proj_b_text = "-"
            if args.billable_unit and args.billable_unit > 0:
                proj_b = billable_total_hours_fn(hours, args.billable_unit)
                proj_b_text = f"{proj_b:.2f}h"

            proj_row = [
                f"[{STYLE_META}]  · {project_name}[/{STYLE_META}]",
                f"[{STYLE_BODY}]{hours:.1f}h[/{STYLE_BODY}]",
            ]
            if show_totals:
                proj_total = (timelog_project_totals or {}).get(project_name)
                proj_total_text = f"{proj_total:.1f}h" if proj_total is not None else "—"
                proj_row.append(f"[{STYLE_META}]{proj_total_text}[/{STYLE_META}]")
            if show_git:
                proj_git = (git_project_totals or {}).get(project_name)
                proj_git_text = f"{proj_git:.1f}h" if proj_git is not None else "—"
                proj_row.append(f"[{STYLE_META}]{proj_git_text}[/{STYLE_META}]")
            proj_row += [
                f"[{STYLE_BODY}]{proj_b_text}[/{STYLE_BODY}]",
                f"[{STYLE_META}]{days}[/{STYLE_META}]",
            ]
            breakdown_table.add_row(*proj_row)
        breakdown_table.add_section()

    console.print(breakdown_table)
    print_history_legend(console, args)

    # Footer legend: derive from canonical source order so new standalone sources
    # are automatically visible without manual output updates.
    legend = _build_dynamic_legend(source_order)
    console.print(legend)
    console.print(f"[{STYLE_META}]Nothing in this report is billable until explicitly approved.[/{STYLE_META}]\n")
