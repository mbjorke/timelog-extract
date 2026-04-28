"""Helpers for setup project-identity customer candidate discovery/rendering."""

from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rich import box
from rich.table import Table

from core.git_project_bootstrap import discover_git_project_hints, discover_local_git_repos, parse_github_origin
from outputs.terminal_theme import STYLE_BORDER, STYLE_LABEL, STYLE_MUTED


def _activity_dot(epoch_ts: int) -> str:
    if epoch_ts <= 0:
        return "[dim]●[/dim]"
    now_epoch = int(datetime.now(tz=timezone.utc).timestamp())
    age_days = (now_epoch - epoch_ts) / 86400
    if age_days <= 30:
        return "[green]●[/green]"
    if age_days <= 90:
        return "[yellow]●[/yellow]"
    return "[red]●[/red]"


def _git_remote_origin(repo: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
    except OSError:
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def _git_last_commit_epoch(repo: Path) -> int:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), "log", "-1", "--format=%ct"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
    except OSError:
        return 0
    if result.returncode != 0:
        return 0
    try:
        return int((result.stdout or "").strip() or "0")
    except ValueError:
        return 0


def _local_owner_activity_summary() -> tuple[dict[str, int], dict[str, str], dict[str, list[tuple[int, str]]]]:
    """Return owner summaries from local git repos."""

    roots = [
        Path.home(),
        Path.cwd(),
        Path.home() / "Workspace",
        Path.home() / "Code",
        Path.home() / "Projects",
        Path.home() / "Developer",
    ]
    seen_roots: set[Path] = set()
    repos: list[Path] = []
    for root in roots:
        try:
            root_resolved = root.resolve()
        except OSError:
            continue
        if root_resolved in seen_roots or not root_resolved.exists() or not root_resolved.is_dir():
            continue
        seen_roots.add(root_resolved)
        repos.extend(discover_local_git_repos(root_resolved, max_depth=4, limit=300))

    owner_to_slugs: dict[str, set[str]] = {}
    owner_best_slug: dict[str, str] = {}
    owner_best_ts: dict[str, int] = {}
    owner_slug_activity: dict[str, list[tuple[int, str]]] = {}
    for repo in repos:
        origin = _git_remote_origin(repo)
        parsed = parse_github_origin(origin)
        if parsed is None:
            continue
        owner, name = parsed
        owner_key = owner.strip().lower()
        if not owner_key:
            continue
        slug = f"{owner_key}/{name.strip().lower()}"
        owner_to_slugs.setdefault(owner_key, set()).add(slug)
        ts = _git_last_commit_epoch(repo)
        owner_slug_activity.setdefault(owner_key, []).append((ts, slug))
        best = owner_best_ts.get(owner_key, -1)
        if ts > best:
            owner_best_ts[owner_key] = ts
            owner_best_slug[owner_key] = slug

    owner_counts = {owner: len(slugs) for owner, slugs in owner_to_slugs.items()}
    owner_top_activity: dict[str, list[tuple[int, str]]] = {}
    for owner, activity in owner_slug_activity.items():
        seen: set[str] = set()
        ranked: list[tuple[int, str]] = []
        for ts, slug in sorted(activity, key=lambda item: item[0], reverse=True):
            if slug in seen:
                continue
            seen.add(slug)
            ranked.append((ts, slug))
            if len(ranked) >= 15:
                break
        owner_top_activity[owner] = ranked
    return owner_counts, owner_best_slug, owner_top_activity


def _customer_candidate_rows(projects: list[dict[str, Any]], customers: list[str]) -> list[tuple[str, str, str, str]]:
    owner_counts, owner_best_slug, owner_top_activity = _local_owner_activity_summary()
    current_hint = discover_git_project_hints(Path.cwd())
    current_owner = (current_hint.remote_owner or "").strip().lower() if current_hint else ""
    current_repo = (current_hint.remote_repo or "").strip().lower() if current_hint else ""
    rows: list[tuple[str, str, str, str]] = []
    for customer in customers:
        slug_hints: list[str] = []
        for project in projects:
            if not isinstance(project, dict):
                continue
            p_customer = str(project.get("customer", "")).strip()
            if p_customer != customer:
                continue
            for term in project.get("match_terms", []) or []:
                raw = str(term).strip().lower()
                if "/" in raw and not raw.startswith(("workspace/", "users/")) and " " not in raw:
                    if raw not in slug_hints:
                        slug_hints.append(raw)

        preferred = ""
        owner_key = customer.strip().lower()
        if current_owner and current_repo and owner_key == current_owner:
            current_slug = f"{current_owner}/{current_repo}"
            if current_slug in slug_hints:
                preferred = current_slug
        if not preferred and owner_key in owner_best_slug:
            preferred = owner_best_slug[owner_key]
        if not preferred and slug_hints:
            preferred = slug_hints[0]

        if preferred:
            count = max(len(slug_hints), owner_counts.get(owner_key, 0))
            top_pairs = list(owner_top_activity.get(owner_key, []))
            if not top_pairs:
                top_pairs = [(0, preferred)]
            if current_owner and current_repo and owner_key == current_owner:
                current_slug = f"{current_owner}/{current_repo}"
                filtered = [(ts, slug) for ts, slug in top_pairs if slug != current_slug]
                current_ts = _git_last_commit_epoch(Path.cwd())
                top_pairs = [(current_ts, current_slug), *filtered]
            shown_pairs = top_pairs[:15]
            top_lines = [f"{_activity_dot(ts)} github.com/{slug}" for ts, slug in shown_pairs]
            most_active = f"github.com/{preferred}" if preferred else "n/a"
            rows.append((customer, str(count), most_active, "\n".join(top_lines) if top_lines else "n/a"))
        else:
            rows.append((customer, "n/a", "n/a", "n/a"))
    return rows


def print_customer_candidates_table(console, projects: list[dict[str, Any]], existing_customers: list[str]) -> None:
    rows = _customer_candidate_rows(projects, existing_customers)
    table = Table(title="Detected customer candidates", box=box.ROUNDED)
    table.border_style = STYLE_BORDER
    table.header_style = f"bold {STYLE_LABEL}"
    table.add_column("Candidate", style=STYLE_LABEL)
    table.add_column("Repos", justify="right")
    table.add_column("Most Active Now", style=STYLE_MUTED)
    table.add_column("Top Active Repos (up to 15)", style=STYLE_MUTED)
    for candidate, repo_count, most_active, top_repos in rows:
        table.add_row(candidate, repo_count, most_active, top_repos)
    console.print(table)
    console.print(
        "[dim]Activity dots:[/dim] "
        "[green]● <= 30d[/green], "
        "[yellow]● <= 90d[/yellow], "
        "[red]● > 90d[/red], "
        "[dim]● unknown timestamp[/dim]."
    )
