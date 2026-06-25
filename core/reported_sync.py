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


def build_reported_proposals(report: "ReportPayload") -> List[ReportedTimeRecord]:
    """One proposed reported_time record per project + day from observed sessions."""
    buckets: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for day, day_data in report.overall_days.items():
        for start, end, session_events in day_data.get("sessions", []):
            project = _dominant_project(session_events)
            seconds = max(0, _session_seconds(session_events, start, end, report.args))
            bucket = buckets.setdefault((project, day), {"seconds": 0, "origins": []})
            bucket["seconds"] += seconds
            bucket["origins"].append(f"{day}T{start.strftime('%H%M')}")

    proposals: List[ReportedTimeRecord] = []
    for (project, day), bucket in sorted(buckets.items()):
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
                )
            )
        else:
            left.append(rec)
    return to_confirm, left
