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

# Impact types for pre-compiled profile index
_IMPACT_GENERIC = 0
_IMPACT_PATH = 1
_IMPACT_NORMAL = 2
_IMPACT_NAME = 3
_IMPACT_URL = 4


@functools.lru_cache(maxsize=1024)
def _is_path_like_term(term: str) -> bool:
    t = (term or "").strip().lower()
    return "/" in t or "\\" in t or t.startswith("users/") or t.startswith("workspace/")


_URL_TOKEN_RE = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)


@functools.lru_cache(maxsize=2048)
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


@functools.lru_cache(maxsize=1024)
def _normalized_url_variants(text: str) -> str:
    if not text or "http" not in text:
        return ""
    variants = []
    for token in _URL_TOKEN_RE.findall(text):
        normalized = _normalize_lovable_url_token(token)
        if normalized:
            variants.append(normalized)
    return " ".join(variants)


@functools.lru_cache(maxsize=1024)
def _prepare_haystack_and_word_set(text_lower: str) -> tuple[str, frozenset[str]]:
    """Pre-calculate combined text and word set for fast O(1) word boundary checks."""
    normalized_variants = _normalized_url_variants(text_lower)
    haystack_with_variants = f"{text_lower} {normalized_variants}".strip()
    word_set = frozenset(re.findall(r"\w+", haystack_with_variants))
    return haystack_with_variants, word_set


def _compile_profiles_index(
    profiles: List[Dict[str, Any]],
) -> tuple[
    dict[str, list[tuple[int, int]]],
    list[tuple[str, list[tuple[int, int]]]],
    dict[str, list[tuple[int, int]]],
]:
    """Index profiles by term for fast lookup.

    Returns:
        fast_terms: Map of alphanumeric terms to (profile_index, impact_type)
        slow_terms: List of (term, impacts) for non-alphanumeric or path-like terms
        all_impacts: Combined map for all terms
    """
    term_to_impacts: dict[str, list[tuple[int, int]]] = {}

    def add_term(term: Any, idx: int, impact: int):
        clean = str(term).strip().lower()
        if not clean:
            return
        if clean not in term_to_impacts:
            term_to_impacts[clean] = []
        term_to_impacts[clean].append((idx, impact))

    for i, profile in enumerate(profiles):
        for term in profile.get("match_terms") or []:
            clean_term = str(term).strip().lower()
            if not clean_term:
                continue
            if clean_term in GENERIC_TOOL_TERMS:
                impact = _IMPACT_GENERIC
            elif _is_path_like_term(clean_term):
                impact = _IMPACT_PATH
            else:
                impact = _IMPACT_NORMAL
            add_term(clean_term, i, impact)

        name_lower = profile["name"].lower()
        if name_lower:
            add_term(name_lower, i, _IMPACT_NAME)

        for url in profile.get("tracked_urls") or []:
            add_term(url, i, _IMPACT_URL)

    fast_terms: dict[str, list[tuple[int, int]]] = {}
    slow_terms: list[tuple[str, list[tuple[int, int]]]] = []
    for term, impacts in term_to_impacts.items():
        if term.isalnum() and not _is_path_like_term(term):
            fast_terms[term] = impacts
        else:
            slow_terms.append((term, impacts))

    return fast_terms, slow_terms, term_to_impacts


_LAST_PROFILES_DATA: tuple[Any, Any, Any] | None = None


def _get_compiled_index(profiles: List[Dict[str, Any]]) -> Any:
    """Caching wrapper to avoid re-compiling the index for the same profiles list."""
    global _LAST_PROFILES_DATA
    # Fingerprint to detect mutation of the same list object (common in tests).
    # We include all profile names to catch renames or project swaps in the same list.
    fingerprint = (len(profiles), tuple(p.get("name") for p in profiles))
    if (
        _LAST_PROFILES_DATA is None
        or _LAST_PROFILES_DATA[0] is not profiles
        or _LAST_PROFILES_DATA[1] != fingerprint
    ):
        _LAST_PROFILES_DATA = (profiles, fingerprint, _compile_profiles_index(profiles))
    return _LAST_PROFILES_DATA[2]


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

    fast_terms, slow_terms, all_impacts = _get_compiled_index(profiles)
    haystack_with_variants, word_set = _prepare_haystack_and_word_set(text.lower())

    matched_terms = set()
    # 1. Fast path: alphanumeric terms that are definitely in the text's word set.
    for term in fast_terms.keys() & word_set:
        matched_terms.add(term)

    # 2. Slow path: path-like or special-char terms.
    # Only check them if the term appears as a substring in the haystack.
    for term, _ in slow_terms:
        if term in haystack_with_variants:
            if _matches_term(term, haystack_with_variants, word_set=word_set):
                matched_terms.add(term)

    if not matched_terms:
        return fallback

    num_profs = len(profiles)
    scores = [0.0] * num_profs
    specifics = [0] * num_profs
    generics = [0] * num_profs
    lens = [0] * num_profs
    counts = [0] * num_profs

    # 3. Single-pass scoring: accumulate rank components for all matching profiles.
    for term in matched_terms:
        t_len = len(term)
        for idx, impact in all_impacts[term]:
            lens[idx] += t_len
            if impact == _IMPACT_GENERIC:
                scores[idx] += 0.25
                generics[idx] += 1
                counts[idx] += 1
            elif impact == _IMPACT_PATH:
                scores[idx] += 2.0
                specifics[idx] += 1
                counts[idx] += 1
            elif impact == _IMPACT_NORMAL:
                scores[idx] += 1.0
                specifics[idx] += 1
                counts[idx] += 1
            elif impact == _IMPACT_NAME:
                scores[idx] += 1.0
                specifics[idx] += 1
            elif impact == _IMPACT_URL:
                scores[idx] += 2.0
                specifics[idx] += 1

    best_name = fallback
    # Rank: (weighted_score, specific_hits, total_match_len, -generic_hits, total_matches)
    best_rank = (0.0, 0, 0, 0, 0)

    for i in range(num_profs):
        if specifics[i] > 0 or scores[i] >= 1.0:
            rank = (scores[i], specifics[i], lens[i], -generics[i], counts[i])
            if rank > best_rank:
                best_rank = rank
                best_name = profiles[i]["name"]

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


def project_billable_raw_hours(
    day_payloads,
    include_agent: bool = False,
    include_presence: bool = False,
) -> float:
    """Raw hours eligible for billing across a project's day payloads.

    Exclusions by default (opt-in restores them):
    - ``agent_hours`` — autonomous work (GH-284 slice 2)
    - ``presence_hours`` — presence-signal / bracketed time (GH-327)

    Mixed attended+agent sessions stay billable (authorship/attendance present).
    Mixed authorship+presence sessions stay billable in Slice 1 except the
    bracketed edge share already folded into ``presence_hours``.
    """
    total = 0.0
    for day_payload in day_payloads.values():
        hours = float(day_payload.get("hours", 0.0))
        if not include_agent:
            hours -= float(day_payload.get("agent_hours", 0.0))
        if not include_presence:
            hours -= float(day_payload.get("presence_hours", 0.0))
        total += max(hours, 0.0)
    return total


def billable_raw_by_project(
    project_reports,
    *,
    reported_hours=None,
    include_agent_billable: bool = False,
    include_presence_billable: bool = False,
) -> dict:
    """Raw billable hours per project for invoice/report (GH-186 / GH-284 / GH-327).

    When ``confirmed``/``edited`` reported_time covers the window
    (``reported_hours`` is a ``{(project, day): hours}`` dict, not ``None``), bill
    those human-approved hours — including manual additions — and ignore observed
    evidence (the D4 adoption switch, matching toggl-/jira-sync). Projects in the
    report but absent from the confirmed set bill 0 in reported mode.

    Before adoption (``reported_hours is None``) fall back to observed hours with
    autonomous agent and presence-signal time excluded by default.
    """
    if reported_hours is not None:
        result = {project: 0.0 for project in project_reports}
        for (project, _day), hours in reported_hours.items():
            result[project] = result.get(project, 0.0) + float(hours)
        return result
    return {
        project: project_billable_raw_hours(
            days,
            include_agent=include_agent_billable,
            include_presence=include_presence_billable,
        )
        for project, days in project_reports.items()
    }


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
