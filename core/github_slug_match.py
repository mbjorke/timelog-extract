"""GitHub slug parsing, repo-family matching, and evidence-weighted activity."""

from __future__ import annotations

import re
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from core.setup_project_identity_candidates import _normalize_github_slug_hint

_GITHUB_SLUG_RE = re.compile(r"github\.com[/:](?P<owner>[^/\s]+)/(?P<repo>[^/\s#?\"']+)", re.IGNORECASE)
_HASH_FORK_SUFFIX = re.compile(r"-[0-9a-f]{6,}$", re.IGNORECASE)
_GH_SEGMENT_RE = re.compile(r"^[a-z0-9](?:[a-z0-9._-]{0,98}[a-z0-9])?$")
_FILE_EXT_IN_REPO_RE = re.compile(r"\.(?:md|json|tsx?|jsx?|py|ya?ml|sh|html|app|mdx)(?:$|/)", re.IGNORECASE)
_BARE_SLUG_CONTEXT_RE = re.compile(
    r"(?:github\.com/|[·(]|\bto\s+|in\s+|merged\s*\(|requests\s*·\s*)"
    r"(?P<owner>[a-z0-9](?:[a-z0-9-]{0,38}[a-z0-9])?)/"
    r"(?P<repo>[a-z0-9](?:[a-z0-9._-]{0,98}[a-z0-9])?)",
    re.IGNORECASE,
)
_GENERIC_REPO_LEAVES = frozenset(
    {
        "docs",
        "ideas",
        "specs",
        "status",
        "extensions",
        "settings.json",
        "hooks.json",
        "report",
        "auth",
        "oauth",
        "authorize",
    }
)
_RESERVED_GH_OWNERS = frozenset(
    {
        "login",
        "logout",
        "sessions",
        "settings",
        "apps",
        "orgs",
        "organizations",
        "sponsors",
        "features",
        "notifications",
        "marketplace",
        "explore",
        "topics",
        "collections",
        "customer-stories",
        "pricing",
        "about",
        "security",
        "pulse",
        "trending",
        "europe",
        "asia",
        "africa",
        "america",
        "north",
        "south",
        "west",
        "east",
        "global",
        "world",
    }
)

def split_github_slug(slug: str) -> tuple[str, str]:
    parts = str(slug or "").strip().lower().split("/", 1)
    if len(parts) == 2:
        return parts[0], parts[1]
    return "", parts[0]


def known_github_owners(profiles: list[dict], extra_slugs: set[str] | None = None) -> set[str]:
    """GitHub owners already present in project config or local repo bindings."""
    owners: set[str] = set()
    for profile in profiles:
        for term in list(profile.get("match_terms") or []) + list(profile.get("tracked_urls") or []):
            norm = _normalize_github_slug_hint(str(term or ""))
            if not norm or "/" not in norm:
                continue
            owner, _repo = split_github_slug(norm)
            if owner:
                owners.add(owner)
    for slug in extra_slugs or set():
        owner, _repo = split_github_slug(str(slug))
        if owner:
            owners.add(owner)
    return owners


def is_new_github_repo_candidate(
    slug: str,
    profiles: list[dict],
    *,
    create_times: dict[str, str],
    github_sourced: set[str],
    activity: dict[str, int],
    bindings: dict[str, Any],
    binding_has_local_clone: Any,
) -> bool:
    """New repos: local clone, GitHub event, or gh repo list (created in report window)."""
    del profiles, activity  # local-first; Chrome-only slugs are not new projects.
    if not is_plausible_github_slug(slug):
        return False
    if binding_has_local_clone(slug, bindings):
        return True
    if slug in create_times or slug in github_sourced:
        return True
    return False


def is_plausible_github_slug(slug: str) -> bool:
    """Reject local paths, doc paths, and tracked URLs misread as owner/repo."""
    owner, repo = split_github_slug(str(slug or "").strip().lower())
    if not owner or not repo:
        return False
    if owner in _RESERVED_GH_OWNERS:
        return False
    if owner.startswith(".") or repo.startswith("."):
        return False
    if "..." in owner or "..." in repo or ".." in owner or ".." in repo:
        return False
    if "." in owner:
        return False
    if _FILE_EXT_IN_REPO_RE.search(repo):
        return False
    if repo in _GENERIC_REPO_LEAVES:
        return False
    if not _GH_SEGMENT_RE.match(owner) or not _GH_SEGMENT_RE.match(repo):
        return False
    return True


def _add_slug(slugs: list[str], seen: set[str], owner: str, repo: str) -> None:
    clean_owner = str(owner or "").strip().lower()
    clean_repo = str(repo or "").strip().lower().removesuffix(".git")
    if not clean_owner or not clean_repo:
        return
    slug = f"{clean_owner}/{clean_repo}"
    if not is_plausible_github_slug(slug) or slug in seen:
        return
    seen.add(slug)
    slugs.append(slug)


def github_slugs_in_text(text: str) -> list[str]:
    slugs: list[str] = []
    seen: set[str] = set()
    haystack = str(text or "")
    for match in _GITHUB_SLUG_RE.finditer(haystack):
        _add_slug(slugs, seen, match.group("owner"), match.group("repo"))
    for match in _BARE_SLUG_CONTEXT_RE.finditer(haystack):
        _add_slug(slugs, seen, match.group("owner"), match.group("repo"))
    return slugs


def github_repo_stem(repo_name: str) -> str:
    """Strip hash forks: financing-portal-dev-31e799cf -> financing-portal-dev."""
    name = str(repo_name or "").strip().lower().removesuffix(".git")
    prev = None
    while name != prev:
        prev = name
        name = _HASH_FORK_SUFFIX.sub("", name)
    return name


def _is_dev_line_variant(repo_name: str, product_stem: str) -> bool:
    """True for financing-portal-dev or financing-portal-dev-<hash>, not blueberry-fintech."""
    repo = str(repo_name or "").strip().lower()
    stem = str(product_stem or "").strip().lower()
    if not repo or not stem:
        return False
    if repo == f"{stem}-dev":
        return True
    return repo.startswith(f"{stem}-dev-")


def same_repo_family(slug_a: str, slug_b: str) -> bool:
    """True when two slugs are the same repo line (dev branch, hash fork), not name-prefix cousins."""
    owner_a, repo_a = split_github_slug(str(slug_a or "").strip().lower())
    owner_b, repo_b = split_github_slug(str(slug_b or "").strip().lower())
    if not owner_a or owner_a != owner_b or not repo_a or not repo_b:
        return False
    stem_a = github_repo_stem(repo_a)
    stem_b = github_repo_stem(repo_b)
    if stem_a == stem_b:
        return True
    if is_successor_repo_slug(slug_a, slug_b) or is_successor_repo_slug(slug_b, slug_a):
        return True
    if _is_dev_line_variant(repo_a, stem_b) or _is_dev_line_variant(repo_b, stem_a):
        return True
    return False


def expand_repo_family(anchor_slugs: set[str], pool: set[str]) -> set[str]:
    """Keep only pool slugs that belong to the same repo family as an anchor."""
    anchors = {slug for slug in anchor_slugs if is_plausible_github_slug(slug)}
    if not anchors:
        return set()
    members = set(anchors)
    for candidate in pool:
        clean = str(candidate or "").strip().lower()
        if not is_plausible_github_slug(clean):
            continue
        if any(same_repo_family(anchor, clean) for anchor in anchors):
            members.add(clean)
    return members


def is_successor_repo_slug(candidate_slug: str, configured_slug: str) -> bool:
    """True when candidate is a strict fork/successor of configured (e.g. hash suffix)."""
    cand_owner, cand_repo = split_github_slug(candidate_slug)
    cfg_owner, cfg_repo = split_github_slug(configured_slug)
    if not cand_owner or cand_owner != cfg_owner:
        return False
    cfg_stem = github_repo_stem(cfg_repo)
    cand_stem = github_repo_stem(cand_repo)
    if cand_stem != cfg_stem:
        return False
    return len(cand_repo) > len(cfg_repo)


def _score_slug_against_profile(owner: str, repo: str, repo_stem: str, needle: str, profile: dict) -> int:
    name = str(profile.get("name") or "").strip()
    if not name:
        return 0
    name_lower = name.lower()
    score = 0
    if name_lower in {repo, repo_stem}:
        score = max(score, 100)
    elif repo_stem == name_lower or repo_stem.startswith(f"{name_lower}-"):
        score = max(score, 85)

    for term in list(profile.get("match_terms") or []) + list(profile.get("tracked_urls") or []):
        raw = str(term or "").strip().lower()
        if not raw:
            continue
        norm = _normalize_github_slug_hint(raw)
        if not norm:
            continue
        if norm == needle:
            score = max(score, 95)
        if "/" not in norm:
            continue
        term_owner, term_repo = split_github_slug(norm)
        term_stem = github_repo_stem(term_repo)
        if owner and term_owner == owner:
            if repo_stem == term_stem:
                score = max(score, 92)
            elif repo.startswith(f"{term_stem}-") or repo_stem.startswith(f"{term_stem}-"):
                score = max(score, 88)
    return score


def is_hash_like_repo_name(repo_name: str) -> bool:
    return bool(_HASH_FORK_SUFFIX.search(str(repo_name or "").strip()))


def prefer_billing_project_name(name: str, profiles: list[dict]) -> str:
    """Map -dev billing aliases to the parent customer project when both exist."""
    clean = str(name or "").strip()
    if not clean.endswith("-dev"):
        return clean
    parent = clean[: -len("-dev")]
    by_name = {str(p.get("name") or "").strip(): p for p in profiles if str(p.get("name") or "").strip()}
    if parent not in by_name:
        return clean
    if str(by_name[clean].get("customer") or "") == str(by_name[parent].get("customer") or ""):
        return parent
    return clean


def profile_for_github_slug(
    slug: str,
    profiles: list[dict],
    *,
    activity: Counter[str] | None = None,
) -> str | None:
    needle = str(slug or "").strip().lower()
    if not needle:
        return None
    owner, repo = split_github_slug(needle)
    repo_stem = github_repo_stem(repo)

    scored: list[tuple[int, str]] = []
    for profile in profiles:
        name = str(profile.get("name") or "").strip()
        if not name:
            continue
        score = _score_slug_against_profile(owner, repo, repo_stem, needle, profile)
        if score:
            scored.append((score, name))
    if not scored:
        return None

    best_score = max(score for score, _ in scored)
    tied = [name for score, name in scored if score == best_score]
    if len(tied) == 1:
        return prefer_billing_project_name(tied[0], profiles)

    if activity:
        tied.sort(key=lambda name: (-int(activity.get(name, 0)), len(name), name))
        return prefer_billing_project_name(tied[0], profiles)

    non_dev = [name for name in tied if not name.endswith("-dev")]
    if len(non_dev) == 1:
        return prefer_billing_project_name(non_dev[0], profiles)
    tied.sort(key=lambda name: (len(name), name))
    return prefer_billing_project_name(tied[0], profiles)


def profile_match_term_github_slugs(profile: dict[str, Any]) -> set[str]:
    """Repo slugs from match_terms only — not tracked_urls (those are host routes, not fork families)."""
    slugs: set[str] = set()
    for term in profile.get("match_terms") or []:
        norm = _normalize_github_slug_hint(str(term or ""))
        if norm and is_plausible_github_slug(norm):
            slugs.add(norm)
    return slugs


def profile_configured_github_slugs(profile: dict[str, Any]) -> set[str]:
    slugs: set[str] = set()
    for term in list(profile.get("match_terms") or []) + list(profile.get("tracked_urls") or []):
        norm = _normalize_github_slug_hint(str(term or ""))
        if norm and is_plausible_github_slug(norm):
            slugs.add(norm)
    return slugs


def cluster_repo_families(slugs: set[str]) -> list[set[str]]:
    """Split configured repo slugs into disjoint same-family clusters."""
    remaining = {slug for slug in slugs if is_plausible_github_slug(slug)}
    clusters: list[set[str]] = []
    while remaining:
        seed = sorted(remaining)[0]
        cluster = expand_repo_family({seed}, remaining)
        clusters.append(cluster)
        remaining -= cluster
    return clusters


from core.github_slug_activity import (  # noqa: E402  re-export for callers
    collect_profile_activity_from_events,
    collect_slug_activity_from_events,
    collect_slug_last_epoch_from_events,
    discover_active_repo_shift_signals,
    github_sourced_slugs_from_events,
    merge_slug_activity,
    suggest_project_from_slug_activity,
)
