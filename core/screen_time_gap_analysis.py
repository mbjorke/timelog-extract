"""Screen Time gap analysis against estimated hours."""

from __future__ import annotations

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

    def as_dict(self) -> dict[str, Any]:
        return {
            "day": self.day,
            "estimated_hours": round(self.estimated_hours, 4),
            "screen_time_hours": round(self.screen_time_hours, 4),
            "coverage_ratio": round(self.coverage_ratio, 4),
            "unexplained_screen_time_hours": round(self.unexplained_screen_time_hours, 4),
            "over_attributed_hours": round(self.over_attributed_hours, 4),
        }


def _project_hours_by_day(report) -> dict[str, dict[str, float]]:
    by_day: dict[str, dict[str, float]] = {}
    for project_name, days in report.project_reports.items():
        for day, payload in days.items():
            by_day.setdefault(day, {})
            by_day[day][project_name] = float(payload.get("hours", 0.0))
    return by_day


def analyze_screen_time_gaps(report) -> dict[str, Any]:
    """Analyze day-level and project-allocated gaps vs screen time."""
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
            coverage = 1.0 if estimated_hours == 0 else 999.0
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
        },
        "project_allocated_gap_hours": {
            name: round(value, 4)
            for name, value in sorted(project_allocated_gap.items(), key=lambda item: (-abs(item[1]), item[0].lower()))
        },
    }

