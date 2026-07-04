"""Report-gap attribution UX (`gittan review --gaps`).

Consolidates the "Uncategorized" report gap into `review`: show gap candidates
(clustered uncategorized evidence), preview which *existing* customer/project
line they would attribute to and the resulting hour impact, then apply via the
same confirmed-write path already used elsewhere (`apply_rule_to_project` +
`backup_projects_config_if_exists`).

Guard (GH-234): this surface never creates a new project profile. A gap can
only be attributed to a project that already exists in the config. If no
project fits, the operator uses `gittan map` / manual config edits — the same
existing-line-only contract as `apply_triage_decisions_payload(allow_create=False)`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

import questionary
import typer
from rich.console import Console

from core.cli_ab_rule_suggestions import _apply_timeframe_prompt
from core.cli_options import TimelogRunOptions
from core.config import (
    apply_rule_to_project,
    backup_projects_config_if_exists,
    load_projects_config_payload,
    save_projects_config_payload,
)
from core.rule_suggestions import RuleSuggestion, preview_suggestion_impact
from core.uncategorized_review import (
    build_uncategorized_clusters,
    count_uncategorized_noise_events,
    format_cluster_headline,
    format_cluster_rule_hint,
    format_cluster_sample,
)
from outputs.terminal_theme import CLR_VALUE_ORANGE

UNCATEGORIZED = "Uncategorized"
_SKIP = "Skip this gap"
_QUIT = "Stop reviewing gaps"


def _existing_project_names(profiles: list[dict[str, Any]]) -> list[str]:
    return sorted(
        {
            str(profile.get("name", "")).strip()
            for profile in profiles
            if isinstance(profile, dict) and str(profile.get("name", "")).strip()
        },
        key=str.lower,
    )


def _project_exists(payload: dict[str, Any], project_name: str) -> bool:
    clean = project_name.strip().lower()
    for project in payload.get("projects", []):
        if isinstance(project, dict) and str(project.get("name", "")).strip().lower() == clean:
            return True
    return False


def _customer_for_project(profiles: list[dict[str, Any]], project_name: str) -> str:
    tnorm = project_name.strip().lower()
    for profile in profiles:
        if isinstance(profile, dict) and str(profile.get("name", "")).strip().lower() == tnorm:
            customer = str(profile.get("customer", "")).strip()
            return customer or project_name
    return project_name


def _cluster_preview(
    report,
    uncategorized_events: list[dict[str, Any]],
    project_name: str,
    cluster,
) -> tuple[int, float, int]:
    suggestion = RuleSuggestion.from_cluster(cluster, "report-gap attribution candidate")
    exclude_list = [k.strip() for k in str(report.args.exclude or "").split(",") if k.strip()]
    return preview_suggestion_impact(
        uncategorized_events,
        report.profiles,
        project_name,
        [suggestion],
        gap_minutes=int(report.args.gap_minutes),
        min_session_minutes=int(report.args.min_session),
        min_session_passive_minutes=int(report.args.min_session_passive),
        exclude_keywords=exclude_list,
        uncategorized_label=UNCATEGORIZED,
    )


def _gap_candidates_json(
    report,
    uncategorized_events: list[dict[str, Any]],
    clusters,
    project_names: list[str],
) -> dict[str, Any]:
    """Read-only candidate payload: never writes config."""
    rows = []
    for cluster in clusters:
        row: dict[str, Any] = {
            "rule_type": cluster.rule_type,
            "rule_value": cluster.rule_value,
            "source": cluster.source,
            "events": cluster.count,
            "samples": list(cluster.samples),
        }
        previews: dict[str, Any] = {}
        for project_name in project_names:
            matched_events, matched_hours, uncategorized_delta = _cluster_preview(
                report, uncategorized_events, project_name, cluster
            )
            if matched_events <= 0:
                continue
            previews[project_name] = {
                "customer": _customer_for_project(report.profiles, project_name),
                "matched_events": matched_events,
                "matched_hours": matched_hours,
                "uncategorized_delta": uncategorized_delta,
            }
        row["candidate_projects"] = previews
        rows.append(row)
    return {
        "schema_version": 1,
        "uncategorized_events": len(uncategorized_events),
        "existing_projects": project_names,
        "gaps": rows,
    }


def run_gap_attribution_review(
    *,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    today: bool = False,
    yesterday: bool = False,
    last_3_days: bool = False,
    last_week: bool = False,
    last_14_days: bool = False,
    last_month: bool = False,
    projects_config: str,
    max_clusters: int = 20,
    samples_per_cluster: int = 4,
    json_out: bool = False,
) -> bool:
    """Preview-first attribution for report gaps (Uncategorized clusters).

    Never creates a new project profile — only existing customer/project
    lines are offered as attribution targets. Returns True when actionable
    gap candidates were shown (advisory next steps should treat the window as
    having attribution candidates).
    """
    from core.report_service import run_timelog_report

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
    project_names = _existing_project_names(report.profiles)

    if not uncategorized_events:
        if json_out:
            print(json.dumps({"schema_version": 1, "uncategorized_events": 0, "existing_projects": project_names, "gaps": []}, indent=2, ensure_ascii=False))
            return False
        console.print("[green]No report gaps (Uncategorized events) found in selected range.[/green]")
        return False

    noise_events = count_uncategorized_noise_events(uncategorized_events)
    clusters = build_uncategorized_clusters(
        uncategorized_events,
        max_clusters=max_clusters,
        samples_per_cluster=samples_per_cluster,
    )

    if json_out:
        payload = _gap_candidates_json(report, uncategorized_events, clusters, project_names)
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return bool(payload["gaps"])

    if not clusters:
        console.print(
            f"[green]No actionable gap candidates.[/green] Filtered {noise_events} tooling-noise events."
        )
        return False

    if not project_names:
        console.print(
            "[yellow]No existing projects in config — nothing to attribute gaps to.[/yellow] "
            "Add a project first (this surface never creates one)."
        )
        return False

    # The picker below reads stdin (questionary); without a real TTY that
    # crashes deep in the event loop (kqueue EINVAL on piped stdin) instead of
    # degrading. Same guard as the anchor flow: prompts only on a terminal.
    from core.anchor_nudge import should_prompt

    if not should_prompt():
        console.print(
            f"[yellow]Interactive gap attribution needs a terminal[/yellow] — "
            f"{len(clusters)} gap candidate(s) found. Use `gittan review --gaps --json` "
            "for the machine-readable list."
        )
        return False

    console.print(
        f"[bold]Report gaps[/bold] | {len(uncategorized_events)} uncategorized events | "
        f"{noise_events} tooling-noise hidden | {len(clusters)} candidates"
    )
    console.print(
        "[dim]Pick an existing customer/project line for each gap; hour impact is previewed "
        "before any write. New projects are never created here.[/dim]"
    )

    config_path = Path(projects_config)
    applied_any = False
    for index, cluster in enumerate(clusters, start=1):
        remaining = len(clusters) - index
        console.print(
            f"\n[bold]Gap {index}/{len(clusters)}[/bold] · {cluster.source} · "
            f"{cluster.count} events · {remaining} left"
        )
        console.print(format_cluster_headline(cluster))
        console.print(f"[dim]{format_cluster_rule_hint(cluster)}[/dim]")
        for sample in cluster.samples:
            console.print(f"  · {format_cluster_sample(sample)}")

        target = questionary.select(
            "Attribute this gap to existing customer/project line",
            choices=[*project_names, _SKIP, _QUIT],
        ).ask()
        if target is None or target == _QUIT:
            break
        if target == _SKIP:
            continue

        matched_events, matched_hours, uncategorized_delta = _cluster_preview(
            report, uncategorized_events, target, cluster
        )
        customer = _customer_for_project(report.profiles, target)
        if matched_events <= 0:
            console.print(
                "[yellow]No hour impact for this project (rule would not match any of these "
                "events after existing rules) — skipping.[/yellow]"
            )
            continue

        console.print(
            f"[bold]Preview[/bold] → customer [cyan]{customer}[/cyan] · line [cyan]{target}[/cyan]: "
            f"[{CLR_VALUE_ORANGE}]+{matched_events} events[/{CLR_VALUE_ORANGE}], "
            f"[{CLR_VALUE_ORANGE}]+{matched_hours:.2f}h[/{CLR_VALUE_ORANGE}], "
            f"[{CLR_VALUE_ORANGE}]{uncategorized_delta} uncategorized[/{CLR_VALUE_ORANGE}]"
        )
        confirmed = questionary.confirm(
            f"Apply {cluster.rule_type}={cluster.rule_value!r} to '{target}' now?",
            default=False,
        ).ask()
        if not confirmed:
            console.print("[dim]Skipped — no config change.[/dim]")
            continue

        payload = load_projects_config_payload(config_path)
        if not _project_exists(payload, target):
            # Guard: this surface only attributes to existing lines. If the
            # target vanished between listing and apply (concurrent edit),
            # refuse rather than silently create a new slug-only profile.
            console.print(
                f"[red]Refusing to create a new project '{target}'.[/red] "
                "Report-gap attribution only writes to existing customer/project lines."
            )
            continue
        field, value, created = apply_rule_to_project(
            payload,
            project_name=target,
            rule_type=cluster.rule_type,
            rule_value=cluster.rule_value,
        )
        if created:
            # The never-create invariant is safety-critical for the invoice
            # config — enforce it at runtime (an assert vanishes under -O).
            console.print(
                f"[red]Refusing write:[/red] applying this rule would have created a new "
                f"project '{target}' — this surface only edits existing lines. Skipping."
            )
            continue
        backup = backup_projects_config_if_exists(config_path)
        try:
            save_projects_config_payload(config_path, payload)
        except PermissionError as exc:
            console.print(f"[red]Error:[/red] Cannot write to config file '{config_path}' - permission denied.")
            raise typer.Exit(code=1) from exc
        except OSError as exc:
            console.print(f"[red]Error:[/red] Cannot save config file '{config_path}': {exc}")
            raise typer.Exit(code=1) from exc
        if backup:
            console.print(f"[dim]Backup:[/dim] {backup}")
        console.print(f"[green]Saved[/green] {field} -> {value!r} for {target!r}.")
        applied_any = True

    if applied_any:
        console.print("[dim]Re-run `gittan report` to see updated project hours.[/dim]")
    return True
