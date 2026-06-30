"""Suggest existing project targets for gittan map (anchors, repos, duplicate families)."""

from __future__ import annotations

from typing import Any

from core.github_slug_match import (
    github_repo_stem,
    github_slugs_in_text,
    is_plausible_github_slug,
    profile_for_github_slug,
    split_github_slug,
)
from core.mapping_suggestions import (
    suggest_project_for_signal,
    suggest_project_from_label_workspace,
)


def _profile_by_name(profiles: list[dict], name: str) -> dict | None:
    key = str(name or "").strip().lower()
    if not key:
        return None
    for profile in profiles:
        if str(profile.get("name") or "").strip().lower() == key:
            return profile
    return None


def _dev_profile_for_repo_stem(repo_stem: str, profiles: list[dict]) -> str | None:
    stem = str(repo_stem or "").strip().lower()
    if not stem.endswith("-dev"):
        return None
    for profile in profiles:
        name = str(profile.get("name") or "").strip()
        if name.lower() == stem:
            return name
    return None


def suggest_project_for_map_slug(slug: str, profiles: list[dict]) -> str | None:
    """Map slug to an existing profile; prefer intentional -dev siblings over parent rollup."""
    needle = str(slug or "").strip().lower()
    if not needle or not is_plausible_github_slug(needle):
        return None
    _owner, repo = split_github_slug(needle)
    repo_stem = github_repo_stem(repo)
    dev = _dev_profile_for_repo_stem(repo_stem, profiles)
    if dev:
        return dev
    return profile_for_github_slug(needle, profiles)


def _exact_anchor_match(value: str, profiles: list[dict]) -> str | None:
    clean = str(value or "").strip().lower()
    if not clean:
        return None
    leaf = clean.rsplit("/", 1)[-1]
    matches: list[tuple[int, str]] = []
    for profile in profiles:
        name = str(profile.get("name") or "").strip()
        if not name:
            continue
        name_lower = name.lower()
        matched = clean == name_lower or leaf == name_lower
        if not matched:
            for term in profile.get("match_terms") or []:
                raw = str(term or "").strip().lower()
                if raw in {clean, leaf}:
                    matched = True
                    break
        if matched:
            matches.append((len(name_lower), name))
    if not matches:
        return None
    matches.sort(key=lambda row: (-row[0], row[1].lower()))
    return matches[0][1]


def _fuzzy_anchor_match(value: str, profiles: list[dict]) -> str | None:
    clean = str(value or "").strip().lower()
    if len(clean) < 4:
        return None
    tokens = {part for part in clean.replace("_", "-").split("-") if len(part) >= 4}
    best_name: str | None = None
    best_score = 0
    for profile in profiles:
        name = str(profile.get("name") or "").strip()
        if not name:
            continue
        name_lower = name.lower()
        score = 0
        if name_lower in clean or clean.startswith(f"{name_lower}-") or clean.startswith(f"{name_lower}_"):
            score = len(name_lower) + 10
        else:
            score = sum(1 for token in tokens if token in name_lower)
        if score > best_score:
            best_score = score
            best_name = name
    return best_name if best_score >= 1 else None


def suggest_project_for_anchor(
    entry: dict[str, Any],
    profiles: list[dict],
    *,
    events: list[dict] | None = None,
) -> str | None:
    """Best existing project for an unmapped dir/branch/label/repo anchor."""
    value = str(entry.get("value") or "").strip()
    if not value:
        return None

    preset = str(entry.get("suggested_project") or "").strip()
    if preset and _profile_by_name(profiles, preset):
        return preset

    exact = _exact_anchor_match(value, profiles)
    if exact:
        return exact

    for slug in github_slugs_in_text(value):
        match = suggest_project_for_map_slug(slug, profiles)
        if match:
            return match

    kind = str(entry.get("kind") or "")
    event_list = list(events or [])
    if kind == "label" and event_list:
        match = suggest_project_from_label_workspace(entry, event_list, profiles)
        if match:
            return match

    if event_list:
        signal = {
            "kind": kind if kind in {"host", "git_repo", "git_slug", "repo_shift", "label"} else "label",
            "value": value,
            "hits": int(entry.get("hits") or 0),
        }
        match = suggest_project_for_signal(signal, profiles=profiles, events=event_list)
        if match and _profile_by_name(profiles, match):
            return match

    return _fuzzy_anchor_match(value, profiles)


def suggest_project_for_new_repo(slug: str, suggested_name: str, profiles: list[dict]) -> str | None:
    """Existing profile for a newly discovered repo slug."""
    match = suggest_project_for_map_slug(slug, profiles)
    if match:
        return match
    leaf = str(suggested_name or "").strip().lower()
    if not leaf:
        return None
    for profile in profiles:
        name = str(profile.get("name") or "").strip()
        if name.lower() == leaf:
            return name
    return _dev_profile_for_repo_stem(github_repo_stem(leaf), profiles)


def suggest_project_for_duplicate_change(
    change: Any,
    profiles: list[dict],
) -> str | None:
    """Prefer the profile that should own active duplicate-line slugs (often -dev)."""
    primary = [
        str(line.slug or "").strip()
        for line in getattr(change, "lines", []) or []
        if "Primary" in str(getattr(line, "status", "") or "")
    ]
    for slug in primary:
        match = suggest_project_for_map_slug(slug, profiles)
        if match:
            return match
    for slug in [getattr(change, "canonical_slug", "")] + [
        str(line.slug or "") for line in getattr(change, "lines", []) or []
    ]:
        match = suggest_project_for_map_slug(str(slug or ""), profiles)
        if match:
            return match
    customer = str(getattr(change, "customer", "") or "").strip()
    dev_siblings = [
        str(profile.get("name") or "").strip()
        for profile in profiles
        if str(profile.get("customer") or "").strip() == customer
        and str(profile.get("name") or "").strip().endswith("-dev")
    ]
    if len(dev_siblings) == 1:
        return dev_siblings[0]
    return None
