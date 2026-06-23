"""Helpers for guided review of uncategorized events."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

from core.triage_noise import (
    TRIAGE_NOISE_DOMAINS,
    is_uncategorized_noise_detail,
    is_uncategorized_noise_term,
)
from core.tracked_url_policy import is_multi_tenant_tracked_url_host


_URL_RE = re.compile(r"https?://[^\s)>\"]+")
_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9._/-]{2,}", re.IGNORECASE)
_DATE_ONLY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DATE_TIME_LIKE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}[tT].+$")
_EXTENSION_VERSION_TOKEN_RE = re.compile(
    r"^[a-z0-9-]+\.[a-z0-9-]+(?:\.[a-z0-9-]+)*-\d+(?:\.\d+)+(?:-[a-z0-9-]+)?$",
    re.IGNORECASE,
)
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


_NOISE_TRACKED_URL_VALUES = {"lovable.dev", "www.lovable.dev"}


def _is_extension_lifecycle_detail(text: str) -> bool:
    lower = (text or "").lower()
    if lower.startswith("started downloading extension: "):
        return True
    if lower.startswith("extracted extension to ") and ".cursor/extensions/" in lower:
        return True
    if lower.startswith("renamed to ") and ".cursor/extensions/" in lower:
        return True
    return False


def _is_extension_lifecycle_token(token: str) -> bool:
    if ".cursor/extensions/" in token:
        return True
    if _EXTENSION_VERSION_TOKEN_RE.match(token):
        return True
    return False


def _is_noise_detail(text: str) -> bool:
    if is_uncategorized_noise_detail(text):
        return True
    lower = (text or "").lower()
    if _is_extension_lifecycle_detail(text):
        return True
    # Cursor marketplace internals are not actionable project signals.
    if "loadfrommarketplacesource" in lower:
        return True
    # Extension metadata churn tends to create misleading uncategorized clusters.
    if "extensions.json" in lower and ("install" in lower or "update" in lower):
        return True
    if "config path:" in lower and "/" in text:
        if any(
            marker in lower
            for marker in (
                ".claude/settings.json",
                ".cursor/hooks.json",
                "settings.json",
                "hooks.json",
            )
        ):
            return True
    return False


def _is_noise_rule_value(rule_type: str, rule_value: str) -> bool:
    if not rule_value:
        return True
    if rule_type == "match_terms":
        if is_uncategorized_noise_term(rule_value):
            return True
        if _DATE_ONLY_RE.match(rule_value):
            return True
        if _DATE_TIME_LIKE_RE.match(rule_value):
            return True
    if rule_type == "tracked_urls":
        host = rule_value.lower().split("/", 1)[0]
        if host.startswith("www."):
            host = host[4:]
        if (
            host in _NOISE_TRACKED_URL_VALUES
            or host in TRIAGE_NOISE_DOMAINS
            or is_multi_tenant_tracked_url_host(rule_value)
        ):
            return True
    return False


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
    tokens = [
        token
        for token in _TOKEN_RE.findall((text or "").lower())
        if token not in _STOPWORDS and not _is_extension_lifecycle_token(token)
    ]
    # Prefer tokens that contain a hyphen or slash: these are more likely to be
    # project-specific identifiers (e.g. "acme-feature", "org/repo") and
    # therefore more useful as suggested match_terms.
    for token in tokens:
        if "-" in token or "/" in token:
            return token[:64]
    return tokens[0][:64] if tokens else ""


def build_uncategorized_clusters(
    events: list[dict],
    *,
    max_clusters: int = 20,
    samples_per_cluster: int = 5,
) -> list[UncategorizedCluster]:
    grouped: dict[tuple[str, str, str], list[dict]] = {}
    for event in events:
        detail = str(event.get("detail") or "")
        if _is_noise_detail(detail):
            continue
        source = str(event.get("source") or "Unknown")
        domain = _extract_domain(detail)
        if domain and domain not in TRIAGE_NOISE_DOMAINS:
            key = ("tracked_urls", domain, source)
        else:
            term = _extract_term(detail)
            if not term:
                continue
            key = ("match_terms", term, source)
        if _is_noise_rule_value(key[0], key[1]):
            continue
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


def count_uncategorized_noise_events(events: list[dict]) -> int:
    return sum(1 for event in events if _is_noise_detail(str(event.get("detail") or "")))


def format_cluster_headline(cluster: UncategorizedCluster) -> str:
    if cluster.rule_type == "tracked_urls":
        return f"Unmapped web host [bold]{cluster.rule_value}[/bold]"
    return f"Repeated text token [bold]{cluster.rule_value}[/bold]"


def format_cluster_rule_hint(cluster: UncategorizedCluster) -> str:
    if cluster.rule_type == "tracked_urls":
        return f"Suggested rule: tracked_urls → {cluster.rule_value!r}"
    return f"Suggested rule: match_terms → {cluster.rule_value!r}"


def format_cluster_sample(sample: str, *, max_len: int = 140) -> str:
    text = " ".join(str(sample or "").split())
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"