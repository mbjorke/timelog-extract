"""Typer command: guided day-level gap triage."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Optional

import questionary
import typer

from core.cli_app import app
from core.cli_options import TimelogRunOptions
from core.config import as_list
from core.report_service import run_timelog_report
from core.calibration.screen_time_gap import analyze_screen_time_gaps
from scripts.calibration.gap_day_triage import (
    DayTopSite,
    apply_domain_mappings,
    fetch_chrome_rows_for_day,
    load_profiles_for_projects_config,
    score_projects_for_sites,
    summarize_day_sites,
)


def select_triage_days(payload: dict, *, max_days: int) -> list[dict]:
    rows = [
        row
        for row in payload.get("days", [])
        if float(row.get("unexplained_screen_time_hours", 0.0)) > 0
    ]
    rows.sort(
        key=lambda row: float(row.get("unexplained_screen_time_hours", 0.0)),
        reverse=True,
    )
    return rows[: max(1, int(max_days))]


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
):
    """Guided loop: confirm/correct project mapping on top unexplained days."""
    from rich.console import Console

    console = Console()
    if scoring_mode not in {"balanced", "site-first"}:
        console.print(f"[red]Invalid --scoring-mode:[/red] {scoring_mode!r} (use balanced or site-first)")
        raise typer.Exit(code=1)
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


