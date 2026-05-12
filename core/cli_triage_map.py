"""URL-first triage mapping flow with candidate table + editable decisions."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Annotated, Optional

import questionary
import typer
from questionary import Choice
from rich.console import Console
from rich.table import Table

from core.cli_app import app
from core.cli_date_range import resolve_date_window
from core.cli_triage import build_triage_plan_dict, load_triage_profiles
from core.cli_triage_apply import apply_triage_decisions_payload
from core.cli_triage_map_candidates import (
    UNCATEGORIZED,
    UrlCandidate,
    _auto_assign_high,
    build_url_candidates_from_gap_days,
)
from core.config import resolve_projects_config_path


def _render_candidates_table(console: Console, rows: list[UrlCandidate]) -> None:
    table = Table(title="URL candidates (Uncategorized)")
    table.add_column("Title", overflow="fold")
    table.add_column("URL key", overflow="fold")
    table.add_column("Suggested")
    table.add_column("Confidence")
    table.add_column("Impact (h)", justify="right")
    table.add_column("Events", justify="right")
    table.add_column("Days", justify="right")
    table.add_column("Last seen")
    for row in rows:
        table.add_row(
            row.title,
            row.url_key,
            row.suggested_project,
            f"{row.confidence_label} ({row.confidence_score:.0%})",
            f"{row.impact_hours:.1f}",
            str(row.events),
            str(row.days),
            row.last_seen,
        )
    console.print(table)


def _render_candidates_table_with_title(console: Console, rows: list[UrlCandidate], title: str) -> None:
    table = Table(title=title)
    table.add_column("Title", overflow="fold")
    table.add_column("URL key", overflow="fold")
    table.add_column("Suggested")
    table.add_column("Confidence")
    table.add_column("Impact (h)", justify="right")
    table.add_column("Events", justify="right")
    table.add_column("Days", justify="right")
    table.add_column("Last seen")
    for row in rows:
        table.add_row(
            row.title,
            row.url_key,
            row.suggested_project,
            f"{row.confidence_label} ({row.confidence_score:.0%})",
            f"{row.impact_hours:.1f}",
            str(row.events),
            str(row.days),
            row.last_seen,
        )
    console.print(table)


def _row_edit_label(row: UrlCandidate, selected_project: str | None) -> str:
    assigned = selected_project or "Skip"
    return (
        f"{row.title} | {row.url_key} | conf={row.confidence_label} {row.confidence_score:.0%} "
        f"| impact={row.impact_hours:.1f}h | events={row.events} | assign={assigned}"
    )


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
    max_rows: Annotated[int, typer.Option(help="Maximum URL candidate rows")] = 50,
    min_events: Annotated[int, typer.Option(help="Minimum events per URL key")] = 2,
    include_low_signal: Annotated[bool, typer.Option(help="Include low-signal/noise URL keys for debugging")] = False,
    max_days: Annotated[int, typer.Option(help="Top unexplained days to source Chrome evidence from")] = 7,
    auto_high: Annotated[bool, typer.Option(help="Auto-propose high-confidence rows first")] = True,
) -> None:
    """Map URL-level candidates to projects across a date range."""
    console = Console()
    date_from_s, date_to_s = resolve_date_window(
        date_from=date_from,
        date_to=date_to,
        today=today,
        yesterday=yesterday,
        last_3_days=last_3_days,
        last_week=last_week,
        last_14_days=last_14_days,
        last_month=last_month,
        fallback_recent_days=7,
    )
    resolved_projects_config = str(Path(projects_config).expanduser()) if projects_config else str(resolve_projects_config_path())
    profiles = load_triage_profiles(resolved_projects_config)
    project_names = sorted({str(p.get("name", "")).strip() for p in profiles if str(p.get("name", "")).strip()})
    plan = build_triage_plan_dict(
        date_from=date_from_s,
        date_to=date_to_s,
        projects_config=resolved_projects_config,
        max_days=max(1, int(max_days)),
        max_sites=5,
        scoring_mode="site-first",
        include_sample_title=True,
    )
    day_unexplained_hours = {
        str(d.get("day", "")).strip(): float((d.get("gap") or {}).get("unexplained_screen_time_hours", 0.0) or 0.0)
        for d in plan.get("days", [])
        if str(d.get("day", "")).strip()
    }
    rows = build_url_candidates_from_gap_days(
        day_unexplained_hours=day_unexplained_hours,
        profiles=profiles,
        max_rows=max_rows,
        min_events=min_events,
        include_low_signal=include_low_signal,
    )
    if not rows:
        console.print("[green]No URL candidates found in this range (gap-day Chrome evidence).[/green]")
        raise typer.Exit(code=0)

    _render_candidates_table(console, rows)
    assignment_by_key: dict[str, str | None] = {}
    for row in rows:
        default_project = row.suggested_project if row.suggested_project in project_names else None
        assignment_by_key[row.url_key] = default_project

    auto_assigned: dict[str, str] = {}
    allowed_project_names = set(project_names)
    if auto_high:
        choice = questionary.select(
            "Bulk apply suggestion",
            choices=[
                Choice(title="Only high confidence", value="high"),
                Choice(title="High and medium confidence", value="high_medium"),
                Choice(title="Everything looks correct", value="all"),
                Choice(title="Skip bulk apply (manual only)", value="none"),
            ],
            default="high",
        ).ask()
        if choice is None:
            console.print("[yellow]Cancelled before writing config.[/yellow]")
            raise typer.Exit(code=0)

        if choice == "high":
            auto_assigned = dict(_auto_assign_high(rows, project_names))
        elif choice == "high_medium":
            for row in rows:
                if row.confidence_label not in {"high", "medium"}:
                    continue
                suggested = str(row.suggested_project or "").strip()
                if not suggested or suggested == UNCATEGORIZED or suggested not in allowed_project_names:
                    continue
                auto_assigned[row.url_key] = suggested
        elif choice == "all":
            for row in rows:
                suggested = str(row.suggested_project or "").strip()
                if not suggested or suggested == UNCATEGORIZED or suggested not in allowed_project_names:
                    continue
                auto_assigned[row.url_key] = suggested

        if auto_assigned:
            console.print(
                f"[bold]Proposal:[/bold] assign {len(auto_assigned)} rows from bulk selection; "
                f"{len(rows) - len(auto_assigned)} rows remain for optional manual review."
            )
            for key, project_name in auto_assigned.items():
                assignment_by_key[key] = project_name
            chosen_rows = [row for row in rows if row.url_key in auto_assigned]
            _render_candidates_table_with_title(
                console,
                chosen_rows,
                f"Bulk-selected rows ({len(chosen_rows)})",
            )

    review_more = questionary.confirm("Review/edit remaining rows manually before apply?", default=False).ask()
    if review_more is None:
        console.print("[yellow]Cancelled before writing config.[/yellow]")
        raise typer.Exit(code=0)
    if review_more:
        review_rows = [row for row in rows if row.url_key not in auto_assigned]
        if not review_rows:
            console.print("[green]No remaining rows to review manually.[/green]")
            review_rows = []
        else:
            _render_candidates_table_with_title(
                console,
                review_rows,
                f"Round 2: Remaining rows for manual review ({len(review_rows)})",
            )
        while True:
            edit_choice = questionary.select(
                "Edit mappings row-by-row",
                choices=[
                    *[
                        Choice(
                            title=_row_edit_label(row, assignment_by_key.get(row.url_key)),
                            value=row.url_key,
                        )
                        for row in review_rows
                    ],
                    Choice(title="Done editing", value="__done__"),
                ],
            ).ask()
            if edit_choice is None:
                console.print("[yellow]Cancelled before writing config.[/yellow]")
                raise typer.Exit(code=0)
            if edit_choice == "__done__":
                break
            row = next((r for r in rows if r.url_key == edit_choice), None)
            if row is None:
                continue
            current = assignment_by_key.get(row.url_key)
            selected_project = questionary.select(
                f"Project for URL key '{row.url_key}'",
                choices=[*project_names, "Skip this URL key"],
                default=current if current in project_names else None,
            ).ask()
            if selected_project is None:
                console.print("[yellow]Cancelled before writing config.[/yellow]")
                raise typer.Exit(code=0)
            assignment_by_key[row.url_key] = None if selected_project == "Skip this URL key" else str(selected_project)

    decisions: list[dict[str, str]] = []
    for row in rows:
        selected_project = assignment_by_key.get(row.url_key)
        if not selected_project:
            continue
        decisions.append(
            {
                "project_name": selected_project,
                "rule_type": "tracked_urls",
                "rule_value": row.url_key,
            }
        )

    if not decisions:
        console.print("[yellow]No decisions selected. Nothing to apply.[/yellow]")
        raise typer.Exit(code=0)

    preview = apply_triage_decisions_payload(
        decisions=decisions,
        projects_config=resolved_projects_config,
        allow_create=False,
        dry_run=True,
        interactive_review=False,
    )
    if preview.get("errors"):
        console.print(preview)
        raise typer.Exit(code=1)
    console.print(preview.get("preview", "No preview available."))
    confirmed = questionary.confirm("Apply these URL mappings now?", default=False).ask()
    if not confirmed:
        console.print("[yellow]Cancelled before writing config.[/yellow]")
        raise typer.Exit(code=0)

    applied = apply_triage_decisions_payload(
        decisions=decisions,
        projects_config=resolved_projects_config,
        allow_create=False,
        dry_run=False,
        interactive_review=False,
    )
    if applied.get("errors"):
        console.print(applied)
        raise typer.Exit(code=1)
    console.print("[green]URL mapping apply complete.[/green]")
