"""Shared helpers for triage domain/repo signal extraction."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

# Union of generic roots used by site-first scoring (`core.triage_site_scoring`) and
# triage-domains guardrails; subdomain hosts count as generic when they end with
# `.<root>` (e.g. mail.google.com).
GENERIC_TRIAGE_ROOT_DOMAINS: frozenset[str] = frozenset(
    {
        "accounts.google.com",
        "atlassian.net",
        "claude.ai",
        "github.com",
        "google.com",
        "home.atlassian.com",
        "id.atlassian.com",
        "linkedin.com",
        "mail.google.com",
    }
)


def canonical_domain_key(host: str) -> str:
    """Normalize host for aggregation (strip leading www, lower-case)."""
    h = str(host or "").strip().lower()
    if h.startswith("www."):
        h = h[4:]
    return h


def is_generic_triage_domain(domain: str) -> bool:
    """True if the host is a known generic surface (including subdomains of roots)."""
    value = canonical_domain_key(domain)
    if not value:
        return False
    if value in GENERIC_TRIAGE_ROOT_DOMAINS:
        return True
    return any(value.endswith(f".{root}") for root in GENERIC_TRIAGE_ROOT_DOMAINS)


def merged_history_entries_for_canonical(
    canonical: str,
    domain_project_counts: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    """Merge per-domain history rows that share the same canonical host key."""
    by_project: dict[str, int] = {}
    want = canonical_domain_key(canonical)
    for raw_domain, rows in domain_project_counts.items():
        if canonical_domain_key(str(raw_domain)) != want:
            continue
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            project = str(row.get("project", "")).strip()
            if not project:
                continue
            by_project[project] = by_project.get(project, 0) + int(row.get("events", 0) or 0)
    ranked = sorted(by_project.items(), key=lambda item: (-item[1], item[0]))
    return [{"project": p, "events": int(n)} for p, n in ranked]


def domain_from_event_detail(detail: str) -> str:
    text = str(detail or "")
    for token in text.split():
        if not token.startswith("http://") and not token.startswith("https://"):
            continue
        try:
            host = urlparse(token).netloc.lower().strip()
        except ValueError:
            continue
        if host.startswith("www."):
            host = host[4:]
        if host:
            return host
    return ""


def github_repo_hint(url: str) -> str:
    text = str(url or "").strip()
    if not text:
        return ""
    try:
        parsed = urlparse(text)
    except ValueError:
        return ""
    host = parsed.netloc.lower().strip()
    if host.startswith("www."):
        host = host[4:]
    if host != "github.com":
        return ""
    segments = [part.strip() for part in parsed.path.split("/") if part.strip()]
    if len(segments) < 2:
        return ""
    owner, repo = segments[0], segments[1]
    if not owner or not repo:
        return ""
    return f"{owner}/{repo}"


def domain_project_counts_from_events(events: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    counts: dict[str, dict[str, int]] = {}
    for event in events:
        project = str(event.get("project") or "").strip()
        if not project:
            continue
        domain = domain_from_event_detail(str(event.get("detail") or ""))
        if not domain:
            continue
        counts.setdefault(domain, {})
        counts[domain][project] = counts[domain].get(project, 0) + 1
    out: dict[str, list[dict[str, Any]]] = {}
    for domain, per_project in counts.items():
        ranked = sorted(per_project.items(), key=lambda item: (-item[1], item[0]))
        out[domain] = [
            {"project": project, "events": int(events_count)}
            for project, events_count in ranked[:3]
        ]
    return out


def tracked_fragment_matches_domain(domain: str, raw_fragment: str) -> bool:
    """True when a tracked_urls entry clearly refers to this host (not loose substring noise)."""
    d = canonical_domain_key(domain)
    t = str(raw_fragment or "").strip().lower().rstrip("/")
    if not d or not t:
        return False
    if "://" in t:
        try:
            host = urlparse(t).netloc.lower()
        except ValueError:
            return False
        if host.startswith("www."):
            host = host[4:]
        if host == d:
            return True
        if len(d) >= 5 and d in t and d in host:
            return True
        return False
    if t == d:
        return True
    if len(t) >= 5 and t in d:
        return True
    if len(d) >= 5 and d in t:
        return True
    return False
