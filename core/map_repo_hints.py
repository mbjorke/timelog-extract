"""Cheap repo-mapping hints from report events (no git/gh workspace scan)."""

from __future__ import annotations

from collections import Counter
from datetime import datetime

from core.github_slug_activity import (
    _SOURCE_WEIGHT,
    collect_slug_activity_from_events,
    github_sourced_slugs_from_events,
)
from core.github_slug_match import (
    github_slugs_in_text,
    is_plausible_github_slug,
    profile_configured_github_slugs,
    profile_for_github_slug,
)


def _repo_slugs_from_event_anchors(events: list[dict]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for event in events:
        anchors = event.get("anchors") or {}
        repo = str(anchors.get("repo") or "").strip().lower()
        if not is_plausible_github_slug(repo):
            continue
        source = str(event.get("source") or "")
        counts[repo] += _SOURCE_WEIGHT.get(source, 1)
    return counts


def github_create_times_from_events(events: list[dict]) -> dict[str, str]:
    """Repo slugs from GitHub ``created …`` event rows."""
    times: dict[str, str] = {}
    for event in events:
        detail = str(event.get("detail") or "")
        if not detail.lower().startswith("created "):
            continue
        for slug in github_slugs_in_text(detail):
            stamp = _format_ts(event.get("local_ts") or event.get("timestamp"))
            if stamp:
                times.setdefault(slug, stamp)
    return times


def _format_ts(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.astimezone().strftime("%Y-%m-%d %H:%M")
    return str(value)


def unconfigured_repo_slugs_in_events(events: list[dict], profiles: list[dict]) -> list[str]:
    """Plausible GitHub slugs in events that no project profile covers yet."""
    configured_all: set[str] = set()
    for profile in profiles:
        configured_all.update(profile_configured_github_slugs(profile))

    activity = collect_slug_activity_from_events(events)
    activity.update(_repo_slugs_from_event_anchors(events))
    candidates: set[str] = set()
    for slug in set(activity) | github_sourced_slugs_from_events(events) | set(github_create_times_from_events(events)):
        clean = str(slug or "").strip().lower()
        if not clean or not is_plausible_github_slug(clean):
            continue
        if clean in configured_all:
            continue
        if profile_for_github_slug(clean, profiles):
            continue
        candidates.add(clean)
    return sorted(candidates, key=lambda item: (-int(activity.get(item, 0)), item))
