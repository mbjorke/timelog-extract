"""Status table helpers for --history columns."""

from __future__ import annotations

from typing import Any, Dict, Iterable, Set


def historical_project_names(
    report: Any,
    *,
    show_history: bool,
) -> Set[str]:
    git_totals = report.git_project_totals or {}
    timelog_totals = report.timelog_project_totals or {}
    names: Set[str] = set()
    if show_history:
        names |= set(git_totals)
        names |= set(timelog_totals)
    return names


def history_table_cells(
    project_name: str,
    *,
    show_history: bool,
    git_totals: Dict[str, float],
    timelog_totals: Dict[str, float],
) -> list[str]:
    if not show_history:
        return []
    git_h = git_totals.get(project_name, 0.0)
    wl_h = timelog_totals.get(project_name, 0.0)
    return [
        f"{git_h:.1f}h" if git_h else "—",
        f"{wl_h:.1f}h" if wl_h else "—",
    ]


def sorted_status_projects(
    project_reports: Dict[str, Any],
    historical_names: Iterable[str],
    *,
    show_history: bool,
) -> list[str]:
    names = set(project_reports)
    if show_history:
        names |= set(historical_names)
    return sorted(names, key=lambda n: n.lower())
