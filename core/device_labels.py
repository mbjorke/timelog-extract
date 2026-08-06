"""Display-only device tokens for report labels.

Billing and hour grouping keep the bare ``event["project"]`` key. These helpers
only decorate what a person reads: session titles, project-hour rows, timeline
project cells.

**Quiet rule (v1):** when a label's event scope has zero or one distinct device,
omit the suffix. When two or more devices contributed, append a short token list
— e.g. ``timelog-extract (Mac, iPhone)``. Never invent a device that is not on
the events.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence


def device_from_event(event: Dict[str, Any] | None) -> str:
    """Return the stored device label, or "" when absent / malformed."""
    if not event:
        return ""
    provenance = event.get("source_provenance")
    if not isinstance(provenance, dict):
        return ""
    return str(provenance.get("device") or "").strip()


def short_device_token(device: str) -> str:
    """Shorten a stored device string for a parenthetical suffix.

    Drops a trailing ``.lan`` / ``.local`` mDNS suffix; otherwise returns the
    stored string unchanged (friendly-name maps are optional later).
    """
    text = str(device or "").strip()
    if not text:
        return ""
    lower = text.lower()
    for suffix in (".lan", ".local"):
        if lower.endswith(suffix) and len(text) > len(suffix):
            return text[: -len(suffix)]
    return text


def devices_for_events(events: Iterable[Dict[str, Any]] | None) -> List[str]:
    """Distinct short device tokens in stable order (casefold sort)."""
    seen: Dict[str, str] = {}
    for event in events or []:
        raw = device_from_event(event)
        if not raw:
            continue
        token = short_device_token(raw)
        if not token:
            continue
        key = token.casefold()
        seen.setdefault(key, token)
    return [seen[key] for key in sorted(seen)]


def display_project_label(
    project: str,
    events: Sequence[Dict[str, Any]] | None = None,
    *,
    devices: Optional[Sequence[str]] = None,
) -> str:
    """Bare project name, or ``name (Dev1, Dev2)`` when multiple devices apply.

    Pass either the events in scope (filtered to this project by the caller or
    mixed — only matching project rows count) or a precomputed ``devices`` list.
    """
    name = str(project or "").strip() or "Uncategorized"
    if devices is None:
        scoped = [
            event
            for event in (events or [])
            if (str(event.get("project") or "").strip() or "Uncategorized") == name
        ]
        tokens = devices_for_events(scoped)
    else:
        tokens = [short_device_token(d) for d in devices if str(d or "").strip()]
        # de-dupe preserving order
        ordered: List[str] = []
        seen: set[str] = set()
        for token in tokens:
            key = token.casefold()
            if key in seen:
                continue
            seen.add(key)
            ordered.append(token)
        tokens = ordered
    if len(tokens) < 2:
        return name
    return f"{name} ({', '.join(tokens)})"


def ensure_live_device(
    events: Sequence[Dict[str, Any]],
    device: str,
) -> List[Dict[str, Any]]:
    """Stamp ``source_provenance.device`` on live events that lack one.

    Ledger / capture rows already carry a device; leave them alone. Replayed
    events are also left unchanged. Does not change fingerprints
    (detail/source/time unchanged).
    """
    resolved = str(device or "").strip()
    if not resolved:
        return list(events)
    out: List[Dict[str, Any]] = []
    for event in events:
        # Skip replayed events — they already carry device from the ledger
        if event.get("replayed"):
            out.append(event)
            continue
        provenance = event.get("source_provenance")
        if isinstance(provenance, dict) and str(provenance.get("device") or "").strip():
            out.append(event)
            continue
        tagged = dict(event)
        prov = dict(provenance) if isinstance(provenance, dict) else {}
        prov["device"] = resolved
        tagged["source_provenance"] = prov
        out.append(tagged)
    return out
