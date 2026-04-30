"""Shared helpers for triage domain/repo signal extraction."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse


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
