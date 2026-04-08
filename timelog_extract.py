#!/usr/bin/env python3
"""CLI entrypoint and backward-compatible exports for timelog extract."""

from __future__ import annotations

from pathlib import Path

from core import domain as core_domain
from core.cli import TimelogRunOptions, as_run_options, parse_args as core_parse_args
from core.config import default_worklog_path as core_default_worklog_path, normalize_profile
from core.report_service import (
    LOCAL_TZ,
    ReportPayload,
    UNCATEGORIZED,
    estimate_hours_by_day,
    generate_invoice_pdf,
    group_by_day,
    run_timelog_cli,
    run_timelog_report,
)

SCRIPT_DIR = Path(__file__).parent.resolve()
DEFAULT_KEYWORDS = ""
DEFAULT_PROJECT = "default-project"
DEFAULT_EMAIL = ""
DEFAULT_EXCLUDE = ""
DEFAULT_CONFIG = str(SCRIPT_DIR / "timelog_projects.json")


def parse_args():
    return core_parse_args(
        default_config=DEFAULT_CONFIG,
        default_keywords=DEFAULT_KEYWORDS,
        default_project=DEFAULT_PROJECT,
        default_email=DEFAULT_EMAIL,
        default_exclude=DEFAULT_EXCLUDE,
    )


def default_worklog_path() -> Path:
    return core_default_worklog_path(SCRIPT_DIR)


def classify_project(text, profiles, fallback=UNCATEGORIZED):
    return core_domain.classify_project(text, profiles, fallback)


def main():
    run_timelog_cli(parse_args())


if __name__ == "__main__":
    main()
