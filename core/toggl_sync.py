"""Build Toggl time-entry candidates from report data and post them.

Mirrors ``core/jira_sync.py`` but maps each Gittan project to a configured
Toggl ``project_id`` (instead of inferring a Jira issue key from git), and
aggregates one candidate per project + day.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Tuple

from collectors.toggl import (
    TogglCredentials,
    build_time_entry_payload,
    list_toggl_time_entries,
    post_toggl_time_entry,
)

if TYPE_CHECKING:
    from core.report_service import ReportPayload

GITTAN_TAG = "gittan"


@dataclass
class TogglEntryCandidate:
    project_name: str
    project_id: int
    day: str
    started: datetime
    seconds: int

    @property
    def hours(self) -> float:
        return self.seconds / 3600.0

    @property
    def marker_tag(self) -> str:
        """Deterministic idempotency tag: skip a re-post if this already exists."""
        return f"{GITTAN_TAG}:{self.project_id}:{self.day}"

    @property
    def description(self) -> str:
        return f"{self.project_name} ({self.day})"

    @property
    def tags(self) -> List[str]:
        return [GITTAN_TAG, self.marker_tag]


@dataclass
class TogglSyncSummary:
    posted: int = 0
    skipped: int = 0
    unmapped: int = 0
    failed: int = 0


def build_project_id_map(profiles: List[Dict[str, Any]]) -> Dict[str, int]:
    """Map project name -> toggl_project_id for profiles that declare one."""
    mapping: Dict[str, int] = {}
    for profile in profiles or []:
        name = str(profile.get("name") or "").strip()
        raw_id = profile.get("toggl_project_id")
        if not name or raw_id in (None, ""):
            continue
        try:
            mapping[name] = int(raw_id)
        except (TypeError, ValueError):
            logging.warning("Invalid toggl_project_id for project %r: %r", name, raw_id)
    return mapping


def _session_seconds(session_events: List[Dict[str, Any]], start: datetime, end: datetime, args: Any) -> int:
    """Duration in seconds using the same path as jira-sync."""
    try:
        from core.domain import session_duration_hours
        from core.sources import AI_SOURCES

        hours = session_duration_hours(
            session_events,
            start,
            end,
            args.min_session,
            args.min_session_passive,
            AI_SOURCES,
        )
        return int(round(hours * 3600))
    except Exception as exc:
        logging.warning("Failed to compute session duration, using floor fallback: %s", exc)
        return int(round(max(0.0, args.min_session / 60) * 3600))


def _candidates_from_reported(
    reported: Dict[Tuple[str, str], float],
    project_ids: Dict[str, int],
) -> Tuple[List[TogglEntryCandidate], int]:
    """Reported-mode (Phase 3): build candidates from confirmed reported hours per
    project+day instead of raw sessions. Projects with no ``toggl_project_id`` are
    counted unmapped. Manual reported time (no observed session) is included."""
    from core.reported_sync import day_start

    unmapped = 0
    buckets: Dict[Tuple[int, str], TogglEntryCandidate] = {}
    for (project_name, day), hours in sorted(reported.items()):
        project_id = project_ids.get(project_name)
        if project_id is None:
            unmapped += 1
            continue
        seconds = int(round(max(0.0, hours) * 3600))
        if seconds <= 0:
            continue
        key = (project_id, day)
        if key not in buckets:
            buckets[key] = TogglEntryCandidate(
                project_name=project_name,
                project_id=project_id,
                day=day,
                started=day_start(day),
                seconds=seconds,
            )
        else:
            buckets[key].seconds += seconds
    candidates = sorted(buckets.values(), key=lambda item: (item.day, item.project_name))
    return candidates, unmapped


def build_toggl_entry_candidates(
    report: "ReportPayload",
    profiles: List[Dict[str, Any]],
    home: Any = None,
) -> Tuple[List[TogglEntryCandidate], int]:
    """
    Aggregate report sessions into one Toggl candidate per mapped project + day.

    When confirmed/edited reported_time exists for the report window, candidates are
    built from those confirmed hours (Phase 3 reported-mode); otherwise from raw
    observed sessions (the pre-adoption fallback). Sessions/projects whose Gittan
    project has no ``toggl_project_id`` are counted as unmapped (and never posted).
    Returns ``(candidates, unmapped_count)``.
    """
    from core.reported_sync import reported_hours_for_window

    project_ids = build_project_id_map(profiles)
    reported = reported_hours_for_window(report, home)
    if reported is not None:
        return _candidates_from_reported(reported, project_ids)
    unmapped_sessions = 0
    buckets: Dict[Tuple[int, str], TogglEntryCandidate] = {}

    for day, day_data in report.overall_days.items():
        sessions = day_data.get("sessions", [])
        for session in sessions:
            start, end, session_events = session[:3]
            project_name = _dominant_project(session_events)
            project_id = project_ids.get(project_name)
            if project_id is None:
                unmapped_sessions += 1
                continue
            seconds = max(0, _session_seconds(session_events, start, end, report.args))
            key = (project_id, day)
            if key not in buckets:
                buckets[key] = TogglEntryCandidate(
                    project_name=project_name,
                    project_id=project_id,
                    day=day,
                    started=start,
                    seconds=seconds,
                )
            else:
                buckets[key].seconds += seconds
                # Keep the earliest start of the day as the entry's start.
                if start < buckets[key].started:
                    buckets[key].started = start

    candidates = sorted(buckets.values(), key=lambda item: (item.day, item.project_name))
    return candidates, unmapped_sessions


def _dominant_project(session_events: List[Dict[str, Any]]) -> str:
    """Most-frequent project name across the session's events."""
    counts: Dict[str, int] = {}
    for event in session_events:
        name = str(event.get("project") or "Uncategorized")
        counts[name] = counts.get(name, 0) + 1
    if not counts:
        return "Uncategorized"
    return max(counts.items(), key=lambda kv: kv[1])[0]


def existing_marker_tags(creds: TogglCredentials, start_date: str, end_date: str) -> set:
    """Marker tags already present on Toggl entries in the window (for dedup)."""
    tags: set = set()
    for entry in list_toggl_time_entries(creds, start_date, end_date):
        for tag in entry.get("tags") or []:
            if isinstance(tag, str) and tag.startswith(f"{GITTAN_TAG}:"):
                tags.add(tag)
    return tags


def candidate_payload(creds: TogglCredentials, candidate: TogglEntryCandidate) -> dict:
    """Exact POST body for a candidate — used for the dry-run payload preview."""
    return build_time_entry_payload(
        creds=creds,
        start=candidate.started,
        duration_seconds=candidate.seconds,
        description=candidate.description,
        project_id=candidate.project_id,
        tags=candidate.tags,
    )


def post_candidate(creds: TogglCredentials, candidate: TogglEntryCandidate) -> str:
    return post_toggl_time_entry(
        creds=creds,
        start=candidate.started,
        duration_seconds=candidate.seconds,
        description=candidate.description,
        project_id=candidate.project_id,
        tags=candidate.tags,
    )


@dataclass
class RollbackResult:
    op_id: str
    deleted: int = 0
    gone: int = 0
    already: int = 0
    failed: int = 0
    lines: List[str] = None  # type: ignore[assignment]

    def __post_init__(self):
        if self.lines is None:
            self.lines = []


def rollback_op(
    creds: TogglCredentials,
    op_id: str,
    *,
    delete_fn=None,
    home=None,
) -> RollbackResult:
    """Delete the Toggl entries a prior push created, idempotently.

    ``delete_fn(creds, entry_id) -> "deleted"|"gone"`` is injected so tests never
    hit the network. Entries already flagged rolled back are skipped; a re-run is
    a clean no-op. Rows deleted (or found already gone) are marked rolled back.
    """
    from collectors.toggl import delete_toggl_time_entry
    from core.toggl_oplog import mark_rolled_back, rows_for_op

    delete_fn = delete_fn or delete_toggl_time_entry
    result = RollbackResult(op_id=op_id)
    rows = rows_for_op(op_id, home=home)
    if not rows:
        result.lines.append(f"No op-log rows for op {op_id} — nothing to roll back.")
        return result

    settled: set = set()
    for row in rows:
        if row.rolled_back:
            result.already += 1
            continue
        try:
            # Delete against the workspace the entry was posted to (recorded in
            # the row), not the currently configured default — a mismatched
            # active workspace must not delete the wrong entry or false-succeed.
            status = delete_fn(creds, row.entry_id, row.workspace_id)
        except Exception as exc:  # noqa: BLE001 - surfaced per-entry, others continue
            result.failed += 1
            result.lines.append(
                f"Failed to delete entry {row.entry_id} ({row.project_id}/{row.day}): {exc}"
            )
            continue
        if status == "gone":
            result.gone += 1
            result.lines.append(
                f"Entry {row.entry_id} ({row.project_id}/{row.day}) already absent in Toggl."
            )
        else:
            result.deleted += 1
            result.lines.append(f"Deleted entry {row.entry_id} ({row.project_id}/{row.day}).")
        settled.add(row.entry_id)

    if settled:
        mark_rolled_back(op_id, settled, home=home)
    return result
