"""Display-only Git estimate totals for --history / legacy --git."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from core.git_totals import compute_git_project_totals


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
    """Return ``(timelog_all_time, git_totals, git_enabled)``.

    ``timelog_all_time`` is always empty (GH-146: no TIMELOG column under ``--history``).
    Observed totals come from the normal collector pass in ``project_reports``.
    """
    del worklog_paths, classify_project_fn, worklog_source  # TIMELOG column removed

    history_source = bool(getattr(args, "history_source", False))
    git_legacy_period = bool(getattr(args, "git_source", False)) and not history_source
    git_enabled = history_source or git_legacy_period

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

    return {}, git_totals, git_enabled
