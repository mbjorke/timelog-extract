"""Terminal report rendering using Rich for a professional CLI experience."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Sequence, Optional
from datetime import datetime
from rich.console import Console, Group
from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns
from rich.text import Text
from rich.tree import Tree
from rich import box

from outputs.gittan_banner import TAGLINE, banner_panel_lines

console = Console()

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
    
    table = Table(title="Source Summary", box=box.ROUNDED)
    table.add_column("Source", style="cyan")
    table.add_column("Events", justify="right", style="green")
    
    for src in sorted(counts, key=lambda s: source_order.index(s) if s in source_order else 99):
        table.add_row(src, str(counts[src]))
    
    table.add_section()
    table.add_row("[bold]Total[/bold]", f"[bold]{sum(counts.values())}[/bold]")
    
    console.print(table)


def get_source_color(source: str) -> str:
    source_lower = source.lower()
    if "claude" in source_lower: return "orange3"
    if "gemini" in source_lower: return "blue"
    if "cursor" in source_lower: return "cyan"
    if "chrome" in source_lower: return "red"
    if "mail" in source_lower: return "yellow"
    if "timelog" in source_lower: return "magenta"
    if "github" in source_lower: return "green"
    return "white"


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
    art = Text("\n".join(banner_panel_lines()), style="cyan")
    headline = Text.assemble(
        ("GITTAN", "bold blue"),
        " — Local Activity & Time Report\n",
        (TAGLINE, "dim"),
    )
    console.print(
        Panel.fit(
            Group(art, Text(""), headline),
            border_style="blue",
            box=box.DOUBLE,
        )
    )

    # Header Info
    header_table = Table.grid(padding=(0, 2))
    header_table.add_row("[bold]Timezone:[/bold]", str(local_tz))
    if config_path:
        header_table.add_row("[bold]Config:[/bold]", str(config_path))
    header_table.add_row("[bold]Projects:[/bold]", ", ".join(p["name"] for p in profiles))
    console.print(header_table)
    console.print()

    total_h = 0.0
    for day in sorted(overall_days):
        day_payload = overall_days[day]
        total_h += day_payload["hours"]
        
        # Day Header Panel
        day_title = Text.assemble(("📅  ", "bold"), (day, "bold yellow"))
        day_stats = f" [cyan]{day_payload['hours']:.1f}h[/cyan] | [magenta]{len(day_payload['sessions'])} sessions[/magenta]"
        
        day_tree = Tree(day_title)
        
        for idx, (start_ts, end_ts, session_events) in enumerate(day_payload["sessions"], 1):
            raw_dur = session_duration_hours_fn(
                session_events, start_ts, end_ts, args.min_session, args.min_session_passive
            )
            session_projects = sorted({event["project"] for event in session_events})
            
            session_text = Text.assemble(
                (f"[{idx}] ", "dim"),
                (f"{start_ts.strftime('%H:%M')}–{end_ts.strftime('%H:%M')} ", "bold green"),
                (f"({raw_dur:.1f}h) ", "cyan"),
                (", ".join(session_projects), "italic blue")
            )
            
            session_node = day_tree.add(session_text)
            
            if getattr(args, "all_events", False):
                display_events = session_events
            else:
                display_events = pick_session_preview_events(session_events, source_order, max_lines=5)
            
            for event in display_events:
                src_color = get_source_color(event["source"])
                event_line = Text.assemble(
                    (f"{event['local_ts'].strftime('%H:%M')} ", "dim"),
                    (f"[{event['source']}] ", src_color),
                    (f"[{event['project']}] ", "blue"),
                    (event["detail"], "white")
                )
                session_node.add(event_line)
            
            if not getattr(args, "all_events", False) and len(display_events) < len(session_events):
                session_node.add(Text(f"… and {len(session_events) - len(display_events)} more", style="dim italic"))
        
        console.print(day_tree)
        
        if screen_time_days and day in screen_time_days:
            screen_h = screen_time_days[day] / 3600
            delta = day_payload["hours"] - screen_h
            console.print(f"    [dim]Screen Time: {screen_h:.1f}h (delta {delta:+.1f}h)[/dim]")
        console.print()

    # Final Summary Dashboard
    summary_table = Table(title="Final Summary", box=box.DOUBLE_EDGE, header_style="bold magenta")
    summary_table.add_column("Metric", style="bold")
    summary_table.add_column("Value", justify="right")
    
    summary_table.add_row("Total Estimated Hours (Raw)", f"[bold green]{total_h:.1f}h[/bold green]")
    
    if args.billable_unit and args.billable_unit > 0:
        grand_billable = sum(
            billable_total_hours_fn(
                sum(day_payload["hours"] for day_payload in project_reports[pn].values()),
                args.billable_unit,
            )
            for pn in project_reports
        )
        summary_table.add_row(f"Billable Total (up to {args.billable_unit:g}h)", f"[bold yellow]{grand_billable:.2f}h[/bold yellow]")
    
    if screen_time_days:
        screen_total_h = sum(screen_time_days.values()) / 3600
        summary_table.add_row("Screen Time Comparison", f"{screen_total_h:.1f}h")
        summary_table.add_row("Delta", f"{total_h - screen_total_h:+.1f}h")
    
    console.print(summary_table)
    console.print()

    # Customer/Project Breakdown
    breakdown_table = Table(title="Hours by Customer & Project", box=box.ROUNDED)
    breakdown_table.add_column("Customer / Project", style="cyan")
    breakdown_table.add_column("Raw Hours", justify="right")
    breakdown_table.add_column("Billable", justify="right", style="green")
    breakdown_table.add_column("Days", justify="right", style="dim")

    profile_by_name = {p["name"]: p for p in profiles}
    projects_by_customer = defaultdict(list)
    for project_name in sorted(project_reports):
        customer = str(profile_by_name.get(project_name, {}).get("customer") or project_name)
        projects_by_customer[customer].append(project_name)

    for customer_name in sorted(projects_by_customer, key=lambda name: name.lower()):
        customer_projects = projects_by_customer[customer_name]
        customer_hours = sum(
            sum(day_payload["hours"] for day_payload in project_reports[p].values())
            for p in customer_projects
        )
        
        cust_b_text = "-"
        if args.billable_unit and args.billable_unit > 0:
            cust_b = sum(
                billable_total_hours_fn(
                    sum(day_payload["hours"] for day_payload in project_reports[p].values()),
                    args.billable_unit,
                )
                for p in customer_projects
            )
            cust_b_text = f"{cust_b:.2f}h"

        breakdown_table.add_row(
            f"[bold]{customer_name}[/bold]",
            f"[bold]{customer_hours:.1f}h[/bold]",
            f"[bold]{cust_b_text}[/bold]",
            ""
        )
        
        for project_name in customer_projects:
            hours = sum(day_payload["hours"] for day_payload in project_reports[project_name].values())
            days = len(project_reports[project_name])
            proj_b_text = "-"
            if args.billable_unit and args.billable_unit > 0:
                proj_b = billable_total_hours_fn(hours, args.billable_unit)
                proj_b_text = f"{proj_b:.2f}h"
            
            breakdown_table.add_row(
                f"  · {project_name}",
                f"{hours:.1f}h",
                proj_b_text,
                str(days)
            )
        breakdown_table.add_section()

    console.print(breakdown_table)
    
    # Footer Legend
    legend = Text.assemble(
        ("Legend: ", "bold"),
        ("[Claude] ", get_source_color("Claude")),
        ("[Gemini] ", get_source_color("Gemini")),
        ("[Cursor] ", get_source_color("Cursor")),
        ("[Chrome] ", get_source_color("Chrome")),
        ("[Mail] ", get_source_color("Mail")),
        ("[GitHub] ", get_source_color("GitHub")),
    )
    console.print(legend)
    console.print()
