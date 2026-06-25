"""Build proposed ``reported_time`` units from observed sessions (Part 2, Phase 2).

Mirrors ``core/toggl_sync.py`` / ``core/jira_sync.py`` candidate building:
aggregate the report's observed sessions into one **proposed** reported_time unit
per project + day (``source="session"``). The CLI then lets the user
confirm / edit / dismiss them, or add net-new manual time the layer never saw.
"""

from __future__ import annotations

import logging
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from core.reported_time import ReportedTimeRecord

if TYPE_CHECKING:
    from core.report_service import ReportPayload

_LOGGER = logging.getLogger(__name__)

# The fallback project name (matches the report pipeline's classify fallback).
UNCATEGORIZED = "Uncategorized"


def _dominant_project(session_events: List[Dict[str, Any]]) -> str:
    counts: Counter = Counter(str(e.get("project") or UNCATEGORIZED) for e in session_events)
    return counts.most_common(1)[0][0] if counts else UNCATEGORIZED


def _session_seconds(session_events, start, end, args) -> int:
    try:
        from core.domain import session_duration_hours
        from core.sources import AI_SOURCES

        hours = session_duration_hours(
            session_events, start, end, args.min_session, args.min_session_passive, AI_SOURCES
        )
        return int(round(hours * 3600))
    except Exception as exc:  # pragma: no cover - defensive
        _LOGGER.warning("Failed to compute session duration, using floor: %s", exc)
        return int(round(max(0.0, args.min_session / 60) * 3600))


def _git_issue_resolver(report: "ReportPayload", repo_path: "Path"):
    """A ``(start, end) -> issue_key|None`` resolver from git (Phase 3b).

    Reuses jira-sync's per-session inference (commits-in-window, then current
    branch) so observed time is stamped with the issue it belongs to at proposal
    time. Returns a resolver that always yields ``None`` if git is unreadable.
    """
    try:
        from core.jira_sync import (
            _issue_key_for_session,
            load_commit_tags,
            load_current_branch_issue_key,
        )

        commits = load_commit_tags(repo_path, report.dt_from, report.dt_to)
        branch_key = load_current_branch_issue_key(repo_path)
    except Exception as exc:  # pragma: no cover - defensive
        _LOGGER.warning("Could not load git issue context: %s", exc)
        return lambda start, end: None

    def resolve(start, end) -> Optional[str]:
        key, _source = _issue_key_for_session(start, end, commits, branch_key)
        return key

    return resolve


def build_reported_proposals(
    report: "ReportPayload", repo_path: Optional["Path"] = None
) -> List[ReportedTimeRecord]:
    """One proposed reported_time record per project + day (+ issue, when a
    ``repo_path`` is given) from observed sessions.

    With ``repo_path`` (Phase 3b), each session's Jira issue is inferred from git
    and stamped on its proposal, so confirmed time keeps its per-issue split for
    jira-sync. Without it, behavior is unchanged (project+day only)."""
    resolve_issue = _git_issue_resolver(report, repo_path) if repo_path else None
    buckets: Dict[Tuple[str, str, Optional[str]], Dict[str, Any]] = {}
    for day, day_data in report.overall_days.items():
        for start, end, session_events in day_data.get("sessions", []):
            project = _dominant_project(session_events)
            issue_key = resolve_issue(start, end) if resolve_issue else None
            seconds = max(0, _session_seconds(session_events, start, end, report.args))
            bucket = buckets.setdefault((project, day, issue_key), {"seconds": 0, "origins": []})
            bucket["seconds"] += seconds
            bucket["origins"].append(f"{day}T{start.strftime('%H%M')}")

    proposals: List[ReportedTimeRecord] = []
    for (project, day, issue_key), bucket in sorted(buckets.items(), key=lambda kv: (kv[0][0], kv[0][1], kv[0][2] or "")):
        hours = round(bucket["seconds"] / 3600.0, 2)
        if hours <= 0:
            continue
        proposals.append(
            ReportedTimeRecord(
                date=day,
                project=project,
                hours=hours,
                source="session",
                state="proposed",
                origin_ref=sorted(bucket["origins"]),
                issue_key=issue_key,
            )
        )
    return proposals


def window_days(report: "ReportPayload") -> List[str]:
    """Every calendar day ``YYYY-MM-DD`` in the report window, inclusive.

    Uses the full date range (not just observed days) so manual reported time on a
    day with no tracked sessions is still in scope for sync.
    """
    start = report.dt_from.date()
    end = report.dt_to.date()
    days: List[str] = []
    cursor = start
    while cursor <= end:
        days.append(cursor.isoformat())
        cursor += timedelta(days=1)
    return days


def day_start(day: str) -> datetime:
    """A tz-aware default start (09:00 local) for a reported project+day.

    Reported records carry no clock time (project+day granularity), so sync needs a
    synthetic start for the Toggl/Jira entry; 09:00 local is a neutral choice.
    """
    return datetime.fromisoformat(f"{day}T09:00:00").astimezone()


def reported_hours_for_window(
    report: "ReportPayload", home: Optional[Path] = None
) -> Optional[Dict[Tuple[str, str], float]]:
    """D4 adoption switch for sync.

    If any ``confirmed``/``edited`` reported_time falls within the report window,
    return ``{(project, day): hours}`` for that window (sync runs in *reported
    mode* — push only confirmed time). If none exists, return ``None`` so callers
    keep today's observed behavior unchanged (the pre-adoption fallback).
    """
    from core.reported_time import reported_hours_by_project_day

    window = set(window_days(report))
    in_window = {
        (project, day): hours
        for (project, day), hours in reported_hours_by_project_day(home).items()
        if day in window
    }
    return in_window or None


def reported_issue_hours_for_window(
    report: "ReportPayload", home: Optional[Path] = None
) -> Optional[Dict[Tuple[str, str, Optional[str]], float]]:
    """Issue-aware D4 switch for jira-sync (Phase 3b).

    Like :func:`reported_hours_for_window` but keyed by
    ``(project, day, issue_key)`` so confirmed time keeps its per-issue split
    (``issue_key`` is ``None`` for project-level records). Returns ``None`` when no
    confirmed/edited reported_time covers the window (observed fallback).
    """
    from core.reported_time import REPORTED_STATES, query

    window = set(window_days(report))
    totals: Dict[Tuple[str, str, Optional[str]], float] = {}
    for rec in query(home, states=REPORTED_STATES):
        if rec.date not in window:
            continue
        key = (rec.project, rec.date, rec.issue_key)
        totals[key] = totals.get(key, 0.0) + float(rec.hours)
    return totals or None


def auto_report_projects(profiles: List[Dict[str, Any]]) -> set:
    """Names of projects the user opted into auto-reporting (`auto_report: true`)."""
    return {str(p.get("name")) for p in (profiles or []) if p.get("auto_report")}


def split_auto_confirm(
    proposals: List[ReportedTimeRecord], profiles: List[Dict[str, Any]]
) -> Tuple[List[ReportedTimeRecord], List[ReportedTimeRecord]]:
    """Split observed proposals into ``(auto_confirm, left_for_review)``.

    A proposal auto-confirms when its project is a configured project the user
    marked ``auto_report: true`` (and is not ``Uncategorized``). The user
    pre-authorized this per project, so it is not a silent promotion. Everything
    else is left untouched for manual review.
    """
    auto = auto_report_projects(profiles)
    to_confirm: List[ReportedTimeRecord] = []
    left: List[ReportedTimeRecord] = []
    for rec in proposals:
        if rec.project in auto and rec.project != UNCATEGORIZED:
            to_confirm.append(
                ReportedTimeRecord(
                    date=rec.date,
                    project=rec.project,
                    hours=rec.hours,
                    source=rec.source,
                    state="confirmed",
                    origin_ref=list(rec.origin_ref),
                    note=rec.note,
                    issue_key=rec.issue_key,
                )
            )
        else:
            left.append(rec)
    return to_confirm, left
