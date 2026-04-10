"""Post-collection report aggregation helpers."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Any, Callable, Dict, List


@dataclass
class AggregationResult:
    all_events: List[Dict[str, Any]]
    included_events: List[Dict[str, Any]]
    grouped: Dict[str, Any]
    overall_days: Dict[str, Any]
    project_reports: Dict[str, Any]


def aggregate_report(
    *,
    all_events: List[Dict[str, Any]],
    args: argparse.Namespace,
    profiles: List[Dict[str, Any]],
    uncategorized: str,
    dedupe_events_fn: Callable[[List[Dict[str, Any]]], List[Dict[str, Any]]],
    filter_included_events_fn: Callable[
        [List[Dict[str, Any]], argparse.Namespace, List[Dict[str, Any]], str], List[Dict[str, Any]]
    ],
    group_by_day_fn: Callable[[List[Dict[str, Any]], List[str]], Dict[str, Any]],
    estimate_hours_by_day_fn: Callable[[Dict[str, Any], int, int, int], Dict[str, Any]],
) -> AggregationResult:
    deduped_events = dedupe_events_fn(all_events)
    included_events = filter_included_events_fn(deduped_events, args, profiles, uncategorized)

    exclude_list = [k.strip() for k in args.exclude.split(",") if k.strip()]
    grouped = group_by_day_fn(included_events, exclude_list)
    overall_days = estimate_hours_by_day_fn(
        grouped,
        args.gap_minutes,
        args.min_session,
        args.min_session_passive,
    )

    project_reports: Dict[str, Any] = {}
    for project_name in sorted({event["project"] for event in included_events}):
        project_events = [event for event in included_events if event["project"] == project_name]
        project_grouped = group_by_day_fn(project_events, exclude_list)
        project_reports[project_name] = estimate_hours_by_day_fn(
            project_grouped,
            args.gap_minutes,
            args.min_session,
            args.min_session_passive,
        )

    return AggregationResult(
        all_events=deduped_events,
        included_events=included_events,
        grouped=grouped,
        overall_days=overall_days,
        project_reports=project_reports,
    )

