"""Screen Time gap analysis against estimated hours."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DayGap:
    day: str
    estimated_hours: float
    screen_time_hours: float
    coverage_ratio: float
    unexplained_screen_time_hours: float
    over_attributed_hours: float
    missing_reference_data: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "day": self.day,
            "estimated_hours": round(self.estimated_hours, 4),
            "screen_time_hours": round(self.screen_time_hours, 4),
            "coverage_ratio": round(self.coverage_ratio, 4),
            "unexplained_screen_time_hours": round(self.unexplained_screen_time_hours, 4),
            "over_attributed_hours": round(self.over_attributed_hours, 4),
            "missing_reference_data": self.missing_reference_data,
        }


def _project_hours_by_day(report) -> dict[str, dict[str, float]]:
    by_day: dict[str, dict[str, float]] = {}
    for project_name, days in report.project_reports.items():
        for day, payload in days.items():
            by_day.setdefault(day, {})
            by_day[day][project_name] = float(payload.get("hours", 0.0))
    return by_day


def analyze_screen_time_gaps(report) -> dict[str, Any]:
    """
    Compute per-day gaps between estimated hours and measured screen time, and distribute each day's signed gap to projects proportionally.
    
    Parameters:
        report: An object providing:
            - screen_time_days: mapping of day -> screen-seconds (may be None),
            - overall_days: mapping of day -> payload containing an "hours" value,
            - project_reports: mapping of project -> day -> payload with an "hours" value.
            These fields are used to align days and compute per-day and per-project allocations.
    
    Returns:
        dict[str, Any]: A dictionary with:
            - "days": list of per-day dictionaries (from DayGap.as_dict()) containing
              the day and numeric fields rounded to 4 decimals.
            - "totals": dictionary with aggregated totals rounded to 4 decimals:
                - "estimated_hours": sum of estimated hours,
                - "screen_time_hours": sum of screen time hours,
                - "coverage_ratio": total_estimated / total_screen when total_screen > 0,
                  otherwise 1.0 if total_estimated == 0 else 0.0,
                - "unexplained_screen_time_hours": sum of unexplained hours,
                - "over_attributed_hours": sum of over-attributed hours.
            - "project_allocated_gap_hours": mapping of project name -> signed gap in hours
              (positive means estimated > screen), values rounded to 4 decimals; entries
              are ordered by descending absolute gap then by project name (case-insensitive).
    """
    screen_time_days = report.screen_time_days or {}
    all_days = sorted(set(report.overall_days.keys()) | set(screen_time_days.keys()))
    rows: list[DayGap] = []
    project_allocated_gap: dict[str, float] = {}
    project_by_day = _project_hours_by_day(report)

    for day in all_days:
        estimated_hours = float((report.overall_days.get(day) or {}).get("hours", 0.0))
        screen_seconds = float(screen_time_days.get(day, 0.0) or 0.0)
        screen_hours = screen_seconds / 3600.0
        if screen_hours > 0:
            coverage = estimated_hours / screen_hours
        else:
            coverage = 1.0 if estimated_hours == 0 else math.inf
        missing_reference_data = screen_hours == 0.0 and estimated_hours > 0.0
        unexplained = max(screen_hours - estimated_hours, 0.0)
        over = max(estimated_hours - screen_hours, 0.0)
        rows.append(
            DayGap(
                day=day,
                estimated_hours=estimated_hours,
                screen_time_hours=screen_hours,
                coverage_ratio=coverage,
                unexplained_screen_time_hours=unexplained,
                over_attributed_hours=over,
                missing_reference_data=missing_reference_data,
            )
        )
        project_map = project_by_day.get(day, {})
        day_project_total = sum(project_map.values())
        if day_project_total <= 0:
            continue
        for project_name, hours in project_map.items():
            share = hours / day_project_total
            signed_gap = estimated_hours - screen_hours
            project_allocated_gap[project_name] = project_allocated_gap.get(project_name, 0.0) + share * signed_gap

    total_estimated = sum(r.estimated_hours for r in rows)
    total_screen = sum(r.screen_time_hours for r in rows)
    total_unexplained = sum(r.unexplained_screen_time_hours for r in rows)
    total_over = sum(r.over_attributed_hours for r in rows)
    return {
        "days": [row.as_dict() for row in rows],
        "totals": {
            "estimated_hours": round(total_estimated, 4),
            "screen_time_hours": round(total_screen, 4),
            "coverage_ratio": (
                round(total_estimated / total_screen, 4)
                if total_screen > 0
                else (1.0 if total_estimated == 0 else 0.0)
            ),
            "unexplained_screen_time_hours": round(total_unexplained, 4),
            "over_attributed_hours": round(total_over, 4),
            "missing_reference_day_count": sum(1 for row in rows if row.missing_reference_data),
        },
        "project_allocated_gap_hours": {
            name: round(value, 4)
            for name, value in sorted(project_allocated_gap.items(), key=lambda item: (-abs(item[1]), item[0].lower()))
        },
    }

