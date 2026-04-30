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
from rich.panel import Panel

from core.config import backup_projects_config_if_exists, load_projects_config_payload, save_projects_config_payload
from core.setup_project_identity_candidates import print_customer_candidates_table
from outputs.cli_heroes import print_command_hero
from outputs.terminal_theme import STYLE_BORDER, STYLE_LABEL, STYLE_MUTED


def _ux_alpha_key(value: str) -> tuple[str, str]:
    return (str(value).casefold(), str(value))


def _slug(text: str) -> str:
    clean = re.sub(r"[^a-z0-9]+", "-", (text or "").strip().lower()).strip("-")
    return clean


def _compact(text: str) -> str:
    return "".join(ch for ch in (text or "").lower() if ch.isalnum())


def _customer_identity_key(value: str) -> str:
    """
    Best-effort identity key for deduping common customer variants.

    Minimal-risk goal: collapse obvious duplicates users enter/see in onboarding:
    - casing differences: "AX Finans" vs "ax-finans"
    - domain vs bare root: "blueberry.ax" vs "Blueberry"
    """
    s = str(value or "").strip().lower()
    if not s:
        return ""
    # URLs/domains: use the leftmost label (before first dot) as "root".
    if "." in s:
        s = s.split(".", 1)[0].strip()
    # If any path-like value appears, keep only the last segment.
    if "/" in s:
        s = s.rsplit("/", 1)[-1].strip()
    return _compact(s)


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
        return curated
    # Fallback: still list existing customer values if no curated set exists yet.
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
    return sorted(candidates, key=_ux_alpha_key)


def _select_candidate_scope(candidates: list[str]) -> list[str]:
    if not candidates:
        return []
    if len(candidates) <= 8:
        return candidates
    mode = questionary.select(
        "How many project candidates do you want to map now?",
        choices=[
            "Map all",
            "Pick specific projects...",
            "Cancel setup",
        ],
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


def _print_project_selection_frame(console, *, customer_label: str, choices: list[str]) -> None:
    shown_limit = 14
    shown = choices[:shown_limit]
    body_lines = [
        f"[{STYLE_MUTED}]Customer:[/] [{STYLE_LABEL}]{customer_label}[/]",
        f"[{STYLE_MUTED}]Candidates:[/] {len(choices)}",
        f"[{STYLE_MUTED}]Use:[/] <space> select, <a> toggle all, <i> invert, <enter> confirm",
        "",
    ]
    body_lines.extend([f"  - [yellow]{name}[/yellow]" for name in shown])
    if len(choices) > shown_limit:
        body_lines.append(f"[{STYLE_MUTED}]... and {len(choices) - shown_limit} more[/]")
    console.print(
        Panel(
            "\n".join(body_lines),
            title="Project Mapping Selection",
            border_style=STYLE_BORDER,
            title_align="left",
            expand=False,
        )
    )


def _pick_projects_with_helpers(console, *, customer_label: str, prompt: str, unresolved: list[str]) -> list[str] | None:
    if not unresolved:
        return []
    choices = sorted(unresolved, key=_ux_alpha_key)
    _print_project_selection_frame(console, customer_label=customer_label, choices=choices)
    picked = questionary.checkbox(prompt, choices=choices).ask()
    if picked is None:
        return None
    return [str(item) for item in (picked or [])]


def _collect_batch_mappings(
    console,
    *,
    projects: list[dict[str, Any]],
    candidates: list[str],
    customers: list[str],
) -> tuple[list[str], dict[str, str]]:
    action_create = "__create_customer__"
    action_edit = "__edit_customers__"
    action_skip = "__skip_projects__"
    action_finish = "__finish_mapping__"
    action_cancel = "__cancel_setup__"
    skip_assignment = "__skip_assignment__"
    def _short_preview(items: list[str], *, limit: int = 6) -> str:
        items_sorted = sorted(items, key=_ux_alpha_key)
        shown = ", ".join(items_sorted[:limit])
        if len(items_sorted) <= limit:
            return shown
        return f"{shown}, … +{len(items_sorted) - limit} more"

    assignments: dict[str, str] = {}
    total_candidates = len(candidates)
    customers = sorted(customers, key=_ux_alpha_key)
    sticky_customer = customers[0] if customers else ""
    while True:
        unresolved = sorted([name for name in candidates if name not in assignments], key=_ux_alpha_key)
        if not unresolved:
            break
        decided = total_candidates - len(unresolved)
        default_choice = sticky_customer if sticky_customer in customers else customers[0]
        action = questionary.select(
            f"Choose customer for batch mapping (decided {decided}/{total_candidates}, remaining {len(unresolved)}; then select projects with checkboxes):",
            choices=[
                *[questionary.Choice(title=customer, value=customer) for customer in customers],
                questionary.Choice(title="Create new customer...", value=action_create),
                questionary.Choice(title="Edit customer list...", value=action_edit),
                questionary.Choice(title="Skip selected projects...", value=action_skip),
                questionary.Choice(title="Finish mapping", value=action_finish),
                questionary.Choice(title="Cancel setup", value=action_cancel),
            ],
            default=default_choice,
        ).ask()
        if action is None:
            console.print("[yellow]Setup cancelled by user.[/yellow]")
            raise KeyboardInterrupt("setup cancelled by user")
        if action == action_cancel:
            console.print("[yellow]Setup cancelled by user.[/yellow]")
            raise KeyboardInterrupt("setup cancelled by user")
        if action == action_finish:
            break
        if action == action_edit:
            customers = _ask_customer_list(
                console,
                projects,
                _existing_customers(projects),
                initial_customers=customers,
            )
            if not customers:
                console.print(f"[{STYLE_MUTED}]No customers provided. Skipping this step.[/]")
                return [], {}
            if sticky_customer not in customers:
                sticky_customer = customers[0]
            continue
        if action == action_create:
            created = (questionary.text("Customer name:", default="").ask() or "").strip()
            if not created:
                continue
            created_key = _customer_identity_key(created)
            existing = next((value for value in customers if _customer_identity_key(value) == created_key), None)
            canonical = existing or created
            if existing is None:
                customers.append(canonical)
                customers = sorted(customers, key=_ux_alpha_key)
            sticky_customer = canonical
            picked = _pick_projects_with_helpers(
                console,
                customer_label=canonical,
                prompt=f"Select project(s) to map to '{canonical}':",
                unresolved=unresolved,
            )
            if picked is None:
                continue
            for item in picked:
                assignments[str(item)] = canonical
            console.print(
                f"[{STYLE_MUTED}]Planned:[/] {canonical} <- {(_short_preview(picked) if picked else 'no projects selected')}"
            )
            continue
        if action == action_skip:
            skipped = _pick_projects_with_helpers(
                console,
                customer_label="Skip selected projects",
                prompt="Select project(s) to skip for now:",
                unresolved=unresolved,
            )
            if skipped is None:
                continue
            for item in skipped:
                assignments[str(item)] = skip_assignment
            console.print(
                f"[{STYLE_MUTED}]Planned:[/] skip {(_short_preview(skipped) if skipped else 'no projects selected')}"
            )
            continue
        customer_choice = str(action)
        sticky_customer = customer_choice
        picked = _pick_projects_with_helpers(
            console,
            customer_label=customer_choice,
            prompt=f"Select project(s) to map to '{customer_choice}':",
            unresolved=unresolved,
        )
        if picked is None:
            continue
        for item in picked:
            assignments[str(item)] = customer_choice
        console.print(
            f"[{STYLE_MUTED}]Planned:[/] {customer_choice} <- {(_short_preview(picked) if picked else 'no projects selected')}"
        )
    return customers, assignments


def run_project_identity_wizard(console, *, config_path: Path, dry_run: bool) -> str:
    payload = load_projects_config_payload(config_path)
    projects = [p for p in payload.get("projects", []) if isinstance(p, dict)]
    if not projects:
        return "No projects"

    console.print("")
    print_command_hero(console, "setup:project-mapping")
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
        return "Skip this step"

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

    candidates = _candidate_projects_for_customer_mapping(projects)
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

    planned_updates: list[tuple[str, list[str]]] = []  # (customer, [project_names...])
    _, selections = _collect_batch_mappings(
        console,
        projects=projects,
        candidates=candidates,
        customers=customers,
    )
    if not selections:
        console.print(f"[{STYLE_MUTED}]No mappings selected. Nothing to save.[/]")
        return "No mappings selected"

    for project_name in candidates:
        customer_choice = selections.get(project_name, "__skip_assignment__")
        if customer_choice == "__skip_assignment__":
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
    else:
        console.print(f"[{STYLE_MUTED}]No projects were updated.[/]")
        return "Nothing to save"

