"""CLI entry: JSON/HTML outputs and terminal report orchestration."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Optional

from core.report_service import (
    ReportPayload,
    _build_invoice_pdf,
    _print_narrative,
    _print_report,
    _print_source_summary,
    _session_duration_hours,
    _want_log,
    default_invoice_pdf_path,
    generate_invoice_pdf,
    run_timelog_report,
)
from core.truth_payload import build_truth_payload
from outputs import html_timeline as html_timeline_output


def _build_truth_payload_dict(report: ReportPayload) -> Dict[str, Any]:
    cfg = str(report.config_path) if report.config_path else ""
    return build_truth_payload(
        overall_days=report.overall_days,
        project_reports=report.project_reports,
        included_events=report.included_events,
        collector_status=report.collector_status,
        screen_time_days=report.screen_time_days,
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
        session_duration_hours_fn=_session_duration_hours,
    )


def run_timelog_cli(args: argparse.Namespace) -> None:
    """Run a full report for parsed CLI args and print or write outputs."""
    if getattr(args, "output_format", "terminal") == "json":
        args.quiet = True
    report = run_timelog_report(args.projects_config, args.date_from, args.date_to, args)

    want_json = getattr(args, "output_format", "terminal") == "json"
    html_path = getattr(args, "report_html", None)
    want_html = bool(html_path)

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
                    )
                if _want_log(args):
                    print(f"PDF created: {built}")
            except Exception as exc:
                raise SystemExit(f"Could not create PDF: {exc}") from exc
        return

    if not report.included_events:
        if report.args.only_project:
            print(f"No events for project {report.args.only_project!r} in selected range.")
        else:
            print("No events found.")
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
