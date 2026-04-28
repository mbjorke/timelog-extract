"""Interactive setup step: reconcile project -> customer mapping safely.

This step is intentionally conservative and safe to run repeatedly:
- It does not invent match_terms.
- It only updates identity/billing fields (customer/default_client/project_id/canonical_project)
  when the user explicitly confirms.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable

import questionary

from core.config import backup_projects_config_if_exists, load_projects_config_payload, save_projects_config_payload
from core.setup_project_identity_candidates import print_customer_candidates_table
from outputs.cli_heroes import print_command_hero
from outputs.terminal_theme import STYLE_LABEL, STYLE_MUTED


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
    print_customer_candidates_table(console, projects, existing_customers)


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

