"""Project-hour review breakdown table for terminal report output."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Optional, Set

from rich.console import Console
from rich.table import Table

from outputs.terminal_history import git_column_label, print_history_legend
from outputs.terminal_theme import (
    CLR_BERRY_BRIGHT,
    CLR_DIM,
    CLR_TEXT_SOFT,
    CLR_VALUE_ORANGE,
    CLR_MUTED,
)

STYLE_HEADING = f"bold {CLR_BERRY_BRIGHT}"
STYLE_BODY = CLR_TEXT_SOFT
STYLE_META = CLR_DIM


def _hours_cell(value: Optional[float], *, bold: bool = False) -> str:
    if value is None:
        text = "—"
        if bold:
            return f"[bold {CLR_VALUE_ORANGE}]{text}[/bold {CLR_VALUE_ORANGE}]"
        return f"[{STYLE_META}]{text}[/{STYLE_META}]"
    text = f"{value:.1f}h"
    if bold:
        return f"[bold {CLR_VALUE_ORANGE}]{text}[/bold {CLR_VALUE_ORANGE}]"
    return f"[{STYLE_BODY}]{text}[/{STYLE_BODY}]"


def print_project_hour_breakdown(
    console: Console,
    *,
    overall_days: Dict[str, Any],
    project_reports: Dict[str, Any],
    profiles: List[Dict[str, Any]],
    args: Any,
    session_duration_hours_fn: Any,
    billable_total_hours_fn: Any,
    timelog_project_totals: Optional[Dict[str, float]] = None,
    git_project_totals: Optional[Dict[str, float]] = None,
    observed_project_totals: Optional[Dict[str, float]] = None,
) -> None:
    additive_summary = bool(getattr(args, "additive_summary", False))
    additive_project_hours: Dict[str, float] = {}
    additive_project_days: Dict[str, Set[str]] = {}
    if additive_summary:
        per_project_hours = defaultdict(float)
        per_project_days: Dict[str, Set[str]] = defaultdict(set)
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

    heading = "Project-hour review"
    if additive_summary:
        heading += " (additive: primary project per session)"
    console.print(f"[{STYLE_HEADING}]{heading}[/{STYLE_HEADING}]")

    show_history = bool(getattr(args, "history_source", False))
    show_observed = show_history
    show_git = show_history or bool(git_project_totals)
    show_totals = bool(timelog_project_totals) and not show_history

    breakdown_table = Table.grid(padding=(0, 2))
    breakdown_table.add_column(style=STYLE_BODY)
    breakdown_table.add_column(justify="right", style=STYLE_BODY, no_wrap=True)
    if show_observed:
        breakdown_table.add_column(justify="right", style=STYLE_BODY, no_wrap=True)
    if show_totals:
        breakdown_table.add_column(justify="right", style=STYLE_BODY, no_wrap=True)
    if show_git:
        breakdown_table.add_column(justify="right", style=STYLE_BODY, no_wrap=True)
    breakdown_table.add_column(justify="right", style=STYLE_BODY, no_wrap=True)
    breakdown_table.add_column(justify="right", style=STYLE_META, no_wrap=True)

    header_row = ["", f"[{STYLE_META}]Hours[/{STYLE_META}]"]
    if show_observed:
        header_row.append(f"[{STYLE_META}]Total (observed)[/{STYLE_META}]")
    if show_totals:
        header_row.append(f"[{STYLE_META}]TIMELOG (all-time)[/{STYLE_META}]")
    if show_git:
        header_row.append(f"[{STYLE_META}]{git_column_label(args)}[/{STYLE_META}]")
    header_row += [f"[{STYLE_META}]Billable[/{STYLE_META}]", f"[{STYLE_META}]Days[/{STYLE_META}]"]
    breakdown_table.add_row(*header_row)

    profile_by_name = {p["name"]: p for p in profiles}
    projects_by_customer: Dict[str, List[str]] = defaultdict(list)
    project_names = sorted(additive_project_hours) if additive_summary else sorted(project_reports)
    for project_name in project_names:
        customer = str(profile_by_name.get(project_name, {}).get("customer") or project_name)
        projects_by_customer[customer].append(project_name)

    def _project_hours(name: str) -> float:
        if additive_summary:
            return additive_project_hours[name]
        return sum(day_payload["hours"] for day_payload in project_reports[name].values())

    for customer_name in sorted(projects_by_customer, key=lambda name: name.lower()):
        customer_projects = projects_by_customer[customer_name]
        customer_hours = sum(_project_hours(p) for p in customer_projects)
        cust_b_text = "-"
        if args.billable_unit and args.billable_unit > 0:
            cust_b = sum(billable_total_hours_fn(_project_hours(p), args.billable_unit) for p in customer_projects)
            cust_b_text = f"{cust_b:.2f}h"

        cust_row = [
            f"[bold {STYLE_BODY}]{customer_name}[/bold {STYLE_BODY}]",
            f"[bold {CLR_VALUE_ORANGE}]{customer_hours:.1f}h[/bold {CLR_VALUE_ORANGE}]",
        ]
        if show_observed:
            cust_obs = sum((observed_project_totals or {}).get(p, 0.0) for p in customer_projects)
            cust_row.append(_hours_cell(cust_obs if cust_obs else None, bold=True))
        if show_totals:
            cust_total = sum((timelog_project_totals or {}).get(p, 0.0) for p in customer_projects)
            cust_row.append(_hours_cell(cust_total if cust_total else None, bold=True))
        if show_git:
            cust_git = sum((git_project_totals or {}).get(p, 0.0) for p in customer_projects)
            cust_row.append(_hours_cell(cust_git if cust_git else None, bold=True))
        cust_row += [f"[bold {CLR_VALUE_ORANGE}]{cust_b_text}[/bold {CLR_VALUE_ORANGE}]", ""]
        breakdown_table.add_row(*cust_row)

        for project_name in customer_projects:
            hours = _project_hours(project_name)
            days = (
                len(additive_project_days.get(project_name, set()))
                if additive_summary
                else len(project_reports[project_name])
            )
            proj_b_text = "-"
            if args.billable_unit and args.billable_unit > 0:
                proj_b_text = f"{billable_total_hours_fn(hours, args.billable_unit):.2f}h"

            proj_row = [
                f"[{STYLE_META}]  · {project_name}[/{STYLE_META}]",
                f"[{STYLE_BODY}]{hours:.1f}h[/{STYLE_BODY}]",
            ]
            if show_observed:
                proj_row.append(_hours_cell((observed_project_totals or {}).get(project_name)))
            if show_totals:
                proj_row.append(_hours_cell((timelog_project_totals or {}).get(project_name)))
            if show_git:
                proj_row.append(_hours_cell((git_project_totals or {}).get(project_name)))
            proj_row += [f"[{STYLE_BODY}]{proj_b_text}[/{STYLE_BODY}]", f"[{STYLE_META}]{days}[/{STYLE_META}]"]
            breakdown_table.add_row(*proj_row)
        breakdown_table.add_section()

    console.print(breakdown_table)
    print_history_legend(console, args)
