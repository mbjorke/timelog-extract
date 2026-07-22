"""Weighted GitHub slug activity from events and repo-shift signal discovery."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any

from core.github_slug_match import (
    github_repo_stem,
    github_slugs_in_text,
    is_plausible_github_slug,
    is_successor_repo_slug,
    prefer_billing_project_name,
    profile_configured_github_slugs,
    profile_for_github_slug,
    split_github_slug,
)
from core.sources import canonical_source_name

_SOURCE_WEIGHT: dict[str, int] = {
    "GitHub": 4,
    "Chrome": 3,
    "WordPress": 3,
    "Lovable (web)": 2,
    "Lovable (desktop)": 2,
    "Cursor": 1,
    "Cursor checkpoints": 1,
    "Devin Desktop": 1,
    "VS Code": 1,
    "Antigravity": 1,
    "Codex IDE": 1,
    "TIMELOG.md": 2,
    "Apple Mail": 1,
}


def collect_profile_activity_from_events(events: list[dict], profiles: list[dict]) -> Counter[str]:
    """Roll GitHub/Chrome/Git slug evidence up to project profiles."""
    profile_activity: Counter[str] = Counter()
    for slug, weight in collect_slug_activity_from_events(events).items():
        project = profile_for_github_slug(slug, profiles)
        if project:
            profile_activity[project] += int(weight)
    return profile_activity


def _event_epoch_seconds(event: dict) -> int:
    ts = event.get("timestamp") or event.get("local_ts")
    if ts is None:
        return 0
    if isinstance(ts, datetime):
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return int(ts.timestamp())
    return 0


def collect_slug_last_epoch_from_events(events: list[dict]) -> dict[str, int]:
    """Latest event timestamp per github slug (GitHub pushes, Chrome, etc.)."""
    last: dict[str, int] = {}
    for event in events:
        epoch = _event_epoch_seconds(event)
        if epoch <= 0:
            continue
        haystack = f"{event.get('detail') or ''} {event.get('project') or ''}"
        for slug in github_slugs_in_text(haystack):
            if is_plausible_github_slug(slug):
                last[slug] = max(last.get(slug, 0), epoch)
    return last


def collect_slug_activity_from_events(events: list[dict]) -> Counter[str]:
    """Weight slug hits by source — GitHub API and Chrome outweigh IDE log noise."""
    counts: Counter[str] = Counter()
    for event in events:
        source = str(event.get("source") or "")
        weight = _SOURCE_WEIGHT.get(canonical_source_name(source), 1)
        haystack = f"{event.get('detail') or ''} {event.get('project') or ''}"
        for slug in github_slugs_in_text(haystack):
            if is_plausible_github_slug(slug):
                counts[slug] += weight
    return counts


def github_sourced_slugs_from_events(events: list[dict]) -> set[str]:
    """Slugs that appear in GitHub collector/API event details (not path noise)."""
    sourced: set[str] = set()
    for event in events:
        if str(event.get("source") or "") != "GitHub":
            continue
        for slug in github_slugs_in_text(str(event.get("detail") or "")):
            if is_plausible_github_slug(slug):
                sourced.add(slug)
    return sourced


def merge_slug_activity(*counters: Counter[str]) -> Counter[str]:
    merged: Counter[str] = Counter()
    for counter in counters:
        merged.update(counter)
    return merged


def _all_configured_github_slugs(profiles: list[dict]) -> set[str]:
    known: set[str] = set()
    for profile in profiles:
        known.update(profile_configured_github_slugs(profile))
    return known


def _pick_profile_for_successor(
    slug: str,
    parent_profiles: list[dict],
    *,
    activity: Counter[str] | None = None,
) -> str:
    """Map a hash fork to the billing project, not a -dev alias when parent exists."""
    owner, repo = split_github_slug(slug)
    repo_stem = github_repo_stem(repo)
    candidates: list[str] = []
    for profile in parent_profiles:
        name = str(profile.get("name") or "").strip()
        if not name:
            continue
        if name.lower() == repo_stem:
            candidates.append(name)
        for configured in profile_configured_github_slugs(profile):
            if is_successor_repo_slug(slug, configured):
                candidates.append(name)
                break
    if not candidates:
        match = profile_for_github_slug(slug, parent_profiles, activity=activity)
        return prefer_billing_project_name(match or "", parent_profiles) if match else ""

    unique = sorted(set(candidates))
    if activity and len(unique) > 1:
        unique.sort(key=lambda name: (-int(activity.get(name, 0)), len(name), name))
    else:
        unique.sort(key=lambda name: (len(name), name))
    return prefer_billing_project_name(unique[0], parent_profiles)


def suggest_project_from_slug_activity(
    events: list[dict],
    profiles: list[dict],
    *,
    anchor_times: list[Any] | None = None,
    window_minutes: int = 120,
) -> str | None:
    """Pick project from weighted GitHub/Chrome evidence (matches contribution-activity view)."""
    from datetime import timedelta

    profile_activity = collect_profile_activity_from_events(events, profiles)
    slug_weights: Counter[str] = Counter()
    window = timedelta(minutes=max(15, window_minutes))
    for event in events:
        ts = event.get("local_ts") or event.get("timestamp")
        if anchor_times and ts is not None:
            if not any(abs(ts - anchor) <= window for anchor in anchor_times):
                continue
        source = str(event.get("source") or "")
        weight = _SOURCE_WEIGHT.get(canonical_source_name(source), 1)
        haystack = f"{event.get('detail') or ''} {event.get('project') or ''}"
        for slug in github_slugs_in_text(haystack):
            slug_weights[slug] += weight

    if not slug_weights:
        if profile_activity:
            return prefer_billing_project_name(profile_activity.most_common(1)[0][0], profiles)
        return None

    profile_scores: Counter[str] = Counter()
    for slug, weight in slug_weights.items():
        project = profile_for_github_slug(slug, profiles, activity=profile_activity)
        if project:
            profile_scores[project] += int(weight)

    if not profile_scores:
        return None
    ranked = profile_scores.most_common()
    return prefer_billing_project_name(ranked[0][0], profiles)


def discover_active_repo_shift_signals(
    profiles: list[dict],
    activity: Counter[str],
    *,
    profile_activity: Counter[str] | None = None,
    min_activity: int = 2,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Surface hash-fork / successor repos that replaced a configured GitHub slug."""
    configured_all = _all_configured_github_slugs(profiles)
    signals: list[dict[str, Any]] = []
    seen: set[str] = set()

    for slug, count in activity.most_common():
        if count < min_activity:
            continue
        if slug in configured_all:
            continue
        parent_profiles: list[dict] = []
        stale_labels: list[str] = []
        best_parent_activity = 0
        for profile in profiles:
            configured = profile_configured_github_slugs(profile)
            matched_parents = [cfg for cfg in configured if is_successor_repo_slug(slug, cfg)]
            if not matched_parents:
                continue
            parent_profiles.append(profile)
            for parent in matched_parents:
                stale_labels.append(parent.split("/", 1)[-1])
                best_parent_activity = max(best_parent_activity, int(activity.get(parent, 0)))
        if not parent_profiles:
            continue
        if count <= best_parent_activity and best_parent_activity > 0:
            continue
        if slug in seen:
            continue
        seen.add(slug)
        repo_leaf = slug.split("/", 1)[-1]
        stale_label = sorted(set(stale_labels), key=len, reverse=True)[0]
        target = _pick_profile_for_successor(slug, parent_profiles, activity=profile_activity)
        signals.append(
            {
                "kind": "repo_shift",
                "value": slug,
                "hits": int(count),
                "rule_type": "match_terms",
                "display": f"Add repo {github_repo_stem(repo_leaf)} (was {stale_label})",
                "suggested_project": target,
                "extra_rules": [slug, github_repo_stem(repo_leaf)],
            }
        )
        if len(signals) >= limit:
            break

    return signals
