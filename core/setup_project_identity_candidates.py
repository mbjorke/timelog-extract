"""Helpers for setup project-identity customer candidate discovery/rendering."""

from __future__ import annotations

import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rich import box
from rich.table import Table

from core.git_project_bootstrap import (
    discover_git_project_hints,
    discover_local_git_repos,
    parse_github_origin,
)
from outputs.terminal_theme import STYLE_BORDER, STYLE_LABEL, STYLE_MUTED


def _compact_identity(text: str) -> str:
    return "".join(ch for ch in (text or "").lower() if ch.isalnum())


def customer_identity_key(value: str) -> str:
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
    return _compact_identity(s)


def project_stem_matches_customer(project_name: str, customer: str) -> bool:
    """True when a project name/slug clearly belongs to a customer domain/label."""
    cust_key = customer_identity_key(customer)
    if not cust_key or len(cust_key) < 3:
        return False
    name = str(project_name or "").strip()
    if not name:
        return False
    name_key = customer_identity_key(name)
    if name_key == cust_key:
        return True
    # Token / prefix: "customer-a-web" for "customer-a.test", "acme-api" for "acme.com".
    compact_name = _compact_identity(name)
    if compact_name == cust_key or compact_name.startswith(cust_key):
        return True
    slug_tokens = [t for t in re.split(r"[^a-z0-9]+", name.lower()) if t]
    return cust_key in slug_tokens


def project_correctly_linked_to_customer(project: dict[str, Any], customer: str) -> bool:
    """True when customer + default_client already point at this customer (non-placeholder)."""
    name = str(project.get("name", "")).strip()
    cust = str(project.get("customer", "")).strip()
    default_client = str(project.get("default_client", "")).strip()
    if not name or not cust or not default_client:
        return False
    if cust.lower() == name.lower():
        return False
    key = customer_identity_key(customer)
    if not key:
        return False
    return customer_identity_key(cust) == key and customer_identity_key(default_client) == key


def batch_choices_for_customer(
    projects: list[dict[str, Any]],
    *,
    customer: str,
    unresolved: list[str],
) -> tuple[list[str], list[str], list[str]]:
    """
    Build checkbox choices for one customer batch-mapping step.

    Returns (choices_ordered, suggested_names, already_linked_names).

    Stem-matching projects for this customer are offered even when the global
    unresolved pool excluded them (e.g. linked to a different customer). Projects
    already correctly linked to this customer are listed separately for the UI;
    they are still included in choices (pre-checked) so the natural match is visible.
    """
    by_name: dict[str, dict[str, Any]] = {}
    for project in projects:
        if not isinstance(project, dict):
            continue
        name = str(project.get("name", "")).strip()
        if name and name not in by_name:
            by_name[name] = project

    already_linked = sorted(
        [
            name
            for name, project in by_name.items()
            if project_correctly_linked_to_customer(project, customer)
        ],
        key=lambda value: (value.casefold(), value),
    )
    already_set = set(already_linked)

    suggested: list[str] = []
    seen: set[str] = set()
    for name, project in by_name.items():
        if name in already_set:
            continue
        if not project_stem_matches_customer(name, customer):
            continue
        if project_correctly_linked_to_customer(project, customer):
            continue
        suggested.append(name)
        seen.add(name)
    # Unresolved stem matches (may already be in suggested via by_name scan).
    for name in unresolved:
        if name in already_set or name in seen:
            continue
        if project_stem_matches_customer(name, customer):
            suggested.append(name)
            seen.add(name)
    suggested = sorted(suggested, key=lambda value: (value.casefold(), value))

    other = sorted(
        [name for name in unresolved if name not in seen and name not in already_set],
        key=lambda value: (value.casefold(), value),
    )
    # When the customer has a clear stem/already-linked signal, only offer those
    # projects — do not dump unrelated unresolved leftovers into the checkbox.
    if already_linked or suggested:
        choices = [*already_linked, *suggested]
    else:
        choices = other
    return choices, suggested, already_linked


def _slug_activity_ts(slug: str, owner_top_activity: dict[str, list[tuple[int, str]]]) -> int:
    owner = slug.split("/", 1)[0].strip().lower()
    for ts, item in owner_top_activity.get(owner, []):
        if item == slug:
            return int(ts)
    return 0


def _customer_owns_github_owner(customer: str, owner: str) -> bool:
    """True when customer label identity matches the GitHub owner (not a shared personal org)."""
    cust_key = customer_identity_key(customer)
    owner_key = customer_identity_key(owner)
    return bool(cust_key and owner_key and cust_key == owner_key)


def _normalize_github_slug_hint(term: str) -> str:
    raw = str(term or "").strip().lower()
    if not raw:
        return ""
    # Ignore filesystem-like paths that can contain "/users/..." and would
    # otherwise be rendered as fake github.com slugs.
    trimmed = raw
    if trimmed.startswith("http://"):
        trimmed = trimmed[len("http://") :]
    elif trimmed.startswith("https://"):
        trimmed = trimmed[len("https://") :]
    if trimmed.startswith("www."):
        trimmed = trimmed[len("www.") :]
    if trimmed.startswith("github.com"):
        remainder = trimmed[len("github.com") :]
        if remainder.startswith("/"):
            trimmed = remainder
        elif not remainder:
            trimmed = ""
        else:
            return ""
    trimmed = trimmed.split("?", 1)[0].split("#", 1)[0].strip().strip("/")
    if trimmed.startswith(("users/", "workspace/", "private/", "var/", "tmp/", "opt/", "home/")):
        return ""
    if " " in trimmed or ":" in trimmed:
        return ""
    parts = [part.strip() for part in trimmed.split("/") if part.strip()]
    if len(parts) != 2:
        return ""
    owner, repo = parts
    if repo.endswith(".git"):
        repo = repo[:-4]
    if not owner or not repo:
        return ""
    return f"{owner}/{repo}"


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
        repos.extend(discover_local_git_repos(root_resolved, max_depth=4, limit=None))

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


def _customer_slug_hints(projects: list[dict[str, Any]], customer: str) -> list[str]:
    slug_hints: list[str] = []
    for project in projects:
        if not isinstance(project, dict):
            continue
        if str(project.get("customer", "")).strip() != customer:
            continue
        for term in project.get("match_terms", []) or []:
            slug = _normalize_github_slug_hint(str(term))
            if slug and slug not in slug_hints:
                slug_hints.append(slug)
    return slug_hints


def _customer_candidate_rows(projects: list[dict[str, Any]], customers: list[str]) -> list[tuple[str, str, str, str]]:
    """
    Build hint rows for detected customers.

    Domains are the strongest signal. Do not attribute a shared personal GitHub
    owner's full local repo dump to every customer that happens to reference one
    of that owner's slugs — that makes unrelated customers look identical.
    """
    owner_counts, owner_best_slug, owner_top_activity = _local_owner_activity_summary()
    current_hint = discover_git_project_hints(Path.cwd())
    current_owner = (current_hint.remote_owner or "").strip().lower() if current_hint else ""
    current_repo = (current_hint.remote_repo or "").strip().lower() if current_hint else ""

    hints_by_customer = {customer: _customer_slug_hints(projects, customer) for customer in customers}
    owner_customer_claims: dict[str, set[str]] = {}
    for customer, hints in hints_by_customer.items():
        for slug in hints:
            owner = slug.split("/", 1)[0].strip().lower()
            if owner:
                owner_customer_claims.setdefault(owner, set()).add(customer)

    rows: list[tuple[str, str, str, str]] = []
    for customer in sorted(customers, key=lambda value: (str(value).casefold(), str(value))):
        slug_hints = list(hints_by_customer.get(customer, []))
        preferred = ""
        owner_key = ""
        expand_owner_activity = False

        if slug_hints:
            owners = {slug.split("/", 1)[0].strip().lower() for slug in slug_hints if "/" in slug}
            # Prefer an owner that belongs to this customer label; else first hint owner.
            matched_owners = [owner for owner in sorted(owners) if _customer_owns_github_owner(customer, owner)]
            owner_key = matched_owners[0] if matched_owners else next(iter(sorted(owners)), "")
            shared = len(owner_customer_claims.get(owner_key, set())) > 1
            expand_owner_activity = bool(matched_owners) or (bool(owner_key) and not shared)
            if current_owner and current_repo and owner_key == current_owner:
                current_slug = f"{current_owner}/{current_repo}"
                if current_slug in slug_hints:
                    preferred = current_slug
            if not preferred and expand_owner_activity and owner_key in owner_best_slug:
                preferred = owner_best_slug[owner_key]
            if not preferred:
                preferred = slug_hints[0]
        else:
            # Domain stem may match a GitHub owner — only expand when exclusive.
            stem = customer_identity_key(customer)
            if stem and stem in owner_best_slug:
                owner_key = stem
                shared = len(owner_customer_claims.get(owner_key, set())) > 1
                # Bare stem with no project hints: allow activity only when owner isn't
                # already claimed by other customers' match_terms.
                if not shared:
                    expand_owner_activity = True
                    preferred = owner_best_slug[owner_key]

        if not preferred:
            rows.append((customer, "n/a", "n/a", "n/a"))
            continue

        if expand_owner_activity and owner_key:
            count = max(len(slug_hints), owner_counts.get(owner_key, 0))
            top_pairs = list(owner_top_activity.get(owner_key, []))
            if not top_pairs:
                top_pairs = [(0, preferred)]
            if current_owner and current_repo and owner_key == current_owner:
                current_slug = f"{current_owner}/{current_repo}"
                filtered = [(ts, slug) for ts, slug in top_pairs if slug != current_slug]
                current_ts = _git_last_commit_epoch(Path.cwd())
                top_pairs = [(current_ts, current_slug), *filtered]
        else:
            # Customer-specific hints only — avoids duplicate personal-repo walls.
            ranked = sorted(
                slug_hints,
                key=lambda slug: (-_slug_activity_ts(slug, owner_top_activity), slug),
            )
            top_pairs = [(_slug_activity_ts(slug, owner_top_activity), slug) for slug in ranked]
            count = len(slug_hints)

        shown_pairs = top_pairs[:15]
        top_lines = [f"{_activity_dot(ts)} github.com/{slug.lstrip('/')}" for ts, slug in shown_pairs]
        most_active = f"github.com/{preferred.lstrip('/')}"
        rows.append((customer, str(count), most_active, "\n".join(top_lines) if top_lines else "n/a"))
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
