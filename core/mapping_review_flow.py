"""Interactive batch UX for `gittan map` mapping review."""

from __future__ import annotations

from core.mapping_review import (
    _CANCEL,
    _STATUS_CANONICAL,
    MappingReview,
    NewProjectProposal,
    ProjectChangeProposal,
    _merge_additions_for_change,
    _merge_removals_for_change,
)


def _print_mapping_cancelled(console) -> None:
    console.print("[yellow]Cancelled — no mapping changes saved.[/yellow]")


def prompt_new_project_fields(
    console,
    *,
    default_profile_name: str,
    existing_names: set[str],
    default_customer: str = "",
) -> tuple[str, str, str] | None:
    """Collect customer and optional display name; slug comes from the repository."""
    import questionary

    slug = str(default_profile_name or "").strip()
    if not slug:
        console.print("[yellow]Could not derive a project slug from the repository.[/yellow]")
        return None
    if slug.lower() in existing_names:
        console.print(
            f"[yellow]'{slug}' is already mapped — use 'Map to existing project' instead.[/yellow]"
        )
        return None

    console.print(f"[dim]Project slug (from repo):[/dim] {slug}")

    customer = ""
    while not customer:
        customer_answer = questionary.text(
            "Customer (who you bill):",
            default="",
        ).ask()
        if customer_answer is None:
            return None
        customer = str(customer_answer).strip() or str(default_customer or "").strip()
        if not customer:
            console.print("[yellow]Customer cannot be empty.[/yellow]")

    title_answer = questionary.text(
        "Display name (optional, for invoices):",
        default="",
    ).ask()
    if title_answer is None:
        return None
    return slug, customer, str(title_answer).strip()


def _print_repo_binding(console, *, dot: str, remote_url: str, local_path: str, status: str) -> None:
    console.print(f"  {dot} Remote: {remote_url}")
    console.print(f"  Local: {local_path} ({status})")


def _print_activity_legend(console) -> None:
    console.print(
        "[dim]Recency dot on the primary duplicate line only[/dim] "
        "([green]● <= 30d[/green], "
        "[yellow]● <= 90d[/yellow], "
        "[red]● > 90d[/red], "
        "[dim]● none in report window[/dim]); "
        "[dim]other variants show ● dim.[/dim]"
    )


def print_mapping_review_summary(console, review: MappingReview) -> None:
    count = review.change_count()
    if not count:
        return
    parts: list[str] = []
    if review.new_projects:
        noun = "repository" if len(review.new_projects) == 1 else "repositories"
        names = ", ".join(proposal.suggested_name for proposal in review.new_projects[:3])
        tail = f" (+{len(review.new_projects) - 3} more)" if len(review.new_projects) > 3 else ""
        parts.append(f"{len(review.new_projects)} new {noun}: {names}{tail}")
    if review.changes:
        label = "duplicate group" if len(review.changes) == 1 else "duplicate groups"
        parts.append(f"{len(review.changes)} {label}")
    console.print(f"\n[bold]Suggested mapping review — {'; '.join(parts)}[/bold]")


def _print_new_project_group(console, proposal: NewProjectProposal) -> None:
    console.print("\n[bold]New remote repository:[/bold]")
    suffix = f" (created at {proposal.created_at})" if proposal.created_at else ""
    _print_repo_binding(
        console,
        dot=proposal.activity_dot,
        remote_url=proposal.url,
        local_path=proposal.local_path,
        status=f"suggested slug: {proposal.suggested_name}{suffix}",
    )


def _print_change_group(console, change: ProjectChangeProposal) -> None:
    customer_label = f" [{change.customer}]" if change.customer else ""
    console.print(f"\n[bold]Suggested changed project[/bold]{customer_label}:")
    _print_repo_binding(
        console,
        dot=change.canonical_activity_dot,
        remote_url=change.canonical_remote_url,
        local_path=change.canonical_local_path,
        status=_STATUS_CANONICAL,
    )
    if change.lines:
        console.print(
            "\n[dim]Merge adds all repo variants to the canonical project and removes "
            "duplicate github slugs from sibling profiles (profiles are kept).[/dim]"
        )
        console.print("\nHow do you want to handle following duplicates?")
        for line in change.lines:
            _print_repo_binding(
                console,
                dot=line.activity_dot,
                remote_url=line.remote_url,
                local_path=line.local_path,
                status=line.status,
            )


def print_mapping_review(console, review: MappingReview) -> None:
    print_mapping_review_summary(console, review)
    for proposal in review.new_projects:
        _print_new_project_group(console, proposal)
    for change in review.changes:
        _print_change_group(console, change)
    if review.changes or review.new_projects:
        console.print("")
        _print_activity_legend(console)


def run_batch_mapping_review(
    console,
    review: MappingReview,
    profiles: list[dict],
    projects_config: str,
) -> int | None:
    import questionary

    if review.change_count() == 0:
        return 0

    print_mapping_review_summary(console, review)
    additions: list[tuple[str, str, str]] = []
    removals: list[tuple[str, str, str]] = []
    existing_names = {
        str(p.get("name") or "").strip().lower()
        for p in profiles
        if str(p.get("name") or "").strip()
    }
    existing = sorted({str(p.get("name") or "").strip() for p in profiles if str(p.get("name") or "").strip()})

    for proposal in review.new_projects:
        _print_new_project_group(console, proposal)
        _print_activity_legend(console)
        choices = ["Add as new project", "Map to existing project", "Skip", _CANCEL]
        answer = questionary.select(
            f"New repo {proposal.url} — how to handle?",
            choices=choices,
            default="Add as new project",
        ).ask()
        if answer is None or answer == _CANCEL:
            _print_mapping_cancelled(console)
            return None
        if answer == "Skip":
            continue
        if answer == "Add as new project":
            fields = prompt_new_project_fields(
                console,
                default_profile_name=proposal.suggested_name,
                existing_names=existing_names,
            )
            if fields is None:
                continue
            profile_name, customer, invoice_title = fields
            additions.append((profile_name, "match_terms", proposal.slug, customer, invoice_title))
            if proposal.suggested_name and proposal.suggested_name != proposal.slug:
                additions.append((profile_name, "match_terms", proposal.suggested_name))
            existing_names.add(profile_name.lower())
            existing.append(profile_name)
            continue
        target = questionary.select(
            "Map to which project?",
            choices=existing + ["Skip", _CANCEL],
        ).ask()
        if target is None or target == _CANCEL:
            _print_mapping_cancelled(console)
            return None
        if target and target != "Skip":
            additions.append((target, "match_terms", proposal.slug))

    for change in review.changes:
        _print_change_group(console, change)
        _print_activity_legend(console)
        label = f"{change.customer} → {change.target_project}" if change.customer else change.target_project
        answer = questionary.select(
            f"Duplicates for {label}",
            choices=["Merge (default)", "Skip", _CANCEL],
            default="Merge (default)",
        ).ask()
        if answer is None or answer == _CANCEL:
            _print_mapping_cancelled(console)
            return None
        if answer == "Skip":
            continue
        if answer == "Merge (default)":
            additions.extend(_merge_additions_for_change(change))
            removals.extend(_merge_removals_for_change(change, profiles))

    if not additions and not removals:
        return 0

    from core.mapping_assistant import apply_mapping_changes

    return apply_mapping_changes(console, additions, removals, projects_config)
