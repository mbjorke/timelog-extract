"""All-time TIMELOG.md hour totals per project, used for the Total observed column."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Sequence

from collectors.timelog import collect_worklog
from core.analytics import estimate_hours_by_day, group_by_day
from core.domain import compute_sessions, session_duration_hours


def _session_dur(session_events, start_ts, end_ts, min_session_minutes, min_session_passive_minutes, ai_sources):
    return session_duration_hours(
        session_events, start_ts, end_ts,
        min_session_minutes, min_session_passive_minutes, ai_sources,
    )


def _accumulate_worklog_totals(
    worklog_path: Path,
    profiles: List[Dict[str, Any]],
    local_tz: Any,
    classify_project_fn: Callable,
    make_event_fn: Callable,
    source_name: str,
    ai_sources: Any,
    *,
    gap_minutes: int,
    min_session_minutes: int,
    min_session_passive_minutes: int,
    worklog_format: str,
    totals: Dict[str, float],
) -> None:
    """Read one worklog file and add hours-per-project into totals in-place."""
    dt_min = datetime(1970, 1, 1, tzinfo=local_tz)
    dt_max = datetime(2099, 12, 31, 23, 59, 59, tzinfo=local_tz)

    events = collect_worklog(
        worklog_path=str(worklog_path),
        dt_from=dt_min,
        dt_to=dt_max,
        profiles=profiles,
        local_tz=local_tz,
        classify_project=classify_project_fn,
        make_event=make_event_fn,
        source_name=source_name,
        worklog_format=worklog_format,
    )
    if not events:
        return

    grouped = group_by_day(events, local_tz=local_tz)
    daily = estimate_hours_by_day(
        grouped,
        gap_minutes=gap_minutes,
        min_session_minutes=min_session_minutes,
        min_session_passive_minutes=min_session_passive_minutes,
        compute_sessions_fn=lambda entries, gap_minutes: compute_sessions(entries, gap_minutes),
        session_duration_hours_fn=lambda se, s, e, mn, mp: _session_dur(se, s, e, mn, mp, ai_sources),
    )

    for day_payload in daily.values():
        for start_ts, end_ts, session_events in day_payload.get("sessions", []):
            project_counts: Dict[str, int] = defaultdict(int)
            for event in session_events:
                pname = str(event.get("project", "")).strip()
                if pname:
                    project_counts[pname] += 1
            if not project_counts:
                continue
            primary = max(project_counts, key=lambda p: (project_counts[p], p.lower()))
            hours = _session_dur(
                session_events, start_ts, end_ts,
                min_session_minutes, min_session_passive_minutes, ai_sources,
            )
            totals[primary] += hours


def compute_timelog_project_totals(
    worklog_paths: Sequence[Path],
    profiles: List[Dict[str, Any]],
    local_tz: Any,
    classify_project_fn: Callable,
    make_event_fn: Callable,
    source_name: str,
    ai_sources: Any,
    *,
    gap_minutes: int = 15,
    min_session_minutes: int = 5,
    min_session_passive_minutes: int = 15,
    worklog_format: str = "auto",
) -> Dict[str, float]:
    """Return {project_name: total_hours} aggregated across all worklog paths, no date filter."""
    totals: Dict[str, float] = defaultdict(float)
    for wlp in worklog_paths:
        _accumulate_worklog_totals(
            worklog_path=wlp,
            profiles=profiles,
            local_tz=local_tz,
            classify_project_fn=classify_project_fn,
            make_event_fn=make_event_fn,
            source_name=source_name,
            ai_sources=ai_sources,
            gap_minutes=gap_minutes,
            min_session_minutes=min_session_minutes,
            min_session_passive_minutes=min_session_passive_minutes,
            worklog_format=worklog_format,
            totals=totals,
        )
    return dict(totals)
