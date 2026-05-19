"""Legacy CLI name for URL mapping (`gittan triage-map` → use `gittan review`)."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Optional

import typer

from core.cli_app import app
from core.cli_deprecation import warn_deprecated_command
from core.cli_url_mapping import run_url_mapping_review


@app.command("triage-map")
def triage_map(
    date_from: Annotated[Optional[datetime], typer.Option("--from", formats=["%Y-%m-%d"], help="Start date (YYYY-MM-DD)")] = None,
    date_to: Annotated[Optional[datetime], typer.Option("--to", formats=["%Y-%m-%d"], help="End date (YYYY-MM-DD)")] = None,
    today: Annotated[bool, typer.Option(help="Limit to today.")] = False,
    yesterday: Annotated[bool, typer.Option(help="Limit to yesterday.")] = False,
    last_3_days: Annotated[bool, typer.Option(help="Limit to last 3 days.")] = False,
    last_week: Annotated[bool, typer.Option(help="Limit to last 7 days.")] = False,
    last_14_days: Annotated[bool, typer.Option(help="Limit to last 14 days.")] = False,
    last_month: Annotated[bool, typer.Option(help="Limit to last 30 days.")] = False,
    projects_config: Annotated[Optional[str], typer.Option(help="JSON config file")] = None,
    max_rows: Annotated[int, typer.Option(help="Maximum URL candidate rows", min=1)] = 50,
    min_events: Annotated[int, typer.Option(help="Minimum events per URL key")] = 2,
    include_low_signal: Annotated[bool, typer.Option(help="Include low-signal/noise URL keys for debugging")] = False,
    max_days: Annotated[int, typer.Option(help="Top unexplained days to source Chrome evidence from")] = 7,
    auto_high: Annotated[bool, typer.Option(help="Auto-propose high-confidence rows first")] = True,
    json_out: Annotated[
        bool,
        typer.Option("--json", help="Print read-only URL candidate JSON to stdout; never writes config"),
    ] = False,
) -> None:
    """[deprecated] Use `gittan review` — map URL-level candidates to projects."""
    warn_deprecated_command("gittan triage-map", replacement="gittan review")
    run_url_mapping_review(
        date_from=date_from,
        date_to=date_to,
        today=today,
        yesterday=yesterday,
        last_3_days=last_3_days,
        last_week=last_week,
        last_14_days=last_14_days,
        last_month=last_month,
        projects_config=projects_config,
        max_rows=max_rows,
        min_events=min_events,
        include_low_signal=include_low_signal,
        max_days=max_days,
        auto_high=auto_high,
        json_out=json_out,
    )
