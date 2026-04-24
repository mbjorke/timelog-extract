"""Project config bootstrap and safe multi-repo merge helpers for setup."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path

import questionary

from core.git_project_bootstrap import (
    RepoBootstrapSummary,
    build_repo_project_seed,
    discover_git_project_hints,
    discover_local_git_repos,
    merge_repo_project_seeds,
    suggest_bootstrap_root,
)


@dataclass(frozen=True)
class ProjectsConfigBootstrapResult:
    status: str
    notes: str
    next_steps: list[str]


def _manual_project_defaults() -> tuple[str, str, str]:
    return "default-project", "Default Customer", "default"


def _project_bootstrap_notes(summary: RepoBootstrapSummary, *, dry_run: bool) -> str:
    prefix = "Would scan" if dry_run else "Scanned"
    fallback = " | fallback profile used" if summary.fallback_used else ""
    return (
        f"{prefix} {summary.root} | discovered={summary.discovered} | "
        f"added={summary.added} | updated={summary.updated} | skipped={summary.skipped}{fallback}"
    )


def _project_bootstrap_next_steps(summary: RepoBootstrapSummary) -> list[str]:
    steps = ["Run `gittan report --today --source-summary` once the imported projects look right."]
    if summary.skipped:
        steps.append("Use `gittan projects` to fill gaps for repos that were skipped or need broader `match_terms`.")
    if summary.discovered and summary.added + summary.updated:
        steps.append("Review imported `match_terms` in `gittan projects` so nearby repos classify cleanly in future reports.")
    return steps


def ensure_projects_config(
    *,
    console,
    yes: bool,
    dry_run: bool,
    bootstrap_root: str | None,
    config_path: Path,
    timestamped_backup_path_fn,
    looks_like_projects_config_fn,
) -> ProjectsConfigBootstrapResult:
    payload: dict | None = None
    if config_path.exists():
        try:
            current_payload = json.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            current_payload = None
        if looks_like_projects_config_fn(current_payload):
            payload = dict(current_payload)
            console.print(f"[green]Project config exists:[/green] {config_path}")
        else:
            console.print(f"[yellow]Project config looks invalid:[/yellow] {config_path}")
            should_repair = yes or questionary.confirm(
                f"Backup and recreate minimal project config at {config_path}?",
                default=False,
            ).ask()
            if not should_repair:
                console.print("[yellow]Keeping current project config unchanged.[/yellow]")
                return ProjectsConfigBootstrapResult("ACTION_REQUIRED", "Invalid config left unchanged.", [])
            backup_path = timestamped_backup_path_fn(config_path)
            if dry_run:
                console.print(f"[yellow]Dry run:[/yellow] would create backup {backup_path}")
                console.print(f"[yellow]Dry run:[/yellow] would recreate {config_path}")
            else:
                shutil.copy2(config_path, backup_path)
                console.print(f"[green]Created backup:[/green] {backup_path}")

    if payload is None:
        should_create = yes or questionary.confirm(f"Create minimal project config at {config_path}?", default=True).ask()
        if not should_create:
            console.print("[yellow]Skipped project config bootstrap.[/yellow]")
            return ProjectsConfigBootstrapResult("SKIPPED", "Project config bootstrap skipped.", [])
        payload = {"worklog": "TIMELOG.md", "projects": []}

    root_path = Path(bootstrap_root).expanduser() if bootstrap_root else suggest_bootstrap_root(Path.cwd())
    if not yes and bootstrap_root is None:
        root_answer = questionary.text("Repo discovery root for multi-repo bootstrap:", default=str(root_path)).ask()
        if root_answer:
            root_path = Path(root_answer).expanduser()

    repos = discover_local_git_repos(root_path)
    seeds = [seed for repo in repos if (seed := build_repo_project_seed(repo)) is not None]
    merged_payload, summary = merge_repo_project_seeds(payload, seeds, root=root_path)
    summary = RepoBootstrapSummary(
        root=summary.root,
        discovered=len(repos),
        added=summary.added,
        updated=summary.updated,
        skipped=summary.skipped + max(0, len(repos) - len(seeds)),
        fallback_used=summary.fallback_used,
    )

    if not seeds and not merged_payload.get("projects"):
        hints = discover_git_project_hints(Path.cwd())
        if hints is not None:
            project_name = hints.project_name
            customer = hints.customer
            keywords = ", ".join(hints.match_terms)
        else:
            project_name, customer, keywords = _manual_project_defaults()
        if not yes:
            project_name = questionary.text("Project name:", default=project_name).ask() or project_name
            customer = questionary.text("Customer name:", default=customer).ask() or customer
            keywords = questionary.text("Match terms (comma separated):", default=keywords).ask() or keywords
        merged_payload["projects"] = [
            {
                "name": project_name,
                "customer": customer,
                "match_terms": [k.strip() for k in keywords.split(",") if k.strip()],
                "tracked_urls": [],
                "email": "",
                "invoice_title": "",
                "invoice_description": "",
                "enabled": True,
            }
        ]
        summary = RepoBootstrapSummary(root=root_path, discovered=0, added=0, updated=0, skipped=0, fallback_used=True)

    if dry_run:
        console.print(f"[yellow]Dry run:[/yellow] would write merged project config to {config_path}")
        return ProjectsConfigBootstrapResult(
            "PASS (dry-run)",
            _project_bootstrap_notes(summary, dry_run=True),
            _project_bootstrap_next_steps(summary),
        )

    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(merged_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    console.print(f"[green]Saved merged project config:[/green] {config_path}")
    return ProjectsConfigBootstrapResult(
        "PASS",
        _project_bootstrap_notes(summary, dry_run=False),
        _project_bootstrap_next_steps(summary),
    )
