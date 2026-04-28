"""Interactive setup step: reconcile project -> customer mapping safely.

This step is intentionally conservative and safe to run repeatedly:
- It does not invent match_terms.
- It only updates identity/billing fields (customer/default_client/project_id/canonical_project)
  when the user explicitly confirms.
"""

from __future__ import annotations

import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import questionary
from rich import box
from rich.table import Table

from core.config import backup_projects_config_if_exists, load_projects_config_payload, save_projects_config_payload
from core.git_project_bootstrap import discover_git_project_hints, discover_local_git_repos, parse_github_origin
from outputs.cli_heroes import print_command_hero
from outputs.terminal_theme import STYLE_BORDER, STYLE_LABEL, STYLE_MUTED


def _slug(text: str) -> str:
    clean = re.sub(r"[^a-z0-9]+", "-", (text or "").strip().lower()).strip("-")
    return clean


def _compact(text: str) -> str:
    return "".join(ch for ch in (text or "").lower() if ch.isalnum())


def _detect_customer_slug_collisions(projects: Iterable[dict[str, Any]]) -> dict[str, list[str]]:
    by_slug: dict[str, list[str]] = {}
    for p in projects:
        customer = str(p.get("customer", "")).strip()
        if not customer:
            continue
        s = _slug(customer)
        if not s:
            continue
        by_slug.setdefault(s, [])
        if customer not in by_slug[s]:
            by_slug[s].append(customer)
    return {k: v for k, v in by_slug.items() if len(v) > 1}


def _existing_customers(projects: list[dict[str, Any]]) -> list[str]:
    # Prefer user-curated customer labels over placeholder customer=name rows.
    curated: list[str] = []
    for p in projects:
        name = str(p.get("name", "")).strip()
        customer = str(p.get("customer", "")).strip()
        if not customer:
            continue
        if customer.lower() == name.lower():
            continue
        if customer not in curated:
            curated.append(customer)
    if curated:
        return curated
    # Fallback: still list existing customer values if no curated set exists yet.
    any_customers: list[str] = []
    for p in projects:
        customer = str(p.get("customer", "")).strip()
        if customer and customer not in any_customers:
            any_customers.append(customer)
    return any_customers


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


def _customer_candidate_rows(projects: list[dict[str, Any]], customers: list[str]) -> list[tuple[str, str, str, str]]:
    owner_counts, owner_best_slug, owner_top_activity = _local_owner_activity_summary()
    current_hint = discover_git_project_hints(Path.cwd())
    current_owner = (current_hint.remote_owner or "").strip().lower() if current_hint else ""
    current_repo = (current_hint.remote_repo or "").strip().lower() if current_hint else ""
    rows: list[tuple[str, str, str, str]] = []
    for customer in customers:
        slug_hints: list[str] = []
        for p in projects:
            if not isinstance(p, dict):
                continue
            p_customer = str(p.get("customer", "")).strip()
            if p_customer != customer:
                continue
            # Prefer repo-slug style hints (owner/repo) when available from bootstrap terms.
            for term in p.get("match_terms", []) or []:
                raw = str(term).strip().lower()
                if (
                    "/" in raw
                    and not raw.startswith("workspace/")
                    and not raw.startswith("users/")
                    and " " not in raw
                ):
                    if raw not in slug_hints:
                        slug_hints.append(raw)

        # Prioritize the current repo slug for the same owner when available.
        preferred = ""
        owner_key = customer.strip().lower()
        if current_owner and current_repo and owner_key == current_owner:
            current_slug = f"{current_owner}/{current_repo}"
            if current_slug in slug_hints:
                preferred = current_slug
        # If available, prefer the locally most active repo for this owner.
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
    """Return owner summaries from local git repos.

    This is read-only and best-effort. If git commands fail, we simply return
    empty summaries and fall back to static hints.
    """

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
        for _ts, slug in sorted(activity, key=lambda item: item[0], reverse=True):
            if slug in seen:
                continue
            seen.add(slug)
            ranked.append((_ts, slug))
            if len(ranked) >= 15:
                break
        owner_top_activity[owner] = ranked
    return owner_counts, owner_best_slug, owner_top_activity


def _candidate_projects_for_customer_mapping(projects: list[dict[str, Any]]) -> list[str]:
    candidates: list[str] = []
    for p in projects:
        name = str(p.get("name", "")).strip()
        if not name:
            continue
        customer = str(p.get("customer", "")).strip()
        default_client = str(p.get("default_client", "")).strip()
        # Heuristic: rows with empty customer/default_client or placeholder customer=name
        # are likely unresolved and worth confirming in onboarding.
        unresolved = (
            not customer
            or customer.lower() == name.lower()
            or not default_client
        )
        if unresolved and name not in candidates:
            candidates.append(name)
    return candidates


def _select_candidate_scope(candidates: list[str]) -> list[str]:
    if not candidates:
        return []
    if len(candidates) <= 8:
        return candidates
    mode = questionary.select(
        "How many project candidates do you want to map now?",
        choices=[
            "Map first 8 (recommended)",
            "Map all",
            "Pick specific projects...",
            "Cancel setup",
        ],
        default="Map first 8 (recommended)",
    ).ask()
    if mode == "Cancel setup":
        raise KeyboardInterrupt("setup cancelled by user")
    if mode == "Map all":
        return candidates
    if mode == "Pick specific projects...":
        picked = questionary.checkbox(
            "Select project candidates to map now:",
            choices=candidates,
        ).ask()
        return [str(item) for item in (picked or [])]
    return candidates[:8]


def _print_customer_candidates_table(console, projects: list[dict[str, Any]], existing_customers: list[str]) -> None:
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


def _ask_customer_list(
    console,
    projects: list[dict[str, Any]],
    existing_customers: list[str],
    *,
    initial_customers: list[str] | None = None,
) -> list[str]:
    # Start empty by default for first-time UX; detected candidates are shown as hints only.
    current: list[str] = list(initial_customers or [])
    while True:
        if existing_customers:
            _print_customer_candidates_table(console, projects, existing_customers)
        console.print("Domains give the strongest matching signal.")
        console.print("Examples: acme.com, northwind.io, summithealth.co")
        raw = questionary.text(
            "Name your customers or customer domains (comma-separated):",
            default=", ".join(current) if current else "",
        ).ask()
        values = [part.strip() for part in (raw or "").split(",") if part and part.strip()]
        deduped: list[str] = []
        for value in values:
            if value not in deduped:
                deduped.append(value)
        if not deduped:
            action = questionary.select(
                "No customers entered.",
                choices=["Try again", "Skip this step", "Cancel setup"],
                default="Try again",
            ).ask()
            if action == "Cancel setup":
                raise KeyboardInterrupt("setup cancelled by user")
            if action == "Skip this step":
                return []
            current = []
            continue
        confirm = questionary.select(
            "Use this customer list?",
            choices=["Continue", "Edit list", "Cancel setup"],
            default="Continue",
        ).ask()
        if confirm == "Cancel setup":
            raise KeyboardInterrupt("setup cancelled by user")
        if confirm == "Edit list":
            current = deduped
            continue
        return deduped


def _apply_customer_to_projects(payload: dict[str, Any], *, customer_label: str, project_names: list[str]) -> int:
    projects = payload.get("projects", [])
    if not isinstance(projects, list):
        return 0
    target_names = {name.strip().lower() for name in project_names if name.strip()}
    if not target_names:
        return 0
    updated = 0
    for p in projects:
        if not isinstance(p, dict):
            continue
        name = str(p.get("name", "")).strip()
        if not name or name.strip().lower() not in target_names:
            continue
        if not str(p.get("project_id", "")).strip():
            p["project_id"] = _slug(name) or name
        if not str(p.get("canonical_project", "")).strip():
            p["canonical_project"] = str(p.get("project_id", "")).strip() or name
        p["customer"] = customer_label
        if not str(p.get("default_client", "")).strip():
            p["default_client"] = customer_label
        updated += 1
    return updated


def run_project_identity_wizard(console, *, config_path: Path, dry_run: bool) -> None:
    payload = load_projects_config_payload(config_path)
    projects = [p for p in payload.get("projects", []) if isinstance(p, dict)]
    if not projects:
        return

    console.print("")
    print_command_hero(console, "setup-project-mapping")
    console.print("")
    console.print(f"[{STYLE_LABEL}]Project mapping setup[/]")
    console.print(f"[{STYLE_MUTED}]Nothing is saved without your approval.[/]")
    proceed = questionary.select(
        "Project mapping step: continue?",
        choices=["Continue", "Skip this step", "Cancel setup"],
        default="Continue",
    ).ask()
    if proceed == "Cancel setup":
        console.print("[yellow]Setup cancelled by user.[/yellow]")
        raise KeyboardInterrupt("setup cancelled by user")
    if proceed == "Skip this step" or not proceed:
        console.print(f"[{STYLE_MUTED}]Skipped this step.[/]")
        return

    collisions = _detect_customer_slug_collisions(projects)
    if collisions:
        console.print("")
        console.print("[yellow]Possible customer duplicates detected.[/yellow]")
        for slug, labels in sorted(collisions.items()):
            console.print(f"[{STYLE_MUTED}]'{slug}':[/] " + " / ".join(labels))
        console.print(f"[{STYLE_MUTED}]Recommendation: pick one spelling per customer.[/]")

    customers = _ask_customer_list(console, projects, _existing_customers(projects))
    if not customers:
        console.print(f"[{STYLE_MUTED}]No customers provided. Skipping this step.[/]")
        return

    candidates = _candidate_projects_for_customer_mapping(projects)
    if not candidates:
        console.print(f"[{STYLE_MUTED}]No unresolved project->customer mappings found. Skipping.[/]")
        return
    candidates = _select_candidate_scope(candidates)
    if not candidates:
        console.print(f"[{STYLE_MUTED}]No candidates selected. Skipping this step.[/]")
        return

    console.print("")
    console.print("[bold]Potential project mappings found.[/bold]")
    console.print(f"[{STYLE_MUTED}]Please confirm each mapping before save.[/]")

    planned_updates: list[tuple[str, list[str]]] = []  # (customer, [project_names...])
    sticky_customer = customers[0] if customers else "Skip"
    total = len(candidates)
    selections: dict[str, str] = {}
    pending_defaults: dict[str, str] = {}
    idx = 0
    while idx < total:
        project_name = candidates[idx]
        project_default = selections.get(project_name, pending_defaults.get(project_name, sticky_customer))
        if project_default not in customers:
            project_default = "Skip"
        action = questionary.select(
            f"Project wizard step {idx + 1} / {total}:\n{project_name} (map to customer)",
            choices=[
                *customers,
                "Create new customer...",
                "Skip",
                "Previous project",
                "Edit customer list...",
                "Cancel setup",
            ],
            default=project_default,
        ).ask()
        if action == "Cancel setup":
            console.print("[yellow]Setup cancelled by user.[/yellow]")
            raise KeyboardInterrupt("setup cancelled by user")
        if action == "Previous project":
            if idx > 0:
                idx -= 1
            continue
        if action == "Edit customer list...":
            # Preserve the current project's suggested value so editing the list
            # does not unexpectedly change the next default for this project.
            if project_name not in selections and project_default != "Skip":
                pending_defaults[project_name] = project_default
            customers = _ask_customer_list(
                console,
                projects,
                _existing_customers(projects),
                initial_customers=customers,
            )
            if not customers:
                console.print(f"[{STYLE_MUTED}]No customers provided. Skipping this step.[/]")
                return
            if sticky_customer not in customers:
                sticky_customer = customers[0]
            resume = questionary.select(
                "Resume mapping where?",
                choices=["Current project", "Previous project"],
                default="Current project",
            ).ask()
            if resume == "Previous project" and idx > 0:
                idx -= 1
            continue
        if not action or action == "Skip":
            selections[project_name] = "Skip"
            idx += 1
            continue
        if action == "Create new customer...":
            created = (questionary.text("Customer name:", default="").ask() or "").strip()
            if not created:
                continue
            if created not in customers:
                customers.append(created)
            selections[project_name] = created
            sticky_customer = created
            idx += 1
            continue
        selections[project_name] = str(action)
        sticky_customer = str(action)
        idx += 1

    for project_name in candidates:
        customer_choice = selections.get(project_name, "Skip")
        if customer_choice == "Skip":
            continue
        planned_updates.append((customer_choice, [project_name]))

    if not planned_updates:
        console.print(f"[{STYLE_MUTED}]No mappings selected. Nothing to save.[/]")
        return

    console.print("")
    console.print("[bold]I will update[/bold]")
    for customer_label, project_names in planned_updates:
        console.print(f"  - {customer_label} -> {', '.join(project_names)}")
    if dry_run:
        console.print("[yellow]Dry run:[/yellow] would update customer mapping fields in your project config.")
        return

    should_save = questionary.select(
        "Save these mapping updates?",
        choices=["Save", "Go back (discard)", "Cancel setup"],
        default="Save",
    ).ask()
    if should_save == "Cancel setup":
        console.print("[yellow]Setup cancelled by user.[/yellow]")
        raise KeyboardInterrupt("setup cancelled by user")
    if should_save != "Save":
        console.print(f"[{STYLE_MUTED}]Cancelled. No changes were saved.[/]")
        return

    updated = 0
    for customer_label, project_names in planned_updates:
        updated += _apply_customer_to_projects(payload, customer_label=customer_label, project_names=project_names)

    if updated:
        backup_projects_config_if_exists(config_path)
        save_projects_config_payload(config_path, payload)
        console.print(f"[green]Saved.[/green] Updated {updated} project(s).")
    else:
        console.print(f"[{STYLE_MUTED}]No projects were updated.[/]")

