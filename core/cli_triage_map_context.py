"""Load URL candidates for `gittan review` (keeps CLI module under CI line limits)."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from core.cli_triage import build_triage_plan_dict, load_triage_profiles
from core.cli_triage_map_candidates import (
    UrlCandidate,
    build_url_candidates,
    build_url_candidates_from_gap_days,
    merge_url_candidate_lists,
)

TRIAGE_MAP_JSON_SCHEMA_VERSION = "1"


def load_triage_map_session(
    *,
    date_from: str,
    date_to: str,
    projects_config: str,
    max_rows: int,
    min_events: int,
    include_low_signal: bool,
    max_days: int,
) -> tuple[list[UrlCandidate], Any]:
    """Load URL candidates and the report used for the same window."""
    profiles = load_triage_profiles(projects_config)
    plan = build_triage_plan_dict(
        date_from=date_from,
        date_to=date_to,
        projects_config=projects_config,
        max_days=max(1, int(max_days)),
        max_sites=5,
        scoring_mode="site-first",
        include_sample_title=True,
    )
    day_unexplained_hours = {
        str(d.get("day", "")).strip(): float((d.get("gap") or {}).get("unexplained_screen_time_hours", 0.0) or 0.0)
        for d in plan.get("days", [])
        if str(d.get("day", "")).strip()
    }
    gap_rows = build_url_candidates_from_gap_days(
        day_unexplained_hours=day_unexplained_hours,
        profiles=profiles,
        max_rows=max_rows,
        min_events=min_events,
        include_low_signal=include_low_signal,
    )
    from core.cli_options import TimelogRunOptions
    from core.report_service import run_timelog_report

    report = run_timelog_report(
        projects_config,
        date_from,
        date_to,
        TimelogRunOptions(
            date_from=date_from,
            date_to=date_to,
            projects_config=projects_config,
            include_uncategorized=True,
            quiet=True,
        ),
    )
    report_rows = build_url_candidates(
        report=report,
        profiles=profiles,
        max_rows=max_rows,
        min_events=min_events,
        include_low_signal=include_low_signal,
    )
    rows = merge_url_candidate_lists(gap_rows, report_rows, max_rows=max_rows)
    # Onboarding/review queue: decidability before impact/confidence (#419).
    from core.cli_review_create_project import decidability_sort_key

    rows.sort(key=decidability_sort_key)
    return rows, report


def load_triage_map_candidates(
    *,
    date_from: str,
    date_to: str,
    projects_config: str,
    max_rows: int,
    min_events: int,
    include_low_signal: bool,
    max_days: int,
) -> list[UrlCandidate]:
    rows, _report = load_triage_map_session(
        date_from=date_from,
        date_to=date_to,
        projects_config=projects_config,
        max_rows=max_rows,
        min_events=min_events,
        include_low_signal=include_low_signal,
        max_days=max_days,
    )
    return rows


def build_triage_map_json_payload(
    *,
    date_from: str,
    date_to: str,
    projects_config: str,
    rows: list[UrlCandidate],
    new_remote_repositories: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": TRIAGE_MAP_JSON_SCHEMA_VERSION,
        "command": "gittan review",
        "date_from": date_from,
        "date_to": date_to,
        "projects_config": projects_config,
        "candidate_count": len(rows),
        "candidates": [asdict(row) for row in rows],
    }
    if new_remote_repositories is not None:
        payload["new_remote_repositories"] = list(new_remote_repositories)
        payload["new_remote_count"] = len(new_remote_repositories)
    return payload
