from __future__ import annotations

import math

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


def classify_project(text, profiles, fallback):
    haystack = (text or "").lower()
    best_name = fallback
    best_rank = (0.0, 0, 0, 0)
    for profile in profiles:
        matched = {term for term in profile["match_terms"] if term and term in haystack}
        weighted_score = 0.0
        specific_hits = 0
        generic_hits = 0
        for term in matched:
            clean = str(term).strip().lower()
            if clean in GENERIC_TOOL_TERMS:
                weighted_score += 0.25
                generic_hits += 1
            elif _is_path_like_term(clean):
                weighted_score += 2.0
                specific_hits += 1
            else:
                weighted_score += 1.0
                specific_hits += 1
        if profile["name"].lower() in haystack:
            weighted_score += 1.0
            specific_hits += 1
        for url in profile.get("tracked_urls") or []:
            fragment = str(url).strip().lower()
            if fragment and fragment in haystack:
                weighted_score += 2.0
                specific_hits += 1
        rank = (weighted_score, specific_hits, -generic_hits, len(matched))
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
    min_h = min_session_minutes / 60
    min_passive_h = min_session_passive_minutes / 60
    sources = {event["source"] for event in session_events}
    minimum = min_h if sources & ai_sources else min_passive_h
    return max((end_ts - start_ts).total_seconds() / 3600, minimum)


def billable_total_hours(raw_hours, unit):
    if not unit or unit <= 0:
        return raw_hours
    q = raw_hours / unit
    eps = 1e-12
    return math.ceil(q - eps) * unit
