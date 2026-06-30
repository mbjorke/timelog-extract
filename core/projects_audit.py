"""Usage statistics for match_terms and tracked_urls over deduped collector events."""

from __future__ import annotations

import re
from collections import Counter
from typing import Any
from urllib.parse import urlparse

from core.events import event_anchors
from core.sources import GITHUB_SOURCE, WORKLOG_SOURCE
from core.triage_domain_signals import canonical_domain_key, tracked_fragment_matches_domain

_URL_RE = re.compile(r"https?://[^\s)>\"']+", re.IGNORECASE)

AUDIT_SCHEMA_VERSION = 2

TRIM_PLAN_SCHEMA_VERSION = 1

ANCHOR_PLAN_SCHEMA_VERSION = 1

# Activity-anchor kinds preserved on events (core.events.make_event) and surfaced
# by the audit: git repo slug, working directory, git branch, and session title.
# All are already part of the classification haystack for their source, so the
# same substring rule decides whether a profile already anchors them. The repo
# slug (owner/repo) is the worktree-invariant key — see
# docs/task-prompts/repo-slug-project-attribution.md.
ANCHOR_KINDS = ("repo", "dir", "branch", "label")
_DELIVERY_LABEL_SOURCES = frozenset({GITHUB_SOURCE, WORKLOG_SOURCE})  # enrich labels, not map targets
_JUNK_FILE_SUFFIXES = (".json", ".jsonl", ".log", ".md", ".txt", ".yaml", ".yml")

ANCHOR_KIND_LABELS = {
    "repo": "git repo",
    "dir": "working directory",
    "branch": "git branch",
    "label": "session title",
}

# A *signal* is any frequency-counted, profile-anchorable value the audit can
# turn into a rule suggestion. Anchors (dir/branch/label → match_terms) and web
# hosts (host → tracked_urls) share one model: aggregate per event, flag whether
# a profile already anchors the value, and propose the matching rule type.
SIGNAL_KINDS = ("host", "repo", "dir", "branch", "label")
SIGNAL_KIND_LABELS = {"host": "web host", **ANCHOR_KIND_LABELS}
SIGNAL_RULE_TYPE = {
    "host": "tracked_urls",
    "repo": "match_terms",
    "dir": "match_terms",
    "branch": "match_terms",
    "label": "match_terms",
}

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

TOP_SIGNALS_NOTE = (
    "top_signals: frequency-counted, profile-anchorable values, counted once per value per event, "
    "sorted by frequency within each kind. kind=host (web host parsed from detail → tracked_urls), "
    "kind=dir/branch/label (working directory / git branch / session title → match_terms). "
    "anchored=true if some profile rule already covers the value (a match_term that is a substring "
    "of it, or for hosts a match_term/tracked_urls rule matching a stub URL for that host — the same "
    "rules as classification). Unanchored, high-hit signals are rule suggestion candidates; rule_type "
    "names the rule each kind would add."
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


def is_value_anchored_by_profiles(value: str, profiles: list[dict[str, Any]]) -> bool:
    """True if any profile match_term is a substring of the anchor value.

    Mirrors how classification anchors an activity signal (working directory,
    git branch, or session title): the value is part of the haystack, so a
    match_term that is a substring of it would classify the event. tracked_urls
    do not apply to anchor values.
    """
    needle = str(value or "").strip().lower()
    if not needle:
        return False
    for profile in profiles:
        for term in profile.get("match_terms") or []:
            t = str(term).strip().lower()
            if t and t in needle:
                return True
    return False


def aggregate_top_anchors(
    events: list[dict[str, Any]], kind: str, *, limit: int
) -> list[tuple[str, int]]:
    """Count each anchor value of a given kind once per event; descending."""
    counts: Counter[str] = Counter()
    for event in events:
        value = str(event_anchors(event).get(kind) or "").strip().lower()
        if value:
            counts[value] += 1
    return counts.most_common(max(0, int(limit)))


def is_junk_anchor_value(value: str) -> bool:
    """True for anchor values that can never be a meaningful project mapping.

    Dotfile leaves (``.claude``, ``.git``), values with trailing punctuation
    from log parsing (``.gittan:``), and hash-like hex names (plugin cache or
    tmp directories) are tool plumbing — suggesting them as match_terms is
    noise, not signal.

    Note: a ``<slug>-<hex>`` *suffix* is deliberately NOT treated as junk. It
    cannot be distinguished from a real project at the leaf level — Lovable
    renames repos with a hex suffix (e.g. ``financing-portal-dev-31e799cf``),
    which is byte-for-byte the same shape as a Claude Code worktree leaf
    (``confident-hopper-fe58c2``). Worktree leakage is solved at the path/remote
    layer instead — see ``docs/task-prompts/repo-slug-project-attribution.md``.
    """
    text = str(value or "").strip().lower()
    if not text:
        return True
    if text.startswith("."):
        return True
    if text.endswith((":", ";", ",")):
        return True
    if text == "head":
        return True
    if text.endswith(_JUNK_FILE_SUFFIXES):
        return True
    compact = text.replace("-", "").replace("_", "")
    if len(compact) >= 16 and all(c in "0123456789abcdef" for c in compact):
        return True
    return False


def _events_without_anchored_coverage(
    events: list[dict[str, Any]], profiles: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Events where no anchor value is matched by any profile yet.

    If *any* anchor on an event is already anchored (e.g. the repo slug is in
    match_terms), the event's other anchors are not actionable mapping gaps:
    the work is attributed. This is what makes per-worktree dir/branch leaves
    stop nagging once the worktree-invariant slug is mapped.
    """
    cache: dict[str, bool] = {}

    def anchored(value: str) -> bool:
        if value not in cache:
            cache[value] = is_value_anchored_by_profiles(value, profiles)
        return cache[value]

    return [
        event
        for event in events
        if not any(anchored(value) for value in event_anchors(event).values())
    ]


def unanchored_top_anchors(
    events: list[dict[str, Any]],
    profiles: list[dict[str, Any]],
    *,
    kinds: tuple[str, ...] = ANCHOR_KINDS,
    min_hits: int = 1,
    limit_per_kind: int = 10,
) -> list[dict[str, Any]]:
    """Anchor values not yet matched by any profile, descending by hits.

    Convenience for report/status nudges across every anchor kind: combines
    aggregate_top_anchors with the anchored check so callers get only actionable
    (unmapped) anchors, each tagged with its kind. Events already covered by an
    anchored value (any kind) are excluded entirely.
    """
    floor = max(1, int(min_hits))
    uncovered = _events_without_anchored_coverage(events, profiles)
    # An event with a repo (slug) anchor attributes via the worktree-invariant
    # slug, so its dir/branch/label leaves are ephemeral noise (worktree names,
    # detached HEAD). Only surface those leaves for events with no repo anchor —
    # i.e. you map the repo, never the worktree name.
    leaf_pool = [e for e in uncovered if not event_anchors(e).get("repo")]
    out: list[dict[str, Any]] = []
    for kind in kinds:
        pool = leaf_pool if kind in ("dir", "branch", "label") else uncovered
        if kind == "label":
            pool = [e for e in pool if str(e.get("source") or "") not in _DELIVERY_LABEL_SOURCES]
        for value, hits in aggregate_top_anchors(pool, kind, limit=max(0, int(limit_per_kind))):
            if hits < floor or is_junk_anchor_value(value) or is_value_anchored_by_profiles(value, profiles):
                continue
            out.append({"kind": kind, "value": value, "hits": int(hits)})
    out.sort(key=lambda row: row["hits"], reverse=True)
    return out


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


def aggregate_signal(events: list[dict[str, Any]], kind: str, *, limit: int) -> list[tuple[str, int]]:
    """Count one signal kind once per value per event; descending (host or anchor)."""
    if kind == "host":
        return aggregate_top_hosts(events, limit=limit)
    return aggregate_top_anchors(events, kind, limit=limit)


def is_signal_anchored(value: str, kind: str, profiles: list[dict[str, Any]]) -> bool:
    """True if a profile rule already covers this signal value (host or anchor rules)."""
    if kind == "host":
        return is_host_anchored_by_profiles(value, profiles)
    return is_value_anchored_by_profiles(value, profiles)


def build_top_signals(
    events: list[dict[str, Any]],
    profiles: list[dict[str, Any]],
    *,
    limit: int,
    kinds: tuple[str, ...] = SIGNAL_KINDS,
) -> list[dict[str, Any]]:
    """Unified rule-suggestion signals across every kind (host + anchors).

    Each row is ``{kind, value, hits, anchored, rule_type}``; rows are grouped by
    kind in ``kinds`` order, sorted by hits within each kind.
    """
    rows: list[dict[str, Any]] = []
    for kind in kinds:
        for value, hits in aggregate_signal(events, kind, limit=limit):
            rows.append(
                {
                    "kind": kind,
                    "value": value,
                    "hits": int(hits),
                    "anchored": is_signal_anchored(value, kind, profiles),
                    "rule_type": SIGNAL_RULE_TYPE.get(kind, "match_terms"),
                }
            )
    return rows


def unanchored_top_signals(
    events: list[dict[str, Any]],
    profiles: list[dict[str, Any]],
    *,
    kinds: tuple[str, ...] = SIGNAL_KINDS,
    min_hits: int = 1,
    limit_per_kind: int = 10,
) -> list[dict[str, Any]]:
    """Unanchored rule-suggestion signals (any kind), descending by hits."""
    floor = max(1, int(min_hits))
    out = [
        row
        for row in build_top_signals(events, profiles, limit=max(0, int(limit_per_kind)), kinds=kinds)
        if not row["anchored"] and row["hits"] >= floor
    ]
    out.sort(key=lambda row: row["hits"], reverse=True)
    return out


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

    top_signals_out = build_top_signals(events, profiles, limit=top_hosts_limit)

    return {
        "schema_version": AUDIT_SCHEMA_VERSION,
        "command": "gittan projects-audit",
        "hit_definition": HIT_DEFINITION_V1,
        "top_signals_note": TOP_SIGNALS_NOTE,
        "pool": pool,
        "options": {
            "date_from": date_from,
            "date_to": date_to,
            "projects_config": projects_config,
            "top_hosts_limit": int(top_hosts_limit),
        },
        "event_count": len(events),
        "projects": projects_out,
        "top_signals": top_signals_out,
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


def build_anchor_plan_from_audit(
    audit_payload: dict[str, Any], *, min_hits: int = 1
) -> dict[str, Any]:
    """Build a `projects-anchor` plan (schema v1): rule additions from signals.

    Each addition is an **unanchored** signal (`top_signals` row with
    `anchored=false`) — a web host (→ tracked_urls), or a working directory, git
    branch, or session title (→ match_terms) — seen at least `min_hits` times in
    the audit window. Each row carries its own `rule_type`; the signal value is
    proposed as the rule value (tagged with its `anchor_kind`), and `project_name`
    defaults to that same value — review and edit it (and trim long title values)
    to target an existing project before applying. Applying via
    `gittan projects-anchor` creates a new project if the name does not exist.
    """
    sv = int(audit_payload.get("schema_version", 0))
    if sv != AUDIT_SCHEMA_VERSION:
        raise ValueError(f"audit schema_version must be {AUDIT_SCHEMA_VERSION}, got {sv}")

    floor = max(1, int(min_hits))
    additions: list[dict[str, Any]] = []
    for row in audit_payload.get("top_signals") or []:
        if row.get("anchored"):
            continue
        value = str(row.get("value", "")).strip()
        hits = int(row.get("hits", 0))
        if not value or hits < floor:
            continue
        kind = str(row.get("kind", ""))
        additions.append(
            {
                "project_name": value,
                "rule_type": str(row.get("rule_type") or SIGNAL_RULE_TYPE.get(kind, "match_terms")),
                "rule_value": value,
                "anchor_kind": kind,
                "hits": hits,
            }
        )

    note = (
        "Candidate rules from unanchored signals (anchor_kind = host/dir/branch/label) in the audit "
        "window only; rule_type is tracked_urls for hosts, match_terms otherwise. project_name "
        "defaults to the signal value — edit it to map to an existing project, and trim long "
        "session-title values (applying an unknown name creates a new project). Apply: "
        "gittan projects-anchor -i <file> --dry-run then rerun without --dry-run."
    )

    return {
        "schema_version": ANCHOR_PLAN_SCHEMA_VERSION,
        "note": note,
        "additions": additions,
        "meta": {
            "source_audit_command": audit_payload.get("command", "gittan projects-audit"),
            "audit_options": audit_payload.get("options", {}),
            "min_hits": floor,
            "anchor_candidates": len(additions),
        },
    }

