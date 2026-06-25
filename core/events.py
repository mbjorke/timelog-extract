"""Event helpers and filtering."""

from __future__ import annotations

from datetime import timezone


def event_key(event, uncategorized):
    return (
        event["source"],
        event["timestamp"].astimezone(timezone.utc).isoformat(),
        event["detail"],
        event.get("project", uncategorized),
    )


def dedupe_events(events, event_key_fn):
    unique = {}
    for event in events:
        unique[event_key_fn(event)] = event
    return sorted(unique.values(), key=lambda e: e["timestamp"])


def _normalize_anchor_value(kind: str, value) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    if kind == "label":
        return text[:80]
    return text.lower()


def make_event(source, ts, detail, project, uncategorized, anchors=None):
    event = {
        "source": source,
        "timestamp": ts,
        "detail": detail,
        "project": project or uncategorized,
    }
    # Namespaced corroborating-context metadata: a {kind: value} map of activity
    # anchors (working directory, git branch, session title) that classification
    # already uses, preserved for audit/suggestion. Never the primary detail.
    # See docs/specs/working-directory-anchor-signal.md.
    clean = {}
    for kind, value in (anchors or {}).items():
        if not kind:
            continue
        normalized = _normalize_anchor_value(str(kind), value)
        if normalized:
            clean[str(kind)] = normalized
    if clean:
        event["anchors"] = clean
    return event


def event_anchors(event) -> dict:
    """The {kind: value} anchor map for an event (empty dict if none)."""
    anchors = event.get("anchors") if isinstance(event, dict) else None
    return anchors if isinstance(anchors, dict) else {}


def event_anchor(event, kind: str):
    """One anchor value for a given kind, or None."""
    return event_anchors(event).get(kind)


_LOVABLE_DESKTOP_SOURCE = "Lovable (desktop)"


def is_always_included_event(event, uncategorized) -> bool:
    """Evidence that must stay visible even when uncategorized rows are filtered out."""
    if str(event.get("source") or "") == _LOVABLE_DESKTOP_SOURCE:
        # Lovable desktop has no Chromium History on many installs; storage UUID signals
        # are the only mapping surface for new projects — hiding them breaks review.
        return True
    # Session titles (label anchors) are primary mapping signals for chat tools.
    if str(event_anchors(event).get("label") or "").strip():
        return True
    return False


def filter_included_events(all_events, args, profiles, uncategorized):
    included_events = (
        all_events
        if args.include_uncategorized
        else [
            event
            for event in all_events
            if event["project"] != uncategorized or is_always_included_event(event, uncategorized)
        ]
    )
    if args.only_project:
        only = args.only_project.strip()
        included_events = [e for e in included_events if e["project"] == only]
    if args.customer:
        wanted_customer = args.customer.strip().lower()
        project_to_customer = {
            p["name"]: str(p.get("customer") or p["name"]).strip().lower()
            for p in profiles
        }
        allowed_projects = {
            project_name
            for project_name, customer_name in project_to_customer.items()
            if customer_name == wanted_customer
        }
        included_events = [e for e in included_events if e["project"] in allowed_projects]
    return included_events
