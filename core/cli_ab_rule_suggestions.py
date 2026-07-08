"""CLI: A/B uncategorized rule suggestions (`suggest-rules`, `apply-suggestions`)."""

from __future__ import annotations

import json
from pathlib import Path

import questionary
import typer

from core.cli_prompts import prompt_for_timeframe
from core.config import (
    apply_rule_to_project,
    backup_projects_config_if_exists,
    load_projects_config_payload,
    save_projects_config_payload,
)
from core.rule_suggestions import (
    ab_suggestions_state_path,
    normalize_payload_projects_list,
    preview_suggestion_impact,
    split_ab_suggestions,
    write_suggestions_state,
)
from core.uncategorized_review import build_uncategorized_clusters

UNCATEGORIZED = "Uncategorized"


def _load_projects_payload(console, config_path: Path) -> dict:
    try:
        payload = load_projects_config_payload(config_path)
        payload["projects"] = normalize_payload_projects_list(payload)
        return payload
    except json.JSONDecodeError as exc:
        console.print(f"[red]Error:[/red] Config file '{config_path}' contains invalid JSON: {exc}")
        console.print("[yellow]Hint:[/yellow] Check the file syntax or delete it to start fresh.")
        raise typer.Exit(code=1) from exc
    except ValueError as exc:
        console.print(f"[red]Error:[/red] Invalid projects structure in '{config_path}': {exc}")
        raise typer.Exit(code=1) from exc
    except PermissionError:
        console.print(f"[red]Error:[/red] Cannot read config file '{config_path}' - permission denied.")
        raise typer.Exit(code=1)
    except OSError as exc:
        console.print(f"[red]Error:[/red] Cannot access config file '{config_path}': {exc}")
        raise typer.Exit(code=1) from exc


def _apply_timeframe_prompt(
    date_from,
    date_to,
    today,
    yesterday,
    last_3_days,
    last_week,
    last_14_days,
    last_month,
):
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
    return date_from, date_to, today, yesterday, last_3_days, last_week, last_14_days, last_month


def print_ab_suggestion_preview(
    console, project_name: str, rules_a: list, rules_b: list, prev_a: tuple, prev_b: tuple
):
    me_a, h_a, u_a = prev_a
    me_b, h_b, u_b = prev_b
    console.print(f"\n[bold]A/B rule suggestions[/bold] for project [cyan]{project_name}[/cyan]")
    if not rules_a:
        console.print("[yellow]Option A (safe): no safe suggestions[/yellow] (heuristics found nothing strong enough).")
    else:
        console.print(f"\n[bold]Option A (safe)[/bold] — {len(rules_a)} rule(s)")
        console.print(
            f"  Impact: [orange]+{me_a} events[/orange], [orange]+{h_a} h[/orange], "
            f"[orange]{u_a} uncategorized[/orange]"
        )
        for suggestion in rules_a:
            console.print(
                f"  • {suggestion.rule_type}={suggestion.rule_value!r} "
                f"({suggestion.cluster_count} clustered) — {suggestion.note}"
            )
            for sample in suggestion.samples[:3]:
                console.print(f"      — {sample}")

    keys_a = {(s.rule_type, s.rule_value) for s in rules_a}
    console.print(f"\n[bold]Option B (broad)[/bold] — {len(rules_b)} rule(s)")
    console.print(
        f"  Impact: [orange]+{me_b} events[/orange], [orange]+{h_b} h[/orange], "
        f"[orange]{u_b} uncategorized[/orange]"
    )
    if not rules_b:
        console.print("  [yellow]No broad suggestions; widen the date range or add rules manually.[/yellow]")
        return
    if rules_a:
        console.print("  [dim](B includes every A rule plus the broad-only items below.)[/dim]")
    for suggestion in rules_b:
        if (suggestion.rule_type, suggestion.rule_value) in keys_a:
            continue
        console.print(
            f"  • {suggestion.rule_type}={suggestion.rule_value!r} "
            f"({suggestion.cluster_count} clustered) — {suggestion.note}"
        )
        for sample in suggestion.samples[:3]:
            console.print(f"      — {sample}")


def gather_ab_suggestions(report, uncategorized_events: list, project_name: str):
    clusters = build_uncategorized_clusters(
        uncategorized_events,
        max_clusters=50,
        samples_per_cluster=3,
    )
    opt_a, opt_b = split_ab_suggestions(clusters, report.profiles, project_name)
    exclude_list = [k.strip() for k in str(report.args.exclude or "").split(",") if k.strip()]
    prev_a = preview_suggestion_impact(
        uncategorized_events,
        report.profiles,
        project_name,
        opt_a,
        gap_minutes=int(report.args.gap_minutes),
        min_session_minutes=int(report.args.min_session),
        min_session_passive_minutes=int(report.args.min_session_passive),
        exclude_keywords=exclude_list,
        uncategorized_label=UNCATEGORIZED,
    )
    prev_b = preview_suggestion_impact(
        uncategorized_events,
        report.profiles,
        project_name,
        opt_b,
        gap_minutes=int(report.args.gap_minutes),
        min_session_minutes=int(report.args.min_session),
        min_session_passive_minutes=int(report.args.min_session_passive),
        exclude_keywords=exclude_list,
        uncategorized_label=UNCATEGORIZED,
    )
    return opt_a, opt_b, prev_a, prev_b


def persist_suggestion_state(
    config_path: Path,
    project_name: str,
    uncategorized_total: int,
    opt_a,
    opt_b,
    prev_a,
    prev_b,
) -> Path:
    previews = {
        "A": {
            "rules": [r.as_json_dict() for r in opt_a],
            "preview": {
                "matched_events": prev_a[0],
                "matched_hours": prev_a[1],
                "uncategorized_delta": prev_a[2],
            },
        },
        "B": {
            "rules": [r.as_json_dict() for r in opt_b],
            "preview": {
                "matched_events": prev_b[0],
                "matched_hours": prev_b[1],
                "uncategorized_delta": prev_b[2],
            },
        },
    }
    state_path = ab_suggestions_state_path(config_path)
    write_suggestions_state(
        state_path,
        projects_config=str(config_path),
        target_project=project_name,
        uncategorized_total=uncategorized_total,
        option_previews=previews,
    )
    return state_path


def prompt_optional_apply(console, config_path: Path, project_name: str, opt_a, opt_b) -> None:
    action = questionary.select(
        "Apply heuristic rules now?",
        choices=[
            "No",
            "Apply option A (safe)",
            "Apply option B (broad)",
        ],
    ).ask()
    if not action or action == "No":
        return

    bundle = "A" if "A (safe)" in action else "B"
    rules = opt_a if bundle == "A" else opt_b
    if not rules:
        console.print("[yellow]Nothing to apply for that option.[/yellow]")
        return

    if not questionary.confirm(
        f"Write {len(rules)} rule(s) ({bundle}) to {config_path} (backup first)?",
        default=False,
    ).ask():
        return

    payload = _load_projects_payload(console, config_path)
    backup = backup_projects_config_if_exists(config_path)
    if backup:
        console.print(f"[dim]Backup: {backup}[/dim]")

    for suggestion in rules:
        apply_rule_to_project(
            payload,
            project_name=project_name,
            rule_type=suggestion.rule_type,
            rule_value=suggestion.rule_value,
        )
    try:
        save_projects_config_payload(config_path, payload)
    except OSError as exc:
        console.print(f"[red]Error:[/red] Cannot save config: {exc}")
        raise typer.Exit(code=1) from exc
    console.print(f"[green]Applied[/green] option {bundle} ({len(rules)} rules) to {config_path}.")


