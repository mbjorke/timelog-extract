"""All-available observed hours per project for the ``--history`` display column."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Union

from core import domain as core_domain
from core.analytics import estimate_hours_by_day, get_date_range, group_by_day
from core.chrome_epoch import CHROME_EPOCH_DELTA_US
from core.cli import TimelogRunOptions, as_run_options
from core.cli_date_range import resolve_all_available_window
from core.config import load_profiles, resolve_worklog_path as core_resolve_worklog_path
from core.events import dedupe_events, event_key, filter_included_events, make_event as core_make_event
from core.evidence_store import maybe_replay
from core.report_aggregate import aggregate_report
from core.report_runtime import build_run_context, collect_runtime_events
from core.sources import CURSOR_CHECKPOINTS_SOURCE, WORKLOG_SOURCE
from core.workspace_root import runtime_workspace_root

HOME = Path.home()
LOCAL_TZ = datetime.now().astimezone().tzinfo or timezone.utc
UNCATEGORIZED = "Uncategorized"
_CURSOR_CHECKPOINTS_DIR = (
    HOME
    / "Library"
    / "Application Support"
    / "Cursor"
    / "User"
    / "globalStorage"
    / "anysphere.cursor-commits"
    / "checkpoints"
)
_CODEX_IDE_SESSION_INDEX = HOME / ".codex" / "session_index.jsonl"


def project_hours_totals(project_reports: Dict[str, Any]) -> Dict[str, float]:
    totals: Dict[str, float] = {}
    for name, days in project_reports.items():
        hours = sum(float(d.get("hours") or 0.0) for d in days.values())
        if hours > 0:
            totals[str(name)] = hours
    return totals


def compute_observed_all_time_totals(
    config_path: str,
    options: Union[TimelogRunOptions, Any],
) -> Dict[str, float]:
    """Collector pass over all available logs; display-only under ``--history``."""
    args = as_run_options(options)
    if not getattr(args, "history_source", False):
        return {}

    df_s, dt_s = resolve_all_available_window()
    context = build_run_context(
        config_path=config_path,
        date_from=df_s,
        date_to=dt_s,
        options=options,
        local_tz=LOCAL_TZ,
        repo_root=runtime_workspace_root(),
        as_run_options_fn=as_run_options,
        get_date_range_fn=lambda f, t: get_date_range(f, t, LOCAL_TZ),
        load_profiles_fn=load_profiles,
        resolve_worklog_path_fn=core_resolve_worklog_path,
        want_log_fn=lambda _a: False,
    )

    def _classify(text: str, profiles: List[Dict[str, Any]]) -> str:
        return core_domain.classify_project(text, profiles, UNCATEGORIZED)

    def _make_event(source: str, ts: Any, detail: str, project: str, anchors: dict | None = None):
        return core_make_event(source, ts, detail, project, UNCATEGORIZED, anchors=anchors)

    all_events, _status = collect_runtime_events(
        context=context,
        home=HOME,
        local_tz=LOCAL_TZ,
        chrome_epoch_delta_us=CHROME_EPOCH_DELTA_US,
        uncategorized=UNCATEGORIZED,
        cursor_checkpoints_dir=_CURSOR_CHECKPOINTS_DIR,
        codex_ide_session_index=_CODEX_IDE_SESSION_INDEX,
        worklog_source=WORKLOG_SOURCE,
        cursor_checkpoints_source=CURSOR_CHECKPOINTS_SOURCE,
        classify_project_fn=_classify,
        make_event_fn=_make_event,
    )
    all_events = maybe_replay(
        all_events,
        args=args,
        dt_from=context.dt_from,
        dt_to=context.dt_to,
        home=HOME,
        local_tz=LOCAL_TZ,
    )

    agg = aggregate_report(
        all_events=all_events,
        args=context.args,
        profiles=context.profiles,
        uncategorized=UNCATEGORIZED,
        dedupe_events_fn=lambda events: dedupe_events(events, lambda e: event_key(e, UNCATEGORIZED)),
        filter_included_events_fn=filter_included_events,
        group_by_day_fn=lambda events, exclude: group_by_day(events, exclude_keywords=exclude),
        estimate_hours_by_day_fn=lambda days, gap, min_s, min_p: estimate_hours_by_day(
            days,
            gap_minutes=gap,
            min_session_minutes=min_s,
            min_session_passive_minutes=min_p,
        ),
    )
    return project_hours_totals(agg.project_reports)
