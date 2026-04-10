"""Stable engine API intended for extension callers.

This module provides a narrow, pure(ish) service boundary that returns the
versioned truth payload as a plain dict. The extension should depend on this
module rather than CLI or output modules.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict, Optional, Union

from core.cli import TimelogRunOptions
from core.report_service import (
    _session_duration_hours,
    generate_invoice_pdf,
    run_timelog_report,
)
from core.truth_payload import build_truth_payload


def _payload_from_report(report) -> Dict[str, Any]:
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
        session_duration_hours_fn=_session_duration_hours,
    )


def run_report_payload(
    config_path: str,
    date_from: Optional[str],
    date_to: Optional[str],
    options: Union[argparse.Namespace, TimelogRunOptions, Dict[str, Any]],
) -> Dict[str, Any]:
    """Run extraction and return a JSON-serializable truth payload dict."""
    report = run_timelog_report(config_path, date_from, date_to, options)
    return _payload_from_report(report)


def run_report_json(
    config_path: str,
    date_from: Optional[str],
    date_to: Optional[str],
    options: Union[argparse.Namespace, TimelogRunOptions, Dict[str, Any]],
) -> Dict[str, Any]:
    """Back-compat alias for callers that expect a JSON-ish return."""
    return run_report_payload(config_path, date_from, date_to, options)


def run_report_with_optional_pdf(
    config_path: str,
    date_from: Optional[str],
    date_to: Optional[str],
    options: Union[argparse.Namespace, TimelogRunOptions, Dict[str, Any]],
    *,
    generate_pdf: bool = False,
    pdf_output_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Run report payload and optionally generate invoice PDF in one boundary call."""
    report = run_timelog_report(config_path, date_from, date_to, options)
    payload = _payload_from_report(report)
    out: Dict[str, Any] = {"payload": payload, "pdf_path": None}
    if generate_pdf:
        path_arg = Path(pdf_output_path).expanduser() if pdf_output_path else None
        pdf_path = generate_invoice_pdf(report, output_path=path_arg, options=options)
        out["pdf_path"] = str(pdf_path)
    return out

