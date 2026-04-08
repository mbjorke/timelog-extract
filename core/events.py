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


def make_event(source, ts, detail, project, uncategorized):
    return {
        "source": source,
        "timestamp": ts,
        "detail": detail,
        "project": project or uncategorized,
    }


def filter_included_events(all_events, args, profiles, uncategorized):
    included_events = all_events if args.include_uncategorized else [
        event for event in all_events if event["project"] != uncategorized
    ]
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
