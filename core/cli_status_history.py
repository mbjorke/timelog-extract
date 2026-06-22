"""Status table helpers for --history columns."""

from __future__ import annotations

from typing import Any, Dict, Iterable, Set


def historical_project_names(
    report: Any,
    *,
    show_history: bool,
) -> Set[str]:
    names: Set[str] = set()
    if show_history:
        names |= set(report.git_project_totals or {})
        names |= set(report.observed_project_totals or {})
    return names


def history_observed_cell(
    project_name: str,
    *,
    show_history: bool,
    observed_totals: Dict[str, float],
) -> str:
    if not show_history:
        return ""
    observed_h = observed_totals.get(project_name)
    return f"{observed_h:.1f}h" if observed_h is not None else "—"


def history_git_cell(project_name: str, *, show_history: bool, git_totals: Dict[str, float]) -> str:
    if not show_history:
        return ""
    git_h = git_totals.get(project_name)
    return f"{git_h:.1f}h" if git_h is not None else "—"


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


HISTORY_LEGEND = (
    "Hours are for the selected period. Total (observed) uses all logs Gittan can still read; "
    "Git estimate uses commits only. Compare — do not add. Retention limits apply."
)
