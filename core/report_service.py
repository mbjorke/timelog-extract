"""End-to-end report orchestration: collect, aggregate, and CLI output side effects."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from collectors import ai_logs as ai_logs_collector
from collectors import chrome as chrome_collector
from collectors import cursor as cursor_collector
from collectors import mail as mail_collector
from collectors import timelog as timelog_collector
from core import domain as core_domain
from core.analytics import (
    estimate_hours_by_day as core_estimate_hours_by_day,
    get_date_range as core_get_date_range,
    group_by_day as core_group_by_day,
)
from core.cli import TimelogRunOptions, as_run_options
from core.collector_registry import build_collector_specs
from core.config import load_profiles, resolve_worklog_path as core_resolve_worklog_path
from core.events import (
    dedupe_events as core_dedupe_events,
    event_key as core_event_key,
    filter_included_events,
    make_event as core_make_event,
)
from core.pipeline import collect_all_events
from core.runtime_collectors import RuntimeCollectors
from core.screen_time import collect_screen_time as core_collect_screen_time
from core.sources import AI_SOURCES, CURSOR_CHECKPOINTS_SOURCE, SOURCE_ORDER, WORKLOG_SOURCE
from outputs import narrative as narrative_output
from outputs import pdf as pdf_output
from outputs import terminal as terminal_output

REPO_ROOT = Path(__file__).resolve().parent.parent
HOME = Path.home()
LOCAL_TZ = datetime.now().astimezone().tzinfo or timezone.utc
APPLE_EPOCH = 978307200
CHROME_EPOCH_DELTA_US = 11_644_473_600 * 1_000_000
UNCATEGORIZED = "Uncategorized"

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
    run_options = as_run_options(options)
    args = argparse.Namespace(**vars(run_options))
    args.projects_config = config_path
    args.date_from = date_from
    args.date_to = date_to

    if args.today:
        today_s = datetime.now(LOCAL_TZ).strftime("%Y-%m-%d")
        args.date_from = today_s
        args.date_to = today_s
    dt_from, dt_to = _get_date_range(args.date_from, args.date_to)
    profiles, loaded_config_path, workspace = load_profiles(args.projects_config, args)
    worklog_path = core_resolve_worklog_path(
        args.worklog, loaded_config_path, workspace.get("worklog"), REPO_ROOT
    )

    print(f"\nScanning: {dt_from.date()} -> {dt_to.date()}")
    if args.only_project:
        print(f"Only project: {args.only_project!r}")
    if args.customer:
        print(f"Only customer: {args.customer!r}")
    print(f"Local timezone: {LOCAL_TZ}")
    print(f"Project profiles: {len(profiles)}")
    print(f"Worklog: {worklog_path}")
    print()

    runtime_collectors = RuntimeCollectors(
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
        ai_logs_collector=ai_logs_collector,
        chrome_collector=chrome_collector,
        cursor_collector=cursor_collector,
        mail_collector=mail_collector,
        timelog_collector=timelog_collector,
    )

    all_events, collector_status = collect_all_events(
        profiles,
        dt_from,
        dt_to,
        args,
        worklog_path,
        home=HOME,
        chrome_history_path_fn=chrome_collector.chrome_history_path,
        detect_mail_root_fn=mail_collector.detect_mail_root,
        build_collector_specs_fn=build_collector_specs,
        collect_claude_code=runtime_collectors.collect_claude_code,
        collect_claude_desktop=runtime_collectors.collect_claude_desktop,
        collect_claude_ai_urls=runtime_collectors.collect_claude_ai_urls,
        collect_gemini_web_urls=runtime_collectors.collect_gemini_web_urls,
        collect_chrome=runtime_collectors.collect_chrome,
        collect_gemini_cli=runtime_collectors.collect_gemini_cli,
        collect_cursor=runtime_collectors.collect_cursor,
        collect_cursor_checkpoints=runtime_collectors.collect_cursor_checkpoints,
        collect_codex_ide=runtime_collectors.collect_codex_ide,
        collect_apple_mail=runtime_collectors.collect_apple_mail,
        collect_worklog=runtime_collectors.collect_worklog,
    )

    screen_time_days = None
    screen_step_index = len(collector_status) + 1
    total_steps = screen_step_index
    print(f"[{screen_step_index}/{total_steps}] Screen Time …")
    if args.screen_time == "off":
        print("      disabled via --screen-time off\n")
        collector_status["Screen Time"] = {
            "enabled": False,
            "reason": "disabled via --screen-time off",
            "days": 0,
        }
    else:
        screen_time_days, screen_msg = _collect_screen_time(dt_from, dt_to)
        if screen_time_days is None:
            if args.screen_time == "on":
                print(f"      could not read Screen Time: {screen_msg}\n")
            else:
                print(f"      skipping: {screen_msg}\n")
            collector_status["Screen Time"] = {
                "enabled": args.screen_time == "on",
                "reason": screen_msg,
                "days": 0,
            }
        else:
            print(f"      {len(screen_time_days)} days loaded from {screen_msg}\n")
            collector_status["Screen Time"] = {
                "enabled": True,
                "reason": "",
                "days": len(screen_time_days),
            }

    all_events = _dedupe_events(all_events)
    included_events = filter_included_events(all_events, args, profiles, UNCATEGORIZED)

    exclude_list = [k.strip() for k in args.exclude.split(",") if k.strip()]
    grouped = _group_by_day(included_events, exclude_keywords=exclude_list)
    overall_days = estimate_hours_by_day(
        grouped,
        gap_minutes=args.gap_minutes,
        min_session_minutes=args.min_session,
        min_session_passive_minutes=args.min_session_passive,
    )

    project_reports = {}
    for project_name in sorted({event["project"] for event in included_events}):
        project_events = [event for event in included_events if event["project"] == project_name]
        project_grouped = _group_by_day(project_events, exclude_keywords=exclude_list)
        project_reports[project_name] = estimate_hours_by_day(
            project_grouped,
            gap_minutes=args.gap_minutes,
            min_session_minutes=args.min_session,
            min_session_passive_minutes=args.min_session_passive,
        )

    return ReportPayload(
        dt_from=dt_from,
        dt_to=dt_to,
        profiles=profiles,
        config_path=loaded_config_path,
        worklog_path=worklog_path,
        all_events=all_events,
        included_events=included_events,
        grouped=grouped,
        overall_days=overall_days,
        project_reports=project_reports,
        screen_time_days=screen_time_days,
        collector_status=collector_status,
        args=args,
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


def run_timelog_cli(args: argparse.Namespace) -> None:
    """Run a full report for parsed CLI args and print or write outputs."""
    report = run_timelog_report(args.projects_config, args.date_from, args.date_to, args)
    if not report.included_events:
        if report.args.only_project:
            print(f"No events for project {report.args.only_project!r} in selected range.")
        else:
            print("No events found.")
        if report.args.narrative:
            _print_narrative(
                report.overall_days,
                report.project_reports,
                report.included_events,
                report.dt_from,
                report.dt_to,
            )
        if report.args.invoice_pdf:
            try:
                out = (
                    Path(report.args.invoice_pdf_file).expanduser()
                    if report.args.invoice_pdf_file
                    else default_invoice_pdf_path(report.dt_to)
                )
                built = _build_invoice_pdf(
                    {},
                    {},
                    report.profiles,
                    report.dt_from,
                    report.dt_to,
                    out,
                    empty_note=(
                        "No classified events for selected range/filter — report is empty (0 hours)."
                    ),
                    customer_name=report.args.customer,
                    billable_unit=report.args.billable_unit,
                )
                print(f"PDF created: {built}")
            except Exception as exc:
                raise SystemExit(f"Could not create PDF: {exc}") from exc
        return

    if report.args.source_summary:
        _print_source_summary(report.included_events)

    _print_report(
        report.overall_days,
        report.project_reports,
        report.screen_time_days,
        report.profiles,
        report.args,
        report.config_path,
    )
    if report.args.narrative:
        _print_narrative(
            report.overall_days,
            report.project_reports,
            report.included_events,
            report.dt_from,
            report.dt_to,
        )
    if report.args.invoice_pdf:
        try:
            built = generate_invoice_pdf(report)
            print(f"PDF created: {built}")
        except Exception as exc:
            raise SystemExit(f"Could not create PDF: {exc}") from exc
