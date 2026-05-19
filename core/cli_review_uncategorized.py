"""Legacy uncategorized cluster loop (`gittan review --uncategorized`)."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import questionary
import typer
from rich.console import Console

from core.cli_ab_rule_suggestions import (
    UNCATEGORIZED,
    _apply_timeframe_prompt,
    _load_projects_payload,
    gather_ab_suggestions,
    persist_suggestion_state,
    print_ab_suggestion_preview,
    prompt_optional_apply,
)
from core.cli_deprecation import warn_deprecated_command
from core.cli_options import TimelogRunOptions
from core.config import apply_rule_to_project, save_projects_config_payload
from core.uncategorized_review import (
    build_uncategorized_clusters,
    count_uncategorized_noise_events,
    format_cluster_headline,
    format_cluster_rule_hint,
    format_cluster_sample,
)


def run_uncategorized_cluster_review(
    *,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    today: bool = False,
    yesterday: bool = False,
    last_3_days: bool = False,
    last_week: bool = False,
    last_14_days: bool = False,
    last_month: bool = False,
    ab_suggestions: bool = False,
    project: Optional[str] = None,
    projects_config: str,
    max_clusters: int = 20,
    samples_per_cluster: int = 4,
) -> None:
    """Advanced manual cleanup for uncategorized activity clusters."""
    from core.report_service import run_timelog_report

    warn_deprecated_command(
        "gittan review --uncategorized",
        extra="Prefer default `gittan review` (URL mapping); clusters are for rare text-token cleanup.",
    )
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
    uncategorized_events = [event for event in report.included_events if event.get("project") == UNCATEGORIZED]
    if not uncategorized_events:
        console.print("[green]No uncategorized events found in selected range.[/green]")
        return

    noise_events = count_uncategorized_noise_events(uncategorized_events)
    clusters = build_uncategorized_clusters(
        uncategorized_events,
        max_clusters=max_clusters,
        samples_per_cluster=samples_per_cluster,
    )
    if not clusters:
        if noise_events:
            console.print(
                f"[green]No actionable mapping clusters.[/green] "
                f"Filtered {noise_events} Cursor/IDE tooling events. "
                "Run [cyan]gittan review[/cyan] (default URL mapping) or widen the date range."
            )
        else:
            console.print("[yellow]No actionable clusters found. Try [cyan]gittan review[/cyan] or a wider range.[/yellow]")
        return

    config_path = Path(projects_config)
    _load_projects_payload(console, config_path)

    if ab_suggestions:
        warn_deprecated_command(
            "gittan review --ab-suggestions",
            extra="Use default `gittan review` for URL mapping.",
        )
        target_project = project or questionary.text("Target project for A/B suggestions:").ask() or ""
        target_project = target_project.strip()
        if not target_project:
            console.print("[yellow]No project name; skipping A/B suggestions.[/yellow]")
        else:
            opt_a, opt_b, prev_a, prev_b = gather_ab_suggestions(report, uncategorized_events, target_project)
            print_ab_suggestion_preview(console, target_project, opt_a, opt_b, prev_a, prev_b)
            state_path = persist_suggestion_state(
                config_path,
                target_project,
                len(uncategorized_events),
                opt_a,
                opt_b,
                prev_a,
                prev_b,
            )
            console.print(f"\n[dim]Saved suggestion state to {state_path} (deprecated apply-suggestions path).[/dim]")
            prompt_optional_apply(console, config_path, target_project, opt_a, opt_b)

    console.print(
        f"[bold]Uncategorized clusters[/bold] | {len(uncategorized_events)} events | "
        f"{noise_events} tooling-noise hidden | {len(clusters)} clusters"
    )
    console.print("[dim]Each cluster suggests match_terms or tracked_urls from log text (not URL review).[/dim]")

    payload = _load_projects_payload(console, config_path)
    project_names = sorted(
        {
            str(project.get("name", "")).strip()
            for project in payload["projects"]
            if isinstance(project, dict) and project.get("name")
        }
    )

    for index, cluster in enumerate(clusters, start=1):
        remaining = len(clusters) - index
        console.print(
            f"\n[bold]Cluster {index}/{len(clusters)}[/bold] · {cluster.source} · "
            f"{cluster.count} events · {remaining} left"
        )
        console.print(format_cluster_headline(cluster))
        console.print(f"[dim]{format_cluster_rule_hint(cluster)}[/dim]")
        for sample in cluster.samples:
            console.print(f"  · {format_cluster_sample(sample)}")

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

        project_name = ""
        if action == "Assign to existing project":
            if not project_names:
                console.print("[yellow]No existing projects found; skipping this cluster.[/yellow]")
                continue
            project_name = questionary.select("Target project:", choices=project_names).ask() or ""
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
        try:
            save_projects_config_payload(config_path, payload)
        except PermissionError as exc:
            console.print(f"[red]Error:[/red] Cannot write to config file '{config_path}' - permission denied.")
            raise typer.Exit(code=1) from exc
        except OSError as exc:
            console.print(f"[red]Error:[/red] Cannot save config file '{config_path}': {exc}")
            raise typer.Exit(code=1) from exc
        except Exception as exc:
            console.print(f"[red]Error:[/red] Failed to save config to '{config_path}': {exc}")
            raise typer.Exit(code=1) from exc
        created_note = " (created project)" if created else ""
        console.print(f"[green]Saved[/green] {field} -> {value!r} for {project_name!r}{created_note}.")
        project_names = sorted(
            {
                str(project.get("name", "")).strip()
                for project in payload["projects"]
                if isinstance(project, dict) and project.get("name")
            }
        )
