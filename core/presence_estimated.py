"""Presence-bounded work-time estimate (display-only; never billable).

Fills soft-work gaps *between* a project's own evidenced events, capped per gap
and per day by measured Screen Time. Spec:
``docs/task-prompts/presence-estimated-hours-task.md``; ceiling:
``docs/specs/cursor-evidence-ceiling.md``.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Mapping, Optional

# Open product default (task prompt: 30 vs 45 vs 60 min).
DEFAULT_MAX_FILL_GAP_MINUTES = 45


@dataclass(frozen=True)
class PresenceEstimatedResult:
    """Separate from observed/billable hours — optional when Screen Time exists."""

    overall_days: Dict[str, float]
    project_days: Dict[str, Dict[str, float]]
    total_hours: float

    @property
    def available(self) -> bool:
        return bool(self.overall_days)


def _screen_hours_by_day(screen_time_days: Optional[Mapping[str, float]]) -> Dict[str, float]:
    if not screen_time_days:
        return {}
    out: Dict[str, float] = {}
    for day, raw in screen_time_days.items():
        value = float(raw or 0.0)
        if value <= 0:
            continue
        # Screen Time is stored as seconds/day; values >> 48 are seconds not hours.
        out[str(day)] = value / 3600.0 if value > 48.0 else value
    return out


def _event_local_ts(event: dict) -> datetime | None:
    ts = event.get("local_ts") or event.get("timestamp")
    return ts if isinstance(ts, datetime) else None


def _gap_fill_hours(
    gap_seconds: float,
    *,
    session_gap_minutes: int,
    max_fill_gap_minutes: int,
) -> float:
    """Credit idle time between events up to max_fill, ignoring sub-session gaps."""
    session_gap_s = max(0, int(session_gap_minutes)) * 60
    max_fill_s = max(0, int(max_fill_gap_minutes)) * 60
    if gap_seconds <= session_gap_s or max_fill_s <= 0:
        return 0.0
    return min(gap_seconds - session_gap_s, max_fill_s) / 3600.0


def _project_gap_fill_hours(
    events: list[dict],
    *,
    session_gap_minutes: int,
    max_fill_gap_minutes: int,
) -> float:
    stamps = sorted({_event_local_ts(ev) for ev in events if _event_local_ts(ev) is not None})
    if len(stamps) < 2:
        return 0.0
    fill = 0.0
    for prev, nxt in zip(stamps, stamps[1:]):
        fill += _gap_fill_hours(
            (nxt - prev).total_seconds(),
            session_gap_minutes=session_gap_minutes,
            max_fill_gap_minutes=max_fill_gap_minutes,
        )
    return fill


def compute_presence_estimated(
    overall_days: Dict[str, Any],
    project_reports: Dict[str, Dict[str, Dict[str, float]]],
    screen_time_days: Optional[Mapping[str, float]],
    *,
    session_gap_minutes: int = 15,
    max_fill_gap_minutes: int = DEFAULT_MAX_FILL_GAP_MINUTES,
) -> PresenceEstimatedResult:
    """Return presence-bounded estimates; empty when Screen Time is unavailable."""
    screen_by_day = _screen_hours_by_day(screen_time_days)
    if not screen_by_day:
        return PresenceEstimatedResult(overall_days={}, project_days={}, total_hours=0.0)

    events_by_day_project: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for day, payload in overall_days.items():
        for ev in payload.get("entries") or []:
            project = str(ev.get("project") or "").strip()
            if not project:
                continue
            events_by_day_project[str(day)][project].append(ev)

    overall_out: Dict[str, float] = {}
    project_out: Dict[str, Dict[str, float]] = defaultdict(dict)

    all_days = sorted(set(overall_days.keys()) & set(screen_by_day.keys()))
    for day in all_days:
        screen_cap = screen_by_day[day]
        evidenced_by_project: Dict[str, float] = {}
        fill_by_project: Dict[str, float] = {}
        for project, day_map in project_reports.items():
            evidenced = float((day_map.get(day) or {}).get("hours", 0.0) or 0.0)
            if evidenced <= 0 and not events_by_day_project.get(day, {}).get(project):
                continue
            events = events_by_day_project.get(day, {}).get(project, [])
            fill = _project_gap_fill_hours(
                events,
                session_gap_minutes=session_gap_minutes,
                max_fill_gap_minutes=max_fill_gap_minutes,
            )
            evidenced_by_project[project] = evidenced
            fill_by_project[project] = fill

        if not evidenced_by_project:
            overall_out[day] = 0.0
            continue

        evidenced_total = sum(evidenced_by_project.values())
        fill_total = sum(fill_by_project.values())
        raw_total = evidenced_total + fill_total

        day_project_hours: Dict[str, float] = {}
        if raw_total <= screen_cap + 1e-9:
            for project, evidenced in evidenced_by_project.items():
                day_project_hours[project] = evidenced + fill_by_project.get(project, 0.0)
        elif evidenced_total >= screen_cap:
            scale = screen_cap / evidenced_total if evidenced_total > 0 else 0.0
            for project, evidenced in evidenced_by_project.items():
                day_project_hours[project] = evidenced * scale
        else:
            fill_budget = screen_cap - evidenced_total
            fill_scale = fill_budget / fill_total if fill_total > 0 else 0.0
            for project, evidenced in evidenced_by_project.items():
                day_project_hours[project] = evidenced + fill_by_project.get(project, 0.0) * fill_scale

        day_total = min(sum(day_project_hours.values()), screen_cap)
        overall_out[day] = round(day_total, 6)
        for project, hours in day_project_hours.items():
            project_out[project][day] = round(hours, 6)

    total = round(sum(overall_out.values()), 6)
    return PresenceEstimatedResult(
        overall_days=overall_out,
        project_days={p: dict(days) for p, days in project_out.items()},
        total_hours=total,
    )
