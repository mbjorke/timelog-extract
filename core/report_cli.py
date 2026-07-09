"""CLI entry: JSON/HTML outputs and terminal report orchestration."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from core.report_invoice import (
    _build_invoice_pdf,
    compute_billable_by_project,
    generate_invoice_pdf,
)
from core.report_postamble import run_post_report_followups
from core.report_service import (
    ReportPayload,
    _print_narrative,
    _print_report,
    _print_source_summary,
    _print_weekly,
    _session_duration_hours,
    _want_log,
    default_invoice_pdf_path,
    run_timelog_report,
)
from core.truth_payload import build_truth_payload
from outputs import html_timeline as html_timeline_output
from outputs.terminal import console as report_console


def _build_truth_payload_dict(report: ReportPayload) -> Dict[str, Any]:
    cfg = str(report.config_path) if report.config_path else ""
    return build_truth_payload(
        overall_days=report.overall_days,
        project_reports=report.project_reports,
        included_events=report.included_events,
        collector_status=report.collector_status,
        screen_time_days=report.screen_time_days,
        presence_estimated=report.presence_estimated,
        presence_edge_gaps=report.presence_edge_gaps,
        presence_bracketing=report.presence_bracketing,
        dt_from=report.dt_from,
        dt_to=report.dt_to,
        worklog_path=str(report.worklog_path),
        config_path=cfg,
        gap_minutes=report.args.gap_minutes,
        min_session_minutes=report.args.min_session,
        min_session_passive_minutes=report.args.min_session_passive,
        source_strategy_requested=getattr(report.args, "source_strategy", "auto"),
        source_strategy_effective=getattr(report.args, "source_strategy_effective", "balanced"),
        primary_source=getattr(report.args, "primary_source", "balanced"),
        worklog_paths=list(getattr(report.args, "worklog_paths", []) or []),
        session_duration_hours_fn=_session_duration_hours,
        chrome_raw=bool(getattr(report.args, "chrome_raw", False)),
    )


def run_timelog_cli(args: argparse.Namespace) -> None:
    """Run a full report for parsed CLI args and print or write outputs."""
    if getattr(args, "output_format", "terminal") == "json":
        args.quiet = True
    report = run_timelog_report(args.projects_config, args.date_from, args.date_to, args)

    want_json = getattr(args, "output_format", "terminal") == "json"

    # Persist the observed-hours cache for the agent statusline (Part A). Only on
    # real, non-quiet terminal runs — quiet/json paths (tests, `reported sync`,
    # the extension) skip it so they never touch the user's ~/.gittan.
    if not want_json and not getattr(args, "quiet", False):
        try:
            from core.observed_cache import write_observed_summary

            write_observed_summary(report)
        except Exception:  # noqa: BLE001 - the cache must never break a report
            logging.getLogger(__name__).debug("observed-cache write skipped", exc_info=True)
    html_path = getattr(args, "report_html", None)
    want_html = bool(html_path)

    from core.cli_report_status_helpers import capture_shadow_log_line, shadow_replay_line

    shadow_line = capture_shadow_log_line(
        getattr(args, "shadow_log", "auto"),
        getattr(report, "all_events", []),
        config_path=getattr(args, "projects_config", None),
    )
    if shadow_line and _want_log(args) and not want_json:
        print(shadow_line)
    replay_line = shadow_replay_line(getattr(report.args, "shadow_replay_restored", 0))
    if replay_line and _want_log(args) and not want_json:
        print(replay_line)

    payload: Optional[Dict[str, Any]] = None
    if want_json or want_html:
        payload = _build_truth_payload_dict(report)
    if want_html:
        out_html = Path(html_path).expanduser()
        assert payload is not None
        html_timeline_output.write_html_timeline(out_html, payload)
        if not want_json and _want_log(args):
            print(f"HTML report written: {out_html}")

    if want_json:
        text = json.dumps(payload, ensure_ascii=False, indent=2)
        print(text)
        jf = getattr(args, "json_file", None)
        if jf:
            Path(jf).expanduser().write_text(text + "\n", encoding="utf-8")
        if report.args.invoice_pdf:
            try:
                out = (
                    Path(report.args.invoice_pdf_file).expanduser()
                    if report.args.invoice_pdf_file
                    else default_invoice_pdf_path(report.dt_to)
                )
                if report.included_events:
                    built = generate_invoice_pdf(report, output_path=out)
                else:
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
                        include_agent_billable=getattr(report.args, "include_agent_billable", False),
                    )
                if _want_log(args):
                    print(f"PDF created: {built}")
            except Exception as exc:
                raise SystemExit(f"Could not create PDF: {exc}") from exc
        return

    if not report.included_events:
        from outputs.terminal_theme import CLR_VALUE_ORANGE, STYLE_MUTED, WARN_ICON
        if report.args.only_project:
            ambiguous = getattr(report.args, "only_project_ambiguous", None) or []
            if ambiguous:
                report_console.print(
                    f"{WARN_ICON} [{CLR_VALUE_ORANGE}]Project filter {report.args.only_project!r} is ambiguous.[/{CLR_VALUE_ORANGE}]"
                )
                report_console.print(
                    f"[{STYLE_MUTED}]Did you mean one of: {', '.join(repr(name) for name in ambiguous)}?[/{STYLE_MUTED}]"
                )
                return
            report_console.print(
                f"{WARN_ICON} [{CLR_VALUE_ORANGE}]No events for project {report.args.only_project!r} in selected range.[/{CLR_VALUE_ORANGE}]"
            )
        else:
            report_console.print(f"{WARN_ICON} [{CLR_VALUE_ORANGE}]No events found.[/{CLR_VALUE_ORANGE}]")
            report_console.print(
                f"[{STYLE_MUTED}]Next: run `gittan doctor` to verify source access, then "
                f"`gittan report --today --source-summary` to inspect collected evidence.[/{STYLE_MUTED}]"
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
                    include_agent_billable=getattr(report.args, "include_agent_billable", False),
                )
                print(f"PDF created: {built}")
            except Exception as exc:
                raise SystemExit(f"Could not create PDF: {exc}") from exc
        return

    if report.args.source_summary:
        _print_source_summary(report.included_events)

    billable_by_project = None
    reported_billing = False
    if getattr(report.args, "billable_unit", 0.0):
        billable_by_project, reported_billing = compute_billable_by_project(report)
    _print_report(
        report.overall_days,
        report.project_reports,
        report.screen_time_days,
        report.profiles,
        report.args,
        report.config_path,
        report.timelog_project_totals or None,
        report.git_project_totals or None,
        report.presence_estimated,
        presence_edge_gaps=report.presence_edge_gaps,
        presence_bracketing=report.presence_bracketing,
        billable_raw_by_project=billable_by_project,
        reported_billing=reported_billing,
    )
    run_post_report_followups(report_console, report)
    if getattr(report.args, "weekly", False):
        _print_weekly(report.project_reports)
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
