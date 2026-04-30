"""Typer command: map domains to projects across a date range."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any, Optional

import questionary
import typer
from questionary import Choice

from core.cli_app import app
from core.cli_date_range import resolve_date_window
from core.cli_triage import build_triage_plan_dict
from core.cli_triage_apply import apply_triage_decisions_payload
from core.config import default_projects_config_option

_DECISIONS_SCHEMA_VERSION = 1
_GENERIC_DOMAINS = {
    "google.com",
    "github.com",
    "claude.ai",
    "linkedin.com",
    "accounts.google.com",
    "mail.google.com",
}


def _is_history_dominant(
    *,
    domain: str,
    project_name: str,
    domain_project_counts: dict[str, list[dict[str, Any]]],
) -> bool:
    history = domain_project_counts.get(domain, [])
    total = sum(int(item.get("events", 0) or 0) for item in history)
    if total <= 0:
        return False
    target = sum(
        int(item.get("events", 0) or 0)
        for item in history
        if str(item.get("project", "")).strip().lower() == project_name.lower()
    )
    return target >= 3 and (target / total) >= 0.7


def build_domain_project_candidates(
    plan: dict[str, Any],
    *,
    min_votes: int,
) -> list[dict[str, Any]]:
    by_domain: dict[str, dict[str, Any]] = {}
    domain_project_counts = {
        str(k): list(v)
        for k, v in (plan.get("domain_project_counts", {}) or {}).items()
        if isinstance(k, str) and isinstance(v, list)
    }
    for day in plan.get("days", []):
        if day.get("skip_reason"):
            continue
        project_name = str(day.get("resolved_project_for_top_suggestion") or "").strip()
        if not project_name:
            continue
        for site in day.get("top_sites", []):
            domain = str(site.get("domain", "")).strip()
            if not domain:
                continue
            info = by_domain.setdefault(
                domain,
                {
                    "project_votes": {},
                    "sample_title": "",
                    "repo_hint": "",
                },
            )
            votes = info["project_votes"]
            votes[project_name] = int(votes.get(project_name, 0)) + 1
            if not info["sample_title"] and str(site.get("sample_title", "")).strip():
                info["sample_title"] = str(site.get("sample_title", "")).strip()
            if not info["repo_hint"] and str(site.get("repo_hint", "")).strip():
                info["repo_hint"] = str(site.get("repo_hint", "")).strip()

    out: list[dict[str, Any]] = []
    for domain, info in by_domain.items():
        ranked = sorted(info["project_votes"].items(), key=lambda item: (-item[1], item[0]))
        top_project, top_votes = ranked[0]
        total_votes = sum(int(v) for _, v in ranked)
        dominance = (top_votes / total_votes) if total_votes else 0.0
        history_dominant = _is_history_dominant(
            domain=domain,
            project_name=top_project,
            domain_project_counts=domain_project_counts,
        )
        if top_votes < int(min_votes) and not history_dominant:
            continue
        generic = domain.lower() in _GENERIC_DOMAINS
        low_confidence = generic and not (history_dominant or bool(info["repo_hint"]))
        out.append(
            {
                "domain": domain,
                "project_name": top_project,
                "votes": int(top_votes),
                "total_votes": int(total_votes),
                "dominance": float(dominance),
                "sample_title": str(info["sample_title"] or ""),
                "repo_hint": str(info["repo_hint"] or ""),
                "history_dominant": history_dominant,
                "low_confidence": low_confidence,
            }
        )
    out.sort(key=lambda item: (-item["votes"], -item["dominance"], item["domain"]))
    return out


def _candidate_choice(item: dict[str, Any]) -> Choice:
    domain = str(item["domain"])
    project_name = str(item["project_name"])
    votes = int(item["votes"])
    dominance = float(item["dominance"])
    title_preview = str(item.get("sample_title", "")).replace("\n", " ").strip()
    if len(title_preview) > 50:
        title_preview = title_preview[:47].rstrip() + "..."
    repo_hint = str(item.get("repo_hint", "")).strip()
    parts = [f"{domain} -> {project_name}", f"votes: {votes}", f"share: {dominance:.0%}"]
    if repo_hint:
        parts.append(repo_hint)
    if title_preview:
        parts.append(title_preview)
    label = " — ".join(parts)
    if bool(item.get("low_confidence")):
        return Choice(title=f"{label} — [low confidence: generic domain]", value=domain, disabled="Needs stronger signal")
    return Choice(title=label, value=domain)


def _decisions_payload(decisions: list[dict[str, str]]) -> dict[str, Any]:
    return {"schema_version": _DECISIONS_SCHEMA_VERSION, "decisions": decisions}


@app.command("triage-domains")
def triage_domains(
    date_from: Annotated[
        Optional[datetime],
        typer.Option("--from", formats=["%Y-%m-%d"], help="Start date (YYYY-MM-DD)"),
    ] = None,
    date_to: Annotated[
        Optional[datetime],
        typer.Option("--to", formats=["%Y-%m-%d"], help="End date (YYYY-MM-DD)"),
    ] = None,
    today: Annotated[bool, typer.Option(help="Limit to today.")] = False,
    yesterday: Annotated[bool, typer.Option(help="Limit to yesterday.")] = False,
    last_3_days: Annotated[bool, typer.Option(help="Limit to last 3 days.")] = False,
    last_week: Annotated[bool, typer.Option(help="Limit to last 7 days.")] = False,
    last_14_days: Annotated[bool, typer.Option(help="Limit to last 14 days.")] = False,
    last_month: Annotated[bool, typer.Option(help="Limit to last 30 days.")] = False,
    projects_config: Annotated[str, typer.Option(help="JSON config file")] = default_projects_config_option(),
    max_days: Annotated[int, typer.Option(help="Max days to scan for domain->project votes")] = 14,
    max_sites: Annotated[int, typer.Option(help="Top sites per day")] = 8,
    min_votes: Annotated[int, typer.Option(help="Minimum day votes per domain unless history is dominant")] = 1,
    scoring_mode: Annotated[str, typer.Option(help="balanced or site-first")] = "site-first",
    write_decisions: Annotated[Optional[str], typer.Option("--write-decisions", help="Write decisions JSON to path")] = None,
) -> None:
    """Aggregate domain->project candidates and apply only explicit selections."""
    from rich.console import Console

    console = Console()
    date_from, date_to = resolve_date_window(
        date_from=date_from,
        date_to=date_to,
        today=today,
        yesterday=yesterday,
        last_3_days=last_3_days,
        last_week=last_week,
        last_14_days=last_14_days,
        last_month=last_month,
    )
    plan = build_triage_plan_dict(
        date_from=date_from,
        date_to=date_to,
        projects_config=projects_config,
        max_days=max_days,
        max_sites=max_sites,
        scoring_mode=scoring_mode,
        include_sample_title=True,
    )
    candidates = build_domain_project_candidates(plan, min_votes=min_votes)
    if not candidates:
        console.print("[yellow]No domain candidates met the threshold in this range.[/yellow]")
        raise typer.Exit(code=0)
    picked_domains = questionary.checkbox(
        "Select domain -> project mappings to apply:",
        choices=[_candidate_choice(item) for item in candidates],
    ).ask()
    if not picked_domains:
        console.print("[yellow]No domain mappings selected. Nothing to apply.[/yellow]")
        raise typer.Exit(code=0)

    by_domain = {str(item["domain"]): item for item in candidates}
    decisions: list[dict[str, str]] = []
    for domain in picked_domains:
        item = by_domain.get(str(domain))
        if not item:
            continue
        decisions.append(
            {
                "project_name": str(item["project_name"]),
                "rule_type": "tracked_urls",
                "rule_value": str(item["domain"]),
            }
        )
    if write_decisions:
        output_path = Path(write_decisions).expanduser()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(_decisions_payload(decisions), indent=2) + "\n", encoding="utf-8")
        console.print(f"[green]Decisions file written:[/green] {output_path}")

    preview = apply_triage_decisions_payload(
        decisions=decisions,
        projects_config=projects_config,
        allow_create=False,
        dry_run=True,
        interactive_review=False,
    )
    if preview.get("errors"):
        console.print(json.dumps(preview, indent=2))
        raise typer.Exit(code=1)
    console.print(preview.get("preview", "No preview available."))
    confirmed = questionary.confirm("Apply these domain mappings now?", default=False).ask()
    if not confirmed:
        console.print("[yellow]Cancelled before writing config.[/yellow]")
        raise typer.Exit(code=0)
    applied = apply_triage_decisions_payload(
        decisions=decisions,
        projects_config=projects_config,
        allow_create=False,
        dry_run=False,
        interactive_review=False,
    )
    if applied.get("errors"):
        console.print(json.dumps(applied, indent=2))
        raise typer.Exit(code=1)
    console.print(json.dumps(applied, indent=2))
    console.print("[green]Domain triage apply complete.[/green]")
