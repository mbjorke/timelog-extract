"""Suggest project targets for unmapped mapping signals (GitHub, git repos, labels)."""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Any

from core.events import event_anchors
from core.git_activity_discovery import collect_git_command_slug_hits
from core.git_project_bootstrap import build_repo_project_seed, discover_local_git_repos, suggest_bootstrap_root
from core.github_slug_match import (
    collect_profile_activity_from_events,
    collect_slug_activity_from_events,
    discover_active_repo_shift_signals,
    github_repo_stem,
    github_slugs_in_text,
    merge_slug_activity,
    prefer_billing_project_name,
    profile_configured_github_slugs,
    profile_for_github_slug,
    suggest_project_from_slug_activity,
)
from core.setup_project_identity_candidates import _normalize_github_slug_hint

_LOVABLE_UUID_RE = re.compile(
    r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})",
    re.IGNORECASE,
)


def _event_ts(event: dict) -> Any:
    return event.get("local_ts") or event.get("timestamp")


def _lovable_uuid_from_signal(value: str) -> str:
    match = _LOVABLE_UUID_RE.search(str(value or ""))
    return match.group(1).lower() if match else ""


def _known_github_slugs(profiles: list[dict]) -> set[str]:
    known: set[str] = set()
    for profile in profiles:
        known.update(profile_configured_github_slugs(profile))
        for term in list(profile.get("match_terms") or []) + list(profile.get("tracked_urls") or []):
            norm = _normalize_github_slug_hint(str(term or ""))
            if norm:
                known.add(norm)
    return known


def _known_project_names(profiles: list[dict]) -> set[str]:
    return {str(p.get("name") or "").strip().lower() for p in profiles if str(p.get("name") or "").strip()}


def _signal_anchor_timestamps(signal: dict[str, Any], events: list[dict]) -> list[Any]:
    kind = str(signal.get("kind") or "")
    value = str(signal.get("value") or "").strip()
    if not value:
        return []
    value_lower = value.lower()
    needle_uuid = _lovable_uuid_from_signal(value) if kind == "host" else ""
    timestamps: list[Any] = []
    for event in events:
        detail = str(event.get("detail") or "")
        detail_lower = detail.lower()
        matched = False
        if kind == "host":
            matched = value_lower in detail_lower or bool(needle_uuid and needle_uuid in detail_lower)
        elif kind == "label":
            matched = str(event_anchors(event).get("label") or "").strip().lower() == value_lower
        elif kind in ("git_repo", "git_slug"):
            matched = value_lower in detail_lower
            if not matched:
                matched = value_lower in {slug.lower() for slug in github_slugs_in_text(detail)}
        if not matched:
            continue
        ts = _event_ts(event)
        if ts is not None:
            timestamps.append(ts)
    return timestamps


def suggest_project_from_nearby_github(
    signal: dict[str, Any],
    events: list[dict],
    profiles: list[dict],
    *,
    window_minutes: int = 120,
    profile_activity: Counter[str] | None = None,
) -> str | None:
    """Correlate signals with weighted GitHub/Chrome slug activity."""
    kind = str(signal.get("kind") or "")
    activity = profile_activity or collect_profile_activity_from_events(events, profiles)
    anchor_times = _signal_anchor_timestamps(signal, events)

    if kind == "host":
        match = suggest_project_from_slug_activity(
            events,
            profiles,
            anchor_times=anchor_times or None,
            window_minutes=window_minutes,
        )
        if match:
            return match

    if kind in ("git_repo", "git_slug", "repo_shift"):
        own = str(signal.get("value") or "").strip().lower()
        if own:
            direct = profile_for_github_slug(own, profiles, activity=activity)
            if direct:
                return prefer_billing_project_name(direct, profiles)

    if not anchor_times:
        return None

    match = suggest_project_from_slug_activity(
        events,
        profiles,
        anchor_times=anchor_times,
        window_minutes=window_minutes,
    )
    return match


def suggest_project_from_label_workspace(
    signal: dict[str, Any],
    events: list[dict],
    profiles: list[dict],
) -> str | None:
    if signal.get("kind") != "label":
        return None
    needle = str(signal.get("value") or "").strip().lower()
    if not needle:
        return None
    dir_leaves: set[str] = set()
    for event in events:
        if str(event_anchors(event).get("label") or "").strip().lower() != needle:
            continue
        leaf = str(event_anchors(event).get("dir") or "").strip().lower()
        if leaf:
            dir_leaves.add(leaf)
    for leaf in sorted(dir_leaves):
        for profile in profiles:
            name = str(profile.get("name") or "").strip()
            if name.lower() == leaf:
                return name
            for term in profile.get("match_terms") or []:
                if str(term or "").strip().lower() == leaf:
                    return name
    return None


def suggest_project_for_signal(
    signal: dict[str, Any],
    *,
    profiles: list[dict],
    events: list[dict],
) -> str | None:
    activity = collect_profile_activity_from_events(events, profiles)
    preset = str(signal.get("suggested_project") or "").strip()
    if preset:
        preset = prefer_billing_project_name(preset, profiles)
    if signal.get("kind") == "repo_shift" and preset:
        return preset

    if signal.get("kind") == "host":
        match = suggest_project_from_nearby_github(
            signal, events, profiles, profile_activity=activity
        )
        if match:
            return prefer_billing_project_name(match, profiles)

    match = suggest_project_from_nearby_github(
        signal, events, profiles, profile_activity=activity
    )
    if match:
        return prefer_billing_project_name(match, profiles)
    if signal.get("kind") == "label":
        match = suggest_project_from_label_workspace(signal, events, profiles)
        if match:
            return prefer_billing_project_name(match, profiles)
    return preset or None


def discover_unmapped_github_slugs_from_events(
    events: list[dict],
    profiles: list[dict],
    *,
    activity: Counter[str] | None = None,
    limit: int = 15,
) -> list[dict[str, Any]]:
    """GitHub slugs with evidence activity that do not map to any existing project."""
    known_slugs = _known_github_slugs(profiles)
    known_names = _known_project_names(profiles)
    counts = activity or collect_slug_activity_from_events(events)
    signals: list[dict[str, Any]] = []
    for slug, hits in counts.most_common(limit * 2):
        if slug in known_slugs:
            continue
        if profile_for_github_slug(slug, profiles):
            continue
        repo_leaf = slug.split("/", 1)[-1]
        if repo_leaf in known_names:
            continue
        suggested = profile_for_github_slug(slug, profiles) or repo_leaf
        signals.append(
            {
                "kind": "git_slug",
                "value": slug,
                "hits": int(hits),
                "rule_type": "match_terms",
                "display": f"GitHub activity {slug}",
                "suggested_project": prefer_billing_project_name(suggested, profiles),
                "extra_rules": [slug, github_repo_stem(repo_leaf)],
            }
        )
        if len(signals) >= limit:
            break
    return signals


def _git_command_activity(
    *,
    cursor_home: Path,
    dt_from: Any,
    dt_to: Any,
    local_tz: Any,
) -> Counter[str]:
    if dt_from is None or dt_to is None:
        return Counter()
    counts: Counter[str] = Counter()
    for slug, (count, _repo_name) in collect_git_command_slug_hits(
        cursor_home, dt_from, dt_to, local_tz
    ).items():
        counts[slug] += int(count)
    return counts


def discover_unmapped_git_repo_signals(
    profiles: list[dict],
    *,
    scan_root: Path | None = None,
    max_depth: int = 2,
    limit: int = 40,
) -> list[dict[str, Any]]:
    """Repos under workspace root that are not represented in project match_terms."""
    root = (scan_root or suggest_bootstrap_root(Path.cwd())).expanduser()
    known_slugs = _known_github_slugs(profiles)
    known_names = _known_project_names(profiles)
    signals: list[dict[str, Any]] = []
    for repo in discover_local_git_repos(root, max_depth=max_depth, limit=limit):
        seed = build_repo_project_seed(repo)
        if seed is None:
            continue
        slug = f"{seed.customer.lower()}/{seed.name.lower()}"
        if slug in known_slugs or seed.name.lower() in known_names:
            continue
        signals.append(
            {
                "kind": "git_repo",
                "value": slug,
                "hits": 1,
                "rule_type": "match_terms",
                "display": f"Git repo {slug} ({repo.name})",
                "suggested_project": seed.name,
                "extra_rules": [slug, seed.name.lower()],
            }
        )
    return signals


def discover_unmapped_git_signals(
    profiles: list[dict],
    *,
    events: list[dict] | None = None,
    scan_root: Path | None = None,
    cursor_home: Path | None = None,
    dt_from: Any = None,
    dt_to: Any = None,
    local_tz: Any = None,
    max_depth: int = 2,
    limit: int = 40,
) -> list[dict[str, Any]]:
    """Evidence-weighted repo activity: shifts, new slugs, workspace scan."""
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    event_list = list(events or [])
    tz = local_tz or (getattr(dt_from, "tzinfo", None) if dt_from else None)
    activity = merge_slug_activity(
        collect_slug_activity_from_events(event_list),
        _git_command_activity(
            cursor_home=cursor_home or Path.home(),
            dt_from=dt_from,
            dt_to=dt_to,
            local_tz=tz,
        ),
    )

    def _append(rows: list[dict[str, Any]]) -> None:
        for row in rows:
            value = str(row.get("value") or "").strip().lower()
            if not value or value in seen:
                continue
            seen.add(value)
            merged.append(row)

    profile_activity = collect_profile_activity_from_events(event_list, profiles) if event_list else Counter()
    if activity:
        _append(
            discover_active_repo_shift_signals(
                profiles,
                activity,
                profile_activity=profile_activity,
            )
        )
    if event_list:
        _append(discover_unmapped_github_slugs_from_events(event_list, profiles, activity=activity))
    _append(discover_unmapped_git_repo_signals(profiles, scan_root=scan_root, max_depth=max_depth, limit=limit))
    merged.sort(key=lambda row: (-int(row.get("hits") or 0), str(row.get("value") or "")))
    return merged[:limit]
