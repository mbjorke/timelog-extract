"""End-to-end report orchestration: collect, aggregate, and CLI output side effects."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from core import domain as core_domain
from core.analytics import (
    estimate_hours_by_day as core_estimate_hours_by_day,
    get_date_range as core_get_date_range,
    group_by_day as core_group_by_day,
)
from core.chrome_epoch import CHROME_EPOCH_DELTA_US
from core.cli import TimelogRunOptions, as_run_options
from core.config import load_profiles, resolve_worklog_path as core_resolve_worklog_path
from core.events import (
    dedupe_events as core_dedupe_events,
    event_key as core_event_key,
    filter_included_events,
    make_event as core_make_event,
)
from core.report_runtime import (
    build_run_context,
    collect_runtime_events,
    collect_screen_time_status,
)
from core.workspace_root import runtime_workspace_root
from core.report_aggregate import aggregate_report
from core.screen_time import collect_screen_time as core_collect_screen_time
from core.sources import AI_SOURCES, CURSOR_CHECKPOINTS_SOURCE, SOURCE_ORDER, WORKLOG_SOURCE
from outputs import narrative as narrative_output
from outputs import pdf as pdf_output
from outputs import terminal as terminal_output

REPO_ROOT = Path(__file__).resolve().parent.parent
HOME = Path.home()
LOCAL_TZ = datetime.now().astimezone().tzinfo or timezone.utc
APPLE_EPOCH = 978307200
UNCATEGORIZED = "Uncategorized"


def _want_log(args: argparse.Namespace) -> bool:
    return not getattr(args, "quiet", False)


SCREEN_TIME_DB_CANDIDATES = [
    HOME / "Library" / "Application Support" / "Knowledge" / "knowledgeC.db",
    HOME / "Library" / "Application Support" / "KnowledgeC" / "knowledgeC.db",
]
CURSOR_CHECKPOINTS_DIR = (
    HOME
    / "Library"
    / "Application Support"
    / "Cursor"
    / "User"
    / "globalStorage"
    / "anysphere.cursor-commits"
    / "checkpoints"
)
CODEX_IDE_SESSION_INDEX = HOME / ".codex" / "session_index.jsonl"


@dataclass
class ReportPayload:
    dt_from: datetime
    dt_to: datetime
    profiles: List[Dict[str, Any]]
    config_path: Optional[Path]
    worklog_path: Path
    all_events: List[Dict[str, Any]]
    included_events: List[Dict[str, Any]]
    grouped: Dict[str, Any]
    overall_days: Dict[str, Any]
    project_reports: Dict[str, Any]
    screen_time_days: Optional[Dict[str, float]]
    collector_status: Dict[str, Dict[str, Any]]
    args: argparse.Namespace
    source_strategy_effective: str


def _event_key(event: Dict[str, Any]) -> Any:
    return core_event_key(event, UNCATEGORIZED)


def _dedupe_events(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return core_dedupe_events(events, _event_key)


def _classify_project(text: str, profiles: List[Dict[str, Any]]) -> str:
    return core_domain.classify_project(text, profiles, UNCATEGORIZED)


def _make_event(source: str, ts: Any, detail: str, project: str) -> Dict[str, Any]:
    return core_make_event(source, ts, detail, project, UNCATEGORIZED)


def _get_date_range(date_from: Optional[str], date_to: Optional[str]):
    return core_get_date_range(date_from, date_to, LOCAL_TZ)


def default_invoice_pdf_path(dt_to: datetime) -> Path:
    local_date = dt_to.astimezone(LOCAL_TZ).date().isoformat()
    return REPO_ROOT / "output" / "pdf" / f"timelog-invoice-{local_date}.pdf"


def _collect_screen_time(dt_from: datetime, dt_to: datetime):
    return core_collect_screen_time(
        dt_from,
        dt_to,
        candidates=SCREEN_TIME_DB_CANDIDATES,
        apple_epoch=APPLE_EPOCH,
        local_tz=LOCAL_TZ,
    )


def _compute_sessions(entries: List[Dict[str, Any]], gap_minutes: int = 15):
    return core_domain.compute_sessions(entries, gap_minutes)


def _session_duration_hours(
    session_events: List[Dict[str, Any]],
    start_ts: Any,
    end_ts: Any,
    min_session_minutes: int,
    min_session_passive_minutes: int,
):
    return core_domain.session_duration_hours(
        session_events,
        start_ts,
        end_ts,
        min_session_minutes,
        min_session_passive_minutes,
        AI_SOURCES,
    )


def _billable_total_hours(raw_hours: float, unit: float) -> float:
    return core_domain.billable_total_hours(raw_hours, unit)


def _estimate_hours_by_day(
    days: Dict[str, Any],
    gap_minutes: int,
    min_session_minutes: int,
    min_session_passive_minutes: int,
):
    return core_estimate_hours_by_day(
        days,
        gap_minutes=gap_minutes,
        min_session_minutes=min_session_minutes,
        min_session_passive_minutes=min_session_passive_minutes,
        compute_sessions_fn=_compute_sessions,
        session_duration_hours_fn=_session_duration_hours,
    )


def estimate_hours_by_day(
    days: Dict[str, Any],
    gap_minutes: int = 15,
    min_session_minutes: int = 15,
    min_session_passive_minutes: int = 5,
):
    """Aggregate per-day hours using the same session rules as the CLI report."""
    return _estimate_hours_by_day(
        days,
        gap_minutes=gap_minutes,
        min_session_minutes=min_session_minutes,
        min_session_passive_minutes=min_session_passive_minutes,
    )


def _group_by_day(events: List[Dict[str, Any]], exclude_keywords: Optional[List[str]] = None):
    return core_group_by_day(events, local_tz=LOCAL_TZ, exclude_keywords=exclude_keywords)


def group_by_day(events: List[Dict[str, Any]], exclude_keywords=None):
    """Group events by local calendar day (same behavior as the CLI report)."""
    return _group_by_day(events, exclude_keywords=exclude_keywords)


def _print_source_summary(events: List[Dict[str, Any]]) -> None:
    terminal_output.print_source_summary(events, SOURCE_ORDER)


def _print_report(
    overall_days: Dict[str, Any],
    project_reports: Dict[str, Any],
    screen_time_days: Optional[Dict[str, float]],
    profiles: List[Dict[str, Any]],
    args: argparse.Namespace,
    config_path: Optional[Path],
) -> None:
    terminal_output.print_report(
        overall_days=overall_days,
        project_reports=project_reports,
        screen_time_days=screen_time_days,
        profiles=profiles,
        args=args,
        config_path=config_path,
        local_tz=LOCAL_TZ,
        source_order=SOURCE_ORDER,
        uncategorized=UNCATEGORIZED,
        session_duration_hours_fn=_session_duration_hours,
        billable_total_hours_fn=_billable_total_hours,
    )


def _print_narrative(
    overall_days: Dict[str, Any],
    project_reports: Dict[str, Any],
    included_events: List[Dict[str, Any]],
    dt_from: datetime,
    dt_to: datetime,
) -> None:
    lines = narrative_output.build_narrative_lines(
        overall_days,
        project_reports,
        included_events,
        UNCATEGORIZED,
        SOURCE_ORDER,
        dt_from,
        dt_to,
    )
    narrative_output.print_executive_narrative(lines)


def _build_invoice_pdf(
    overall_days: Dict[str, Any],
    project_reports: Dict[str, Any],
    profiles: List[Dict[str, Any]],
    dt_from: datetime,
    dt_to: datetime,
    output_path: Path,
    *,
    empty_note: Optional[str] = None,
    customer_name: Optional[str] = None,
    billable_unit: float = 0.0,
) -> Path:
    return pdf_output.build_invoice_pdf(
        overall_days=overall_days,
        project_reports=project_reports,
        profiles=profiles,
        dt_from=dt_from,
        dt_to=dt_to,
        output_path=output_path,
        local_tz=LOCAL_TZ,
        billable_total_hours_fn=_billable_total_hours,
        empty_note=empty_note,
        customer_name=customer_name,
        billable_unit=billable_unit,
    )


def run_timelog_report(
    config_path: str,
    date_from: Optional[str],
    date_to: Optional[str],
    options: Union[argparse.Namespace, TimelogRunOptions, Dict[str, Any]],
) -> ReportPayload:
    context = build_run_context(
        config_path=config_path,
        date_from=date_from,
        date_to=date_to,
        options=options,
        local_tz=LOCAL_TZ,
        repo_root=runtime_workspace_root(),
        as_run_options_fn=as_run_options,
        get_date_range_fn=_get_date_range,
        load_profiles_fn=load_profiles,
        resolve_worklog_path_fn=core_resolve_worklog_path,
        want_log_fn=_want_log,
    )
    args = context.args
    dt_from = context.dt_from
    dt_to = context.dt_to
    profiles = context.profiles
    loaded_config_path = context.loaded_config_path
    worklog_path = context.worklog_path

    all_events, collector_status = collect_runtime_events(
        context=context,
        home=HOME,
        local_tz=LOCAL_TZ,
        chrome_epoch_delta_us=CHROME_EPOCH_DELTA_US,
        uncategorized=UNCATEGORIZED,
        cursor_checkpoints_dir=CURSOR_CHECKPOINTS_DIR,
        codex_ide_session_index=CODEX_IDE_SESSION_INDEX,
        worklog_source=WORKLOG_SOURCE,
        cursor_checkpoints_source=CURSOR_CHECKPOINTS_SOURCE,
        classify_project_fn=_classify_project,
        make_event_fn=_make_event,
    )

    screen_time_days = collect_screen_time_status(
        args=args,
        dt_from=dt_from,
        dt_to=dt_to,
        collector_status=collector_status,
        collect_screen_time_fn=_collect_screen_time,
        want_log_fn=_want_log,
    )

    agg = aggregate_report(
        all_events=all_events,
        args=args,
        profiles=profiles,
        uncategorized=UNCATEGORIZED,
        dedupe_events_fn=_dedupe_events,
        filter_included_events_fn=filter_included_events,
        group_by_day_fn=lambda events, exclude: _group_by_day(events, exclude_keywords=exclude),
        estimate_hours_by_day_fn=lambda days, gap, min_s, min_p: estimate_hours_by_day(
            days,
            gap_minutes=gap,
            min_session_minutes=min_s,
            min_session_passive_minutes=min_p,
        ),
    )

    return ReportPayload(
        dt_from=dt_from,
        dt_to=dt_to,
        profiles=profiles,
        config_path=loaded_config_path,
        worklog_path=worklog_path,
        all_events=agg.all_events,
        included_events=agg.included_events,
        grouped=agg.grouped,
        overall_days=agg.overall_days,
        project_reports=agg.project_reports,
        screen_time_days=screen_time_days,
        collector_status=collector_status,
        args=args,
        source_strategy_effective=context.source_strategy_effective,
    )


def generate_invoice_pdf(
    report_payload: ReportPayload,
    output_path: Optional[Path] = None,
    options: Optional[Union[argparse.Namespace, TimelogRunOptions, Dict[str, Any]]] = None,
) -> Path:
    if options is None:
        args = report_payload.args
    elif isinstance(options, dict):
        merged = {**vars(report_payload.args), **options}
        args = argparse.Namespace(**vars(as_run_options(merged)))
    else:
        args = argparse.Namespace(**vars(as_run_options(options)))
    if output_path is None:
        output_path = (
            Path(args.invoice_pdf_file).expanduser()
            if args.invoice_pdf_file
            else default_invoice_pdf_path(report_payload.dt_to)
        )
    return _build_invoice_pdf(
        report_payload.overall_days,
        report_payload.project_reports,
        report_payload.profiles,
        report_payload.dt_from,
        report_payload.dt_to,
        output_path,
        customer_name=args.customer,
        billable_unit=args.billable_unit,
    )
