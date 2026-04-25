"""Run options dataclass and normalization (service boundary)."""

from __future__ import annotations

import argparse
import importlib.metadata
from dataclasses import dataclass
from typing import Any, List, Optional
from core.noise_profiles import DEFAULT_LOVABLE_NOISE_PROFILE, DEFAULT_NOISE_PROFILE


def package_version() -> str:
    try:
        return importlib.metadata.version("timelog-extract")
    except importlib.metadata.PackageNotFoundError:
        return "0.2.13-dev"


@dataclass
class TimelogRunOptions:
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    today: bool = False
    yesterday: bool = False
    last_3_days: bool = False
    last_week: bool = False
    last_14_days: bool = False
    last_month: bool = False
    projects_config: str = ""
    keywords: str = ""
    project: str = "default-project"
    email: str = ""
    min_session: int = 15
    min_session_passive: int = 5
    gap_minutes: int = 15
    chrome_collapse_minutes: int = 12
    exclude: str = ""
    worklog: Optional[str] = None
    worklog_format: str = "auto"
    source_strategy: str = "auto"
    screen_time: str = "auto"
    include_uncategorized: bool = False
    only_project: Optional[str] = None
    customer: Optional[str] = None
    all_events: bool = False
    source_summary: bool = False
    narrative: bool = False
    invoice_pdf: bool = False
    invoice_pdf_file: Optional[str] = None
    billable_unit: float = 0.0
    billable_round: str = "ceil"
    chrome_source: str = "on"
    mail_source: str = "auto"
    github_source: str = "auto"
    github_user: Optional[str] = None
    output_format: str = "terminal"
    quiet: bool = False
    json_file: Optional[str] = None
    report_html: Optional[str] = None
    additive_summary: bool = False
    noise_profile: str = DEFAULT_NOISE_PROFILE
    lovable_noise_profile: str = DEFAULT_LOVABLE_NOISE_PROFILE
    invoice_mode: str = "baseline"
    invoice_ground_truth: Optional[str] = None


def split_comma_separated_list(value: Optional[str]) -> List[str]:
    """Split comma-separated user input (e.g. match terms). None or empty → []."""
    if value is None or not value.strip():
        return []
    return [t.strip() for t in value.split(",") if t.strip()]


def as_run_options(options: Any) -> TimelogRunOptions:
    allowed_fields = set(TimelogRunOptions.__dataclass_fields__.keys())
    if isinstance(options, TimelogRunOptions):
        return options
    if isinstance(options, dict):
        unknown = set(options.keys()) - allowed_fields
        if unknown:
            raise ValueError(f"Unknown run option(s): {sorted(unknown)}")
        return TimelogRunOptions(
            **{k: v for k, v in options.items() if k in allowed_fields}
        )
    if isinstance(options, argparse.Namespace):
        d = vars(options)
        unknown = set(d.keys()) - allowed_fields
        if unknown:
            raise ValueError(f"Unknown run option(s): {sorted(unknown)}")
        return TimelogRunOptions(**{k: v for k, v in d.items() if k in allowed_fields})
    raise TypeError(f"Unsupported options type: {type(options)!r}")
