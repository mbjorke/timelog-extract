"""Typer command for posting Gittan-derived hours to Toggl time entries."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from typing import Annotated, Optional

import typer

from collectors.toggl import resolve_toggl_credentials, toggl_sync_enabled
from core.cli_app import app
from core.cli_options import TimelogRunOptions
from core.config import default_projects_config_option
from core.toggl_oplog import new_op_id, record_push
from core.toggl_sync import (
    TogglSyncSummary,
    build_toggl_entry_candidates,
    candidate_payload,
    existing_marker_tags,
    post_candidate,
    rollback_op,
)


def _next_step_hint(summary: TogglSyncSummary) -> str:
    """One concise line after the summary for every outcome."""
    if summary.failed > 0:
        return "Next: verify Toggl token/workspace, then rerun `gittan toggl-sync --dry-run`."
    if summary.unmapped > 0:
        return "Next: add `toggl_project_id` to the unmapped projects in timelog_projects.json."
    if summary.posted > 0:
        return "Next: verify the time entries in Toggl for the posted project(s)."
    if summary.skipped > 0:
        return "Next: nothing new — entries already exist or were declined."
    return "Next: nothing to post — sync complete."


@app.command("toggl-sync")
def toggl_sync(
    date_from: Annotated[Optional[datetime], typer.Option("--from", formats=["%Y-%m-%d"], help="Start date (YYYY-MM-DD)")] = None,
    date_to: Annotated[Optional[datetime], typer.Option("--to", formats=["%Y-%m-%d"], help="End date (YYYY-MM-DD)")] = None,
    today: Annotated[bool, typer.Option(help="Limit to today.")] = False,
    yesterday: Annotated[bool, typer.Option(help="Limit to yesterday.")] = False,
    last_3_days: Annotated[bool, typer.Option(help="Limit to last 3 days.")] = False,
    last_week: Annotated[bool, typer.Option(help="Limit to last 7 days.")] = False,
    last_14_days: Annotated[bool, typer.Option(help="Limit to last 14 days.")] = False,
    last_month: Annotated[bool, typer.Option(help="Limit to last 30 days.")] = False,
    projects_config: Annotated[str, typer.Option(help="JSON config file")] = default_projects_config_option(),
    worklog: Annotated[Optional[str], typer.Option(help="Path to TIMELOG.md")] = None,
    worklog_format: Annotated[str, typer.Option(help="auto/md/gtimelog")] = "auto",
    toggl_sync_mode: Annotated[str, typer.Option("--toggl-sync", help="auto/on/off")] = "auto",
    toggl_api_token: Annotated[Optional[str], typer.Option(help="Toggl API token")] = None,
    toggl_workspace_id: Annotated[Optional[int], typer.Option(help="Toggl workspace id")] = None,
    dry_run: Annotated[bool, typer.Option(help="Preview candidates; do not post")] = False,
    require_confirm: Annotated[bool, typer.Option(help="Confirm each post interactively")] = True,
    rollback: Annotated[Optional[str], typer.Option(help="Roll back a prior push by op-id (deletes its Toggl entries)")] = None,
    list_ops: Annotated[bool, typer.Option("--list-ops", help="List recorded push operations and exit")] = False,
):
    """Post Gittan-derived hours to Toggl as time entries (one per project + day)."""
    from core.report_service import run_timelog_report

    # Op-log subcommands short-circuit the report/post path entirely.
    if list_ops:
        _print_ops()
        return
    if rollback:
        _run_rollback(rollback, toggl_sync_mode, toggl_api_token, toggl_workspace_id)
        return

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

    gate_args = SimpleNamespace(
        toggl_sync=toggl_sync_mode,
        toggl_api_token=toggl_api_token,
        toggl_workspace_id=toggl_workspace_id,
    )
    enabled, reason = toggl_sync_enabled(gate_args)
    if not enabled:
        raise typer.BadParameter(reason or "Toggl sync is not enabled")
    creds = resolve_toggl_credentials(gate_args)
    if creds is None:
        raise typer.BadParameter("Missing Toggl credentials")

    candidates, unmapped = build_toggl_entry_candidates(report, report.profiles)
    if not candidates:
        typer.echo("No Toggl time-entry candidates found.")
        if unmapped:
            typer.echo(f"Unmapped sessions (no toggl_project_id): {unmapped}")
        typer.echo(_next_step_hint(TogglSyncSummary(unmapped=unmapped)))
        return

    summary = TogglSyncSummary(unmapped=unmapped)
    op_id = new_op_id()
    existing = set()
    if not dry_run:
        # Toggl's end_date is exclusive, so add a day to cover dt_to's full day.
        from datetime import timedelta

        start_date = report.dt_from.strftime("%Y-%m-%d")
        end_date = (report.dt_to.date() + timedelta(days=1)).strftime("%Y-%m-%d")
        try:
            existing = existing_marker_tags(creds, start_date, end_date)
        except Exception as exc:
            # Fail closed: without the dedup list we can't tell what already
            # exists, so abort rather than risk double-posting.
            raise typer.BadParameter(
                f"Could not list existing Toggl entries for dedup ({exc}); "
                "aborting to avoid duplicate posts. Re-run once Toggl is reachable, "
                "or use --dry-run to preview."
            )

    for candidate in candidates:
        typer.echo(
            f"{candidate.day} {candidate.project_name} {candidate.hours:.2f}h "
            f"({candidate.seconds}s) project_id={candidate.project_id}"
        )
        if dry_run:
            # Solo-first guardrail: print the exact outgoing payload before any post.
            import json

            typer.echo(json.dumps(candidate_payload(creds, candidate), indent=2))
            summary.skipped += 1
            continue
        if candidate.marker_tag in existing:
            typer.echo(f"Skipped (already in Toggl): {candidate.marker_tag}")
            summary.skipped += 1
            continue
        if require_confirm:
            if not typer.confirm("Post this time entry to Toggl?", default=False):
                summary.skipped += 1
                continue
        try:
            entry_id = post_candidate(creds, candidate)
            summary.posted += 1
            typer.echo(f"Posted Toggl time entry id={entry_id}")
            try:
                record_push(
                    op_id=op_id,
                    workspace_id=creds.workspace_id,
                    entry_id=entry_id,
                    project_id=candidate.project_id,
                    day=candidate.day,
                    marker_tag=candidate.marker_tag,
                    payload=candidate_payload(creds, candidate),
                )
            except Exception as log_exc:  # noqa: BLE001 - logging must not fail a post
                import logging

                logging.warning("Toggl op-log write failed for entry %s: %s", entry_id, log_exc)
        except Exception as exc:
            import logging
            import traceback

            summary.failed += 1
            typer.echo(f"Failed to post {candidate.project_name} ({candidate.day}): {exc}")
            logging.error(
                "Toggl time entry post failed for %s: %s",
                candidate.project_name,
                traceback.format_exc(),
            )

    typer.echo(
        "Toggl sync summary: "
        f"posted={summary.posted}, skipped={summary.skipped}, "
        f"unmapped={summary.unmapped}, failed={summary.failed}"
    )
    if summary.posted > 0:
        typer.echo(f"Operation id: {op_id}  (undo with `gittan toggl-sync --rollback {op_id}`)")
    typer.echo(_next_step_hint(summary))


def _toggl_creds_or_exit(mode, token, workspace_id):
    """Resolve Toggl creds for op-log subcommands, or raise a clean CLI error."""
    gate_args = SimpleNamespace(
        toggl_sync=mode, toggl_api_token=token, toggl_workspace_id=workspace_id
    )
    enabled, reason = toggl_sync_enabled(gate_args)
    if not enabled:
        raise typer.BadParameter(reason or "Toggl sync is not enabled")
    creds = resolve_toggl_credentials(gate_args)
    if creds is None:
        raise typer.BadParameter("Missing Toggl credentials")
    return creds


def _print_ops():
    from core.toggl_oplog import list_ops

    ops = list_ops()
    if not ops:
        typer.echo("No Toggl push operations recorded yet.")
        return
    typer.echo("Recorded Toggl push operations (newest first):")
    for op in ops:
        state = f"{op['rolled_back']}/{op['entries']} rolled back" if op["rolled_back"] else f"{op['entries']} entries"
        typer.echo(f"  {op['op_id']}  {op['ts']}  {state}  days={','.join(op['days'])}")


def _run_rollback(op_id, mode, token, workspace_id):
    creds = _toggl_creds_or_exit(mode, token, workspace_id)
    result = rollback_op(creds, op_id)
    for line in result.lines:
        typer.echo(line)
    typer.echo(
        "Rollback summary: "
        f"deleted={result.deleted}, already_gone={result.gone}, "
        f"already_rolled_back={result.already}, failed={result.failed}"
    )
    if result.failed:
        typer.echo(
            "Next: some deletions failed — re-run the same `--rollback` once Toggl "
            "is reachable; entries already removed are skipped."
        )
