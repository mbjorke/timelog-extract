"""Typer command: guided day-level gap triage."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any, Optional

import questionary
import typer

from core.cli_app import app
from core.cli_options import TimelogRunOptions
from core.config import as_list
from core.calibration.screen_time_gap import analyze_screen_time_gaps
from scripts.calibration.gap_day_triage import (
    DayTopSite,
    ProjectSuggestion,
    apply_domain_mappings,
    fetch_chrome_rows_for_day,
    load_profiles_for_projects_config,
    score_projects_for_sites,
    summarize_day_sites,
)

AGENT_TRIAGE_SCHEMA_VERSION = 1

NOTES_FOR_AGENTS = [
    "JSON mode omits Chrome page titles to reduce accidental PII in logs; domains and counts remain.",
    "Primary mapping signal is tracked_urls / site-first scoring; match_terms is secondary.",
    "Use --json for plans only; --yes applies mappings. Never pipe --json output back into config blindly.",
]


def _site_to_plan_dict(site: DayTopSite) -> dict[str, Any]:
    return {
        "domain": site.domain,
        "visits": site.visits,
        "share": round(float(site.share), 6),
    }


def _suggestion_to_plan_dict(s: ProjectSuggestion, tags: list[str]) -> dict[str, Any]:
    return {
        "canonical": s.canonical,
        "score": s.score,
        "aliases": list(s.aliases),
        "explicit_domain_hits": s.explicit_domain_hits,
        "term_hits": s.term_hits,
        "alias_or_name_hits": s.alias_or_name_hits,
        "ticket_mode": s.ticket_mode,
        "default_client": s.default_client,
        "tags": tags,
    }


def _build_choices(
    suggestions: list[ProjectSuggestion],
    tags_by_canonical: dict[str, list[str]],
    max_choices: int = 3,
) -> list[dict[str, Any]]:
    choices: list[dict[str, Any]] = []
    for s in suggestions[: max(0, max_choices - 1)]:
        tags = tags_by_canonical.get(s.canonical, [])
        tag_prefix = f"#PROJ-{tags[0].upper()} · " if tags else "#PROJ · "
        choices.append({"canonical": s.canonical, "tags": tags, "label": f"{tag_prefix}{s.canonical}"})
    choices.append({"canonical": None, "tags": [], "label": "None of these / skip"})
    return choices


def _build_question(gap: dict[str, Any], suggestions: list[ProjectSuggestion]) -> Optional[str]:
    hours = float(gap.get("unexplained_screen_time_hours", 0.0))
    day = gap.get("day", "?")
    if not suggestions:
        return None
    if len(suggestions) == 1:
        return f"Does this {hours:.1f}h on {day} belong to {suggestions[0].canonical}?"
    return f"Does this {hours:.1f}h on {day} belong to {suggestions[0].canonical} or {suggestions[1].canonical}?"


def _yes_automation_plan(
    *,
    suggestions: list[ProjectSuggestion],
    profiles: list[dict],
    all_names: list[str],
    top_sites: list[DayTopSite],
) -> dict[str, Any]:
    if not suggestions:
        return {"would_apply": False, "reason": "no_suggestions"}
    suggested_project = resolve_target_project_name(profiles, suggestions[0].canonical)
    if suggested_project not in all_names:
        return {
            "would_apply": False,
            "reason": "suggested_project_not_in_config",
            "suggested_project": suggested_project,
        }
    return {
        "would_apply": True,
        "target_project": suggested_project,
        "domains": [site.domain for site in top_sites[:2]],
    }


def build_triage_plan_dict(
    *,
    date_from: Optional[str],
    date_to: Optional[str],
    projects_config: str,
    max_days: int,
    max_sites: int,
    scoring_mode: str,
    home: Optional[Path] = None,
) -> dict[str, Any]:
    """Assemble the read-only triage plan (same inputs as the CLI). Intended for --json and tests."""
    from core.report_service import run_timelog_report

    root_home = home if home is not None else Path.home()
    options = TimelogRunOptions(
        date_from=date_from,
        date_to=date_to,
        projects_config=projects_config,
        include_uncategorized=True,
        quiet=True,
        screen_time="on",
    )
    report = run_timelog_report(options.projects_config, options.date_from, options.date_to, options)
    payload = analyze_screen_time_gaps(report)
    day_rows = select_triage_days(payload, max_days=max_days)
    profiles = load_profiles_for_projects_config(projects_config)
    all_names = sorted(
        {
            str(profile.get("name", "")).strip()
            for profile in profiles
            if str(profile.get("name", "")).strip()
        }
    )
    tags_by_canonical: dict[str, list[str]] = {}
    for p in profiles:
        c = str(p.get("canonical_project", p.get("name", ""))).strip()
        for tag in p.get("tags", []):
            if tag not in tags_by_canonical.get(c, []):
                tags_by_canonical.setdefault(c, []).append(tag)
    out_days: list[dict[str, Any]] = []
    empty_reason: Optional[str] = None
    if not day_rows:
        empty_reason = "no_unexplained_days"

    for row in day_rows:
        day = str(row.get("day"))
        top_sites = summarize_day_sites(
            fetch_chrome_rows_for_day(day, home=root_home),
            limit=max_sites,
        )
        suggestions = score_projects_for_sites(profiles, top_sites, scoring_mode=scoring_mode)
        skip_reason: Optional[str] = None
        if not top_sites:
            skip_reason = "no_chrome_sites"
        elif not suggestions:
            skip_reason = "no_suggestions"

        resolved: Optional[str] = None
        resolved_ok: Optional[bool] = None
        yes_automation: dict[str, Any]
        if suggestions:
            resolved = resolve_target_project_name(profiles, suggestions[0].canonical)
            resolved_ok = resolved in all_names
            yes_automation = _yes_automation_plan(
                suggestions=suggestions,
                profiles=profiles,
                all_names=all_names,
                top_sites=top_sites,
            )
        else:
            yes_automation = {"would_apply": False, "reason": "no_suggestions"}

        gap_data = {
            "estimated_hours": float(row.get("estimated_hours", 0.0)),
            "screen_time_hours": float(row.get("screen_time_hours", 0.0)),
            "unexplained_screen_time_hours": float(row.get("unexplained_screen_time_hours", 0.0)),
        }
        out_days.append(
            {
                "day": day,
                "gap": gap_data,
                "top_sites": [_site_to_plan_dict(s) for s in top_sites],
                "suggestions": [
                    _suggestion_to_plan_dict(s, tags_by_canonical.get(s.canonical, []))
                    for s in suggestions
                ],
                "question": _build_question({**gap_data, "day": day}, suggestions),
                "choices": _build_choices(suggestions, tags_by_canonical),
                "resolved_project_for_top_suggestion": resolved,
                "resolved_in_config": resolved_ok,
                "yes_automation": yes_automation,
                "skip_reason": skip_reason,
            }
        )

    return {
        "schema_version": AGENT_TRIAGE_SCHEMA_VERSION,
        "command": "gittan triage",
        "options": {
            "date_from": date_from,
            "date_to": date_to,
            "projects_config": projects_config,
            "max_days": int(max_days),
            "max_sites": int(max_sites),
            "scoring_mode": scoring_mode,
        },
        "project_names": all_names,
        "empty_reason": empty_reason,
        "days": out_days,
        "notes_for_agents": list(NOTES_FOR_AGENTS),
    }


def select_triage_days(payload: dict, *, max_days: int) -> list[dict]:
    if int(max_days) < 1:
        raise ValueError(f"max_days must be at least 1, got {max_days}")
    rows = [
        row
        for row in payload.get("days", [])
        if float(row.get("unexplained_screen_time_hours", 0.0)) > 0
    ]
    rows.sort(
        key=lambda row: float(row.get("unexplained_screen_time_hours", 0.0)),
        reverse=True,
    )
    return rows[: int(max_days)]


def resolve_target_project_name(profiles: list[dict], canonical: str) -> str:
    clean = canonical.strip().lower()
    for profile in profiles:
        name = str(profile.get("name", "")).strip()
        if name.lower() == clean:
            return name
    for profile in profiles:
        if str(profile.get("canonical_project", "")).strip().lower() == clean:
            return str(profile.get("name", "")).strip()
    return canonical


def _render_day_summary(row: dict, top_sites: list[DayTopSite]) -> str:
    lines = [
        f"Day: {row.get('day')}",
        f"  Estimated: {float(row.get('estimated_hours', 0.0)):.2f}h",
        f"  Screen: {float(row.get('screen_time_hours', 0.0)):.2f}h",
        f"  Unexplained: {float(row.get('unexplained_screen_time_hours', 0.0)):.2f}h",
        "  Top sites:",
    ]
    for site in top_sites:
        lines.append(f"    - {site.domain} ({site.visits} visits)")
    return "\n".join(lines)


@app.command("triage")
def triage(
    date_from: Annotated[Optional[str], typer.Option("--from", help="Start date (YYYY-MM-DD)")] = None,
    date_to: Annotated[Optional[str], typer.Option("--to", help="End date (YYYY-MM-DD)")] = None,
    projects_config: Annotated[str, typer.Option(help="JSON config file")] = "timelog_projects.json",
    max_days: Annotated[int, typer.Option(help="Max unexplained days to review")] = 3,
    max_sites: Annotated[int, typer.Option(help="Top sites shown/mappable per day")] = 5,
    scoring_mode: Annotated[str, typer.Option(help="balanced or site-first")] = "site-first",
    yes: Annotated[bool, typer.Option(help="Auto-accept top suggestion and top 2 domains")] = False,
    json_out: Annotated[
        bool,
        typer.Option("--json", help="Print read-only JSON plan to stdout; never writes config"),
    ] = False,
):
    """Guided loop: confirm/correct project mapping on top unexplained days."""
    from rich.console import Console

    # Deferred import: core.report_service imports core.cli, which loads this module first.
    from core.report_service import run_timelog_report

    console = Console()
    if json_out and yes:
        console.print("[red]Cannot combine --json with --yes.[/red] Use --json alone for a read-only plan.")
        raise typer.Exit(code=1)
    if scoring_mode not in {"balanced", "site-first"}:
        console.print(f"[red]Invalid --scoring-mode:[/red] {scoring_mode!r} (use balanced or site-first)")
        raise typer.Exit(code=1)
    if int(max_days) < 1:
        console.print(f"[red]Invalid --max-days:[/red] must be at least 1, got {max_days}")
        raise typer.Exit(code=1)
    if json_out:
        plan = build_triage_plan_dict(
            date_from=date_from,
            date_to=date_to,
            projects_config=projects_config,
            max_days=max_days,
            max_sites=max_sites,
            scoring_mode=scoring_mode,
        )
        print(json.dumps(plan, indent=2, ensure_ascii=False))
        raise typer.Exit(code=0)

    options = TimelogRunOptions(
        date_from=date_from,
        date_to=date_to,
        projects_config=projects_config,
        include_uncategorized=True,
        quiet=True,
        screen_time="on",
    )
    report = run_timelog_report(options.projects_config, options.date_from, options.date_to, options)
    payload = analyze_screen_time_gaps(report)
    days = select_triage_days(payload, max_days=max_days)
    if not days:
        console.print("[green]No unexplained days to triage in this range.[/green]")
        raise typer.Exit(code=0)

    profiles = load_profiles_for_projects_config(projects_config)
    all_names = sorted(
        {
            str(profile.get("name", "")).strip()
            for profile in profiles
            if str(profile.get("name", "")).strip()
        }
    )
    applied_total = 0
    for row in days:
        day = str(row.get("day"))
        top_sites = summarize_day_sites(fetch_chrome_rows_for_day(day, home=Path.home()), limit=max_sites)
        suggestions = score_projects_for_sites(profiles, top_sites, scoring_mode=scoring_mode)
        console.print("")
        console.print(_render_day_summary(row, top_sites))
        if not top_sites:
            continue
        if not suggestions:
            console.print("[yellow]No project suggestions found; skipping day.[/yellow]")
            continue
        suggested_project = resolve_target_project_name(profiles, suggestions[0].canonical)
        if yes:
            target = suggested_project
            if target not in all_names:
                console.print(f"[yellow]Skipping {day}: suggested project '{target}' not found in config[/yellow]")
                continue
            selected_domains = [site.domain for site in top_sites[:2]]
        else:
            project_choice = questionary.select(
                f"{day}: choose project",
                choices=[*all_names, "Skip day"],
                default=suggested_project if suggested_project in all_names else None,
            ).ask()
            if not project_choice or project_choice == "Skip day":
                continue
            target = project_choice
            selected_domains = questionary.checkbox(
                f"{day}: pick domains to map to '{target}'",
                choices=[site.domain for site in top_sites],
                validate=lambda value: True if value else "Select at least one domain or skip day.",
            ).ask()
            if not selected_domains:
                continue
        assignments = [(domain, target) for domain in as_list(selected_domains)]
        if not assignments:
            continue
        applied, _created = apply_domain_mappings(
            Path(projects_config),
            assignments,
            allow_create_projects=False,
        )
        applied_total += applied
        console.print(f"[green]Applied[/green] {applied} mapping(s) for {day} -> {target}")
        profiles = load_profiles_for_projects_config(projects_config)
    console.print(f"\n[bold]Triage complete.[/bold] applied mappings: {applied_total}")

