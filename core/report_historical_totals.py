"""Display-only historical column totals for --history / legacy --git."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from core.git_totals import compute_git_project_totals
from core.timelog_totals import compute_timelog_project_totals


def compute_report_historical_totals(
    *,
    args: Any,
    profiles: List[Dict[str, Any]],
    worklog_paths: Sequence[Any],
    local_tz: Any,
    dt_from: datetime,
    dt_to: datetime,
    classify_project_fn: Callable,
    make_event_fn: Callable,
    worklog_source: str,
    ai_sources: Any,
) -> Tuple[Dict[str, float], Dict[str, float], bool]:
    """Return (timelog_all_time, git_totals, git_enabled_for_status)."""
    history_source = bool(getattr(args, "history_source", False))
    git_legacy_period = bool(getattr(args, "git_source", False)) and not history_source
    git_enabled = history_source or git_legacy_period

    timelog_totals: Dict[str, float] = {}
    if history_source and worklog_paths:
        timelog_totals = compute_timelog_project_totals(
            worklog_paths=worklog_paths,
            profiles=profiles,
            local_tz=local_tz,
            classify_project_fn=classify_project_fn,
            make_event_fn=make_event_fn,
            source_name=worklog_source,
            ai_sources=ai_sources,
            gap_minutes=args.gap_minutes,
            min_session_minutes=args.min_session,
            min_session_passive_minutes=args.min_session_passive,
            worklog_format=str(getattr(args, "worklog_format", "auto") or "auto"),
        )

    git_totals: Dict[str, float] = {}
    if git_enabled:
        git_kw: Dict[str, Any] = dict(
            profiles=profiles,
            local_tz=local_tz,
            make_event_fn=make_event_fn,
            ai_sources=ai_sources,
            gap_minutes=args.gap_minutes,
            min_session_minutes=args.min_session,
            min_session_passive_minutes=args.min_session_passive,
        )
        if history_source:
            git_totals = compute_git_project_totals(**git_kw)
        else:
            git_totals = compute_git_project_totals(**git_kw, dt_from=dt_from, dt_to=dt_to)

    return timelog_totals, git_totals, git_enabled
