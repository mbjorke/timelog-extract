"""Typer command: guided uncategorized review."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Optional

import questionary
import typer

from core.cli_app import app
from core.cli_options import TimelogRunOptions
from core.cli_prompts import prompt_for_timeframe
from core.config import (
    apply_rule_to_project,
    load_projects_config_payload,
    save_projects_config_payload,
)
from core.uncategorized_review import build_uncategorized_clusters


@app.command()
def review(
    date_from: Annotated[Optional[str], typer.Option("--from", help="Start date (YYYY-MM-DD)")] = None,
    date_to: Annotated[Optional[str], typer.Option("--to", help="End date (YYYY-MM-DD)")] = None,
    today: Annotated[bool, typer.Option(help="Limit to today.")] = False,
    yesterday: Annotated[bool, typer.Option(help="Limit to yesterday.")] = False,
    last_3_days: Annotated[bool, typer.Option(help="Limit to last 3 days.")] = False,
    last_week: Annotated[bool, typer.Option(help="Limit to last 7 days.")] = False,
    last_14_days: Annotated[bool, typer.Option(help="Limit to last 14 days.")] = False,
    last_month: Annotated[bool, typer.Option(help="Limit to last 30 days.")] = False,
    uncategorized: Annotated[bool, typer.Option(help="Review uncategorized activity clusters.")] = True,
    projects_config: Annotated[str, typer.Option(help="JSON config file")] = "timelog_projects.json",
    max_clusters: Annotated[int, typer.Option(help="Max clusters to review")] = 20,
    samples_per_cluster: Annotated[int, typer.Option(help="Sample events shown per cluster")] = 4,
):
    """Guided review loop for uncategorized activity."""
    from rich.console import Console
    from core.report_service import run_timelog_report

    console = Console()
    if not uncategorized:
        console.print("[yellow]Only uncategorized review is supported in this command for now.[/yellow]")
        raise typer.Exit(code=0)

    if not (today or yesterday or last_3_days or last_week or last_14_days or last_month or date_from or date_to):
        picked = prompt_for_timeframe()
        today = picked.get("today", False)
        yesterday = picked.get("yesterday", False)
        last_3_days = picked.get("last_3_days", False)
        last_week = picked.get("last_week", False)
        last_14_days = picked.get("last_14_days", False)
        last_month = picked.get("last_month", False)
        date_from = picked.get("date_from")
        date_to = picked.get("date_to")

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
    uncategorized_events = [event for event in report.included_events if event.get("project") == "Uncategorized"]
    if not uncategorized_events:
        console.print("[green]No uncategorized events found in selected range.[/green]")
        return

    clusters = build_uncategorized_clusters(
        uncategorized_events,
        max_clusters=max_clusters,
        samples_per_cluster=samples_per_cluster,
    )
    if not clusters:
        console.print("[yellow]No actionable clusters found. Try a wider range.[/yellow]")
        return

    config_path = Path(projects_config)
    payload = load_projects_config_payload(config_path)
    console.print(
        f"[bold]Guided review[/bold] | uncategorized events: {len(uncategorized_events)} | clusters: {len(clusters)}"
    )

    for index, cluster in enumerate(clusters, start=1):
        remaining = len(clusters) - index
        console.print(
            f"\n[bold]Cluster {index}/{len(clusters)}[/bold] [{cluster.source}] "
            f"{cluster.rule_type}={cluster.rule_value!r} ({cluster.count} events, remaining {remaining})"
        )
        for sample in cluster.samples:
            console.print(f"- {sample}")

        action = questionary.select(
            "Action",
            choices=[
                "Assign to existing project",
                "Create new project",
                "Skip",
                "Quit",
            ],
        ).ask()
        if not action or action == "Quit":
            break
        if action == "Skip":
            continue

        project_names = [str(project.get("name", "")).strip() for project in payload.get("projects", []) if project.get("name")]
        project_name = ""
        if action == "Assign to existing project":
            if not project_names:
                console.print("[yellow]No existing projects found; skipping this cluster.[/yellow]")
                continue
            project_name = questionary.select("Target project:", choices=sorted(project_names)).ask() or ""
        else:
            project_name = questionary.text("New project name:").ask() or ""
        if not project_name.strip():
            console.print("[yellow]No project selected; cluster skipped.[/yellow]")
            continue

        rule_value = questionary.text(
            f"{cluster.rule_type} value to save:",
            default=cluster.rule_value,
        ).ask()
        if rule_value is None or not rule_value.strip():
            console.print("[yellow]No rule value entered; cluster skipped.[/yellow]")
            continue

        field, value, created = apply_rule_to_project(
            payload,
            project_name=project_name,
            rule_type=cluster.rule_type,
            rule_value=rule_value,
        )
        save_projects_config_payload(config_path, payload)
        created_note = " (created project)" if created else ""
        console.print(f"[green]Saved[/green] {field} -> {value!r} for {project_name!r}{created_note}.")
