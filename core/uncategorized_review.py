"""Helpers for guided review of uncategorized events."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse


_URL_RE = re.compile(r"https?://[^\s)>\"]+")
_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9._/-]{2,}", re.IGNORECASE)
_STOPWORDS = {
    "error",
    "info",
    "debug",
    "cursor",
    "claude",
    "chrome",
    "gmail",
    "github",
    "log",
    "default",
    "project",
    "session",
}


@dataclass(frozen=True)
class UncategorizedCluster:
    key: str
    rule_type: str
    rule_value: str
    source: str
    count: int
    samples: list[str]


def _extract_domain(text: str) -> str:
    match = _URL_RE.search(text or "")
    if not match:
        return ""
    host = urlparse(match.group(0)).netloc
    # Strip common surrounding punctuation characters
    host = host.strip('.,;:)(\u005d}"\u0027').lower().strip()
    if host.startswith("www."):
        host = host[4:]
    return host


def _extract_term(text: str) -> str:
    for token in _TOKEN_RE.findall((text or "").lower()):
        if token in _STOPWORDS:
            continue
        return token[:64]
    return ""


def build_uncategorized_clusters(
    events: list[dict],
    *,
    max_clusters: int = 20,
    samples_per_cluster: int = 5,
) -> list[UncategorizedCluster]:
    grouped: dict[tuple[str, str, str], list[dict]] = {}
    for event in events:
        detail = str(event.get("detail") or "")
        source = str(event.get("source") or "Unknown")
        domain = _extract_domain(detail)
        if domain:
            key = ("tracked_urls", domain, source)
        else:
            term = _extract_term(detail)
            if not term:
                continue
            key = ("match_terms", term, source)
        grouped.setdefault(key, []).append(event)

    clusters: list[UncategorizedCluster] = []
    for (rule_type, rule_value, source), grouped_events in grouped.items():
        sample_values: list[str] = []
        if samples_per_cluster == 0:
            # Skip collecting samples if limit is zero
            pass
        else:
            for event in grouped_events:
                if len(sample_values) >= samples_per_cluster:
                    break
                detail = str(event.get("detail") or "").strip()
                if not detail or detail in sample_values:
                    continue
                sample_values.append(detail)
        clusters.append(
            UncategorizedCluster(
                key=f"{rule_type}:{rule_value}:{source}",
                rule_type=rule_type,
                rule_value=rule_value,
                source=source,
                count=len(grouped_events),
                samples=sample_values,
            )
        )
    clusters.sort(key=lambda cluster: cluster.count, reverse=True)
    return clusters[: max(0, max_clusters)]