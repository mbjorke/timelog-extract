from __future__ import annotations

import math
import re
from urllib.parse import urlparse, urlunparse

GENERIC_TOOL_TERMS = {
    "cloudflare",
    "jira",
    "jira.com",
    "atlassian",
    "toggl",
    "toggl.com",
    "toggle",
    "toggle.com",
}


def _is_path_like_term(term: str) -> bool:
    t = (term or "").strip().lower()
    return "/" in t or "\\" in t or t.startswith("users/") or t.startswith("workspace/")


_URL_TOKEN_RE = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)


def _normalize_lovable_url_token(url: str) -> str:
    raw = (url or "").strip().rstrip(".,;)")
    if not raw:
        return ""
    try:
        parsed = urlparse(raw)
    except ValueError:
        return ""
    if parsed.scheme not in {"http", "https"}:
        return ""
    host = (parsed.netloc or "").lower().strip().rstrip(".")
    if not host:
        return ""
    if host.endswith(".lovableproject"):
        host = f"{host}.com"
    elif host == "lovableproject":
        host = "lovableproject.com"
    rebuilt = urlunparse(
        (parsed.scheme, host, parsed.path or "", parsed.params or "", parsed.query or "", parsed.fragment or "")
    )
    return rebuilt.lower()


def _normalized_url_variants(text: str) -> str:
    variants = []
    for token in _URL_TOKEN_RE.findall(text or ""):
        normalized = _normalize_lovable_url_token(token)
        if normalized:
            variants.append(normalized)
    return " ".join(variants)


def _matches_term(term: str, haystack: str) -> bool:
    """True when term appears in haystack, respecting word boundaries for plain terms."""
    clean = str(term).strip().lower()
    if not clean or clean not in haystack:
        return False
    # If it's a path or contains special characters (hyphens, dots, spaces, etc.),
    # it's likely a specific code, domain, or multi-word phrase that we can
    # safely match anywhere.
    if _is_path_like_term(clean) or not clean.isalnum():
        return True
    # Plain alphanumeric words must respect word boundaries to avoid 'cat' matching 'category'.
    pattern = rf"\b{re.escape(clean)}\b"
    return bool(re.search(pattern, haystack))


def classify_project(text, profiles, fallback):
    haystack = (text or "").lower()
    normalized_variants = _normalized_url_variants(text or "")
    haystack_with_variants = f"{haystack} {normalized_variants}".strip()
    best_name = fallback
    # Rank: (weighted_score, specific_hits, total_match_len, -generic_hits, total_matches)
    best_rank = (0.0, 0, 0, 0, 0)
    for profile in profiles:
        matched = {term for term in profile["match_terms"] if _matches_term(term, haystack_with_variants)}
        weighted_score = 0.0
        specific_hits = 0
        generic_hits = 0
        match_len = 0
        for term in matched:
            clean = str(term).strip().lower()
            match_len += len(clean)
            if clean in GENERIC_TOOL_TERMS:
                weighted_score += 0.25
                generic_hits += 1
            elif _is_path_like_term(clean):
                weighted_score += 2.0
                specific_hits += 1
            else:
                weighted_score += 1.0
                specific_hits += 1

        name_lower = profile["name"].lower()
        if _matches_term(name_lower, haystack_with_variants):
            weighted_score += 1.0
            specific_hits += 1
            match_len += len(name_lower)

        for url in profile.get("tracked_urls") or []:
            fragment = str(url).strip().lower()
            if fragment and _matches_term(fragment, haystack_with_variants):
                weighted_score += 2.0
                specific_hits += 1
                match_len += len(fragment)

        rank = (weighted_score, specific_hits, match_len, -generic_hits, len(matched))
        if (specific_hits > 0 or weighted_score >= 1.0) and rank > best_rank:
            best_rank = rank
            best_name = profile["name"]
    return best_name


def compute_sessions(entries, gap_minutes=15):
    if not entries:
        return []
    sorted_entries = sorted(entries, key=lambda x: x["local_ts"])
    sessions = []
    s_start = sorted_entries[0]["local_ts"]
    s_end = sorted_entries[0]["local_ts"]
    s_events = [sorted_entries[0]]

    for event in sorted_entries[1:]:
        gap_s = (event["local_ts"] - s_end).total_seconds()
        if gap_s < gap_minutes * 60:
            s_end = event["local_ts"]
            s_events.append(event)
        else:
            sessions.append((s_start, s_end, s_events))
            s_start = event["local_ts"]
            s_end = event["local_ts"]
            s_events = [event]

    sessions.append((s_start, s_end, s_events))
    return sessions


def session_duration_hours(
    session_events,
    start_ts,
    end_ts,
    min_session_minutes,
    min_session_passive_minutes,
    ai_sources,
):
    from core.sources import PASSIVE_CONTEXT, get_source_role

    min_h = min_session_minutes / 60
    min_passive_h = min_session_passive_minutes / 60
    sources = {event["source"] for event in session_events}
    roles = {get_source_role(source) for source in sources}
    if roles and roles <= {PASSIVE_CONTEXT}:
        minimum = 0.0
    elif sources & ai_sources:
        minimum = min_h
    else:
        minimum = min_passive_h
    return max((end_ts - start_ts).total_seconds() / 3600, minimum)


def billable_total_hours(raw_hours, unit):
    if not unit or unit <= 0:
        return raw_hours
    q = raw_hours / unit
    eps = 1e-12
    return math.ceil(q - eps) * unit


def classify_attendance(events: list[dict]) -> str:
    """Categorize a collection of events as attended, agent, or mixed (GH-284)."""
    from core.sources import AGENT_SOURCES, ATTENDED_SOURCES

    has_attended = False
    has_agent = False
    for event in events:
        source = str(event.get("source") or "")
        if source in ATTENDED_SOURCES:
            has_attended = True
        elif source in AGENT_SOURCES:
            has_agent = True

    if has_attended and has_agent:
        return "mixed"
    if has_agent:
        return "agent"
    return "attended"
