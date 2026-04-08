"""CLI parsing and run-option normalization."""

from __future__ import annotations

import argparse
import importlib.metadata
from dataclasses import dataclass
from typing import Any, Optional


def package_version() -> str:
    try:
        return importlib.metadata.version("timelog-extract")
    except importlib.metadata.PackageNotFoundError:
        return "0.1.0-dev"


@dataclass
class TimelogRunOptions:
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    today: bool = False
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
    screen_time: str = "auto"
    include_uncategorized: bool = False
    only_project: Optional[str] = None
    customer: Optional[str] = None
    all_events: bool = False
    source_summary: bool = False
    invoice_pdf: bool = False
    invoice_pdf_file: Optional[str] = None
    billable_unit: float = 0.0
    billable_round: str = "ceil"
    chrome_source: str = "on"
    mail_source: str = "auto"


def as_run_options(options: Any) -> TimelogRunOptions:
    allowed_fields = set(TimelogRunOptions.__dataclass_fields__.keys())
    if isinstance(options, TimelogRunOptions):
        return options
    if isinstance(options, argparse.Namespace):
        raw = vars(options)
        return TimelogRunOptions(**{k: v for k, v in raw.items() if k in allowed_fields})
    if isinstance(options, dict):
        return TimelogRunOptions(**{k: v for k, v in options.items() if k in allowed_fields})
    raise TypeError(f"Unsupported options type: {type(options)!r}")


def parse_args(default_config: str, default_keywords: str, default_project: str, default_email: str, default_exclude: str):
    p = argparse.ArgumentParser(
        description="Aggregate work time from multiple local sources and projects",
        prog="timelog-extract",
    )
    p.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"%(prog)s {package_version()}",
    )
    p.add_argument("--from", dest="date_from", metavar="YYYY-MM-DD",
                   help="Start date in local time (default: 30 days ago)")
    p.add_argument("--to", dest="date_to", metavar="YYYY-MM-DD",
                   help="End date in local time (default: today)")
    p.add_argument("--projects-config", default=default_config,
                   help=f"JSON config with project profiles (default: {default_config})")
    p.add_argument("--keywords", default=default_keywords,
                   help="Legacy fallback: comma-separated project keywords")
    p.add_argument("--project", default=default_project,
                   help="Legacy fallback: project name for AI logs")
    p.add_argument("--email", default=default_email,
                   help=f"Legacy fallback: sender email for sent mail (default: {default_email})")
    p.add_argument("--min-session", dest="min_session", type=int, default=15,
                   help="Minimitid i minuter per AI-session (default: 15)")
    p.add_argument("--min-session-passive", dest="min_session_passive", type=int, default=5,
                   help="Minimum duration in minutes for Chrome/Mail-only sessions (default: 5)")
    p.add_argument("--gap-minutes", type=int, default=15,
                   help="Gaps shorter than N minutes are merged into one session (default: 15)")
    p.add_argument("--chrome-collapse-minutes", type=int, default=12,
                   help="Skip repeated Chrome visits to the same page within N minutes (0=off; reduces refresh noise)")
    p.add_argument(
        "--chrome-source",
        choices=["on", "off"],
        default="on",
        help="Explicitly enable/disable Chrome source (default: on).",
    )
    p.add_argument(
        "--mail-source",
        choices=["auto", "on", "off"],
        default="auto",
        help="Enable/disable Apple Mail source (default: auto).",
    )
    p.add_argument("--exclude", default=default_exclude,
                   help="Kommaseparerade ord att filtrera bort")
    p.add_argument(
        "--worklog",
        default=None,
        metavar="PATH",
        help="Path to timelog file (default: TIMELOG.md in repo root)",
    )
    p.add_argument("--screen-time", choices=["auto", "on", "off"], default="auto",
                   help="Compare with Screen Time when possible (default: auto)")
    p.add_argument("--include-uncategorized", action="store_true",
                   help="Include uncategorized events in the report")
    p.add_argument(
        "--only-project",
        metavar="NAMN",
        default=None,
        help="Show only events for this project (exact string as 'name' in JSON)",
    )
    p.add_argument(
        "--customer",
        metavar="NAMN",
        default=None,
        help="Show only events for this customer (matches 'customer' in JSON, otherwise project name)",
    )
    p.add_argument(
        "--today",
        action="store_true",
        help="Limit to today in local timezone (--from and --to both set to today)",
    )
    p.add_argument(
        "--all-events",
        action="store_true",
        help="Print every event per session (otherwise max 5 distinct lines per session)",
    )
    p.add_argument(
        "--source-summary",
        action="store_true",
        help="Print event counts per source after filtering (IDE logs vs checkpoints, etc.)",
    )
    p.add_argument(
        "--invoice-pdf",
        action="store_true",
        help="Create an invoice-friendly PDF summary of hours",
    )
    p.add_argument(
        "--invoice-pdf-file",
        default=None,
        help="Optional file path for PDF (default: output/pdf/timelog-invoice-<date>.pdf)",
    )
    p.add_argument(
        "--billable-unit",
        type=float,
        default=0.0,
        metavar="TIMMAR",
        help=(
            "Billable granularity (0=off, e.g. 0.25): raw time is summed per project/customer first, "
            "then rounded up to the nearest N hours - not per session."
        ),
    )
    p.add_argument(
        "--billable-round",
        choices=["ceil", "nearest", "floor"],
        default="ceil",
        help=(
            "Backward compatibility: ignored. Rounding is always upward (ceil) on aggregated project time."
        ),
    )
    return p.parse_args()
