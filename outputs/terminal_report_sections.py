"""Review summary and project-hour sections for terminal reports."""

from __future__ import annotations

from collections import defaultdict
from contextlib import contextmanager
from datetime import date, datetime
from typing import Any, Dict, Iterator, List, Optional

from rich.console import Console
from rich.table import Table
from rich.text import Text

from core.anchor_nudge import should_prompt
from outputs.terminal_theme import (
    CLR_BERRY_BRIGHT,
    CLR_DIM,
    CLR_TEXT_SOFT,
    CLR_VALUE_ORANGE,
)

STYLE_HEADING = f"bold {CLR_BERRY_BRIGHT}"
STYLE_BODY = CLR_TEXT_SOFT
STYLE_META = CLR_DIM
from outputs.terminal_warnings import print_report_warnings


def _format_period_bound(value: Any) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def period_label(args: Any) -> str | None:
    """Human-readable report window from CLI args, or None when unset."""
    date_from = getattr(args, "date_from", None)
    date_to = getattr(args, "date_to", None)
    if not date_from or not date_to:
        return None
    start = _format_period_bound(date_from)
    end = _format_period_bound(date_to)
    if start == end:
        return start
    return f"{start} to {end}"


def period_heading_suffix(args: Any) -> str:
    """Suffix for section headings, e.g. ' (2026-05-01 to 2026-05-30)'."""
    label = period_label(args)
    return f" ({label})" if label else ""


@contextmanager
def report_section_spinner(
    console: Console,
    message: str,
    *,
    day_count: int,
) -> Iterator[None]:
    """Show a Rich spinner for heavier summary sections on multi-day reports."""
    if day_count >= 7 and should_prompt():
        with console.status(message, spinner="dots"):
            yield
    else:
        yield


def print_review_summary_section(
    console: Console,
    *,
    args: Any,
    total_h: float,
    project_reports: Dict[str, Any],
    screen_time_days: Optional[Dict[str, float]],
    presence_estimated: Any,
    overall_days: Dict[str, Any],
    session_duration_hours_fn: Any,
    billable_total_hours_fn: Any,
    billable_raw_by_project: Optional[Dict[str, float]] = None,
    reported_billing: bool = False,
    presence_edge_gaps: Any = None,
) -> None:
    """Print the Review summary block and sanity warnings."""
    console.print(f"[{STYLE_HEADING}]Review summary{period_heading_suffix(args)}[/{STYLE_HEADING}]")
    summary_table = Table.grid(padding=(0, 2))
    summary_table.add_column(style=f"bold {STYLE_BODY}", no_wrap=True)
    summary_table.add_column(justify="right", style=STYLE_BODY, no_wrap=True)

    summary_table.add_row(
        "Observed timeline hours",
        f"[bold {CLR_VALUE_ORANGE}]{total_h:.1f}h[/bold {CLR_VALUE_ORANGE}]",
    )

    attended_h = sum(float(d.get("attended_hours", 0.0)) for d in overall_days.values())
    mixed_h = sum(float(d.get("mixed_hours", 0.0)) for d in overall_days.values())
    agent_h = sum(float(d.get("agent_hours", 0.0)) for d in overall_days.values())
    if agent_h > 0 or mixed_h > 0:
        summary_table.add_row(
            "  · Attended / Mixed",
            f"[{STYLE_META}]{attended_h + mixed_h:.1f}h[/{STYLE_META}]",
        )
        summary_table.add_row(
            "  · Agent (autonomous)",
            f"[{STYLE_META}]{agent_h:.1f}h[/{STYLE_META}]",
        )

    if presence_estimated is not None and getattr(presence_estimated, "available", False):
        est_total = float(getattr(presence_estimated, "total_hours", 0.0) or 0.0)
        summary_table.add_row(
            "Est. (presence)",
            f"[italic {STYLE_META}]{est_total:.1f}h[/italic {STYLE_META}]",
        )

    if (
        presence_edge_gaps is not None
        and getattr(presence_edge_gaps, "available", False)
        and float(getattr(presence_edge_gaps, "total_edge_hours", 0.0) or 0.0) > 0
    ):
        edge_h = float(presence_edge_gaps.total_edge_hours)
        lead_h = float(presence_edge_gaps.total_lead_hours)
        trail_h = float(presence_edge_gaps.total_trail_hours)
        capped_h = float(getattr(presence_edge_gaps, "capped_edge_hours", 0.0) or 0.0)
        cap_min = int(getattr(presence_edge_gaps, "edge_cap_minutes", 10) or 10)
        summary_table.add_row(
            "Edge gap (presence)",
            f"[italic {STYLE_META}]{edge_h:.1f}h[/italic {STYLE_META}]",
        )
        summary_table.add_row(
            "  · Lead / Trail",
            f"[{STYLE_META}]{lead_h:.1f}h / {trail_h:.1f}h[/{STYLE_META}]",
        )
        summary_table.add_row(
            f"  · Bracketable (≤{cap_min}m/edge)",
            f"[{STYLE_META}]{capped_h:.1f}h[/{STYLE_META}]",
        )

    if args.billable_unit and args.billable_unit > 0:
        from core.domain import billable_raw_by_project as _billable_by_project

        include_agent = bool(getattr(args, "include_agent_billable", False))
        raw_by_project = billable_raw_by_project
        if raw_by_project is None:
            raw_by_project = _billable_by_project(project_reports, include_agent_billable=include_agent)
        # Sum the canonical billing set (incl. manual reported-only projects), not
        # just project_reports, so the total matches the invoice.
        grand_billable = sum(
            billable_total_hours_fn(hours, args.billable_unit)
            for hours in raw_by_project.values()
        )
        if reported_billing:
            note = " · from confirmed reported time"
        elif not include_agent:
            note = " · agent excluded"
        else:
            note = ""
        summary_table.add_row(
            f"Billable Total (up to {args.billable_unit:g}h{note})",
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
    if (
        presence_edge_gaps is not None
        and getattr(presence_edge_gaps, "available", False)
        and float(getattr(presence_edge_gaps, "total_edge_hours", 0.0) or 0.0) > 0
    ):
        console.print(
            f"[{STYLE_META}]Edge gap (presence): unique wall-clock of continuous Timely "
            f"Memory adjacent to session edges (lead before first event / trail after "
            f"last). Bracketable applies the Slice 2 default per-edge cap. Diagnostic "
            f"only — does not change observed hours (GH-332 Slice 1).[/{STYLE_META}]"
        )

    print_report_warnings(
        console,
        overall_days=overall_days,
        project_reports=project_reports,
        observed_hours=total_h,
        screen_time_hours=screen_total_h,
        screen_time_days=screen_time_days,
        session_duration_hours_fn=session_duration_hours_fn,
        args=args,
    )


def print_project_hour_review_section(
    console: Console,
    *,
    args: Any,
    overall_days: Dict[str, Any],
    project_reports: Dict[str, Any],
    profiles: List[Dict[str, Any]],
    timelog_project_totals: Optional[Dict[str, float]],
    git_project_totals: Optional[Dict[str, float]],
    session_duration_hours_fn: Any,
    billable_total_hours_fn: Any,
) -> None:
    """Print customer/project hour breakdown."""
    additive_summary = bool(getattr(args, "additive_summary", False))
    additive_project_hours: Dict[str, float] = {}
    additive_project_days: Dict[str, set[str]] = {}
    if additive_summary:
        per_project_hours = defaultdict(float)
        per_project_days = defaultdict(set)
        for day, day_payload in overall_days.items():
            for session in day_payload["sessions"]:
                start_ts, end_ts, session_events = session[:3]
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

    heading = f"Project-hour review{period_heading_suffix(args)}"
    if additive_summary:
        heading += " (additive: primary project per session)"
    console.print(f"[{STYLE_HEADING}]{heading}[/{STYLE_HEADING}]")
    show_totals = bool(timelog_project_totals)
    show_git = bool(git_project_totals)
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
        header_row.append(f"[{STYLE_META}]Total observed[/{STYLE_META}]")
    if show_git:
        header_row.append(f"[{STYLE_META}]Git only[/{STYLE_META}]")
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
            (
                additive_project_hours[p]
                if additive_summary
                else sum(day_payload["hours"] for day_payload in project_reports[p].values())
            )
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

        cust_hours_text = Text.assemble(
            (f"{customer_hours:.1f}h", f"bold {CLR_VALUE_ORANGE}")
        )
        if not additive_summary:
            cust_attended_h = sum(
                sum(
                    float(day_payload.get("attended_hours", 0.0)) + float(day_payload.get("mixed_hours", 0.0))
                    for day_payload in project_reports[p].values()
                )
                for p in customer_projects
            )
            cust_agent_h = sum(
                sum(
                    float(day_payload.get("agent_hours", 0.0))
                    for day_payload in project_reports[p].values()
                )
                for p in customer_projects
            )
            cust_mixed_h = sum(
                sum(
                    float(day_payload.get("mixed_hours", 0.0))
                    for day_payload in project_reports[p].values()
                )
                for p in customer_projects
            )
            if cust_agent_h > 0 or cust_mixed_h > 0:
                cust_hours_text.append(f" ({cust_attended_h:.1f} + {cust_agent_h:.1f})", STYLE_META)

        cust_row = [
            f"[bold {STYLE_BODY}]{customer_name}[/bold {STYLE_BODY}]",
            cust_hours_text,
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
                proj_total = (timelog_project_totals or {}).get(project_name, 0.0)
                proj_total_text = f"{proj_total:.1f}h" if proj_total else "—"
                proj_row.append(f"[{STYLE_META}]{proj_total_text}[/{STYLE_META}]")
            if show_git:
                proj_git = (git_project_totals or {}).get(project_name, 0.0)
                proj_git_text = f"{proj_git:.1f}h" if proj_git else "—"
                proj_row.append(f"[{STYLE_META}]{proj_git_text}[/{STYLE_META}]")
            proj_row += [
                f"[{STYLE_BODY}]{proj_b_text}[/{STYLE_BODY}]",
                f"[{STYLE_META}]{days}[/{STYLE_META}]",
            ]
            breakdown_table.add_row(*proj_row)
        breakdown_table.add_section()

    console.print(breakdown_table)
