"""Invoice/billable rendering split out of report_service.

Prefers confirmed ``reported_time`` over observed hours (GH-186 Phase 4) and
excludes autonomous agent time by default (GH-284 slice 2). Depends one-way on
``report_service`` for ``ReportPayload`` / ``LOCAL_TZ`` / billing helpers.
"""
from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from core.cli import TimelogRunOptions, as_run_options
from core.report_service import (
    LOCAL_TZ,
    ReportPayload,
    _billable_total_hours,
    default_invoice_pdf_path,
)
from outputs import pdf as pdf_output


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
    include_agent_billable: bool = False,
    billable_raw_by_project: Optional[Dict[str, float]] = None,
    reported_billing: bool = False,
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
        include_agent_billable=include_agent_billable,
        billable_raw_by_project=billable_raw_by_project,
        reported_billing=reported_billing,
    )


def compute_billable_by_project(
    report_payload: ReportPayload, home: Optional[Path] = None
) -> Tuple[Dict[str, float], bool]:
    """Raw billable hours per project + whether reported mode is active (GH-186 Phase 4).

    Prefers confirmed/edited ``reported_time`` over observed hours (the same D4
    adoption switch toggl-/jira-sync use); before adoption, falls back to observed
    hours with autonomous agent time excluded by default (GH-284 slice 2).
    """
    from core.domain import billable_raw_by_project
    from core.reported_sync import reported_hours_for_window

    reported = reported_hours_for_window(report_payload, home)
    include_agent = bool(getattr(report_payload.args, "include_agent_billable", False))
    by_project = billable_raw_by_project(
        report_payload.project_reports,
        reported_hours=reported,
        include_agent_billable=include_agent,
    )
    return by_project, reported is not None


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
    billable_by_project, reported_billing = compute_billable_by_project(report_payload)
    return _build_invoice_pdf(
        report_payload.overall_days,
        report_payload.project_reports,
        report_payload.profiles,
        report_payload.dt_from,
        report_payload.dt_to,
        output_path,
        customer_name=args.customer,
        billable_unit=args.billable_unit,
        include_agent_billable=getattr(args, "include_agent_billable", False),
        billable_raw_by_project=billable_by_project,
        reported_billing=reported_billing,
    )
