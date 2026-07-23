"""Create-project affordance for interactive `gittan review` (#419).

Prefills slug/name from durable evidence (title or path/GitHub slug), writes
``tracked_urls: [url_key]`` plus stable ``match_terms`` from repo/path slug only
(never session titles), after a timestamped config backup.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.cli_triage_map_candidates import UrlCandidate, _is_lovable_project_url_key
from core.config import (
    backup_projects_config_if_exists,
    load_projects_config_payload,
    save_projects_config_payload,
)

_CREATE_LABEL = "+ Create project"
_PARK_LABEL = "Park (not enough evidence)"
_SKIP_LABEL = "Skip this URL key"
_UNTITLED = frozenset({"", "untitled", "-", "—", "–"})
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
_SLUG_CLEAN_RE = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True)
class ReviewCreateProposal:
    """Suggested new profile for a decidable URL candidate."""

    profile_name: str
    match_terms: list[str]
    tracked_urls: list[str]
    display_name: str = ""


@dataclass(frozen=True)
class ReviewCreateResult:
    project_name: str
    backup_path: Path | None


def create_choice_label() -> str:
    return _CREATE_LABEL


def park_choice_label() -> str:
    return _PARK_LABEL


def skip_choice_label() -> str:
    return _SKIP_LABEL


def has_human_title(title: str) -> bool:
    text = str(title or "").strip()
    return bool(text) and text.lower() not in _UNTITLED


def _slugify(text: str) -> str:
    return _SLUG_CLEAN_RE.sub("-", str(text or "").strip().lower()).strip("-")


def _path_segments(url_key: str) -> list[str]:
    return [p for p in str(url_key or "").strip().lower().split("/") if p]


def durable_match_terms_from_url_key(url_key: str) -> list[str]:
    """Stable match_terms from repo/path slug only — never titles or bare UUIDs."""
    key = str(url_key or "").strip().lower()
    if not key or _is_lovable_project_url_key(key):
        return []
    parts = _path_segments(key)
    if not parts:
        return []
    host = parts[0]
    if host == "github.com" and len(parts) >= 3:
        return [f"{parts[1]}/{parts[2]}"]
    if host == "pypi.org" and len(parts) >= 3 and parts[1] == "project":
        return [parts[2]]
    if len(parts) >= 2:
        segment = parts[1]
        if _UUID_RE.match(segment) or len(segment) < 3:
            return []
        return [segment]
    if "." in host and not host.endswith(".lovableproject.com"):
        return [host]
    return []


def suggested_profile_name(row: UrlCandidate) -> str:
    """Prefill profile slug from path/GitHub slug, else human title — never bare UUID."""
    terms = durable_match_terms_from_url_key(row.url_key)
    if terms:
        leaf = terms[0].rsplit("/", 1)[-1]
        if leaf and not _UUID_RE.match(leaf):
            return leaf
    if has_human_title(row.title):
        return _slugify(row.title)
    return ""


def is_decidable_candidate(row: UrlCandidate) -> bool:
    """True when evidence supports map/create — not mere event volume."""
    if has_human_title(row.title):
        return True
    return bool(durable_match_terms_from_url_key(row.url_key))


def propose_create_from_candidate(row: UrlCandidate) -> ReviewCreateProposal | None:
    """Return a create proposal, or None for undecidable / bare-UUID rows."""
    if not is_decidable_candidate(row):
        return None
    name = suggested_profile_name(row)
    if not name:
        return None
    terms = durable_match_terms_from_url_key(row.url_key)
    # Profile slug is a stable identifier; never add the raw session title.
    match_terms = list(terms) if terms else [name]
    display = str(row.title).strip() if has_human_title(row.title) else ""
    return ReviewCreateProposal(
        profile_name=name,
        match_terms=match_terms,
        tracked_urls=[str(row.url_key).strip()],
        display_name=display,
    )


def decidability_sort_key(row: UrlCandidate) -> tuple:
    """Prefer decidable rows; rank by title/events/recency — not impact hours."""
    return (
        0 if is_decidable_candidate(row) else 1,
        0 if has_human_title(row.title) else 1,
        -int(row.events),
        -int(row.days),
        str(row.last_seen or ""),
        str(row.url_key or ""),
    )


def partition_candidates(
    rows: list[UrlCandidate],
) -> tuple[list[UrlCandidate], list[UrlCandidate]]:
    """Split into (decidable approval queue, park / not-enough-evidence)."""
    decidable = [r for r in rows if is_decidable_candidate(r)]
    parked = [r for r in rows if not is_decidable_candidate(r)]
    decidable.sort(key=decidability_sort_key)
    parked.sort(key=decidability_sort_key)
    return decidable, parked


def write_created_project(
    *,
    projects_config: str,
    proposal: ReviewCreateProposal,
    customer: str,
    console: Any | None = None,
) -> Path | None:
    """Backup (if present) then write the new profile. Returns backup path or None."""
    cfg_path = Path(projects_config).expanduser()
    payload = load_projects_config_payload(cfg_path)
    projects = payload.setdefault("projects", [])
    if not isinstance(projects, list):
        raise ValueError("payload.projects must be a list")

    name = proposal.profile_name.strip()
    cleaned_customer = str(customer or "").strip() or name
    cleaned_title = str(proposal.display_name or "").strip()
    aliases = [name]
    if cleaned_title and cleaned_title.lower() != name.lower():
        aliases.append(cleaned_title)

    match_terms = sorted(
        {str(t).strip() for t in proposal.match_terms if str(t).strip()}
    ) or [name]
    tracked = sorted(
        {str(u).strip() for u in proposal.tracked_urls if str(u).strip()}
    )
    projects.append(
        {
            "name": name,
            "project_id": name,
            "customer": cleaned_customer,
            "ticket_mode": "optional",
            "default_client": cleaned_customer,
            "match_terms": match_terms,
            "tracked_urls": tracked,
            "canonical_project": name,
            "aliases": aliases,
            "email": "",
            "invoice_title": cleaned_title,
            "invoice_description": "",
            "enabled": True,
        }
    )
    backup = backup_projects_config_if_exists(cfg_path)
    if backup and console is not None:
        console.print(f"[dim]Backup:[/dim] {backup}")
    save_projects_config_payload(cfg_path, payload)
    if console is not None:
        console.print(
            f"[green]Created project[/green] {name!r} with "
            f"tracked_urls={tracked!r}, match_terms={match_terms!r}."
        )
    return backup


def create_project_interactive(
    console,
    row: UrlCandidate,
    *,
    projects_config: str,
    existing_names: set[str],
) -> ReviewCreateResult | None:
    """Full interactive create: editable prefill → backup → write."""
    import questionary

    proposal = propose_create_from_candidate(row)
    if proposal is None:
        console.print(
            "[yellow]Not enough evidence to create a project for this URL key "
            "(Park or Skip).[/yellow]"
        )
        return None

    console.print(
        f"[dim]Evidence:[/dim] {row.title} | {row.url_key} | "
        f"{row.events} events · last {row.last_seen}"
    )
    console.print(
        f"[dim]Will set tracked_urls:[/dim] {', '.join(proposal.tracked_urls)}"
    )
    console.print(
        f"[dim]Stable match_terms (repo/path slug only):[/dim] "
        f"{', '.join(proposal.match_terms)}"
    )

    name_answer = questionary.text(
        "Project slug / name:",
        default=proposal.profile_name,
    ).ask()
    if name_answer is None:
        return None
    profile_name = str(name_answer).strip()
    if not profile_name:
        console.print("[yellow]Project name cannot be empty.[/yellow]")
        return None
    if profile_name.lower() in {n.lower() for n in existing_names}:
        console.print(
            f"[yellow]'{profile_name}' already exists — map to it instead.[/yellow]"
        )
        return None

    customer_answer = questionary.text("Customer (who you bill):", default="").ask()
    if customer_answer is None:
        return None
    customer = str(customer_answer).strip()
    if not customer:
        console.print("[yellow]Customer cannot be empty.[/yellow]")
        return None

    title_answer = questionary.text(
        "Display name (optional, for invoices):",
        default=proposal.display_name or "",
    ).ask()
    if title_answer is None:
        return None

    terms = list(proposal.match_terms)
    if profile_name.lower() not in {t.lower() for t in terms}:
        terms = [profile_name, *terms]
    final = ReviewCreateProposal(
        profile_name=profile_name,
        match_terms=terms,
        tracked_urls=list(proposal.tracked_urls),
        display_name=str(title_answer).strip(),
    )
    confirmed = questionary.confirm(
        f"Create project {final.profile_name!r} and write to config now?",
        default=True,
    ).ask()
    if not confirmed:
        return None

    backup = write_created_project(
        projects_config=projects_config,
        proposal=final,
        customer=customer,
        console=console,
    )
    return ReviewCreateResult(project_name=final.profile_name, backup_path=backup)
