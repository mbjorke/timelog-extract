"""Typer commands: `gittan review` (URL mapping) and `gittan evidence-check`."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Optional

import typer

from core.cli_ab_rule_suggestions import _apply_timeframe_prompt
from core.cli_app import app
from core.cli_options import TimelogRunOptions
from core.cli_review_uncategorized import run_uncategorized_cluster_review
from core.cli_url_mapping import run_url_mapping_review
from core.config import default_projects_config_option, resolve_projects_config_path
from core.evidence_diagnostics import build_evidence_snapshot, build_evidence_warnings


@app.command()
def review(
    date_from: Annotated[Optional[datetime], typer.Option("--from", formats=["%Y-%m-%d"], help="Start date (YYYY-MM-DD)")] = None,
    date_to: Annotated[Optional[datetime], typer.Option("--to", formats=["%Y-%m-%d"], help="End date (YYYY-MM-DD)")] = None,
    today: Annotated[bool, typer.Option(help="Limit to today.")] = False,
    yesterday: Annotated[bool, typer.Option(help="Limit to yesterday.")] = False,
    last_3_days: Annotated[bool, typer.Option(help="Limit to last 3 days.")] = False,
    last_week: Annotated[bool, typer.Option(help="Limit to last 7 days.")] = False,
    last_14_days: Annotated[bool, typer.Option(help="Limit to last 14 days.")] = False,
    last_month: Annotated[bool, typer.Option(help="Limit to last 30 days.")] = False,
    uncategorized: Annotated[
        bool,
        typer.Option(
            "--uncategorized",
            help="Legacy: review uncategorized log-text clusters instead of URL mapping.",
        ),
    ] = False,
    ab_suggestions: Annotated[
        bool,
        typer.Option(help="[deprecated] With --uncategorized only: A/B rule suggestions."),
    ] = False,
    project: Annotated[
        Optional[str],
        typer.Option(help="With --uncategorized --ab-suggestions: target project name."),
    ] = None,
    projects_config: Annotated[Optional[str], typer.Option(help="JSON config file")] = None,
    max_clusters: Annotated[int, typer.Option(help="With --uncategorized: max clusters")] = 20,
    samples_per_cluster: Annotated[int, typer.Option(help="With --uncategorized: samples per cluster")] = 4,
    max_rows: Annotated[int, typer.Option(help="Maximum URL candidate rows", min=1)] = 50,
    min_events: Annotated[int, typer.Option(help="Minimum events per URL key")] = 2,
    include_low_signal: Annotated[bool, typer.Option(help="Include low-signal/noise URL keys for debugging")] = False,
    max_days: Annotated[int, typer.Option(help="Top unexplained days to source Chrome evidence from")] = 7,
    auto_high: Annotated[bool, typer.Option(help="Auto-propose high-confidence URL rows first")] = True,
    json_out: Annotated[
        bool,
        typer.Option("--json", help="Print read-only URL candidate JSON to stdout; never writes config"),
    ] = False,
):
    """Map URL hosts to projects (default). Use --uncategorized for legacy log-cluster cleanup."""
    if uncategorized:
        resolved = str(projects_config) if projects_config else str(resolve_projects_config_path())

        def _date_str(value: Optional[datetime]) -> Optional[str]:
            return value.strftime("%Y-%m-%d") if isinstance(value, datetime) else None

        run_uncategorized_cluster_review(
            date_from=_date_str(date_from),
            date_to=_date_str(date_to),
            today=today,
            yesterday=yesterday,
            last_3_days=last_3_days,
            last_week=last_week,
            last_14_days=last_14_days,
            last_month=last_month,
            ab_suggestions=ab_suggestions,
            project=project,
            projects_config=resolved,
            max_clusters=max_clusters,
            samples_per_cluster=samples_per_cluster,
        )
        return

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


@app.command("evidence-check")
def evidence_check(
    date_from: Annotated[Optional[str], typer.Option("--from", help="Start date (YYYY-MM-DD)")] = None,
    date_to: Annotated[Optional[str], typer.Option("--to", help="End date (YYYY-MM-DD)")] = None,
    today: Annotated[bool, typer.Option(help="Limit to today.")] = False,
    yesterday: Annotated[bool, typer.Option(help="Limit to yesterday.")] = False,
    last_3_days: Annotated[bool, typer.Option(help="Limit to last 3 days.")] = False,
    last_week: Annotated[bool, typer.Option(help="Limit to last 7 days.")] = False,
    last_14_days: Annotated[bool, typer.Option(help="Limit to last 14 days.")] = False,
    last_month: Annotated[bool, typer.Option(help="Limit to last 30 days.")] = False,
    projects_config: Annotated[str, typer.Option(help="JSON config file")] = default_projects_config_option(),
):
    """Quick evidence-health check for source coverage vs Screen Time."""
    from rich.console import Console
    from core.report_service import run_timelog_report

    console = Console()
    date_from, date_to, today, yesterday, last_3_days, last_week, last_14_days, last_month = _apply_timeframe_prompt(
        date_from,
        date_to,
        today,
        yesterday,
        last_3_days,
        last_week,
        last_14_days,
        last_month,
    )
    options = TimelogRunOptions(
        date_from=date_from,
        date_to=date_to,
        today=today,
        yesterday=yesterday,
        last_3_days=last_3_days,
        last_week=last_week,
        last_14_days=last_14_days,
        last_month=last_month,
        projects_config=projects_config,
        include_uncategorized=True,
        quiet=True,
    )
    report = run_timelog_report(options.projects_config, options.date_from, options.date_to, options)
    snapshot = build_evidence_snapshot(report)
    warnings = build_evidence_warnings(snapshot)
    console.print("[bold]Evidence check[/bold]")
    console.print(f"- Observed timeline hours: {snapshot['observed_hours']:.1f}h")
    console.print(f"- Screen Time hours: {snapshot['screen_time_hours']:.1f}h")
    console.print(f"- Delta (Screen Time - observed): {snapshot['delta_hours']:+.1f}h")
    source_counts = snapshot["source_counts"]
    if source_counts:
        console.print("- Source counts:")
        for source, count in sorted(source_counts.items(), key=lambda item: (-item[1], item[0])):
            console.print(f"  - {source}: {count}")
    if warnings:
        console.print("[yellow]Warnings[/yellow]")
        for warning in warnings:
            console.print(f"- {warning}")
    else:
        console.print("[green]No major evidence gaps detected.[/green]")
