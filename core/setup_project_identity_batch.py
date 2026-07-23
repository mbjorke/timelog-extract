"""Batch customer→project mapping prompts for setup project-identity."""

from __future__ import annotations

from typing import Any, Callable

import questionary
from rich.panel import Panel

from core.setup_project_identity_candidates import (
    batch_choices_for_customer,
    customer_identity_key,
)
from outputs.terminal_theme import STYLE_BORDER, STYLE_LABEL, STYLE_MUTED


def _ux_alpha_key(value: str) -> tuple[str, str]:
    return (str(value).casefold(), str(value))


def _print_project_selection_frame(
    console,
    *,
    customer_label: str,
    choices: list[str],
    suggested: list[str] | None = None,
    already_linked: list[str] | None = None,
) -> None:
    shown_limit = 14
    suggested_set = set(suggested or [])
    already_set = set(already_linked or [])
    shown = choices[:shown_limit]
    body_lines = [
        f"[{STYLE_MUTED}]Customer:[/] [{STYLE_LABEL}]{customer_label}[/]",
        f"[{STYLE_MUTED}]Candidates:[/] {len(choices)}",
        f"[{STYLE_MUTED}]Use:[/] <space> select, <a> toggle all, <i> invert, <enter> confirm",
        "",
    ]
    if already_linked:
        preview = ", ".join(already_linked[:8]) + ("…" if len(already_linked) > 8 else "")
        body_lines.append(f"[{STYLE_MUTED}]Already mapped:[/] {preview}")
        body_lines.append("")
    for name in shown:
        if name in already_set:
            marker = f"[{STYLE_MUTED}](already mapped)[/]"
        elif name in suggested_set:
            marker = f"[{STYLE_MUTED}](suggested)[/]"
        else:
            marker = ""
        suffix = f" {marker}" if marker else ""
        body_lines.append(f"  - [yellow]{name}[/yellow]{suffix}")
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


def pick_projects_with_helpers(
    console,
    *,
    customer_label: str,
    prompt: str,
    unresolved: list[str],
    projects: list[dict[str, Any]] | None = None,
    rank_for_customer: bool = False,
) -> list[str] | None:
    suggested: list[str] = []
    already_linked: list[str] = []
    if rank_for_customer and projects is not None:
        choices, suggested, already_linked = batch_choices_for_customer(
            projects,
            customer=customer_label,
            unresolved=unresolved,
        )
        if not choices:
            if already_linked:
                console.print(
                    f"[{STYLE_MUTED}]Already mapped to {customer_label}:[/] " + ", ".join(already_linked)
                )
            return []
        already_set = set(already_linked)
        suggested_set = set(suggested)
        if already_set or suggested_set:
            checkbox_choices = [
                questionary.Choice(
                    title=(f"{name} (already mapped)" if name in already_set else name),
                    value=name,
                    checked=(name in already_set or name in suggested_set),
                )
                for name in choices
            ]
        else:
            # No customer-specific signal — plain unresolved list (legacy UX / tests).
            checkbox_choices = choices
    else:
        if not unresolved:
            return []
        choices = sorted(unresolved, key=_ux_alpha_key)
        checkbox_choices = choices
    _print_project_selection_frame(
        console,
        customer_label=customer_label,
        choices=choices,
        suggested=suggested,
        already_linked=already_linked,
    )
    picked = questionary.checkbox(prompt, choices=checkbox_choices).ask()
    if picked is None:
        return None
    return [str(item) for item in (picked or [])]


def collect_batch_mappings(
    console,
    *,
    projects: list[dict[str, Any]],
    candidates: list[str],
    customers: list[str],
    ask_customer_list: Callable[..., list[str]],
    existing_customers: Callable[[list[dict[str, Any]]], list[str]],
) -> tuple[list[str], dict[str, str | None]]:
    action_create = ("action", "create_customer")
    action_edit = ("action", "edit_customers")
    action_skip = ("action", "skip_projects")
    action_finish = ("action", "finish_mapping")
    action_cancel = ("action", "cancel_setup")
    # Legacy sentinels remain accepted for test mocks and old scripted flows.
    legacy_action_create = "__create_customer__"
    legacy_action_edit = "__edit_customers__"
    legacy_action_skip = "__skip_projects__"
    legacy_action_finish = "__finish_mapping__"
    legacy_action_cancel = "__cancel_setup__"
    skip_assignment = None

    def _short_preview(items: list[str], *, limit: int = 6) -> str:
        items_sorted = sorted(items, key=_ux_alpha_key)
        shown = ", ".join(items_sorted[:limit])
        if len(items_sorted) <= limit:
            return shown
        return f"{shown}, … +{len(items_sorted) - limit} more"

    assignments: dict[str, str | None] = {}
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
        if action in {action_cancel, legacy_action_cancel}:
            console.print("[yellow]Setup cancelled by user.[/yellow]")
            raise KeyboardInterrupt("setup cancelled by user")
        if action in {action_finish, legacy_action_finish}:
            break
        if action in {action_edit, legacy_action_edit}:
            customers = ask_customer_list(
                console,
                projects,
                existing_customers(projects),
                initial_customers=customers,
            )
            if not customers:
                console.print(f"[{STYLE_MUTED}]No customers provided. Skipping this step.[/]")
                return [], {}
            if sticky_customer not in customers:
                sticky_customer = customers[0]
            continue
        if action in {action_create, legacy_action_create}:
            created = (questionary.text("Customer name:", default="").ask() or "").strip()
            if not created:
                continue
            created_key = customer_identity_key(created)
            existing = next(
                (value for value in customers if customer_identity_key(value) == created_key),
                None,
            )
            canonical = existing or created
            if existing is None:
                customers.append(canonical)
                customers = sorted(customers, key=_ux_alpha_key)
            sticky_customer = canonical
            picked = pick_projects_with_helpers(
                console,
                customer_label=canonical,
                prompt=f"Select project(s) to map to '{canonical}':",
                unresolved=unresolved,
                projects=projects,
                rank_for_customer=True,
            )
            if picked is None:
                continue
            for item in picked:
                assignments[str(item)] = canonical
            console.print(
                f"[{STYLE_MUTED}]Planned:[/] {canonical} <- "
                f"{(_short_preview(picked) if picked else 'no projects selected')}"
            )
            continue
        if action in {action_skip, legacy_action_skip}:
            skipped = pick_projects_with_helpers(
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
                f"[{STYLE_MUTED}]Planned:[/] skip "
                f"{(_short_preview(skipped) if skipped else 'no projects selected')}"
            )
            continue
        customer_choice = str(action)
        sticky_customer = customer_choice
        picked = pick_projects_with_helpers(
            console,
            customer_label=customer_choice,
            prompt=f"Select project(s) to map to '{customer_choice}':",
            unresolved=unresolved,
            projects=projects,
            rank_for_customer=True,
        )
        if picked is None:
            continue
        for item in picked:
            assignments[str(item)] = customer_choice
        console.print(
            f"[{STYLE_MUTED}]Planned:[/] {customer_choice} <- "
            f"{(_short_preview(picked) if picked else 'no projects selected')}"
        )
    return customers, assignments
