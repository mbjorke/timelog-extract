"""Per-project git-only hour estimates from configured git repos."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from collectors.git_commits import collect_git_commit_timestamps
from core.analytics import estimate_hours_by_day, group_by_day
from core.domain import compute_sessions, session_duration_hours
from core.sources import GIT_COMMITS_SOURCE


def _session_dur(session_events, start_ts, end_ts, min_s, min_p, ai_sources):
    return session_duration_hours(session_events, start_ts, end_ts, min_s, min_p, ai_sources)


def compute_git_project_totals(
    profiles: List[Dict[str, Any]],
    local_tz: Any,
    make_event_fn: Callable,
    ai_sources: Any,
    *,
    dt_from: Optional[datetime] = None,
    dt_to: Optional[datetime] = None,
    gap_minutes: int = 15,
    min_session_minutes: int = 5,
    min_session_passive_minutes: int = 15,
) -> Dict[str, float]:
    """Return {project_name: hours} from git log for each profile with a git_repo field.

    Uses the passive session floor (git commits are not AI-tier activity).
    If dt_from/dt_to are None, covers all history (1970-2099).
    """
    _from = dt_from or datetime(1970, 1, 1, tzinfo=local_tz)
    _to = dt_to or datetime(2099, 12, 31, 23, 59, 59, tzinfo=local_tz)

    all_events = []
    for profile in profiles:
        git_repo = profile.get("git_repo")
        if not git_repo:
            continue
        repo_paths = [git_repo] if isinstance(git_repo, str) else list(git_repo)
        project_name = profile["name"]
        for rp in repo_paths:
            repo = Path(rp).expanduser()
            events = collect_git_commit_timestamps(
                repo_path=repo,
                local_tz=local_tz,
                make_event_fn=make_event_fn,
                project=project_name,
                source_name=GIT_COMMITS_SOURCE,
                dt_from=_from,
                dt_to=_to,
            )
            all_events.extend(events)

    if not all_events:
        return {}

    grouped = group_by_day(all_events, local_tz=local_tz)
    daily = estimate_hours_by_day(
        grouped,
        gap_minutes=gap_minutes,
        min_session_minutes=min_session_minutes,
        min_session_passive_minutes=min_session_passive_minutes,
        compute_sessions_fn=lambda entries, gap_minutes: compute_sessions(entries, gap_minutes),
        session_duration_hours_fn=lambda se, s, e, mn, mp: _session_dur(se, s, e, mn, mp, ai_sources),
    )

    totals: Dict[str, float] = defaultdict(float)
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

    return dict(totals)
