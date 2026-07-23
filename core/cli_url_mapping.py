"""Interactive URL → project mapping (`gittan review`, legacy `gittan triage-map`)."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

import questionary
import typer
from questionary import Choice
from rich import box
from rich.console import Console
from rich.table import Table

from core.anchor_nudge import should_prompt
from core.cli_date_range import resolve_date_window
from core.cli_review_create_project import (
    create_choice_label,
    create_project_interactive,
    is_decidable_candidate,
    park_choice_label,
    partition_candidates,
    propose_create_from_candidate,
    skip_choice_label,
)
from core.cli_triage import load_triage_profiles
from core.cli_triage_apply import apply_triage_decisions_payload
from core.cli_triage_map_candidates import UNCATEGORIZED, UrlCandidate, _auto_assign_high
from core.cli_triage_map_context import build_triage_map_json_payload, load_triage_map_candidates
from core.config import resolve_projects_config_path
from core.onboarding_guidance import finish_review_guidance
from outputs.terminal_theme import (
    CLR_GREEN,
    CLR_VALUE_ORANGE,
    STYLE_BORDER,
    STYLE_DIM,
    STYLE_LABEL,
    STYLE_MUTED,
)


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
    table = Table(title=title, box=box.ROUNDED)
    table.border_style = STYLE_BORDER
    table.header_style = f"bold {STYLE_LABEL}"
    table.add_column("Title", overflow="fold", style=STYLE_LABEL)
    table.add_column("URL key", overflow="fold", style=STYLE_MUTED)
    table.add_column("Suggested", style=STYLE_LABEL)
    table.add_column("Confidence", style=STYLE_MUTED)
    table.add_column("Impact (h)", justify="right", style=CLR_VALUE_ORANGE)
    table.add_column("Events", justify="right", style=STYLE_MUTED)
    table.add_column("Days", justify="right", style=STYLE_DIM)
    table.add_column("Last seen", style=STYLE_DIM)
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
    create_hint = ""
    if is_decidable_candidate(row) and propose_create_from_candidate(row) is not None:
        create_hint = " · creatable"
    return (
        f"{row.title} | {row.url_key} | conf={row.confidence_label} {row.confidence_score:.0%} "
        f"| events={row.events} | assign={assigned}{create_hint}"
    )


def _project_choices_for_row(
    row: UrlCandidate,
    *,
    project_names: list[str],
) -> list[str]:
    """Decidable rows may create; bare UUID / undecidable → Park or Skip only."""
    skip = skip_choice_label()
    if is_decidable_candidate(row) and propose_create_from_candidate(row) is not None:
        return [*project_names, create_choice_label(), skip]
    return [*project_names, park_choice_label(), skip]


def _prompt_project_for_row(
    console: Console,
    row: UrlCandidate,
    *,
    project_names: list[str],
    allowed_project_names: set[str],
    projects_config: str,
    current: str | None,
) -> tuple[str | None, list[str], set[str]]:
    """Return (assignment, updated project_names, updated allowed set).

    Create writes config immediately. Park/Skip → None assignment.
    """
    suggested_default = (
        row.suggested_project
        if row.suggested_project in allowed_project_names and row.suggested_project != UNCATEGORIZED
        else None
    )
    choices = _project_choices_for_row(row, project_names=project_names)
    default = current if current in project_names else suggested_default
    if default not in choices:
        default = None
    selected = questionary.select(
        f"Project for URL key '{row.url_key}'",
        choices=choices,
        default=default,
    ).ask()
    if selected is None:
        return "__cancel__", project_names, allowed_project_names
    if selected in {skip_choice_label(), park_choice_label()}:
        return None, project_names, allowed_project_names
    if selected == create_choice_label():
        created = create_project_interactive(
            console,
            row,
            projects_config=projects_config,
            existing_names=allowed_project_names,
        )
        if created is None:
            return current, project_names, allowed_project_names
        name = created.project_name
        if name not in project_names:
            project_names = sorted({*project_names, name})
        allowed_project_names = set(allowed_project_names) | {name}
        # tracked_urls already written; no deferred decision needed.
        return "__created__", project_names, allowed_project_names
    return str(selected), project_names, allowed_project_names


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

    # Interactive mapping needs a real terminal for the questionary prompts.
    # Check before the expensive candidate load (which runs a report), and use
    # the repo's shared gate (stdin AND stdout, exception-safe) so a redirected
    # stdout or a closed fd exits cleanly instead of crashing mid-prompt.
    if not json_out and not should_prompt():
        console.print(
            f"[{CLR_VALUE_ORANGE}]`gittan review` needs an interactive terminal to map URLs. "
            f"Use [bold]gittan review --json[/bold] for a machine-readable plan.[/{CLR_VALUE_ORANGE}]"
        )
        raise typer.Exit(code=1)

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
        console.print(f"[{CLR_GREEN}]No URL candidates found in this range (gap-day Chrome evidence).[/{CLR_GREEN}]")
        _exit_url_mapping_review(console, projects_config=resolved_projects_config, has_candidates=False)

    decidable_rows, parked_rows = partition_candidates(rows)
    if decidable_rows:
        _render_candidates_table(
            console,
            decidable_rows,
            title=f"URL candidates — decidable ({len(decidable_rows)})",
        )
    if parked_rows:
        _render_candidates_table(
            console,
            parked_rows,
            title=f"Not enough evidence to attribute — Park/Skip only ({len(parked_rows)})",
        )
        console.print(
            f"[{STYLE_DIM}]Bare UUID / untitled hosts stay out of the create queue "
            f"(decidability ≠ impact).[/{STYLE_DIM}]"
        )

    # Manual review + bulk apply operate on decidable rows; parked stay Skip.
    review_pool = decidable_rows
    assignment_by_key: dict[str, str | None] = {row.url_key: None for row in rows}
    created_keys: set[str] = set()
    allowed_project_names = set(project_names)
    auto_assigned: dict[str, str] = {}
    # Fresh config: no projects to bulk-map onto — go straight to create/manual.
    fresh_config = not project_names
    if auto_high and review_pool and not fresh_config:
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
            auto_assigned = dict(_auto_assign_high(review_pool, project_names))
        elif choice == "high_medium":
            for row in review_pool:
                if row.confidence_label not in {"high", "medium"}:
                    continue
                suggested = str(row.suggested_project or "").strip()
                if not suggested or suggested == UNCATEGORIZED or suggested not in allowed_project_names:
                    continue
                auto_assigned[row.url_key] = suggested
        elif choice == "all":
            for row in review_pool:
                suggested = str(row.suggested_project or "").strip()
                if not suggested or suggested == UNCATEGORIZED or suggested not in allowed_project_names:
                    continue
                auto_assigned[row.url_key] = suggested

        if auto_assigned:
            console.print(
                f"[bold]Proposal:[/bold] assign {len(auto_assigned)} rows from bulk selection; "
                f"{len(review_pool) - len(auto_assigned)} decidable rows remain for optional manual review."
            )
            for key, project_name in auto_assigned.items():
                assignment_by_key[key] = project_name
            chosen_rows = [row for row in review_pool if row.url_key in auto_assigned]
            _render_candidates_table(
                console,
                chosen_rows,
                title=f"Bulk-selected rows ({len(chosen_rows)})",
            )

    if fresh_config and review_pool:
        console.print(
            f"[{STYLE_MUTED}]No projects in config yet — create from decidable URL keys "
            f"or Park/Skip undecidable rows.[/{STYLE_MUTED}]"
        )
        review_more = True
    else:
        review_more = questionary.confirm(
            "Review/edit remaining rows manually before apply?",
            default=False,
        ).ask()
    if review_more is None:
        console.print(f"[{CLR_VALUE_ORANGE}]Cancelled before writing config.[/{CLR_VALUE_ORANGE}]")
        _exit_url_mapping_review(console, projects_config=resolved_projects_config, has_candidates=True)
    if review_more:
        # Include parked so operator can Park/Skip (never force create).
        review_rows = [row for row in rows if row.url_key not in auto_assigned and row.url_key not in created_keys]
        if not review_rows:
            console.print(f"[{CLR_GREEN}]No remaining rows to review manually.[/{CLR_GREEN}]")
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
            selected_project, project_names, allowed_project_names = _prompt_project_for_row(
                console,
                row,
                project_names=project_names,
                allowed_project_names=allowed_project_names,
                projects_config=resolved_projects_config,
                current=assignment_by_key.get(row.url_key),
            )
            if selected_project == "__cancel__":
                console.print(f"[{CLR_VALUE_ORANGE}]Cancelled before writing config.[/{CLR_VALUE_ORANGE}]")
                _exit_url_mapping_review(console, projects_config=resolved_projects_config, has_candidates=True)
            if selected_project == "__created__":
                created_keys.add(row.url_key)
                assignment_by_key[row.url_key] = None
                continue
            assignment_by_key[row.url_key] = selected_project

    decisions: list[dict[str, str]] = []
    for row in rows:
        if row.url_key in created_keys:
            continue
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

    if not decisions and not created_keys:
        console.print(f"[{CLR_VALUE_ORANGE}]No decisions selected. Nothing to apply.[/{CLR_VALUE_ORANGE}]")
        _exit_url_mapping_review(console, projects_config=resolved_projects_config, has_candidates=True)

    if not decisions:
        console.print(f"[{CLR_GREEN}]Create-project writes already saved; no further mappings.[/{CLR_GREEN}]")
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
    console.print(f"[{CLR_GREEN}]URL mapping apply complete.[/{CLR_GREEN}]")
    _exit_url_mapping_review(console, projects_config=resolved_projects_config, has_candidates=True)
