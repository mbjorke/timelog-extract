"""Merge Lovable storage/cache presence events by project UUID (GH-448)."""

from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import urlparse

_LOVABLE_PROJECT_UUID_RE = re.compile(
    r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})",
    re.IGNORECASE,
)
_NIL_PROJECT_UUID = "00000000-0000-0000-0000-000000000000"
_MAX_PROJECT_UUID = "ffffffff-ffff-ffff-ffff-ffffffffffff"


def is_plausible_lovable_project_uuid(uuid: str) -> bool:
    """True for UUID v4 project ids — reject nil/max and UUID-shaped binary noise.

    Chromium cache blobs contain many RFC-looking tokens (incl. v7 time UUIDs and
    all-zero). Emitting those flooded ``gittan review`` with unmapped map nudges
    after per-UUID merge (GH-448). Lovable project hosts observed in the wild are
    UUID version 4 with RFC variant bits.
    """
    text = str(uuid or "").strip().lower()
    if len(text) != 36 or text in {_NIL_PROJECT_UUID, _MAX_PROJECT_UUID}:
        return False
    parts = text.split("-")
    if len(parts) != 5 or [len(p) for p in parts] != [8, 4, 4, 4, 12]:
        return False
    if parts[2][0] != "4" or parts[3][0] not in "89ab":
        return False
    try:
        int(text.replace("-", ""), 16)
    except ValueError:
        return False
    return True


def _lovable_project_uuid_key(url: str) -> str:
    # Mirrors collectors/lovable_desktop.py — duplicated to avoid circular import
    # (lovable_desktop → lovable_merge → lovable_desktop). Keep both in sync.
    try:
        host = (urlparse(url).netloc or "").lower()
    except ValueError:
        return ""
    match = _LOVABLE_PROJECT_UUID_RE.search(host)
    return match.group(1).lower() if match else ""


def _storage_event_score(event: dict) -> tuple[int, int, int, int, datetime]:
    project = str(event.get("project") or "").strip()
    mapped = 1 if project and project != "Uncategorized" else 0
    detail = str(event.get("detail") or "")
    titled = 1 if detail and "unmapped Lovable" not in detail and "storage signal" not in detail else 0
    url = detail.split("—", 1)[-1].strip() if "—" in detail else detail
    host_score = 2 if ".lovableproject.com" in url.lower() else 1 if ".lovable.app" in url.lower() else 0
    uuid_len = len(_lovable_project_uuid_key(url))
    return (mapped, titled, host_score, uuid_len, event["timestamp"])


def _pick_best_storage_event(group: list) -> dict:
    return max(enumerate(group), key=lambda item: (_storage_event_score(item[1]), item[0]))[1]


def _storage_event_identity_key(event: dict) -> str:
    """Stable identity for merge: project UUID when present, else project name.

    Distinct UUIDs must not collapse into one winner within the merge window —
    a mapped project must not erase a newer unmapped UUID (GH-448).
    """
    detail = str(event.get("detail") or "")
    url = detail.split("—", 1)[-1].strip() if "—" in detail else detail
    uuid = _lovable_project_uuid_key(url)
    if not uuid:
        match = _LOVABLE_PROJECT_UUID_RE.search(detail)
        if match:
            uuid = match.group(1).lower()
    if uuid:
        return f"uuid:{uuid}"
    project = str(event.get("project") or "").strip().lower()
    if project:
        return f"project:{project}"
    return f"detail:{detail[:80]}"


def _merge_storage_events(events: list, *, merge_seconds: int) -> list:
    """Collapse same-UUID LevelDB bursts; keep distinct project UUIDs separate."""
    if not events or merge_seconds <= 0:
        return events
    sorted_events = sorted(events, key=lambda event: event["timestamp"])
    by_identity: dict[str, list] = {}
    for event in sorted_events:
        by_identity.setdefault(_storage_event_identity_key(event), []).append(event)

    merged: list[dict] = []
    for identity_events in by_identity.values():
        group = [identity_events[0]]
        for event in identity_events[1:]:
            gap = (event["timestamp"] - group[-1]["timestamp"]).total_seconds()
            if gap <= merge_seconds:
                group.append(event)
                continue
            merged.append(_pick_best_storage_event(group))
            group = [event]
        merged.append(_pick_best_storage_event(group))
    return sorted(merged, key=lambda event: event["timestamp"])
