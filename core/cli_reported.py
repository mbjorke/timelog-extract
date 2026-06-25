"""`gittan reported` — turn observed time into confirmed reported time, or add
net-new manual time (Part 2, Phase 2).

`reported review` lists observed sessions as per-project+day proposals and lets
the user confirm / edit hours / dismiss each; `reported add` records manual time
gittan never saw (SFTP, mail, meetings); `reported list` shows confirmed totals.
Only confirmed/edited records are later pushed (Toggl/Jira) or billed.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Optional

import typer

from core.cli_app import app
from core.cli_options import TimelogRunOptions
from core.config import default_projects_config_option
from core.reported_sync import build_reported_proposals
from core.reported_time import (
    REPORTED_STATES,
    ReportedTimeRecord,
    append_record,
    query,
    reported_hours_by_project_day,
)

reported_app = typer.Typer(
    help="Review observed time into confirmed reported time, or add manual time.",
    no_args_is_help=True,
)
app.add_typer(reported_app, name="reported")


def _run_report(**flags):
    from core.report_service import run_timelog_report

    options = TimelogRunOptions(
        projects_config=flags.pop("projects_config"),
        output_format="json",
        screen_time="off",
        quiet=True,
        include_uncategorized=True,
        **flags,
    )
    return run_timelog_report(options.projects_config, options.date_from, options.date_to, options)


@reported_app.command("review")
def reported_review(
    date_from: Annotated[Optional[datetime], typer.Option("--from", formats=["%Y-%m-%d"])] = None,
    date_to: Annotated[Optional[datetime], typer.Option("--to", formats=["%Y-%m-%d"])] = None,
    today: Annotated[bool, typer.Option(help="Limit to today.")] = False,
    yesterday: Annotated[bool, typer.Option(help="Limit to yesterday.")] = False,
    last_week: Annotated[bool, typer.Option(help="Limit to last 7 days.")] = False,
    last_month: Annotated[bool, typer.Option(help="Limit to last 30 days.")] = False,
    projects_config: Annotated[str, typer.Option(help="JSON config file")] = default_projects_config_option(),
    dry_run: Annotated[bool, typer.Option(help="Preview proposals; write nothing.")] = False,
):
    """Confirm / edit / dismiss observed time into reported_time records."""
    report = _run_report(
        date_from=date_from.strftime("%Y-%m-%d") if date_from else None,
        date_to=date_to.strftime("%Y-%m-%d") if date_to else None,
        today=today, yesterday=yesterday, last_week=last_week, last_month=last_month,
        projects_config=projects_config,
    )
    proposals = build_reported_proposals(report)
    if not proposals:
        typer.echo("No observed time to review for this period.")
        return

    confirmed = edited = dismissed = skipped = already = 0
    for rec in proposals:
        if query(project=rec.project, date=rec.date, states=REPORTED_STATES):
            already += 1
            continue
        typer.echo(f"{rec.date}  {rec.project}  {rec.hours:.2f}h  (observed)")
        if dry_run:
            skipped += 1
            continue
        choice = (typer.prompt("[c]onfirm / [e]dit hours / [d]ismiss / [s]kip", default="s") or "s").strip().lower()
        if choice == "c":
            append_record(_with(rec, state="confirmed"))
            confirmed += 1
        elif choice == "e":
            new_hours = float(typer.prompt("hours", default=rec.hours))
            append_record(_with(rec, state="edited", hours=new_hours, edited_from_hours=rec.hours))
            edited += 1
        elif choice == "d":
            append_record(_with(rec, state="dismissed"))
            dismissed += 1
        else:
            skipped += 1

    typer.echo(
        f"Reported review: confirmed={confirmed}, edited={edited}, dismissed={dismissed}, "
        f"already={already}, skipped={skipped}"
    )


def _with(rec: ReportedTimeRecord, **changes) -> ReportedTimeRecord:
    return ReportedTimeRecord(
        date=changes.get("date", rec.date),
        project=changes.get("project", rec.project),
        hours=changes.get("hours", rec.hours),
        source=rec.source,
        state=changes["state"],
        origin_ref=list(rec.origin_ref),
        note=rec.note,
        edited_from_hours=changes.get("edited_from_hours"),
    )


@reported_app.command("add")
def reported_add(
    project: Annotated[str, typer.Option(help="Project/customer name.")],
    date: Annotated[datetime, typer.Option("--date", formats=["%Y-%m-%d"], help="YYYY-MM-DD")],
    hours: Annotated[float, typer.Option(help="Hours worked.")],
    note: Annotated[str, typer.Option(help="What the time was (required — no silent time).")],
):
    """Add net-new manual time gittan never observed (SFTP, mail, meetings)."""
    if not note.strip():
        raise typer.BadParameter("A note is required for manual reported time.")
    if hours <= 0:
        raise typer.BadParameter("Hours must be greater than 0.")
    rec = ReportedTimeRecord(
        date=date.strftime("%Y-%m-%d"), project=project, hours=hours,
        source="manual", state="confirmed", note=note.strip(),
    )
    append_record(rec)
    typer.echo(f"Added manual reported time: {rec.date} {project} {hours:.2f}h — {note.strip()}")


@reported_app.command("list")
def reported_list():
    """Show confirmed reported hours per project + day."""
    totals = reported_hours_by_project_day()
    if not totals:
        typer.echo("No confirmed reported time yet. Use `gittan reported review` or `add`.")
        return
    for (project, day) in sorted(totals):
        typer.echo(f"{day}  {project}  {totals[(project, day)]:.2f}h")
