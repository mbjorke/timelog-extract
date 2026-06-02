"""Weekly (ISO week × project) pivot of per-project daily hours.

This reuses the hours already computed by ``aggregate_report`` — it does not
recompute sessions. Input is the ``project_reports`` mapping
(``{project: {day_iso: {"hours": float, ...}}}``); output is a pivot suitable
for a WeekNumber × project table with row/column/grand totals.

Motivated by the Pierre persona (docs/product/persona-pierre-calendar-timereport.md):
his existing tool's core view is a WeekNumber × project pivot, so a familiar
weekly view is a parity win.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List


def iso_week_label(day_iso: str) -> str:
    """ISO day string ``YYYY-MM-DD`` -> ISO week label ``YYYY-Www`` (e.g. 2025-W32)."""
    y, w, _ = date.fromisoformat(day_iso).isocalendar()
    return f"{y}-W{w:02d}"


@dataclass
class WeeklyPivot:
    weeks: List[str]                       # sorted ISO week labels (rows)
    projects: List[str]                    # sorted project names (columns)
    cells: Dict[str, Dict[str, float]]     # cells[week][project] -> hours
    week_totals: Dict[str, float]          # week -> total hours across projects
    project_totals: Dict[str, float]       # project -> total hours across weeks
    grand_total: float = 0.0
    _empty: bool = field(default=False, repr=False)

    @property
    def is_empty(self) -> bool:
        return not self.weeks


def pivot_hours_by_week_project(
    project_reports: Dict[str, Dict[str, Dict[str, Any]]],
    *,
    round_ndigits: int = 2,
) -> WeeklyPivot:
    """Pivot per-project daily hours into an ISO week × project table.

    ``project_reports`` is ``ReportPayload.project_reports``:
    ``{project: {day_iso: {"hours": float, ...}}}``. Days with zero hours still
    contribute nothing; weeks/projects with no hours do not appear.
    """
    cells: Dict[str, Dict[str, float]] = {}
    week_totals: Dict[str, float] = {}
    project_totals: Dict[str, float] = {}
    grand_total = 0.0

    for project, day_map in project_reports.items():
        for day_iso, day_data in day_map.items():
            hours = float(day_data.get("hours", 0.0) or 0.0)
            if hours <= 0:
                continue
            week = iso_week_label(day_iso)
            cells.setdefault(week, {})
            cells[week][project] = cells[week].get(project, 0.0) + hours
            week_totals[week] = week_totals.get(week, 0.0) + hours
            project_totals[project] = project_totals.get(project, 0.0) + hours
            grand_total += hours

    def _round_map(m: Dict[str, float]) -> Dict[str, float]:
        return {k: round(v, round_ndigits) for k, v in m.items()}

    cells = {w: _round_map(p) for w, p in cells.items()}

    return WeeklyPivot(
        weeks=sorted(cells.keys()),
        projects=sorted(project_totals.keys()),
        cells=cells,
        week_totals=_round_map(week_totals),
        project_totals=_round_map(project_totals),
        grand_total=round(grand_total, round_ndigits),
    )
