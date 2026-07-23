"""Setup step: evidence mapping (Lovable/titles/repos) then customer->project identity."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable

import questionary

from core.config import (
    backup_projects_config_if_exists,
    load_projects_config_payload,
    save_projects_config_payload,
)
from core.mapping_assistant import reload_projects_after_evidence_mapping
from core.setup_project_identity_batch import collect_batch_mappings
from core.setup_project_identity_candidates import (
    customer_identity_key as _customer_identity_key,
    print_customer_candidates_table,
    project_correctly_linked_to_customer,
    project_stem_matches_customer,
)
from outputs.cli_heroes import print_command_hero
from outputs.terminal_theme import STYLE_LABEL, STYLE_MUTED


def _ux_alpha_key(value: str) -> tuple[str, str]:
    return (str(value).casefold(), str(value))


def _slug(text: str) -> str:
    clean = re.sub(r"[^a-z0-9]+", "-", (text or "").strip().lower()).strip("-")
    return clean


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
    # Prefer domain-shaped labels when ranking (strongest matching signal).
    curated: list[str] = []
    seen_keys: set[str] = set()
    for p in projects:
        name = str(p.get("name", "")).strip()
        customer = str(p.get("customer", "")).strip()
        if not customer:
            continue
        if customer.lower() == name.lower():
            continue
        key = _customer_identity_key(customer)
        if not key or key in seen_keys:
            continue
        curated.append(customer)
        seen_keys.add(key)
    if curated:
        return sorted(curated, key=lambda value: (0 if "." in value else 1, value.casefold(), value))
    any_customers: list[str] = []
    seen_keys = set()
    for p in projects:
        customer = str(p.get("customer", "")).strip()
        if not customer:
            continue
        key = _customer_identity_key(customer)
        if not key or key in seen_keys:
            continue
        any_customers.append(customer)
        seen_keys.add(key)
    return sorted(any_customers, key=lambda value: (0 if "." in value else 1, value.casefold(), value))


def _candidate_projects_for_customer_mapping(
    projects: list[dict[str, Any]],
    customers: list[str] | None = None,
) -> list[str]:
    candidates: list[str] = []
    for p in projects:
        name = str(p.get("name", "")).strip()
        if not name:
            continue
        customer = str(p.get("customer", "")).strip()
        default_client = str(p.get("default_client", "")).strip()
        unresolved = not customer or customer.lower() == name.lower() or not default_client
        if unresolved and name not in candidates:
            candidates.append(name)

    for customer_label in customers or []:
        for p in projects:
            if not isinstance(p, dict):
                continue
            name = str(p.get("name", "")).strip()
            if not name or name in candidates:
                continue
            if project_correctly_linked_to_customer(p, customer_label):
                continue
            if project_stem_matches_customer(name, customer_label):
                candidates.append(name)
    return sorted(candidates, key=_ux_alpha_key)


def _select_candidate_scope(candidates: list[str]) -> list[str]:
    if not candidates:
        return []
    if len(candidates) <= 8:
        return candidates
    mode = questionary.select(
        "How many project candidates do you want to map now?",
        choices=["Map all", "Pick specific projects...", "Cancel setup"],
        default="Map all",
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
    return candidates


def _ask_customer_list(
    console,
    projects: list[dict[str, Any]],
    existing_customers: list[str],
    *,
    initial_customers: list[str] | None = None,
) -> list[str]:
    current: list[str] = list(initial_customers or [])
    while True:
        if existing_customers:
            print_customer_candidates_table(console, projects, existing_customers)
        console.print("Domains give the strongest matching signal.")
        console.print("Examples: acme.com, northwind.io, summithealth.co")
        raw = questionary.text(
            "Name your customers or customer domains (comma-separated):",
            default=", ".join(current) if current else "",
        ).ask()
        values = [part.strip() for part in (raw or "").split(",") if part and part.strip()]

        deduped: list[str] = []
        seen_keys: set[str] = set()
        for value in values:
            key = _customer_identity_key(value)
            if not key or key in seen_keys:
                continue
            deduped.append(value)
            seen_keys.add(key)
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


def _collect_batch_mappings(
    console,
    *,
    projects: list[dict[str, Any]],
    candidates: list[str],
    customers: list[str],
) -> tuple[list[str], dict[str, str | None]]:
    return collect_batch_mappings(
        console,
        projects=projects,
        candidates=candidates,
        customers=customers,
        ask_customer_list=_ask_customer_list,
        existing_customers=_existing_customers,
    )


def run_project_identity_wizard(console, *, config_path: Path, dry_run: bool) -> str:
    payload = load_projects_config_payload(config_path)
    projects = [p for p in payload.get("projects", []) if isinstance(p, dict)]
    if not projects:
        return "No projects"

    console.print()
    print_command_hero(console, "setup:project-mapping")
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
        return "Skip this step"

    projects = reload_projects_after_evidence_mapping(console, config_path=config_path, dry_run=dry_run)

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
        return "No customers provided"

    candidates = _candidate_projects_for_customer_mapping(projects, customers=customers)
    if not candidates:
        console.print(f"[{STYLE_MUTED}]No unresolved project->customer mappings found. Skipping.[/]")
        return "No unresolved mappings"
    candidates = _select_candidate_scope(candidates)
    if not candidates:
        console.print(f"[{STYLE_MUTED}]No candidates selected. Skipping this step.[/]")
        return "No candidates selected"

    console.print("")
    console.print("[bold]Potential project mappings found.[/bold]")
    console.print(f"[{STYLE_MUTED}]Batch map projects with checkboxes before save.[/]")

    planned_updates: list[tuple[str, list[str]]] = []
    _, selections = _collect_batch_mappings(
        console,
        projects=projects,
        candidates=candidates,
        customers=customers,
    )
    if not selections:
        console.print(f"[{STYLE_MUTED}]No mappings selected. Nothing to save.[/]")
        return "No mappings selected"

    for project_name, customer_choice in selections.items():
        if customer_choice is None:
            continue
        planned_updates.append((customer_choice, [project_name]))

    if not planned_updates:
        console.print(f"[{STYLE_MUTED}]No mappings selected. Nothing to save.[/]")
        return "No mappings selected"

    console.print("")
    console.print("[bold]I will update[/bold]")
    for customer_label, project_names in planned_updates:
        console.print(f"  - {customer_label} -> {', '.join(project_names)}")
    if dry_run:
        console.print("[yellow]Dry run:[/yellow] would update customer mapping fields in your project config.")
        return "Confirmed (dry-run)"

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
        return "Nothing to save"

    updated = 0
    for customer_label, project_names in planned_updates:
        updated += _apply_customer_to_projects(payload, customer_label=customer_label, project_names=project_names)

    if updated:
        backup_projects_config_if_exists(config_path)
        save_projects_config_payload(config_path, payload)
        console.print(f"[green]Saved.[/green] Updated {updated} project(s).")
        return "Confirmed"
    console.print(f"[{STYLE_MUTED}]No projects were updated.[/]")
    return "Nothing to save"
