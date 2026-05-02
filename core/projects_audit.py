"""Usage statistics for match_terms and tracked_urls over deduped collector events."""

from __future__ import annotations

import re
from collections import Counter
from typing import Any
from urllib.parse import urlparse

from core.triage_domain_signals import canonical_domain_key, tracked_fragment_matches_domain

_URL_RE = re.compile(r"https?://[^\s)>\"']+", re.IGNORECASE)

AUDIT_SCHEMA_VERSION = 1

HIT_DEFINITION_V1 = (
    "match_terms: each event is counted once per term if the term is a case-insensitive "
    "substring of the event detail (same text field used by project classification). "
    "tracked_urls: counted when any http(s) host parsed from the detail matches the stored "
    "fragment using the same host rules as triage-domains "
    "(core.triage_domain_signals.tracked_fragment_matches_domain), or when the fragment (no scheme) "
    "appears as a substring of the detail if no URLs were parsed. "
    "Counts apply only to this date window and deduped collector events; zero hits does not "
    "prove a rule is unused outside the window."
)

TOP_HOSTS_NOTE = (
    "top_hosts: http(s) hosts parsed from event details, counted once per host per event, sorted by "
    "frequency. anchored=true if some profile already has a match_term substring of the host or a "
    "tracked_urls rule matching a stub URL for that host (same rules as tracked_url hits)."
)


def extract_hosts_from_detail(detail: str) -> list[str]:
    hosts: list[str] = []
    for m in _URL_RE.finditer(detail or ""):
        try:
            netloc = urlparse(m.group(0)).netloc.lower()
        except ValueError:
            continue
        if netloc.startswith("www."):
            netloc = netloc[4:]
        if netloc:
            hosts.append(netloc)
    return hosts


def event_matches_tracked_url(detail: str, raw_fragment: str) -> bool:
    frag = str(raw_fragment or "").strip()
    if not frag:
        return False
    haystack = (detail or "").lower()
    hosts = extract_hosts_from_detail(detail)
    if hosts:
        return any(tracked_fragment_matches_domain(h, frag) for h in hosts)
    return frag.lower() in haystack


def is_host_anchored_by_profiles(host: str, profiles: list[dict[str, Any]]) -> bool:
    """True if any enabled profile rule would match this host (mapping hint already present)."""
    h = canonical_domain_key(host)
    if not h:
        return False
    hay = h.lower()
    stub_detail = f"https://{h}/"
    for profile in profiles:
        for term in profile.get("match_terms") or []:
            t = str(term).strip().lower()
            if t and t in hay:
                return True
        for raw in profile.get("tracked_urls") or []:
            if event_matches_tracked_url(stub_detail, str(raw)):
                return True
    return False


def aggregate_top_hosts(events: list[dict[str, Any]], *, limit: int) -> list[tuple[str, int]]:
    """Count each canonical host at most once per event; return (host, count) descending."""
    counts: Counter[str] = Counter()
    for event in events:
        detail = str(event.get("detail") or "")
        seen: set[str] = set()
        for raw_host in extract_hosts_from_detail(detail):
            key = canonical_domain_key(raw_host)
            if not key or key in seen:
                continue
            seen.add(key)
            counts[key] += 1
    return counts.most_common(max(0, int(limit)))


def build_projects_audit_payload(
    *,
    events: list[dict[str, Any]],
    profiles: list[dict[str, Any]],
    date_from: str | None,
    date_to: str | None,
    projects_config: str,
    pool: str,
    top_hosts_limit: int = 30,
) -> dict[str, Any]:
    """Assemble read-only audit JSON (`schema_version` = AUDIT_SCHEMA_VERSION)."""
    match_counts: dict[str, dict[str, int]] = {}
    tracked_counts: dict[str, dict[str, int]] = {}
    for profile in profiles:
        name = str(profile.get("name", "")).strip()
        if not name:
            continue
        match_counts[name] = {str(t).strip(): 0 for t in (profile.get("match_terms") or [])}
        tracked_counts[name] = {str(u).strip(): 0 for u in (profile.get("tracked_urls") or [])}

    for event in events:
        detail = str(event.get("detail") or "")
        haystack = detail.lower()
        for profile in profiles:
            name = str(profile.get("name", "")).strip()
            if not name:
                continue
            for term in profile.get("match_terms") or []:
                key = str(term).strip()
                t = key.lower()
                if t and t in haystack:
                    match_counts[name][key] = match_counts[name].get(key, 0) + 1
            for raw in profile.get("tracked_urls") or []:
                key = str(raw).strip()
                if event_matches_tracked_url(detail, key):
                    tracked_counts[name][key] = tracked_counts[name].get(key, 0) + 1

    projects_out: list[dict[str, Any]] = []
    for profile in sorted(profiles, key=lambda p: str(p.get("name", "")).lower()):
        name = str(profile.get("name", "")).strip()
        if not name:
            continue
        projects_out.append(
            {
                "name": name,
                "match_terms": [
                    {"value": k, "hits": int(match_counts.get(name, {}).get(k, 0))}
                    for k in profile.get("match_terms") or []
                ],
                "tracked_urls": [
                    {"value": k, "hits": int(tracked_counts.get(name, {}).get(k, 0))}
                    for k in profile.get("tracked_urls") or []
                ],
            }
        )

    top_rows = aggregate_top_hosts(events, limit=top_hosts_limit)
    top_hosts_out = [
        {
            "host": host,
            "hits": int(n),
            "anchored": is_host_anchored_by_profiles(host, profiles),
        }
        for host, n in top_rows
    ]

    return {
        "schema_version": AUDIT_SCHEMA_VERSION,
        "command": "gittan projects-audit",
        "hit_definition": HIT_DEFINITION_V1,
        "top_hosts_note": TOP_HOSTS_NOTE,
        "pool": pool,
        "options": {
            "date_from": date_from,
            "date_to": date_to,
            "projects_config": projects_config,
            "top_hosts_limit": int(top_hosts_limit),
        },
        "event_count": len(events),
        "projects": projects_out,
        "top_hosts": top_hosts_out,
    }
