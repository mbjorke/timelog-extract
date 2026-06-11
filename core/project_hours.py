"""Proportional project-hour allocation from mixed sessions."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any, Callable, Dict

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
        timestamps = [ts for e in events if (ts := _event_local_ts(e)) is not None]
        if not timestamps:
            continue
        start_ts, end_ts = min(timestamps), max(timestamps)
        out[project] = session_duration_hours_fn(
            events,
            start_ts,
            end_ts,
            min_session_minutes,
            min_session_passive_minutes,
            AI_SOURCES,
        )
    return out


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
            return high_signal

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
        for start_ts, end_ts, session_events in payload.get("sessions", []):
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
    return {project: dict(days) for project, days in reports.items()}
