"""Batch project-mapping review — git-local remote bindings and activity."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from core.gh_repo_discovery import collect_gh_repo_list_data
from core.github_slug_activity import (
    collect_slug_activity_from_events,
    github_sourced_slugs_from_events,
)
from core.github_slug_match import (
    cluster_repo_families,
    expand_repo_family,
    github_repo_stem,
    is_hash_like_repo_name,
    is_new_github_repo_candidate,
    is_plausible_github_slug,
    profile_configured_github_slugs,
    profile_for_github_slug,
    profile_match_term_github_slugs,
    split_github_slug,
)
from core.map_repo_hints import github_create_times_from_events
from core.mapping_repo_status import (
    SlugGitBinding,
    activity_dot,
    binding_activity_epoch,
    binding_for_slug,
    binding_has_local_clone,
    enrich_bindings_with_remote_activity,
    git_activity_score,
    index_local_slug_bindings,
    pick_active_slug_by_git,
    slug_has_git_evidence,
    slug_to_remote_url,
)
from core.setup_project_identity_candidates import _normalize_github_slug_hint

_STATUS_CANONICAL = "Canonical billing repo"
_CANCEL = "Cancel..."


def _normalize_customer(value: str) -> str:
    return str(value or "").strip().lower()


def customer_for_github_slug(slug: str, profiles: list[dict]) -> str:
    project = profile_for_github_slug(slug, profiles)
    if not project:
        return ""
    for profile in profiles:
        if str(profile.get("name") or "").strip() == project:
            return str(profile.get("customer") or "").strip()
    return ""


def merge_target_for_customer(customer: str, profiles: list[dict]) -> str:
    """Primary billing project for a customer (non-dev profile whose name matches canonical_project)."""
    key = _normalize_customer(customer)
    if not key:
        return ""
    rows = [profile for profile in profiles if _normalize_customer(profile.get("customer")) == key]
    if not rows:
        return ""
    for profile in rows:
        name = str(profile.get("name") or "").strip()
        canon = str(profile.get("canonical_project") or name).strip()
        if name and name == canon and not name.endswith("-dev"):
            return name
    names = sorted(
        {str(profile.get("name") or "").strip() for profile in rows if str(profile.get("name") or "").strip()},
        key=lambda item: (item.endswith("-dev"), len(item), item.lower()),
    )
    return names[0] if names else customer


def slug_to_github_url(slug: str) -> str:
    return slug_to_remote_url(slug)


def _github_slugs_on_named_profile(profile_name: str, profiles: list[dict]) -> set[str]:
    for profile in profiles:
        if str(profile.get("name") or "").strip() == profile_name:
            return profile_match_term_github_slugs(profile)
    return set()


def _sibling_profiles_hold_family_github_slug(
    customer: str,
    merge_target: str,
    family_slugs: set[str],
    profiles: list[dict],
) -> bool:
    """True when a sibling profile still owns a github slug in the same repo family."""
    from core.github_slug_match import same_repo_family

    customer_key = _normalize_customer(customer)
    for profile in profiles:
        name = str(profile.get("name") or "").strip()
        if not name or name == merge_target:
            continue
        if _normalize_customer(profile.get("customer")) != customer_key:
            continue
        for term in profile.get("match_terms") or []:
            norm = _normalize_github_slug_hint(str(term or "").strip())
            if not norm or not is_plausible_github_slug(norm):
                continue
            if any(same_repo_family(norm, slug) for slug in family_slugs):
                return True
    return False


def _duplicate_group_needs_review(
    merge_target: str,
    review_slugs: set[str],
    configured_all: set[str],
    bindings: dict[str, SlugGitBinding],
    activity: dict[str, int],
    customer: str,
    profiles: list[dict],
) -> bool:
    """Review only while family slugs are missing from the billing project or live on siblings."""
    relevant = {
        slug
        for slug in review_slugs
        if slug in configured_all
        or slug_has_git_evidence(slug, bindings)
        or int(activity.get(slug, 0)) >= 1
    }
    if len(relevant) < 2:
        return False
    merge_target_slugs = _github_slugs_on_named_profile(merge_target, profiles)
    if not relevant.issubset(merge_target_slugs):
        return True
    return _sibling_profiles_hold_family_github_slug(customer, merge_target, relevant, profiles)


def _pick_canonical_slug(project: str, slugs: set[str], bindings: dict[str, SlugGitBinding]) -> str:
    project_lower = project.lower()
    exact = [s for s in slugs if s.split("/", 1)[-1] == project_lower]
    if exact:
        return sorted(exact, key=lambda slug: git_activity_score(bindings.get(slug)))[0]
    plain = [
        s
        for s in slugs
        if not is_hash_like_repo_name(s.split("/", 1)[-1]) and not s.split("/", 1)[-1].endswith("-dev")
    ]
    if plain:
        return sorted(plain, key=lambda slug: (git_activity_score(bindings.get(slug)), len(slug)))[0]
    non_hash = [s for s in slugs if not is_hash_like_repo_name(s.split("/", 1)[-1])]
    if non_hash:
        return sorted(non_hash, key=lambda slug: (git_activity_score(bindings.get(slug)), len(slug)))[0]
    return sorted(slugs, key=lambda slug: git_activity_score(bindings.get(slug)))[0]


@dataclass
class RepoDuplicateLine:
    slug: str
    remote_url: str
    local_path: str
    activity_dot: str
    status: str


@dataclass
class NewProjectProposal:
    slug: str
    url: str
    created_at: str | None
    suggested_name: str
    local_path: str = ""
    activity_dot: str = "[dim]●[/dim]"


@dataclass
class ProjectChangeProposal:
    target_project: str
    customer: str
    canonical_slug: str
    canonical_remote_url: str
    canonical_local_path: str
    canonical_activity_dot: str
    lines: list[RepoDuplicateLine] = field(default_factory=list)


@dataclass
class MappingReview:
    new_projects: list[NewProjectProposal] = field(default_factory=list)
    changes: list[ProjectChangeProposal] = field(default_factory=list)

    def change_count(self) -> int:
        return len(self.new_projects) + len(self.changes)


def _duplicate_line_status(
    slug: str,
    bindings: dict[str, SlugGitBinding],
    *,
    active: str,
) -> str:
    binding = binding_for_slug(slug, bindings)
    if slug == active:
        if binding_has_local_clone(slug, bindings):
            return "Primary — local working copy"
        if binding.in_window_epoch > 0 or binding.remote_hits > 0:
            return "Primary — remote activity in window"
        return "Primary variant"
    if not binding_has_local_clone(slug, bindings):
        return "Duplicate — remote only"
    return "Duplicate variant"


def _activity_dot_for_duplicate_line(
    slug: str,
    bindings: dict[str, SlugGitBinding],
    *,
    active: str,
) -> str:
    """Only the primary duplicate line gets a recency dot; others stay dim."""
    if slug != active:
        return "[dim]●[/dim]"
    binding = binding_for_slug(slug, bindings)
    return activity_dot(binding_activity_epoch(binding))


def _line_for_slug(
    slug: str,
    bindings: dict[str, SlugGitBinding],
    *,
    canonical: str,
    active: str,
) -> RepoDuplicateLine:
    binding = binding_for_slug(slug, bindings)
    return RepoDuplicateLine(
        slug=slug,
        remote_url=binding.remote_url,
        local_path=binding.local_path,
        activity_dot=_activity_dot_for_duplicate_line(slug, bindings, active=active),
        status=_duplicate_line_status(slug, bindings, active=active),
    )


def build_mapping_review(
    events: list[dict],
    profiles: list[dict],
    *,
    extra_signals: list[dict[str, Any]] | None = None,
    slug_bindings: dict[str, SlugGitBinding] | None = None,
    dt_from: Any = None,
    dt_to: Any = None,
    local_tz: Any = None,
    gh_discovery: bool = True,
) -> MappingReview:
    del extra_signals  # git-local review only; callers may still pass legacy signals.
    activity = {
        slug: int(weight)
        for slug, weight in collect_slug_activity_from_events(events).items()
        if is_plausible_github_slug(slug)
    }
    if slug_bindings is None:
        bindings = index_local_slug_bindings(
            dt_from=dt_from,
            dt_to=dt_to,
            local_tz=local_tz,
        )
    else:
        bindings = slug_bindings
    create_times = github_create_times_from_events(events)
    github_sourced = github_sourced_slugs_from_events(events)
    if gh_discovery:
        gh_create_times, gh_pushed_epochs = collect_gh_repo_list_data(
            dt_from,
            dt_to,
            profiles=profiles,
            extra_slugs=set(bindings),
            local_tz=local_tz,
        )
    else:
        gh_create_times, gh_pushed_epochs = {}, {}
    for slug, stamp in gh_create_times.items():
        create_times.setdefault(slug, stamp)
    bindings = enrich_bindings_with_remote_activity(
        bindings,
        events,
        activity=activity,
        gh_pushed_epochs=gh_pushed_epochs,
        dt_from=dt_from,
        dt_to=dt_to,
    )
    configured_all: set[str] = set()
    for profile in profiles:
        configured_all.update(profile_configured_github_slugs(profile))

    review = MappingReview()
    seen_families: set[str] = set()

    customer_configured: dict[str, set[str]] = {}
    for profile in profiles:
        customer = str(profile.get("customer") or "").strip()
        if not customer:
            continue
        customer_configured.setdefault(customer, set()).update(profile_match_term_github_slugs(profile))

    for customer, configured in sorted(customer_configured.items()):
        if not configured:
            continue
        merge_target = merge_target_for_customer(customer, profiles)
        if not merge_target:
            continue

        candidate_pool: set[str] = set(configured)
        for slug in bindings:
            if customer_for_github_slug(slug, profiles) == customer:
                candidate_pool.add(slug)
        for slug in activity:
            if customer_for_github_slug(slug, profiles) == customer:
                candidate_pool.add(slug)

        for anchor_cluster in cluster_repo_families(configured):
            family_key = f"{_normalize_customer(customer)}::{sorted(anchor_cluster)[0]}"
            if family_key in seen_families:
                continue

            family_slugs = expand_repo_family(anchor_cluster, candidate_pool)
            review_slugs = {
                slug
                for slug in family_slugs
                if slug in configured_all
                or slug_has_git_evidence(slug, bindings)
                or int(activity.get(slug, 0)) >= 1
            }
            if len(review_slugs) < 2:
                continue

            canonical = _pick_canonical_slug(merge_target, review_slugs, bindings)
            active = pick_active_slug_by_git(review_slugs, bindings, canonical=canonical)
            if not _duplicate_group_needs_review(
                merge_target,
                review_slugs,
                configured_all,
                bindings,
                activity,
                customer,
                profiles,
            ):
                continue

            seen_families.add(family_key)
            canonical_binding = binding_for_slug(canonical, bindings)
            lines: list[RepoDuplicateLine] = []
            for slug in sorted(review_slugs, key=lambda item: (item != canonical, item != active, item)):
                if slug == canonical:
                    continue
                lines.append(_line_for_slug(slug, bindings, canonical=canonical, active=active))

            review.changes.append(
                ProjectChangeProposal(
                    target_project=merge_target,
                    customer=customer,
                    canonical_slug=canonical,
                    canonical_remote_url=canonical_binding.remote_url,
                    canonical_local_path=canonical_binding.local_path,
                    canonical_activity_dot=activity_dot(binding_activity_epoch(canonical_binding)),
                    lines=lines,
                )
            )

    new_slug_candidates: set[str] = set(create_times)
    new_slug_candidates.update(github_sourced)
    new_slug_candidates.update(gh_create_times)
    new_slug_candidates.update(activity)
    new_slug_candidates.update(bindings)

    for slug in sorted(new_slug_candidates, key=lambda item: (-int(activity.get(item, 0)), str(item))):
        if profile_for_github_slug(slug, profiles):
            continue
        if slug in configured_all:
            continue
        if any(row.slug == slug for row in review.new_projects):
            continue
        if not is_new_github_repo_candidate(
            slug,
            profiles,
            create_times=create_times,
            github_sourced=github_sourced,
            activity=activity,
            bindings=bindings,
            binding_has_local_clone=binding_has_local_clone,
        ):
            continue
        _, repo = split_github_slug(slug)
        binding = binding_for_slug(slug, bindings)
        review.new_projects.append(
            NewProjectProposal(
                slug=slug,
                url=binding.remote_url,
                created_at=create_times.get(slug),
                suggested_name=repo,
                local_path=binding.local_path,
                activity_dot=activity_dot(binding_activity_epoch(binding)),
            )
        )

    return review


def _family_slugs_for_change(change: ProjectChangeProposal) -> set[str]:
    return {change.canonical_slug, *(line.slug for line in change.lines)}


def _merge_additions_for_change(change: ProjectChangeProposal) -> list[tuple[str, str, str]]:
    """Add canonical + every duplicate repo variant to the billing project."""
    target = change.target_project
    additions: list[tuple[str, str, str]] = []
    seen: set[str] = set()

    def _add(rule_type: str, value: str) -> None:
        clean = str(value or "").strip()
        if not clean or clean in seen:
            return
        seen.add(clean)
        additions.append((target, rule_type, clean))

    _add("match_terms", change.canonical_slug)
    for line in change.lines:
        _add("match_terms", line.slug)
        stem = github_repo_stem(line.slug.split("/", 1)[-1])
        if stem:
            _add("match_terms", stem)
    return additions


def _merge_removals_for_change(
    change: ProjectChangeProposal,
    profiles: list[dict],
) -> list[tuple[str, str, str]]:
    """Drop duplicate github slugs from sibling profiles (same customer), keep profile rows."""
    from core.github_slug_match import same_repo_family

    target = change.target_project
    customer = str(change.customer or "").strip()
    if not customer:
        return []

    family_slugs = _family_slugs_for_change(change)
    removals: list[tuple[str, str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for profile in profiles:
        name = str(profile.get("name") or "").strip()
        if not name or name == target:
            continue
        if str(profile.get("customer") or "").strip() != customer:
            continue
        for term in list(profile.get("match_terms") or []):
            raw = str(term or "").strip()
            norm = _normalize_github_slug_hint(raw)
            if not norm or not is_plausible_github_slug(norm):
                continue
            if not any(same_repo_family(norm, family_slug) for family_slug in family_slugs):
                continue
            key = (name, "match_terms", raw)
            if key in seen:
                continue
            seen.add(key)
            removals.append(key)
    return removals


from core.mapping_review_flow import (  # noqa: E402, F401  re-export for callers
    print_mapping_review,
    print_mapping_review_summary,
    prompt_new_project_fields,
    run_batch_mapping_review,
)

