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
from outputs.terminal_theme import (
    CLR_BERRY_BRIGHT,
    CLR_DIM,
    CLR_GREEN,
    CLR_SOURCE_BLUE,
    CLR_TEXT_SOFT,
    CLR_VALUE_ORANGE,
    CLR_MUTED,
    STYLE_BORDER,
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
        legend.append(source, style=f"italic {get_source_color(source)}")
        if idx < len(source_order) - 1:
            legend.append("  ", style=STYLE_META)
    return legend


def pick_session_preview_events(
    session_events: Sequence[Dict[str, Any]],
    source_order: Sequence[str],
    max_lines: int = 5,
) -> List[Dict[str, Any]]:
    """
    Pick up to max_lines events to print for a session: prefer at least one distinct
    line per source (first chronological hit per source), then fill remaining slots
    in time order with distinct project|detail markers.
    """
    ordered = sorted(session_events, key=lambda e: e["local_ts"])
    sources_seen: List[str] = []
    for ev in ordered:
        if ev["source"] not in sources_seen:
            sources_seen.append(ev["source"])
    sources_by_order = sorted(
        sources_seen,
        key=lambda s: source_order.index(s) if s in source_order else 99,
    )
    markers = set()
    picked: List[Dict[str, Any]] = []

    def try_add(event: Dict[str, Any]) -> bool:
        marker = f"{event['project']} | {event['detail']}"
        if marker in markers:
            return False
        markers.add(marker)
        picked.append(event)
        return True

    for src in sources_by_order:
        if len(picked) >= max_lines:
            break
        for event in ordered:
            if event["source"] != src:
                continue
            if try_add(event):
                break

    for event in ordered:
        if len(picked) >= max_lines:
            break
        try_add(event)

    return picked


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
        table.add_row(src, str(counts[src]))
    table.add_section()
    table.add_row(
        f"[bold {STYLE_LABEL}]Total[/bold {STYLE_LABEL}]",
        f"[bold {CLR_VALUE_ORANGE}]{sum(counts.values())}[/bold {CLR_VALUE_ORANGE}]",
    )

    console.print(table)
    console.print(
        f"[{STYLE_META}]Review these counts before trusting attribution or invoice totals.[/{STYLE_META}]"
    )


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
        mix_table.add_row(src, str(counts[src]))
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

            if getattr(args, "all_events", False):
                display_events = session_events
            else:
                display_events = pick_session_preview_events(session_events, source_order, max_lines=5)

            for event in display_events:
                src_color = get_source_color(event["source"])
                event_line = Text.assemble(
                    (f"{event['local_ts'].strftime('%H:%M')} ", STYLE_POSITIVE),
                    (f"{event['source']} ", f"italic {src_color}"),
                    (f"{event['project']} ", STYLE_LABEL),
                    (event["detail"], STYLE_META),
                )
                session_node.add(event_line)

            if not getattr(args, "all_events", False) and len(display_events) < len(session_events):
                session_node.add(
                    Text(
                        f"… and {len(session_events) - len(display_events)} more",
                        style=f"italic {STYLE_META}",
                    )
                )

        console.print(day_tree)

        if screen_time_days and day in screen_time_days:
            screen_h = screen_time_days[day] / 3600
            delta = day_payload["hours"] - screen_h
            console.print(f"    [{STYLE_META}]Screen Time: {screen_h:.1f}h (delta {delta:+.1f}h)[/{STYLE_META}]")
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

    if screen_time_days:
        screen_total_h = sum(screen_time_days.values()) / 3600
        summary_table.add_row("Screen Time Comparison", f"{screen_total_h:.1f}h")
        summary_table.add_row("Delta", f"{total_h - screen_total_h:+.1f}h")

    console.print(summary_table)
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
    breakdown_table = Table.grid(padding=(0, 2))
    breakdown_table.add_column(style=STYLE_BODY)
    breakdown_table.add_column(justify="right", style=STYLE_BODY, no_wrap=True)
    breakdown_table.add_column(justify="right", style=STYLE_BODY, no_wrap=True)
    breakdown_table.add_column(justify="right", style=STYLE_META, no_wrap=True)
    breakdown_table.add_row(
        "",
        f"[{STYLE_META}]Hours[/{STYLE_META}]",
        f"[{STYLE_META}]Billable[/{STYLE_META}]",
        f"[{STYLE_META}]Days[/{STYLE_META}]",
    )

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

        breakdown_table.add_row(
            f"[bold {STYLE_BODY}]{customer_name}[/bold {STYLE_BODY}]",
            f"[bold {CLR_VALUE_ORANGE}]{customer_hours:.1f}h[/bold {CLR_VALUE_ORANGE}]",
            f"[bold {CLR_VALUE_ORANGE}]{cust_b_text}[/bold {CLR_VALUE_ORANGE}]",
            "",
        )

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

            breakdown_table.add_row(
                f"[{STYLE_META}]  · {project_name}[/{STYLE_META}]",
                f"[{STYLE_BODY}]{hours:.1f}h[/{STYLE_BODY}]",
                f"[{STYLE_BODY}]{proj_b_text}[/{STYLE_BODY}]",
                f"[{STYLE_META}]{days}[/{STYLE_META}]",
            )
        breakdown_table.add_section()

    console.print(breakdown_table)

    # Footer legend: derive from canonical source order so new standalone sources
    # are automatically visible without manual output updates.
    legend = _build_dynamic_legend(source_order)
    console.print(legend)
    console.print(
        f"[{STYLE_META}]Nothing in this report is billable until explicitly approved.[/{STYLE_META}]"
    )
    console.print()
