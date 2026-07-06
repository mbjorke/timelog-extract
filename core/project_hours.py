"""Proportional project-hour allocation from mixed sessions."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any, Callable, Dict

from core.domain import compute_sessions
from core.events import event_anchors
from core.sources import AI_SOURCES

_HIGH_SIGNAL_MIN_WEIGHT = 5.0


def event_attribution_weight(event: dict) -> float:
    """Higher weight = stronger signal that session time belongs to this project."""
    if str(event_anchors(event).get("label") or "").strip():
        return 10.0
    source = str(event.get("source") or "")
    if "worklog" in source.lower() or source == "TIMELOG.md":
        return 10.0
    if source == "GitHub":
        return 5.0
    if source == "Lovable (desktop)":
        return 8.0
    if source in AI_SOURCES:
        return 3.0
    if source == "Chrome":
        return 0.0
    return 2.0


def _chrome_attribution_key(event: dict) -> tuple[str, str]:
    project = str(event.get("project") or "").strip() or "Uncategorized"
    detail = str(event.get("detail") or "").strip().lower()
    if " · " in detail:
        detail = detail.split(" · ", 1)[0].strip()
    return project, detail[:96]


def _event_local_ts(event: dict) -> datetime | None:
    ts = event.get("local_ts") or event.get("timestamp")
    return ts if isinstance(ts, datetime) else None


def _cap_allocation_to_session_hours(
    allocation: dict[str, float],
    session_hours: float,
) -> dict[str, float]:
    """Scale project chunks down when high-signal spans overlap in one session."""
    total = sum(allocation.values())
    if total <= 0 or session_hours <= 0 or total <= session_hours + 1e-9:
        return allocation
    scale = session_hours / total
    return {project: value * scale for project, value in allocation.items()}


def _high_signal_hours_by_project(
    session_events: list,
    *,
    session_duration_hours_fn: Callable[..., float],
    min_session_minutes: int,
    min_session_passive_minutes: int,
) -> Dict[str, float]:
    """Bill from worklog, GitHub, composer titles, Lovable — not Chrome tab churn."""
    by_project: dict[str, list[dict]] = defaultdict(list)
    for event in session_events:
        if event_attribution_weight(event) < _HIGH_SIGNAL_MIN_WEIGHT:
            continue
        project = str(event.get("project") or "").strip() or "Uncategorized"
        by_project[project].append(event)

    out: dict[str, float] = {}
    for project, events in by_project.items():
        with_ts = [event for event in events if _event_local_ts(event) is not None]
        if not with_ts:
            continue
        project_hours = 0.0
        for start_ts, end_ts, chunk_events in compute_sessions(with_ts, gap_minutes=15):
            project_hours += session_duration_hours_fn(
                chunk_events,
                start_ts,
                end_ts,
                min_session_minutes,
                min_session_passive_minutes,
                AI_SOURCES,
            )
        if project_hours > 0:
            out[project] = project_hours
    return out


def _weighted_project_split(session_events: list, hours: float) -> Dict[str, float]:
    """Split hours by event attribution weights (Chrome tab churn deduped)."""
    weights: dict[str, float] = defaultdict(float)
    chrome_seen: set[tuple[str, str]] = set()
    for event in session_events:
        project = str(event.get("project") or "").strip() or "Uncategorized"
        if str(event.get("source") or "") == "Chrome":
            key = _chrome_attribution_key(event)
            if key in chrome_seen:
                continue
            chrome_seen.add(key)
        weight = event_attribution_weight(event)
        if weight <= 0:
            continue
        weights[project] += weight
    total = sum(weights.values())
    if total <= 0:
        if not session_events:
            return {}
        projects = sorted({str(e.get("project") or "Uncategorized") for e in session_events})
        share = hours / len(projects) if projects else hours
        return {name: share for name in projects}
    return {project: hours * (weight / total) for project, weight in weights.items()}


def allocate_session_hours_by_project(
    session_events: list,
    hours: float,
    *,
    session_duration_hours_fn: Callable[..., float] | None = None,
    min_session_minutes: int = 15,
    min_session_passive_minutes: int = 5,
) -> Dict[str, float]:
    """Split session duration across projects; prefer high-signal spans when present."""
    if session_duration_hours_fn is not None:
        high_signal = _high_signal_hours_by_project(
            session_events,
            session_duration_hours_fn=session_duration_hours_fn,
            min_session_minutes=min_session_minutes,
            min_session_passive_minutes=min_session_passive_minutes,
        )
        if high_signal:
            capped = _cap_allocation_to_session_hours(high_signal, hours)
            allocated = sum(capped.values())
            if allocated < hours - 1e-9:
                remainder = hours - allocated
                for project, chunk in _weighted_project_split(session_events, remainder).items():
                    capped[project] = capped.get(project, 0.0) + chunk
            return capped

    return _weighted_project_split(session_events, hours)


def build_project_reports_from_sessions(
    overall_days: Dict[str, Any],
    *,
    session_duration_hours_fn: Callable[..., float],
    min_session_minutes: int,
    min_session_passive_minutes: int,
) -> Dict[str, Dict[str, Dict[str, float]]]:
    """Derive per-project daily hours from overall sessions (no double-counting)."""
    reports: dict[str, dict[str, dict[str, float]]] = defaultdict(
        lambda: defaultdict(lambda: {"hours": 0.0})
    )
    for day, payload in overall_days.items():
        for s_tuple in payload.get("sessions", []):
            start_ts, end_ts, session_events = s_tuple[:3]
            attendance = s_tuple[3] if len(s_tuple) > 3 else "attended"
            hours = session_duration_hours_fn(
                session_events,
                start_ts,
                end_ts,
                min_session_minutes,
                min_session_passive_minutes,
                AI_SOURCES,
            )
            for project, chunk in allocate_session_hours_by_project(
                session_events,
                hours,
                session_duration_hours_fn=session_duration_hours_fn,
                min_session_minutes=min_session_minutes,
                min_session_passive_minutes=min_session_passive_minutes,
            ).items():
                reports[project][day]["hours"] += chunk
                if attendance == "attended":
                    reports[project][day]["attended_hours"] = reports[project][day].get("attended_hours", 0.0) + chunk
                elif attendance == "agent":
                    reports[project][day]["agent_hours"] = reports[project][day].get("agent_hours", 0.0) + chunk
                elif attendance == "mixed":
                    reports[project][day]["mixed_hours"] = reports[project][day].get("mixed_hours", 0.0) + chunk
    return {project: dict(days) for project, days in reports.items()}


def count_project_sessions_from_overall_days(
    overall_days: Dict[str, Any],
) -> Dict[str, int]:
    """Count sessions per project from overall timeline (hours-only project_reports safe)."""
    counts: dict[str, int] = defaultdict(int)
    for day_data in overall_days.values():
        for session in day_data.get("sessions", []):
            if not isinstance(session, (list, tuple)) or len(session) < 3:
                continue
            _start_ts, _end_ts, session_events = session
            projects = {
                str(event.get("project") or "").strip() or "Uncategorized"
                for event in session_events
            }
            for project in projects:
                counts[project] += 1
    return dict(counts)
