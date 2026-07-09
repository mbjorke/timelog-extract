"""Proportional project-hour allocation from mixed sessions."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any, Callable, Dict

from core.domain import compute_sessions
from core.events import event_anchors
from core.sources import AI_SOURCES

_HIGH_SIGNAL_MIN_WEIGHT = 5.0
_BROWSER_TAB_SOURCES = frozenset({"Chrome", "WordPress", "Lovable (web)"})


def event_attribution_weight(event: dict) -> float:
    """Higher weight = stronger signal that session time belongs to this project."""
    if str(event_anchors(event).get("label") or "").strip():
        return 10.0
    source = str(event.get("source") or "")
    if "worklog" in source.lower() or source == "TIMELOG.md":
        return 10.0
    if source == "GitHub":
        return 5.0
    # Below high-signal floor so lone Lovable cache hits do not Tier-A-claim
    # multi-hour mixed sessions (WordPress/Chrome days).
    if source == "Lovable (desktop)":
        return 4.0
    if source == "WordPress":
        return 3.0
    # Browser Lovable (lovable.dev) — stronger than generic Chrome, weaker than
    # the Electron desktop app's local history/cache signals.
    if source == "Lovable (web)":
        return 2.0
    if source in AI_SOURCES:
        return 3.0
    if source == "Chrome":
        return 0.0
    return 2.0


def _browser_attribution_key(event: dict) -> tuple[str, str]:
    """Dedupe key for browser tab churn within one session.

    Keep the full detail prefix (not a `` · `` lead split): that separator is
    GitHub-title specific and would collapse unrelated page titles.
    """
    project = str(event.get("project") or "").strip() or "Uncategorized"
    detail = str(event.get("detail") or "").strip().lower()
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


def _subspan_hours_by_project(
    session_events: list,
    *,
    session_duration_hours_fn: Callable[..., float],
    min_session_minutes: int,
    min_session_passive_minutes: int,
    gap_minutes: int = 15,
    include_event: Callable[[dict], bool] | None = None,
) -> Dict[str, float]:
    """Sum per-project sub-session wall-clock from that project's events."""
    by_project: dict[str, list[dict]] = defaultdict(list)
    for event in session_events:
        if include_event is not None and not include_event(event):
            continue
        project = str(event.get("project") or "").strip() or "Uncategorized"
        by_project[project].append(event)

    out: dict[str, float] = {}
    for project, events in by_project.items():
        with_ts = [event for event in events if _event_local_ts(event) is not None]
        if not with_ts:
            continue
        project_hours = 0.0
        for start_ts, end_ts, chunk_events in compute_sessions(with_ts, gap_minutes=gap_minutes):
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


def _high_signal_hours_by_project(
    session_events: list,
    *,
    session_duration_hours_fn: Callable[..., float],
    min_session_minutes: int,
    min_session_passive_minutes: int,
    gap_minutes: int = 15,
) -> Dict[str, float]:
    """Bill from worklog, GitHub, composer titles — not Chrome/WordPress tab churn."""
    return _subspan_hours_by_project(
        session_events,
        session_duration_hours_fn=session_duration_hours_fn,
        min_session_minutes=min_session_minutes,
        min_session_passive_minutes=min_session_passive_minutes,
        gap_minutes=gap_minutes,
        include_event=lambda event: event_attribution_weight(event) >= _HIGH_SIGNAL_MIN_WEIGHT,
    )


def _weighted_project_split(session_events: list, hours: float) -> Dict[str, float]:
    """Split hours by event attribution weights (browser tab churn deduped)."""
    weights: dict[str, float] = defaultdict(float)
    browser_seen: set[tuple[str, str]] = set()
    for event in session_events:
        project = str(event.get("project") or "").strip() or "Uncategorized"
        if str(event.get("source") or "") in _BROWSER_TAB_SOURCES:
            key = _browser_attribution_key(event)
            if key in browser_seen:
                continue
            browser_seen.add(key)
        weight = event_attribution_weight(event)
        if weight <= 0:
            continue
        weights[project] += weight
    total = sum(weights.values())
    if total <= 0:
        return {}
    return {project: hours * (weight / total) for project, weight in weights.items()}


def _span_project_split(
    session_events: list,
    hours: float,
    *,
    session_duration_hours_fn: Callable[..., float],
    min_session_minutes: int,
    min_session_passive_minutes: int,
    gap_minutes: int = 15,
) -> Dict[str, float]:
    """Allocate hours by per-project event sub-spans (includes WordPress/Chrome)."""
    spans = _subspan_hours_by_project(
        session_events,
        session_duration_hours_fn=session_duration_hours_fn,
        min_session_minutes=min_session_minutes,
        min_session_passive_minutes=min_session_passive_minutes,
        gap_minutes=gap_minutes,
        include_event=None,
    )
    if not spans:
        return {}
    capped = _cap_allocation_to_session_hours(spans, hours)
    allocated = sum(capped.values())
    if allocated <= 0:
        return {}
    if abs(allocated - hours) <= 1e-9:
        return capped
    # Scale up sparse floors so the remainder fills the parent session without
    # inventing projects that have no events.
    scale = hours / allocated
    return {project: value * scale for project, value in capped.items()}


def allocate_session_hours_by_project(
    session_events: list,
    hours: float,
    *,
    session_duration_hours_fn: Callable[..., float] | None = None,
    min_session_minutes: int = 15,
    min_session_passive_minutes: int = 5,
    gap_minutes: int = 15,
) -> Dict[str, float]:
    """Split session duration across projects; prefer high-signal spans when present."""
    if hours <= 0 or not session_events:
        return {}

    def _remainder_split(remainder: float) -> Dict[str, float]:
        weighted = _weighted_project_split(session_events, remainder)
        if weighted:
            return weighted
        if session_duration_hours_fn is None:
            return {}
        return _span_project_split(
            session_events,
            remainder,
            session_duration_hours_fn=session_duration_hours_fn,
            min_session_minutes=min_session_minutes,
            min_session_passive_minutes=min_session_passive_minutes,
            gap_minutes=gap_minutes,
        )

    if session_duration_hours_fn is not None:
        high_signal = _high_signal_hours_by_project(
            session_events,
            session_duration_hours_fn=session_duration_hours_fn,
            min_session_minutes=min_session_minutes,
            min_session_passive_minutes=min_session_passive_minutes,
            gap_minutes=gap_minutes,
        )
        if high_signal:
            capped = _cap_allocation_to_session_hours(high_signal, hours)
            allocated = sum(capped.values())
            if allocated < hours - 1e-9:
                for project, chunk in _remainder_split(hours - allocated).items():
                    capped[project] = capped.get(project, 0.0) + chunk
            return capped

        # No high-signal: prefer per-project event sub-spans (WordPress/Chrome can own time).
        span_split = _span_project_split(
            session_events,
            hours,
            session_duration_hours_fn=session_duration_hours_fn,
            min_session_minutes=min_session_minutes,
            min_session_passive_minutes=min_session_passive_minutes,
            gap_minutes=gap_minutes,
        )
        if span_split:
            return span_split

    weighted = _weighted_project_split(session_events, hours)
    if weighted:
        return weighted
    # Last resort: equal split only when every event has weight 0 and span math
    # could not run (no duration fn / no timestamps).
    projects = sorted({str(e.get("project") or "Uncategorized") for e in session_events})
    share = hours / len(projects) if projects else hours
    return {name: share for name in projects}


def build_project_reports_from_sessions(
    overall_days: Dict[str, Any],
    *,
    session_duration_hours_fn: Callable[..., float],
    min_session_minutes: int,
    min_session_passive_minutes: int,
    gap_minutes: int = 15,
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
                gap_minutes=gap_minutes,
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
            session_events = session[2]
            projects = {
                str(event.get("project") or "").strip() or "Uncategorized"
                for event in session_events
            }
            for project in projects:
                counts[project] += 1
    return dict(counts)
