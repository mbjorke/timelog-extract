"""Usage statistics for match_terms and tracked_urls over deduped collector events."""

from __future__ import annotations

import re
from collections import Counter
from typing import Any
from urllib.parse import urlparse

from core.triage_domain_signals import canonical_domain_key, tracked_fragment_matches_domain

_URL_RE = re.compile(r"https?://[^\s)>\"']+", re.IGNORECASE)

AUDIT_SCHEMA_VERSION = 1

TRIM_PLAN_SCHEMA_VERSION = 1

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


def build_zero_hit_trim_plan_from_audit(audit_payload: dict[str, Any]) -> dict[str, Any]:
    """Build a `projects-trim` JSON plan (schema v1) with **candidate** removals.

    Each entry is a rule that had **zero hits** in the audit's date window. That does not prove the
    rule is unused outside the window — review before applying.
    """
    sv = int(audit_payload.get("schema_version", 0))
    if sv != AUDIT_SCHEMA_VERSION:
        raise ValueError(f"audit schema_version must be {AUDIT_SCHEMA_VERSION}, got {sv}")

    removals: list[dict[str, str]] = []
    for block in audit_payload.get("projects") or []:
        pname = str(block.get("name", "")).strip()
        if not pname:
            continue
        for row in block.get("match_terms") or []:
            if int(row.get("hits", 0)) != 0:
                continue
            val = str(row.get("value", "")).strip()
            if val:
                removals.append(
                    {"project_name": pname, "rule_type": "match_terms", "rule_value": val}
                )
        for row in block.get("tracked_urls") or []:
            if int(row.get("hits", 0)) != 0:
                continue
            val = str(row.get("value", "")).strip()
            if val:
                removals.append(
                    {"project_name": pname, "rule_type": "tracked_urls", "rule_value": val}
                )

    note = (
        "Candidate removals: rules with zero hits in the audit window only (see audit hit_definition). "
        "Review or delete rows you want to keep. Apply: gittan projects-trim -i <file> --dry-run "
        "then rerun without --dry-run."
    )

    return {
        "schema_version": TRIM_PLAN_SCHEMA_VERSION,
        "note": note,
        "removals": removals,
        "meta": {
            "source_audit_command": audit_payload.get("command", "gittan projects-audit"),
            "audit_options": audit_payload.get("options", {}),
            "zero_hit_candidates": len(removals),
        },
    }


def build_inline_mapping_suggestions(
    *,
    events: list[dict[str, Any]],
    profiles: list[dict[str, Any]],
    max_candidates: int = 3,
) -> list[str]:
    """Build concise rule-mapping hints for report/status terminal output.

    Uses the same counting semantics as projects-audit and returns at most
    `max_candidates` user-facing suggestion lines.
    """
    limit = max(0, int(max_candidates))
    if limit == 0 or not events or not profiles:
        return []

    payload = build_projects_audit_payload(
        events=events,
        profiles=profiles,
        date_from=None,
        date_to=None,
        projects_config="",
        pool="deduped_all_events",
        top_hosts_limit=max(6, limit * 2),
    )
    if int(payload.get("event_count", 0)) < 5:
        return []

    suggestions: list[str] = []

    for row in payload.get("top_hosts", []):
        if len(suggestions) >= limit:
            break
        hits = int(row.get("hits", 0))
        if bool(row.get("anchored")) or hits < 3:
            continue
        host = str(row.get("host", "")).strip()
        if not host:
            continue
        suggestions.append(
            f"Host '{host}' appears in {hits} events; consider adding tracked_urls in the right project."
        )

    if len(suggestions) >= limit:
        return suggestions

    per_project_totals: dict[str, int] = {}
    for block in payload.get("projects", []):
        name = str(block.get("name", "")).strip()
        if not name:
            continue
        total = 0
        for row in block.get("match_terms", []) or []:
            total += int(row.get("hits", 0))
        for row in block.get("tracked_urls", []) or []:
            total += int(row.get("hits", 0))
        per_project_totals[name] = total

    for block in payload.get("projects", []):
        if len(suggestions) >= limit:
            break
        name = str(block.get("name", "")).strip()
        if not name or per_project_totals.get(name, 0) < 3:
            continue
        for row in block.get("match_terms", []) or []:
            if len(suggestions) >= limit:
                break
            if int(row.get("hits", 0)) != 0:
                continue
            value = str(row.get("value", "")).strip()
            if not value:
                continue
            suggestions.append(
                f"Project '{name}' term '{value}' had zero hits; consider moving term or removing it."
            )

    return suggestions[:limit]
