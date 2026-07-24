"""New GitHub remotes step inside `gittan review` (setup/map evidence UX)."""

from __future__ import annotations

from typing import Any

from core.mapping_assistant import run_interactive_mapping_flow
from core.mapping_review import MappingReview, build_mapping_review
from outputs.terminal_theme import STYLE_DIM, STYLE_LABEL, STYLE_MUTED


def build_review_remote_mapping(
    report,
    *,
    profiles: list[dict] | None = None,
    gh_discovery: bool = True,
) -> MappingReview:
    """Build the same new-remote / duplicate mapping review used by setup/map."""
    events = list(getattr(report, "all_events", None) or getattr(report, "included_events", []) or [])
    resolved_profiles = list(profiles if profiles is not None else (getattr(report, "profiles", []) or []))
    dt_from = getattr(report, "dt_from", None)
    dt_to = getattr(report, "dt_to", None)
    return build_mapping_review(
        events,
        resolved_profiles,
        dt_from=dt_from,
        dt_to=dt_to,
        local_tz=getattr(dt_from, "tzinfo", None) if dt_from else None,
        gh_discovery=gh_discovery,
    )


def new_remote_candidates_payload(review: MappingReview) -> list[dict[str, Any]]:
    """Machine-readable new-remote rows (Lovable UUID parks stay out of this list)."""
    rows: list[dict[str, Any]] = []
    for proposal in review.new_projects:
        rows.append(
            {
                "slug": proposal.slug,
                "suggested_name": proposal.suggested_name,
                "url": proposal.url,
                "local_path": proposal.local_path,
                "created_at": proposal.created_at,
            }
        )
    return rows


def run_review_new_remotes_step(
    console,
    report,
    *,
    projects_config: str,
    profiles: list[dict] | None = None,
) -> int:
    """Offer Add / Map / Skip for new remotes before URL candidates.

    Accepting a choice writes the projects config after a timestamped backup
    (same path as setup evidence mapping).
    """
    review = build_review_remote_mapping(report, profiles=profiles)
    if review.change_count() == 0:
        return 0

    console.print("")
    console.print(f"[{STYLE_LABEL}]New remote repositories[/]")
    console.print(
        f"[{STYLE_MUTED}]Same options as setup/map: Add as new project, "
        "Map to existing, or Skip.[/]"
    )
    console.print(
        f"[{STYLE_DIM}]Accepting Add or Map writes your projects config "
        "(timestamped backup first).[/]"
    )

    return run_interactive_mapping_flow(
        console,
        [],
        list(profiles if profiles is not None else (getattr(report, "profiles", []) or [])),
        projects_config,
        review=review,
    )
