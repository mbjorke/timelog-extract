"""Typer command for syncing TIMELOG-derived hours to Jira worklogs."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Annotated, Optional

import typer

from collectors.jira import jira_sync_enabled, resolve_jira_credentials
from core.cli_app import app
from core.cli_options import TimelogRunOptions
from core.jira_sync import JiraSyncSummary, build_jira_worklog_candidates, post_candidate


@app.command("jira-sync")
def jira_sync(
    date_from: Annotated[Optional[datetime], typer.Option("--from", formats=["%Y-%m-%d"], help="Start date (YYYY-MM-DD)")] = None,
    date_to: Annotated[Optional[datetime], typer.Option("--to", formats=["%Y-%m-%d"], help="End date (YYYY-MM-DD)")] = None,
    today: Annotated[bool, typer.Option(help="Limit to today.")] = False,
    yesterday: Annotated[bool, typer.Option(help="Limit to yesterday.")] = False,
    last_3_days: Annotated[bool, typer.Option(help="Limit to last 3 days.")] = False,
    last_week: Annotated[bool, typer.Option(help="Limit to last 7 days.")] = False,
    last_14_days: Annotated[bool, typer.Option(help="Limit to last 14 days.")] = False,
    last_month: Annotated[bool, typer.Option(help="Limit to last 30 days.")] = False,
    projects_config: Annotated[str, typer.Option(help="JSON config file")] = "timelog_projects.json",
    worklog: Annotated[Optional[str], typer.Option(help="Path to TIMELOG.md")] = None,
    worklog_format: Annotated[str, typer.Option(help="auto/md/gtimelog")] = "auto",
    jira_sync: Annotated[str, typer.Option(help="auto/on/off")] = "auto",
    jira_base_url: Annotated[Optional[str], typer.Option(help="Jira base URL")] = None,
    jira_email: Annotated[Optional[str], typer.Option(help="Jira user email")] = None,
    jira_api_token: Annotated[Optional[str], typer.Option(help="Jira API token")] = None,
    dry_run: Annotated[bool, typer.Option(help="Preview candidates; do not post")] = False,
    require_confirm: Annotated[bool, typer.Option(help="Confirm each post interactively")] = True,
    git_repo: Annotated[str, typer.Option(help="Path to git repository for issue tag lookup")] = ".",
):
    """Sync TIMELOG-derived hours to Jira worklogs."""
    from core.report_service import run_timelog_report

    options = TimelogRunOptions(
        date_from=date_from.strftime("%Y-%m-%d") if date_from else None,
        date_to=date_to.strftime("%Y-%m-%d") if date_to else None,
        today=today,
        yesterday=yesterday,
        last_3_days=last_3_days,
        last_week=last_week,
        last_14_days=last_14_days,
        last_month=last_month,
        projects_config=projects_config,
        worklog=worklog,
        worklog_format=worklog_format,
        output_format="json",
        screen_time="off",
        quiet=True,
        include_uncategorized=True,
    )
    report = run_timelog_report(
        options.projects_config,
        options.date_from,
        options.date_to,
        options,
    )

    enabled, reason = jira_sync_enabled(
        SimpleNamespace(
            jira_sync=jira_sync,
            jira_base_url=jira_base_url,
            jira_email=jira_email,
            jira_api_token=jira_api_token,
        )
    )
    if not enabled:
        raise typer.BadParameter(reason or "Jira sync is not enabled")

    creds = resolve_jira_credentials(
        SimpleNamespace(
            jira_base_url=jira_base_url,
            jira_email=jira_email,
            jira_api_token=jira_api_token,
        )
    )
    if creds is None:
        raise typer.BadParameter("Missing Jira credentials")

    candidates, unresolved = build_jira_worklog_candidates(report, Path(git_repo).expanduser())
    if not candidates:
        typer.echo("No Jira worklog candidates found.")
        if unresolved:
            typer.echo(f"Unresolved sessions (no issue key): {unresolved}")
        return

    summary = JiraSyncSummary(unresolved=unresolved)
    for candidate in candidates:
        typer.echo(
            f"{candidate.day} {candidate.issue_key} {candidate.hours:.2f}h "
            f"({candidate.seconds}s) source={candidate.source}"
        )
        if dry_run:
            summary.skipped += 1
            continue
        if require_confirm:
            ok = typer.confirm("Post this worklog to Jira?", default=False)
            if not ok:
                summary.skipped += 1
                continue
        try:
            worklog_id = post_candidate(creds, candidate)
            summary.posted += 1
            typer.echo(f"Posted Jira worklog id={worklog_id}")
        except Exception as exc:
            import logging
            import traceback
            summary.failed += 1
            typer.echo(f"Failed to post {candidate.issue_key} ({candidate.day}): {exc}")
            logging.error(f"Jira worklog post failed for {candidate.issue_key}: {traceback.format_exc()}")

    typer.echo(
        "Jira sync summary: "
        f"posted={summary.posted}, skipped={summary.skipped}, "
        f"unresolved={summary.unresolved}, failed={summary.failed}"
    )
