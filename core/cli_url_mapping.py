"""Interactive URL → project mapping (`gittan review`, legacy `gittan triage-map`)."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

import questionary
import typer
from questionary import Choice
from rich.console import Console
from rich.table import Table

from core.cli_date_range import resolve_date_window
from core.cli_triage import load_triage_profiles
from core.cli_triage_apply import apply_triage_decisions_payload
from core.cli_triage_map_candidates import UNCATEGORIZED, UrlCandidate, _auto_assign_high
from core.cli_triage_map_context import build_triage_map_json_payload, load_triage_map_candidates
from core.config import resolve_projects_config_path
from core.onboarding_guidance import finish_review_guidance
from outputs.terminal_theme import CLR_VALUE_ORANGE


def _exit_url_mapping_review(
    console: Console,
    *,
    projects_config: str,
    has_candidates: bool,
    code: int = 0,
) -> None:
    finish_review_guidance(
        console,
        projects_config=projects_config,
        has_candidates=has_candidates,
        uncategorized=False,
    )
    raise typer.Exit(code=code)


def _render_candidates_table(
    console: Console, rows: list[UrlCandidate], *, title: str = "URL candidates (Uncategorized)"
) -> None:
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


def _row_edit_label(row: UrlCandidate, selected_project: str | None, *, project_names: set[str]) -> str:
    if selected_project and selected_project in project_names:
        assigned = selected_project
    else:
        sug = (
            row.suggested_project
            if row.suggested_project in project_names and str(row.suggested_project).strip() != UNCATEGORIZED
            else None
        )
        assigned = f"Skip (suggested: {sug})" if sug else "Skip"
    return (
        f"{row.title} | {row.url_key} | conf={row.confidence_label} {row.confidence_score:.0%} "
        f"| impact={row.impact_hours:.1f}h | events={row.events} | assign={assigned}"
    )


def run_url_mapping_review(
    *,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    today: bool = False,
    yesterday: bool = False,
    last_3_days: bool = False,
    last_week: bool = False,
    last_14_days: bool = False,
    last_month: bool = False,
    projects_config: Optional[str] = None,
    max_rows: int = 50,
    min_events: int = 2,
    include_low_signal: bool = False,
    max_days: int = 7,
    auto_high: bool = True,
    json_out: bool = False,
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
    rows = load_triage_map_candidates(
        date_from=date_from_s,
        date_to=date_to_s,
        projects_config=resolved_projects_config,
        max_rows=max_rows,
        min_events=min_events,
        include_low_signal=include_low_signal,
        max_days=max_days,
    )
    if json_out:
        payload = build_triage_map_json_payload(
            date_from=date_from_s,
            date_to=date_to_s,
            projects_config=resolved_projects_config,
            rows=rows,
        )
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        raise typer.Exit(code=0)

    profiles = load_triage_profiles(resolved_projects_config)
    project_names = sorted({str(p.get("name", "")).strip() for p in profiles if str(p.get("name", "")).strip()})
    if not rows:
        console.print("[green]No URL candidates found in this range (gap-day Chrome evidence).[/green]")
        _exit_url_mapping_review(console, projects_config=resolved_projects_config, has_candidates=False)

    _render_candidates_table(console, rows)
    assignment_by_key: dict[str, str | None] = {row.url_key: None for row in rows}
    allowed_project_names = set(project_names)
    auto_assigned: dict[str, str] = {}
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
            console.print(f"[{CLR_VALUE_ORANGE}]Cancelled before writing config.[/{CLR_VALUE_ORANGE}]")
            _exit_url_mapping_review(console, projects_config=resolved_projects_config, has_candidates=True)

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
            _render_candidates_table(
                console,
                chosen_rows,
                title=f"Bulk-selected rows ({len(chosen_rows)})",
            )

    review_more = questionary.confirm("Review/edit remaining rows manually before apply?", default=False).ask()
    if review_more is None:
        console.print(f"[{CLR_VALUE_ORANGE}]Cancelled before writing config.[/{CLR_VALUE_ORANGE}]")
        _exit_url_mapping_review(console, projects_config=resolved_projects_config, has_candidates=True)
    if review_more:
        review_rows = [row for row in rows if row.url_key not in auto_assigned]
        if not review_rows:
            console.print("[green]No remaining rows to review manually.[/green]")
        else:
            _render_candidates_table(
                console,
                review_rows,
                title=f"Round 2: Remaining rows for manual review ({len(review_rows)})",
            )
        while True:
            edit_choice = questionary.select(
                "Edit mappings row-by-row",
                choices=[
                    *[
                        Choice(
                            title=_row_edit_label(row, assignment_by_key.get(row.url_key), project_names=allowed_project_names),
                            value=row.url_key,
                        )
                        for row in review_rows
                    ],
                    Choice(title="Done editing", value="__done__"),
                ],
            ).ask()
            if edit_choice is None:
                console.print(f"[{CLR_VALUE_ORANGE}]Cancelled before writing config.[/{CLR_VALUE_ORANGE}]")
                _exit_url_mapping_review(console, projects_config=resolved_projects_config, has_candidates=True)
            if edit_choice == "__done__":
                break
            row = next((r for r in rows if r.url_key == edit_choice), None)
            if row is None:
                continue
            current = assignment_by_key.get(row.url_key)
            suggested_default = (
                row.suggested_project
                if row.suggested_project in allowed_project_names and row.suggested_project != UNCATEGORIZED
                else None
            )
            selected_project = questionary.select(
                f"Project for URL key '{row.url_key}'",
                choices=[*project_names, "Skip this URL key"],
                default=current if current in project_names else suggested_default,
            ).ask()
            if selected_project is None:
                console.print(f"[{CLR_VALUE_ORANGE}]Cancelled before writing config.[/{CLR_VALUE_ORANGE}]")
                _exit_url_mapping_review(console, projects_config=resolved_projects_config, has_candidates=True)
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
        _exit_url_mapping_review(console, projects_config=resolved_projects_config, has_candidates=True)

    preview = apply_triage_decisions_payload(
        decisions=decisions,
        projects_config=resolved_projects_config,
        allow_create=False,
        dry_run=True,
        interactive_review=False,
    )
    if preview.get("errors"):
        console.print(preview)
        _exit_url_mapping_review(console, projects_config=resolved_projects_config, has_candidates=True, code=1)
    console.print(preview.get("preview", "No preview available."))
    confirmed = questionary.confirm("Apply these URL mappings now?", default=False).ask()
    if not confirmed:
        console.print(f"[{CLR_VALUE_ORANGE}]Cancelled before writing config.[/{CLR_VALUE_ORANGE}]")
        _exit_url_mapping_review(console, projects_config=resolved_projects_config, has_candidates=True)

    applied = apply_triage_decisions_payload(
        decisions=decisions,
        projects_config=resolved_projects_config,
        allow_create=False,
        dry_run=False,
        interactive_review=False,
    )
    if applied.get("errors"):
        console.print(applied)
        _exit_url_mapping_review(console, projects_config=resolved_projects_config, has_candidates=True, code=1)
    console.print("[green]URL mapping apply complete.[/green]")
    _exit_url_mapping_review(console, projects_config=resolved_projects_config, has_candidates=True)
