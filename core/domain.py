from __future__ import annotations

import functools
import math
import re
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urlparse, urlunparse

from core.sources import AGENT_SOURCES, ATTENDED_SOURCES

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


@functools.lru_cache(maxsize=1024)
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
    if not text or "http" not in text:
        return ""
    variants = []
    for token in _URL_TOKEN_RE.findall(text):
        normalized = _normalize_lovable_url_token(token)
        if normalized:
            variants.append(normalized)
    return " ".join(variants)


def _matches_term(term: str, haystack: str, word_set: Optional[Set[str]] = None) -> bool:
    """True when term appears in haystack, respecting word boundaries for plain terms."""
    if not term:
        return False
    if word_set is not None and term.isalnum() and not _is_path_like_term(term):
        return term in word_set
    if term not in haystack:
        return False
    # If it's a path or contains special characters (hyphens, dots, spaces, etc.),
    # it's likely a specific code, domain, or multi-word phrase that we can
    # safely match anywhere.
    if _is_path_like_term(term) or not term.isalnum():
        return True
    # Plain alphanumeric words must respect word boundaries to avoid 'cat' matching 'category'.
    pattern = rf"\b{re.escape(term)}\b"
    return bool(re.search(pattern, haystack))


def classify_project(text: str, profiles: List[Dict[str, Any]], fallback: str) -> str:
    if not text:
        return fallback
    haystack = text.lower()
    normalized_variants = _normalized_url_variants(haystack)
    haystack_with_variants = f"{haystack} {normalized_variants}".strip()

    # Pre-calculate word set for fast alphanumeric matching (bypassing re.search)
    word_set = set(re.findall(r"\w+", haystack_with_variants))

    # Pre-calculate match cache for all unique terms across all profiles.
    # Terms must be normalized to lowercase for the match check to be correct.
    match_cache: Dict[str, bool] = {}
    for profile in profiles:
        for term in profile.get("match_terms") or []:
            clean = str(term).strip().lower()
            if clean and clean not in match_cache and clean in haystack_with_variants:
                match_cache[clean] = _matches_term(clean, haystack_with_variants, word_set=word_set)

        name_lower = profile["name"].lower()
        if name_lower and name_lower not in match_cache and name_lower in haystack_with_variants:
            match_cache[name_lower] = _matches_term(
                name_lower, haystack_with_variants, word_set=word_set
            )

        for url in profile.get("tracked_urls") or []:
            fragment = str(url).strip().lower()
            if fragment and fragment not in match_cache and fragment in haystack_with_variants:
                match_cache[fragment] = _matches_term(
                    fragment, haystack_with_variants, word_set=word_set
                )

    best_name = fallback
    # Rank: (weighted_score, specific_hits, total_match_len, -generic_hits, total_matches)
    best_rank = (0.0, 0, 0, 0, 0)

    for profile in profiles:
        match_terms = profile.get("match_terms") or []
        matched_terms = []
        for term in match_terms:
            clean = str(term).strip().lower()
            if match_cache.get(clean):
                matched_terms.append(clean)

        weighted_score = 0.0
        specific_hits = 0
        generic_hits = 0
        match_len = 0
        for clean in matched_terms:
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
        if name_lower and match_cache.get(name_lower):
            weighted_score += 1.0
            specific_hits += 1
            match_len += len(name_lower)

        for url in profile.get("tracked_urls") or []:
            fragment = str(url).strip().lower()
            if fragment and match_cache.get(fragment):
                weighted_score += 2.0
                specific_hits += 1
                match_len += len(fragment)

        rank = (weighted_score, specific_hits, match_len, -generic_hits, len(matched_terms))
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


def project_billable_raw_hours(day_payloads, include_agent: bool = False) -> float:
    """Raw hours eligible for billing across a project's day payloads (GH-284 slice 2).

    Agent (autonomous) hours are excluded by default: they require the same
    explicit approval as any other time before they can be billed. Pass
    ``include_agent=True`` to opt them back in. Mixed sessions (user + agent
    interleaved) stay billable, matching the attended/agent split the report shows.
    Uncertain attendance is classified ``attended`` upstream, so it stays billable.
    """
    total = 0.0
    for day_payload in day_payloads.values():
        hours = float(day_payload.get("hours", 0.0))
        if not include_agent:
            hours -= float(day_payload.get("agent_hours", 0.0))
        total += max(hours, 0.0)
    return total


def classify_attendance(events: list[dict]) -> str:
    """Categorize a collection of events as attended, agent, or mixed (GH-284)."""
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
